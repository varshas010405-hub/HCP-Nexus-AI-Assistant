import os
import json
import logging
from dotenv import load_dotenv

# Ensure environment variables from .env are loaded when this module is imported
load_dotenv()
from datetime import datetime, date, timedelta
import re
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models.models import Doctor, Interaction, FollowUp, Product, User
from backend.langgraph.prompts import SUMMARY_PROMPT, INSIGHTS_PROMPT
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


def _coerce_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    lower_text = text.lower()
    if lower_text in {"today", "now"}:
        return date.today()
    if lower_text == "yesterday":
        return date.today() - timedelta(days=1)
    if lower_text == "tomorrow":
        return date.today() + timedelta(days=1)

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _extract_doctor_name(text: str) -> str | None:
    if not text:
        return None
    match = re.search(r"(?:doctor|dr\.?)\s+([A-Z][A-Za-z .'-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    fallback_match = re.search(r"(?:for|with|about|meeting\s+with)\s+([A-Z][A-Za-z .'-]+)", text, re.IGNORECASE)
    if fallback_match:
        return fallback_match.group(1).strip()

    return None


def _clean_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
    else:
        cleaned = str(value).strip()
    return cleaned or None


def normalize_extracted_payload(extracted: dict) -> dict | None:
    if not isinstance(extracted, dict):
        return None

    cleaned = {}
    for field in ["doctor_name", "hospital", "specialization", "department", "visit_date", "summary", "interest_level", "followup_date"]:
        value = _clean_text(extracted.get(field))
        if value:
            cleaned[field] = value

    products = extracted.get("products")
    if isinstance(products, list):
        normalized_products = [_clean_text(item) for item in products if _clean_text(item)]
    elif isinstance(products, str):
        normalized_products = [item.strip() for item in products.split(",") if item.strip()]
    else:
        normalized_products = []
    if normalized_products:
        cleaned["products"] = normalized_products

    action_items = extracted.get("action_items")
    if isinstance(action_items, list):
        normalized_action_items = [_clean_text(item) for item in action_items if _clean_text(item)]
    elif isinstance(action_items, str):
        normalized_action_items = [item.strip() for item in action_items.split(";") if item.strip()]
    else:
        normalized_action_items = []
    if normalized_action_items:
        cleaned["action_items"] = normalized_action_items

    # Set default interest_level if not provided
    if not cleaned.get("interest_level"):
        cleaned["interest_level"] = "Medium"

    # Require a minimum set of fields to allow saving. Specialization and department
    # are optional because the AI extractor or user may not provide them immediately.
    required_fields = ["doctor_name", "hospital", "visit_date", "products"]
    if not all(cleaned.get(field) for field in required_fields):
        return None

    return cleaned


def _extract_search_filters(query_str: str = "", filters: dict | None = None) -> dict:
    normalized = {key: value for key, value in (filters or {}).items() if value not in (None, "")}
    if not query_str and not normalized:
        return {}

    search_text = query_str or ""
    lower_text = search_text.lower()

    if not normalized.get("doctor_name"):
        doctor_match = re.search(r"(?:doctor|doctor_name|dr\.?)\s+([A-Za-z][A-Za-z .'-]+)", search_text, re.IGNORECASE)
        if doctor_match:
            normalized["doctor_name"] = doctor_match.group(1).strip()
        else:
            fallback_doctor_match = re.search(r"(?:for|with|about|meeting\s+with)\s+([A-Z][A-Za-z .'-]+)", search_text, re.IGNORECASE)
            if fallback_doctor_match:
                normalized["doctor_name"] = fallback_doctor_match.group(1).strip()

    if not normalized.get("hospital"):
        hospital_match = re.search(r"(?:hospital|facility|clinic)\s+([A-Za-z][A-Za-z .'-]+)", search_text, re.IGNORECASE)
        if hospital_match:
            normalized["hospital"] = hospital_match.group(1).strip()
        else:
            location_match = re.search(r"(?:at|in|to)\s+([A-Z][A-Za-z0-9 .'-]+?(?:Hospital|Clinic|Center|Medical))", search_text, re.IGNORECASE)
            if location_match:
                normalized["hospital"] = location_match.group(1).strip()

    if not normalized.get("product"):
        product_match = re.search(r"(?:product|products|drug)\s+([A-Za-z0-9][A-Za-z0-9 .'-]+)", search_text, re.IGNORECASE)
        if product_match:
            normalized["product"] = product_match.group(1).strip()

    if not normalized.get("date"):
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2}|today|yesterday|tomorrow)\b", search_text, re.IGNORECASE)
        if date_match:
            normalized["date"] = date_match.group(1)

    if not normalized.get("query_text") and search_text:
        cleaned = search_text
        if normalized.get("hospital"):
            cleaned = re.sub(re.escape(normalized["hospital"]), "", cleaned, flags=re.IGNORECASE)
        if normalized.get("doctor_name"):
            cleaned = re.sub(re.escape(normalized["doctor_name"]), "", cleaned, flags=re.IGNORECASE)
        if normalized.get("product"):
            cleaned = re.sub(re.escape(normalized["product"]), "", cleaned, flags=re.IGNORECASE)
            
        cleaned = re.sub(r"\b(search|find|lookup|show|list|get|for|by|on|from|with|to|at|in|are|is|interested|about)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            normalized["query_text"] = cleaned

    if not normalized.get("query_text") and lower_text.startswith("search") and len(lower_text.split()) > 1:
        normalized["query_text"] = " ".join(lower_text.split()[1:])

    return normalized


def _extract_edit_fields(text: str) -> dict:
    fields = {}
    if not text:
        return fields

    lower_text = text.lower()
    if re.search(r"\bnotes?\b", lower_text):
        note_match = re.search(r"(?:notes?|discussion notes?)\s*(?:is|to|as|:)?\s*(.+)", text, re.IGNORECASE)
        if note_match:
            fields["notes"] = note_match.group(1).strip()

    if re.search(r"\bsummary\b", lower_text):
        summary_match = re.search(r"summary\s*(?:is|to|as|:)?\s*(.+)", text, re.IGNORECASE)
        if summary_match:
            fields["summary"] = summary_match.group(1).strip()

    if re.search(r"\bdoctor(?:\s+name)?\b", lower_text):
        doctor_match = re.search(r"doctor(?:\s+name)?\s*(?:is|to|as|:)?\s*([A-Za-z][A-Za-z .'-]+)", text, re.IGNORECASE)
        if doctor_match:
            fields["doctor_name"] = doctor_match.group(1).strip()

    if re.search(r"\b(hospital|facility|clinic)\b", lower_text):
        hospital_match = re.search(r"(?:hospital|facility|clinic)\s*(?:is|to|as|:)?\s*([A-Za-z][A-Za-z .'-]+)", text, re.IGNORECASE)
        if hospital_match:
            fields["hospital"] = hospital_match.group(1).strip()

    if re.search(r"\bproduct(?:s)?\b", lower_text):
        product_match = re.search(r"product(?:s)?\s*(?:are|is|to|as|:)?\s*([A-Za-z0-9 ,.-]+)", text, re.IGNORECASE)
        if product_match:
            fields["products"] = [item.strip() for item in product_match.group(1).split(",") if item.strip()]

    if re.search(r"\binterest(?:\s+level)?\b", lower_text):
        if "high" in lower_text:
            fields["interest_level"] = "High"
        elif "low" in lower_text:
            fields["interest_level"] = "Low"
        elif "medium interest" in lower_text or "moderate" in lower_text:
            fields["interest_level"] = "Medium"

    if re.search(r"\bvisit\s+date\b", lower_text):
        visit_match = re.search(r"visit\s+date\s*(?:is|to|as|:)?\s*([A-Za-z0-9/-]+)", text, re.IGNORECASE)
        if visit_match:
            fields["visit_date"] = visit_match.group(1).strip()

    if re.search(r"\bfollow[- ]?up(?:\s+date)?\b", lower_text):
        followup_match = re.search(r"follow[- ]?up(?:\s+date)?\s*(?:is|to|as|:)?\s*([A-Za-z0-9/-]+)", text, re.IGNORECASE)
        if followup_match:
            fields["followup_date"] = followup_match.group(1).strip()

    if not fields:
        fields["notes"] = text.strip()

    return fields


# --- LLM CALL WRAPPER ---
def call_llm(system_prompt: str, user_content: str, model_name: str = "gemma2-9b-it") -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.info("GROQ_API_KEY not found. Running Mock LLM simulation.")
        return simulate_llm(system_prompt, user_content)
    
    try:
        # Use gemma2-9b-it or llama-3.3-70b-versatile
        selected_model = model_name if model_name else "gemma2-9b-it"
        llm = ChatGroq(
            temperature=0.2,
            model_name=selected_model,
            groq_api_key=api_key
        )
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ])
        return response.content
    except Exception as e:
        logger.error(f"Error calling Groq API: {e}. Falling back to simulation.")
        return simulate_llm(system_prompt, user_content)

# --- MOCK LLM ENGINE (For sandbox & fallback mode) ---
def simulate_llm(system_prompt: str, user_content: str) -> str:
    # 1. Check if we need to do classification (Intent Detection)
    if "Intent Detection Unit" in system_prompt:
        content_lower = user_content.lower()
        if any(w in content_lower for w in ["summary", "summarize", "notes", "recap"]):
            return "summarize"
        elif any(w in content_lower for w in ["schedule", "remind", "followup", "follow-up", "reminder"]):
            return "schedule"
        elif any(w in content_lower for w in ["insight", "strategy", "recommend", "advice", "trends"]):
            return "insights"
        elif any(w in content_lower for w in ["search", "find", "history", "lookup", "filter", "previous visit", "past visit"]):
            return "search"
        elif any(w in content_lower for w in ["edit", "update", "modify", "change"]):
            return "edit"
        elif any(w in content_lower for w in ["log", "record", "visit", "met", "saw", "discussed"]):
            return "log"
        else:
            return "general"

    # 2. Check if we need information extraction
    if "Information Extraction Unit" in system_prompt:
        doc_match = re.search(r"(?:doctor|dr\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", user_content, re.IGNORECASE)
        doctor = doc_match.group(1).strip() if doc_match else None
        if not doctor:
            context_match = re.search(r"(?:with|for|meeting\s+with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", user_content, re.IGNORECASE)
            if context_match:
                doctor = context_match.group(1).strip()

        hosp_match = re.search(r"(?:at|in|at the|in the)\s+([A-Za-z0-9 .'-]+?(?:Hospital|Clinic|Center|Medical))", user_content, re.IGNORECASE)
        hospital = hosp_match.group(1).strip() if hosp_match else None

        prod_list = []
        for p in ["CardioPlus", "DiabeCare", "NeuroMax", "RespiClear", "OsteoShield"]:
            if p.lower() in user_content.lower():
                prod_list.append(p)

        visit_date = None
        if "yesterday" in user_content.lower():
            visit_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        elif "today" in user_content.lower():
            visit_date = date.today().strftime("%Y-%m-%d")
        elif re.search(r"\b\d{4}-\d{2}-\d{2}\b", user_content):
            visit_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", user_content).group(0)

        followup_date = None
        if "next tuesday" in user_content.lower():
            days_ahead = 1 - date.today().weekday()
            if days_ahead <= 0: days_ahead += 7
            followup_date = (date.today() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        elif "next monday" in user_content.lower():
            days_ahead = 0 - date.today().weekday()
            if days_ahead <= 0: days_ahead += 7
            followup_date = (date.today() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        interest = None
        lower_content = user_content.lower()
        if any(w in lower_content for w in ["high interest", "interest was high", "very high", "highly interested", "very interested", "excited", "impressed"]):
            interest = "High"
        elif any(w in lower_content for w in ["low interest", "interest was low", "not interested", "hesitant", "skeptical"]):
            interest = "Low"
        elif any(w in lower_content for w in ["medium interest", "moderate interest", "interest was moderate", "interest was medium", "some interest"]):
            interest = "Medium"
        elif "high" in lower_content and "interest" in lower_content:
            interest = "High"
        elif "low" in lower_content and "interest" in lower_content:
            interest = "Low"
        elif "medium" in lower_content and "interest" in lower_content:
            interest = "Medium"

        summary = None
        if doctor and hospital and prod_list:
            summary = f"Visited {doctor} at {hospital} to discuss {', '.join(prod_list)}."
        action_items = []
        if "sample" in user_content.lower():
            action_items.append("Provide product samples")
        if "remind" in user_content.lower() or "followup" in user_content.lower():
            action_items.append("Perform follow-up check")

        extracted = {}
        if doctor:
            extracted["doctor_name"] = doctor
        if hospital:
            extracted["hospital"] = hospital

        if any(p.lower() in "".join(prod_list).lower() for p in ["cardio", "cardiovascular"]):
            extracted["specialization"] = "Cardiology"
            extracted["department"] = "Cardiology Dept"
        elif prod_list and not any(p.lower() in "".join(prod_list).lower() for p in ["cardio", "cardiovascular"]):
            extracted["specialization"] = "General Medicine"
            extracted["department"] = "Outpatient"

        if visit_date:
            extracted["visit_date"] = visit_date
        if prod_list:
            extracted["products"] = prod_list
        if summary:
            extracted["summary"] = summary
        if action_items:
            extracted["action_items"] = action_items
        if interest:
            extracted["interest_level"] = interest
        if followup_date:
            extracted["followup_date"] = followup_date
        return json.dumps(extracted)

    # 3. Check if we need strategy recommendations
    if "AI Strategy Advisor" in system_prompt:
        return f"""### Executive Summary
The physician shows stable engagement. Past interaction records indicate high clinical discussions primarily focused on cardiology related therapies.

### Recommended Engagement Strategy
- Focus on providing clinical trial endpoints and data comparisons.
- Schedule visits during mid-week outpatient hours (Tuesdays or Wednesdays).

### Product Recommendation
- **CardioPlus**: Recommended as primary therapy due to discussion trends and doctor's interest.

### Next Best Action
- Schedule a lunch-and-learn seminar for the hospital cardiology department staff on CardioPlus efficacy.
"""

    # 4. Visit summary
    if "Clinical Interaction Summarizer" in system_prompt:
        return f"""### Visit Summary
The meeting centered around introducing new therapeutic options. The doctor showed interest in modern cardiovascular treatments and requested peer-reviewed clinical studies.

### Doctor's Concerns / Questions
- Clinical efficacy trial details.
- Patient pricing and insurance coverage compatibility.

### Key Outcomes & Action Items
- Share clinical dossier.
- Arrange for sample distribution by next week.
"""

    # 5. Database Search Summary
    if "Based on the following database records" in system_prompt:
        if "cardioplus" in user_content.lower() and "which doctors" in user_content.lower():
            return "Based on your records, Dr. Rajesh Patel and Dr. Sarah Jenkins have shown interest in CardioPlus."
        else:
            return "Here are the top matches I found in the database:\n" + system_prompt.split("\n\n")[-1]

    # 6. General conversational fallback for mock LLM
    if "You are HCP Nexus AI" in system_prompt or "professional and helpful pharmaceutical CRM assistant" in system_prompt:
        text = user_content.strip().lower()
        if any(greet in text for greet in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]):
            return "Hello! I can help you log doctor visits, summarize interactions, schedule follow-ups, and review your CRM records. What would you like to do?"
        if any(thanks in text for thanks in ["thank", "thanks", "appreciate"]):
            return "You’re welcome! I can also help log a visit or summarize an interaction if you want."
        if any(kw in text for kw in ["bp", "blood pressure"]):
            return "Normal blood pressure for most adults is defined as a systolic pressure of less than 120 and a diastolic pressure of less than 80. I can also help you log these details if needed."
        if any(kw in text for kw in ["heart beat", "heart rate"]):
            return "A normal resting heart rate for adults ranges from 60 to 100 beats per minute."
        if any(kw in text for kw in ["sugar", "blood sugar", "glucose", "hypertension", "diabetes"]):
            return "I’m not a medical professional, but I can help you capture these details in your doctor visit log so you can review them with your clinician later."
        if any(kw in text for kw in ["log", "record", "visit", "meeting", "appointment", "doctor"]):
            return "Please share the doctor name, hospital, products discussed, and follow-up date, and I’ll log the interaction for you."
        if any(kw in text for kw in ["summary", "summarize", "recap", "notes"]):
            return "Tell me the main points of the visit, and I’ll create a concise summary of the interaction."
        if any(kw in text for kw in ["schedule", "follow-up", "followup", "reminder", "next visit"]):
            return "Let me know which doctor and what date you want to follow up, and I’ll add that task to your CRM follow-up list."
        if any(kw in text for kw in ["product", "therapy", "drug", "treatment", "medication"]):
            return "I can track your conversation around products and therapies and store the interaction with the relevant details."
        if any(kw in text for kw in ["how", "what", "why", "where", "when", "who"]):
            return "I can help answer questions about using the CRM assistant or logging interactions. For example, if you want to log a visit, say: 'I met Dr. X at Hospital Y and discussed Product Z.'"
        return "I’m here to help with doctor visit logs, summaries, and follow-up planning. Please describe the question or visit details you want assistance with."

    return "General greeting from HCP Nexus AI. How can I help you today with your doctor visits?"


# --- DATABASE TOOLS IMPLEMENTATION ---

# 1. Log Interaction Tool
def log_interaction_tool(extracted: dict, user_id: int | None = None) -> dict:
    db: Session = SessionLocal()
    try:
        payload = normalize_extracted_payload(extracted)
        if not payload:
            return {
                "success": False,
                "message": "No reliable interaction details were provided, so nothing was saved.",
                "error": "No reliable interaction details were provided, so nothing was saved."
            }

        doc_name = payload.get("doctor_name")
        hosp = payload.get("hospital")
        spec = payload.get("specialization") or "General Medicine"
        dept = payload.get("department") or "General Dept"

        if user_id is not None:
            default_user = db.query(User).filter(User.id == user_id).first()
        else:
            default_user = None

        if not default_user:
            default_user = db.query(User).first()
        if not default_user:
            default_user = User(
                name="AI Assistant",
                email="ai.assistant@nexuspharma.com",
                role="",
                region=""
            )
            db.add(default_user)
            db.commit()
            db.refresh(default_user)

        doctor = db.query(Doctor).filter(Doctor.name.ilike(doc_name)).first()
        if not doctor:
            doctor = Doctor(
                name=doc_name,
                hospital=hosp,
                specialization=spec,
                department=dept
            )
            db.add(doctor)
            db.commit()
            db.refresh(doctor)

        visit_dt = _coerce_date(payload.get("visit_date"))
        if visit_dt is None:
            return {
                "success": False,
                "message": "A valid visit date is required to log an interaction.",
                "error": "A valid visit date is required to log an interaction."
            }

        followup_dt = _coerce_date(payload.get("followup_date"))
        products_list = payload.get("products") or []
        products_str = ", ".join(products_list) if isinstance(products_list, list) else str(products_list)

        action_items = payload.get("action_items") or []
        action_items_str = "; ".join(action_items) if isinstance(action_items, list) else str(action_items)

        interaction = Interaction(
            user_id=default_user.id,
            doctor_id=doctor.id,
            doctor_name=doctor.name,
            hospital=doctor.hospital,
            specialization=doctor.specialization,
            department=doctor.department,
            visit_date=visit_dt,
            products=products_str,
            summary=payload.get("summary"),
            notes=action_items_str or None,
            interest_level=payload["interest_level"],
            followup_date=followup_dt
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)

        if followup_dt:
            for item in action_items or ["Follow-up visit"]:
                db_followup = FollowUp(
                    interaction_id=interaction.id,
                    doctor_id=doctor.id,
                    date=followup_dt,
                    action_item=item,
                    status="Pending"
                )
                db.add(db_followup)
            db.commit()

        return {
            "success": True,
            "interaction_id": interaction.id,
            "doctor_id": doctor.id,
            "message": f"Successfully logged visit for {doctor.name} at {doctor.hospital}."
        }
    except Exception as e:
        db.rollback()
        logger.exception("Error in log_interaction_tool")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

# 2. Edit Interaction Tool
def edit_interaction_tool(interaction_id: int, fields_to_update: dict | None = None, source_text: str | None = None) -> dict:
    db: Session = SessionLocal()
    try:
        interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
        if not interaction:
            return {"success": False, "error": f"Interaction with ID {interaction_id} not found."}

        updates = dict(fields_to_update or {})
        if not updates and source_text:
            updates = _extract_edit_fields(source_text)

        if not updates:
            updates = {"notes": "Updated via AI assistant."}

        for key, val in updates.items():
            if hasattr(interaction, key) and val is not None:
                if key in ["visit_date", "followup_date"]:
                    parsed_date = _coerce_date(val)
                    setattr(interaction, key, parsed_date)
                elif key == "products" and isinstance(val, list):
                    setattr(interaction, key, ", ".join(val))
                else:
                    setattr(interaction, key, val)

        db.commit()
        return {"success": True, "message": f"Interaction {interaction_id} updated successfully."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

# 3. Search Interaction Tool
def search_interaction_tool(query_str: str = "", filters: dict | None = None) -> dict:
    db: Session = SessionLocal()
    try:
        parsed_filters = _extract_search_filters(query_str, filters)
        query = db.query(Interaction)

        if parsed_filters.get("doctor_name"):
            query = query.filter(Interaction.doctor_name.ilike(f"%{parsed_filters['doctor_name']}%"))
        if parsed_filters.get("hospital"):
            query = query.filter(Interaction.hospital.ilike(f"%{parsed_filters['hospital']}%"))
        if parsed_filters.get("product"):
            query = query.filter(Interaction.products.ilike(f"%{parsed_filters['product']}%"))
        if parsed_filters.get("date"):
            parsed_date = _coerce_date(parsed_filters["date"])
            if parsed_date:
                query = query.filter(Interaction.visit_date == parsed_date)
        if parsed_filters.get("query_text"):
            query = query.filter(
                (Interaction.doctor_name.ilike(f"%{parsed_filters['query_text']}%")) |
                (Interaction.hospital.ilike(f"%{parsed_filters['query_text']}%")) |
                (Interaction.products.ilike(f"%{parsed_filters['query_text']}%")) |
                (Interaction.summary.ilike(f"%{parsed_filters['query_text']}%")) |
                (Interaction.notes.ilike(f"%{parsed_filters['query_text']}%"))
            )

        results = query.order_by(Interaction.visit_date.desc()).limit(10).all()

        serialized = []
        for r in results:
            serialized.append({
                "id": r.id,
                "doctor_name": r.doctor_name,
                "hospital": r.hospital,
                "visit_date": r.visit_date.strftime("%Y-%m-%d"),
                "products": r.products,
                "interest_level": r.interest_level,
                "summary": r.summary
            })
        return {"success": True, "results": serialized, "filters": parsed_filters}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()

# 4. Generate Visit Summary Tool
def generate_summary_tool(notes: str, model_name: str = "gemma2-9b-it") -> str:
    user_prompt = f"Please write a structured visit summary for the following interaction notes:\n{notes}"
    return call_llm(SUMMARY_PROMPT, user_prompt, model_name)

# 5. Schedule Follow-up Tool
def schedule_followup_tool(doctor_name: str, followup_date_str: str, action_item: str) -> dict:
    db: Session = SessionLocal()
    try:
        doctor = db.query(Doctor).filter(Doctor.name.ilike(doctor_name)).first()
        if not doctor:
            # Create a mock doctor just to satisfy foreign key constraints
            doctor = Doctor(
                name=doctor_name,
                hospital="General Hospital",
                specialization="General Medicine",
                department="General Dept"
            )
            db.add(doctor)
            db.commit()
            db.refresh(doctor)

        f_date = _coerce_date(followup_date_str)
        if f_date is None:
            f_date = date.today() + timedelta(days=7)

        # Create a mock or direct interaction to tie this followup to
        dummy_interaction = db.query(Interaction).filter(Interaction.doctor_id == doctor.id).order_by(Interaction.visit_date.desc()).first()
        if not dummy_interaction:
            dummy_interaction = Interaction(
                doctor_id=doctor.id,
                doctor_name=doctor.name,
                hospital=doctor.hospital,
                specialization=doctor.specialization,
                department=doctor.department,
                visit_date=date.today(),
                products="General",
                summary="System scheduled follow-up.",
                interest_level="Medium"
            )
            db.add(dummy_interaction)
            db.commit()
            db.refresh(dummy_interaction)

        db_followup = FollowUp(
            interaction_id=dummy_interaction.id,
            doctor_id=doctor.id,
            date=f_date,
            action_item=action_item,
            status="Pending"
        )
        db.add(db_followup)
        db.commit()
        return {"success": True, "message": f"Scheduled follow-up for {doctor_name} on {followup_date_str}."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

# 6. Doctor Insights Tool
def doctor_insights_tool(doctor_name: str, model_name: str = "gemma2-9b-it") -> str:
    db: Session = SessionLocal()
    try:
        doctor = db.query(Doctor).filter(Doctor.name.ilike(doctor_name)).first()
        if not doctor:
            return f"Doctor '{doctor_name}' not found. Please log interactions first to gather insights."

        interactions = db.query(Interaction).filter(Interaction.doctor_id == doctor.id).order_by(Interaction.visit_date.desc()).all()
        if not interactions:
            return f"No prior interactions found for Dr. {doctor.name} at {doctor.hospital}."

        history_text = f"Doctor: {doctor.name}\nSpecialization: {doctor.specialization}\nHospital: {doctor.hospital}\n\nPast interactions:\n"
        for idx, inter in enumerate(interactions):
            history_text += f"{idx+1}. Date: {inter.visit_date} | Products: {inter.products} | Interest: {inter.interest_level} | Notes: {inter.notes} | Summary: {inter.summary}\n"

        return call_llm(INSIGHTS_PROMPT, history_text, model_name)
    except Exception as e:
        return f"Error retrieving doctor insights: {str(e)}"
    finally:
        db.close()
