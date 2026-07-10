from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models.models import Doctor, Interaction
from backend.schemas.schemas import DoctorResponse, DoctorCreate

router = APIRouter(prefix="/doctor", tags=["Doctors"])

@router.get("s", response_model=List[DoctorResponse])
def get_all_doctors(db: Session = Depends(get_db)):
    """Fetch all doctors in the directory."""
    return db.query(Doctor).order_by(Doctor.name.asc()).all()

@router.get("/{id}")
def get_doctor_details(id: int, db: Session = Depends(get_db)):
    """Retrieve full details of a doctor and all their past interactions."""
    doctor = db.query(Doctor).filter(Doctor.id == id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    interactions = db.query(Interaction).filter(Interaction.doctor_id == id).order_by(Interaction.visit_date.desc()).all()
    
    # Format timeline response
    interactions_serialized = []
    for inter in interactions:
        interactions_serialized.append({
            "id": inter.id,
            "visit_date": inter.visit_date.strftime("%Y-%m-%d"),
            "products": inter.products,
            "interest_level": inter.interest_level,
            "summary": inter.summary,
            "notes": inter.notes,
            "followup_date": inter.followup_date.strftime("%Y-%m-%d") if inter.followup_date else None
        })

    return {
        "id": doctor.id,
        "name": doctor.name,
        "hospital": doctor.hospital,
        "specialization": doctor.specialization,
        "department": doctor.department,
        "created_at": doctor.created_at,
        "interactions": interactions_serialized
    }

@router.post("", response_model=DoctorResponse)
def create_doctor(payload: DoctorCreate, db: Session = Depends(get_db)):
    """Create a new doctor manually."""
    existing = db.query(Doctor).filter(Doctor.name.ilike(payload.name)).first()
    if existing:
        return existing
        
    doctor = Doctor(
        name=payload.name,
        hospital=payload.hospital,
        specialization=payload.specialization,
        department=payload.department
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor
