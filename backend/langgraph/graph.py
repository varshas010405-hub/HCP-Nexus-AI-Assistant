import os
import json
from datetime import date
from langgraph.graph import StateGraph, END
from backend.langgraph.state import AgentState
from backend.langgraph.prompts import INTENT_DETECTION_PROMPT, EXTRACTION_PROMPT
from backend.langgraph.tools import (
    call_llm,
    log_interaction_tool,
    edit_interaction_tool,
    search_interaction_tool,
    generate_summary_tool,
    schedule_followup_tool,
    doctor_insights_tool,
    _extract_doctor_name,
    _extract_search_filters,
)
import logging

logger = logging.getLogger(__name__)

# Node 1: Intent Detection
def detect_intent_node(state: AgentState) -> AgentState:
    messages = state.get("messages", [])
    if not messages:
        return {**state, "intent": "general"}
    
    last_user_msg = messages[-1]["content"]
    model_name = state.get("model_override") or os.getenv("GROQ_MODEL", "gemma2-9b-it")
    # Check intent using LLM or Mock
    intent = call_llm(INTENT_DETECTION_PROMPT, last_user_msg, model_name=model_name).strip().lower()

    # Sanitize if LLM outputs extra text
    valid_intents = ["log", "edit", "search", "summarize", "schedule", "insights", "general"]
    matched_intent = "general"
    for v in valid_intents:
        if v in intent:
            matched_intent = v
            break

    # Respect explicit search commands first (avoid overriding to 'log')
    lower_text = last_user_msg.lower()
    search_indicators = ["search", "find", "lookup", "previous visits", "previous visit", "history", "past visits", "past visit", "last visit", "show me", "which doctors", "who is", "interested in"]
    if any(si in lower_text for si in search_indicators):
        matched_intent = "search"
    else:
        # Heuristic override: if user clearly describes a visit/meeting, prefer 'log' even
        # if the LLM also mentioned scheduling (e.g., "followup next Monday").
        visit_indicators = ["met dr", "met doctor", "met ", "visited", "i met", "saw dr", "saw doctor", "discussed", "discuss" , "visited dr", "visit"]
        if any(ind in lower_text for ind in visit_indicators):
            # Also require at least one strong entity hint (hospital, product, or 'dr')
            if ("hospital" in lower_text or "dr" in lower_text or "doctor" in lower_text or any(p.lower() in lower_text for p in ["cardioplus", "diabecare", "neuromax", "respiclear", "osteoshield"])):
                matched_intent = "log"
    logger.info("Intent detection: llm_intent=%s matched_intent=%s text=%s", intent, matched_intent, lower_text)
    return {**state, "intent": matched_intent}

# Node 2: Tool Execution Node
def execute_tool_node(state: AgentState) -> AgentState:
    intent = state.get("intent", "general")
    messages = state.get("messages", [])
    last_user_msg = messages[-1]["content"]
    model_name = state.get("model_override") or os.getenv("GROQ_MODEL", "gemma2-9b-it")

    extracted_fields = None
    tool_result = None
    tool_triggered = None

    if intent == "log":
        tool_triggered = "Log Interaction"
        # 1. Extract Details
        current_date_str = date.today().strftime("%Y-%m-%d")
        sys_prompt = EXTRACTION_PROMPT.format(current_date=current_date_str)
        extracted_raw = call_llm(sys_prompt, last_user_msg, model_name=model_name)
        
        try:
            # Clean possible markdown wrap
            cleaned = extracted_raw.replace("```json", "").replace("```", "").strip()
            extracted_fields = json.loads(cleaned)
        except Exception:
            # Fallback mock extraction
            from backend.langgraph.tools import simulate_llm
            extracted_fields = json.loads(simulate_llm(sys_prompt, last_user_msg))

        # 2. Trigger DB Logging (Save details in DB)
        user_id = state.get("user_id")
        tool_result = log_interaction_tool(extracted_fields, user_id=user_id)

    elif intent == "edit":
        tool_triggered = "Edit Interaction"
        import re
        id_match = re.search(r"interaction\s*(\d+)|id\s*(\d+)", last_user_msg, re.IGNORECASE)
        interaction_id = int(id_match.group(1) or id_match.group(2)) if id_match else 1

        tool_result = edit_interaction_tool(interaction_id, source_text=last_user_msg)

    elif intent == "search":
        tool_triggered = "Search Interaction"
        clean_q = last_user_msg.lower()
        for kw in ["search", "find", "lookup", "previous visits", "previous visit", "history", "past visits", "past visit", "last visit", "show me"]:
            clean_q = clean_q.replace(kw, "")
        clean_q = clean_q.strip()
        search_filters = _extract_search_filters(clean_q)
        tool_result = search_interaction_tool(clean_q, filters=search_filters)

    elif intent == "summarize":
        tool_triggered = "Generate Visit Summary"
        summary_md = generate_summary_tool(last_user_msg, model_name=model_name)
        tool_result = {"success": True, "summary": summary_md}

    elif intent == "schedule":
        tool_triggered = "Schedule Follow-up"
        import re
        doctor = _extract_doctor_name(last_user_msg)
        if not doctor:
            doctor = "the doctor"
        followup_date = None
        date_match = re.search(r"(\d{4}-\d{2}-\d{2}|today|tomorrow|yesterday)", last_user_msg, re.IGNORECASE)
        if date_match:
            followup_date = date_match.group(1)
        else:
            from datetime import timedelta
            days_ahead = 1 - date.today().weekday()
            if days_ahead <= 0:
                days_ahead += 7
            followup_date = (date.today() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        tool_result = schedule_followup_tool(doctor, followup_date, "Follow-up visit discussed in chat.")

    elif intent == "insights":
        tool_triggered = "Doctor Insights"
        doctor = _extract_doctor_name(last_user_msg)
        if not doctor:
            doctor = "the doctor"
        insights_md = doctor_insights_tool(doctor, model_name=model_name)
        tool_result = {"success": True, "insights": insights_md}

    else:
        # General chat
        tool_triggered = "None"
        tool_result = {"success": True, "response": "General greeting from Nexus AI."}

    return {
        **state,
        "extracted_fields": extracted_fields,
        "tool_result": tool_result,
        "tool_triggered": tool_triggered
    }

# Node 3: Generate Response Node
def generate_response_node(state: AgentState) -> AgentState:
    intent = state.get("intent", "general")
    tool_triggered = state.get("tool_triggered", "None")
    tool_result = state.get("tool_result", {})
    extracted_fields = state.get("extracted_fields")
    messages = state.get("messages", [])
    last_user_msg = messages[-1]["content"]
    model_name = state.get("model_override") or os.getenv("GROQ_MODEL", "gemma2-9b-it")

    if intent == "log":
        if tool_result.get("success"):
            doc = extracted_fields.get("doctor_name") if extracted_fields else None
            hosp = extracted_fields.get("hospital") if extracted_fields else None
            prods = ", ".join(extracted_fields.get("products", [])) if extracted_fields else ""
            if doc and hosp and prods:
                response = f"I've successfully logged your visit with **{doc}** at **{hosp}** discussing **{prods}**. I have also extracted the interaction details for you to review and edit."
            else:
                response = "I've successfully logged your interaction and saved the available details. Please review and update any missing fields if needed."
        else:
            error_message = tool_result.get("error") or tool_result.get("message") or "Unknown error."
            response = f"I attempted to log the interaction but encountered an issue: {error_message}"

    elif intent == "edit":
        if tool_result.get("success"):
            response = f"Successfully updated the interaction in the database! {tool_result.get('message')}"
        else:
            response = f"Could not update interaction. Error: {tool_result.get('error')}"

    elif intent == "search":
        history_str = ""
        if len(messages) > 1:
            history_str = "\nConversation History:\n" + "\n".join([f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in messages[:-1]])
        
        full_query = f"{history_str}\n\nCurrent Query: {last_user_msg}"

        if tool_result.get("success") and tool_result.get("results"):
            results = tool_result["results"]
            prompt = "You are a pharmaceutical CRM assistant. Based on the following database records, answer the user's question or summarize the records naturally. Keep it concise.\n\n"
            for r in results:
                prompt += f"- Visit ID {r['id']}: Dr. {r['doctor_name']} at {r['hospital']} on {r['visit_date']}. Discussed: {r['products']}. Interest: {r['interest_level']}\n"
            
            response = call_llm(prompt, full_query, model_name=model_name)
        elif not tool_result.get("success"):
            prompt = f"You are a pharmaceutical CRM assistant. The database search failed. Error: {tool_result.get('error')}. Please politely inform the user and try to answer their question based on your knowledge if applicable."
            response = call_llm(prompt, full_query, model_name=model_name)
        else:
            prompt = "You are a pharmaceutical CRM assistant. No matching records were found in the interaction database. Politely inform the user that there are no past records matching their query, and then answer their question based on your general knowledge or suggest what they can do next."
            response = call_llm(prompt, full_query, model_name=model_name)

    elif intent == "summarize":
        response = tool_result.get("summary", "No summary generated.")

    elif intent == "schedule":
        if tool_result.get("success"):
            response = f"I have scheduled the follow-up reminder for you! {tool_result.get('message')}"
        else:
            response = f"Failed to schedule follow-up. Error: {tool_result.get('error')}"

    elif intent == "insights":
        response = tool_result.get("insights", "No insights generated.")

    else:
        # General chat - call LLM for a natural response
        from backend.database import SessionLocal
        from backend.models.models import Doctor
        db = SessionLocal()
        try:
            doctors = db.query(Doctor).all()
            doc_context = "\n".join([f"- Dr. {d.name}, {d.specialization} at {d.hospital} ({d.department})" for d in doctors])
        except Exception:
            doc_context = "No database connection."
        finally:
            db.close()

        system_chat_prompt = f"You are HCP Nexus AI, an advanced AI chatbot and medical CRM assistant. You have vast knowledge and should comprehensively answer all user queries, including general medical details (e.g., normal BP levels, heart rates), details about doctors and hospitals, and fetch any history or data they ask for. Be detailed, professional, and helpful.\nHere is some context about the doctors and hospitals in your system:\n{doc_context}"
        
        history_str = ""
        if len(messages) > 1:
            history_str = "\nConversation History:\n" + "\n".join([f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in messages[:-1]])
        
        full_query = f"{history_str}\n\nCurrent Query: {last_user_msg}"
        response = call_llm(system_chat_prompt, full_query, model_name=model_name)

    return {**state, "final_response": response}

# Configure Graph
workflow = StateGraph(AgentState)
workflow.add_node("detect_intent", detect_intent_node)
workflow.add_node("execute_tool", execute_tool_node)
workflow.add_node("generate_response", generate_response_node)

workflow.set_entry_point("detect_intent")
workflow.add_edge("detect_intent", "execute_tool")
workflow.add_edge("execute_tool", "generate_response")
workflow.add_edge("generate_response", END)

app = workflow.compile()
