import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, timedelta
from sqlalchemy import text

from backend.database import engine, Base, SessionLocal, ensure_sqlite_schema
from backend.models.models import Doctor, Product, Interaction, FollowUp, User
from backend.routers import doctors, dashboard, interactions, chat, auth

app = FastAPI(
    title="HCP Nexus AI Backend",
    description="Enterprise AI-First CRM Platform for Pharmaceutical Sales Representatives",
    version="1.0.0"
)

# Enable CORS for React Frontend development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(dashboard.router)
app.include_router(interactions.router)
app.include_router(doctors.router)
app.include_router(chat.router)
app.include_router(auth.router)

@app.on_event("startup")
def startup_db_setup():
    """Create database tables and seed with high-fidelity mockup data if empty."""
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()

    db = SessionLocal()
    try:
        # 1. Seed Products if empty
        if db.query(Product).count() == 0:
            products = [
                Product(name="CardioPlus", category="Cardiovascular", description="Advanced beta-blocker for hypertension management and vascular support."),
                Product(name="DiabeCare", category="Endocrinology", description="Next-generation oral hypoglycemic agent optimizing glucose sensitivity."),
                Product(name="NeuroMax", category="Neurology", description="Neuroprotective therapeutic designed for cognitive restoration and nerve support."),
                Product(name="RespiClear", category="Pulmonology", description="Inhaled bronchodilator for chronic asthma and COPD symptom alleviation."),
                Product(name="OsteoShield", category="Orthopedics", description="Calcium-channel regulator accelerating bone mineral density recovery.")
            ]
            db.add_all(products)
            db.commit()
            print("Successfully seeded database with products.")

        # 2. Seed Doctors if empty
        if db.query(Doctor).count() == 0:
            doctors_list = [
                Doctor(name="Rajesh Patel", hospital="Apollo Hospital", specialization="Cardiology", department="Cardiology Dept"),
                Doctor(name="Sarah Jenkins", hospital="Metro Medical Clinic", specialization="Neurology", department="Neurology Ward"),
                Doctor(name="Gregory House", hospital="Mercy Health Hospital", specialization="General Medicine", department="Diagnostics"),
                Doctor(name="Emily Watson", hospital="St. Jude Pediatric Hospital", specialization="Pediatrics", department="Outpatient Pediatrics"),
                Doctor(name="Alan Grant", hospital="Mount Sinai Orthopedics", specialization="Orthopedics", department="Joint Surgery Center")
            ]
            db.add_all(doctors_list)
            db.commit()
            print("Successfully seeded database with doctors.")

        # 3. Seed a default user if empty
        if db.query(User).count() == 0:
            default_user = User(
                name=os.environ.get("USERNAME") or os.environ.get("USER") or "Default User",
                email=os.environ.get("USER_EMAIL") or "default.user@nexuspharma.com",
                role=os.environ.get("USER_ROLE") or "",
                region=os.environ.get("USER_REGION") or ""
            )
            db.add(default_user)
            db.commit()
            db.refresh(default_user)
        else:
            default_user = db.query(User).first()

        if engine.url.get_backend_name() == "sqlite":
            db.execute(text("UPDATE interactions SET user_id = :user_id WHERE user_id IS NULL"), {"user_id": default_user.id})
            db.commit()

        # 4. Seed Interactions & FollowUps if empty
        if db.query(Interaction).count() == 0:
            doc_rajesh = db.query(Doctor).filter(Doctor.name == "Rajesh Patel").first()
            doc_sarah = db.query(Doctor).filter(Doctor.name == "Sarah Jenkins").first()
            doc_house = db.query(Doctor).filter(Doctor.name == "Gregory House").first()

            interactions = [
                Interaction(
                    user_id=default_user.id,
                    doctor_id=doc_rajesh.id,
                    doctor_name=doc_rajesh.name,
                    hospital=doc_rajesh.hospital,
                    specialization=doc_rajesh.specialization,
                    department=doc_rajesh.department,
                    visit_date=date.today() - timedelta(days=2),
                    products="CardioPlus",
                    summary="Detailed presentation on CardioPlus clinical trial outcomes.",
                    notes="Dr. Rajesh Patel expressed great interest in our phase-III trial data. He requested 10 patient starter packages.",
                    interest_level="High",
                    followup_date=date.today() + timedelta(days=5)
                ),
                Interaction(
                    user_id=default_user.id,
                    doctor_id=doc_sarah.id,
                    doctor_name=doc_sarah.name,
                    hospital=doc_sarah.hospital,
                    specialization=doc_sarah.specialization,
                    department=doc_sarah.department,
                    visit_date=date.today() - timedelta(days=4),
                    products="NeuroMax",
                    summary="Introduction meeting to showcase NeuroMax.",
                    notes="Doctor was busy but gave us 5 minutes. She wants a follow-up presentation with the department head.",
                    interest_level="Medium",
                    followup_date=date.today() + timedelta(days=10)
                ),
                Interaction(
                    user_id=default_user.id,
                    doctor_id=doc_house.id,
                    doctor_name=doc_house.name,
                    hospital=doc_house.hospital,
                    specialization=doc_house.specialization,
                    department=doc_house.department,
                    visit_date=date.today() - timedelta(days=1),
                    products="DiabeCare, CardioPlus",
                    summary="Discussed complex case applications for DiabeCare.",
                    notes="Skeptical about pricing compared to generics, but acknowledged the cardiovascular protection benefits of CardioPlus.",
                    interest_level="Low",
                    followup_date=None
                )
            ]
            db.add_all(interactions)
            db.commit()

            # Seed FollowUps based on interactions
            inter_rajesh = db.query(Interaction).filter(Interaction.doctor_id == doc_rajesh.id).first()
            inter_sarah = db.query(Interaction).filter(Interaction.doctor_id == doc_sarah.id).first()

            followups = [
                FollowUp(
                    interaction_id=inter_rajesh.id,
                    doctor_id=doc_rajesh.id,
                    date=date.today() + timedelta(days=5),
                    action_item="Deliver 10 CardioPlus patient starter packages",
                    status="Pending"
                ),
                FollowUp(
                    interaction_id=inter_sarah.id,
                    doctor_id=doc_sarah.id,
                    date=date.today() + timedelta(days=10),
                    action_item="Arrange presentation with department head",
                    status="Pending"
                )
            ]
            db.add_all(followups)
            db.commit()
            print("Successfully seeded interactions and followups.")
            
    except Exception as e:
        print(f"Error seeding database: {e}")
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "HCP Nexus AI FastAPI is online and running."}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
