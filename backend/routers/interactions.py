from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc
from datetime import date, datetime
from typing import List, Optional
import csv
import io

from backend.routers.auth import get_current_user_optional, get_current_user

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from backend.database import get_db
from backend.models.models import Interaction, Doctor, FollowUp
from backend.schemas.schemas import InteractionCreate, InteractionUpdate, InteractionResponse

router = APIRouter(tags=["Interactions"])


def _clean_text(value):
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
    else:
        cleaned = str(value).strip()
    return cleaned or None


@router.get("/interactions")
def get_interactions(
    search: Optional[str] = None,
    specialization: Optional[str] = None,
    hospital: Optional[str] = None,
    interest_level: Optional[str] = None,
    visit_date: Optional[str] = None,
    sort_by: str = "visit_date",
    sort_order: str = "desc",
    page: int = 1,
    limit: int = 10,
    current_user: object = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List interactions with server-side searching, multi-filter sorting, and pagination."""
    query = db.query(Interaction)
    if current_user:
        query = query.filter(Interaction.user_id == current_user.id)

    # Search filter
    if search:
        query = query.filter(
            or_(
                Interaction.doctor_name.ilike(f"%{search}%"),
                Interaction.hospital.ilike(f"%{search}%"),
                Interaction.products.ilike(f"%{search}%"),
                Interaction.notes.ilike(f"%{search}%")
            )
        )

    # Specific filters
    if specialization:
        query = query.filter(Interaction.specialization == specialization)
    if hospital:
        query = query.filter(Interaction.hospital == hospital)
    if interest_level:
        query = query.filter(Interaction.interest_level == interest_level)
    if visit_date:
        try:
            parsed_date = datetime.strptime(visit_date, "%Y-%m-%d").date()
            query = query.filter(Interaction.visit_date == parsed_date)
        except ValueError:
            pass

    # Sorting
    col = getattr(Interaction, sort_by, Interaction.visit_date)
    if sort_order == "desc":
        query = query.order_by(desc(col))
    else:
        query = query.order_by(asc(col))

    # Pagination
    total = query.count()
    offset = (page - 1) * limit
    results = query.offset(offset).limit(limit).all()

    # Get filter dropdown options dynamically for UI
    specializations = [r[0] for r in db.query(Interaction.specialization).distinct().all() if r[0]]
    hospitals = [r[0] for r in db.query(Interaction.hospital).distinct().all() if r[0]]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "results": results,
        "filter_options": {
            "specializations": specializations,
            "hospitals": hospitals
        }
    }

@router.get("/interaction/{id}", response_model=InteractionResponse)
def get_interaction_by_id(id: int, current_user: object = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve details for a single interaction."""
    query = db.query(Interaction).filter(Interaction.id == id)
    if current_user:
        query = query.filter(Interaction.user_id == current_user.id)
    interaction = query.first()
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return interaction

@router.post("/interaction/log", response_model=InteractionResponse)
def log_interaction(payload: InteractionCreate, current_user: object = Depends(get_current_user), db: Session = Depends(get_db)):
    """Log a new doctor interaction (structured form)."""
    doctor_name = _clean_text(payload.doctor_name)
    hospital = _clean_text(payload.hospital)
    specialization = _clean_text(payload.specialization)
    department = _clean_text(payload.department)
    products = _clean_text(payload.products)
    interest_level = _clean_text(payload.interest_level)
    summary = _clean_text(payload.summary)
    notes = _clean_text(payload.notes)

    if not all([doctor_name, hospital, specialization, department, products, interest_level]):
        raise HTTPException(status_code=422, detail="Please provide complete, non-placeholder interaction details.")

    # 1. Resolve or create Doctor
    doctor = db.query(Doctor).filter(Doctor.name.ilike(doctor_name)).first()
    if not doctor:
        doctor = Doctor(
            name=doctor_name,
            hospital=hospital,
            specialization=specialization,
            department=department
        )
        db.add(doctor)
        db.commit()
        db.refresh(doctor)
    
    # 2. Save Interaction
    interaction = Interaction(
        user_id=current_user.id,
        doctor_id=doctor.id,
        doctor_name=doctor.name,
        hospital=doctor.hospital,
        specialization=doctor.specialization,
        department=doctor.department,
        visit_date=payload.visit_date,
        products=products,
        summary=summary,
        notes=notes,
        interest_level=interest_level,
        followup_date=payload.followup_date
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    # 3. Create FollowUp task if date specified
    if payload.followup_date:
        action = f"Follow-up with Dr. {doctor.name} on products: {payload.products}"
        db_followup = FollowUp(
            interaction_id=interaction.id,
            doctor_id=doctor.id,
            date=payload.followup_date,
            action_item=action,
            status="Pending"
        )
        db.add(db_followup)
        db.commit()

    return interaction

@router.put("/interaction/edit/{id}", response_model=InteractionResponse)
def edit_interaction(id: int, payload: InteractionUpdate, current_user: object = Depends(get_current_user), db: Session = Depends(get_db)):
    """Edit an existing interaction record."""
    query = db.query(Interaction).filter(Interaction.id == id)
    if current_user:
        query = query.filter(Interaction.user_id == current_user.id)
    interaction = query.first()
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    # Update interaction values
    for key, val in payload.dict(exclude_unset=True).items():
        setattr(interaction, key, val)

    # Update associated follow-up date if followup_date changes
    if payload.followup_date:
        followup = db.query(FollowUp).filter(FollowUp.interaction_id == id).first()
        if followup:
            followup.date = payload.followup_date
        else:
            db_followup = FollowUp(
                interaction_id=interaction.id,
                doctor_id=interaction.doctor_id or 1,
                date=payload.followup_date,
                action_item=f"Follow-up with Dr. {interaction.doctor_name} regarding {interaction.products}",
                status="Pending"
            )
            db.add(db_followup)

    db.commit()
    db.refresh(interaction)
    return interaction

@router.delete("/interaction/{id}")
def delete_interaction(id: int, current_user: object = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete an interaction from the database."""
    query = db.query(Interaction).filter(Interaction.id == id)
    if current_user:
        query = query.filter(Interaction.user_id == current_user.id)
    interaction = query.first()
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    
    db.delete(interaction)
    db.commit()
    return {"message": "Interaction deleted successfully", "id": id}


# --- DATA EXPORT ENDPOINTS ---

@router.get("/interactions/export/csv")
def export_interactions_csv(current_user: object = Depends(get_current_user), db: Session = Depends(get_db)):
    """Export all interactions to a download-friendly CSV file."""
    query = db.query(Interaction)
    if current_user:
        query = query.filter(Interaction.user_id == current_user.id)
    interactions = query.order_by(Interaction.visit_date.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        "ID", "Doctor Name", "Hospital", "Specialization", "Department",
        "Visit Date", "Products Discussed", "Summary", "Interest Level", "Follow-up Date"
    ])
    
    for item in interactions:
        writer.writerow([
            item.id,
            item.doctor_name,
            item.hospital,
            item.specialization,
            item.department,
            item.visit_date.strftime("%Y-%m-%d"),
            item.products,
            item.summary or "",
            item.interest_level,
            item.followup_date.strftime("%Y-%m-%d") if item.followup_date else ""
        ])
    
    output.seek(0)
    
    headers = {
        'Content-Disposition': 'attachment; filename="hcp_nexus_interactions.csv"'
    }
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)


@router.get("/interactions/export/pdf")
def export_interactions_pdf(current_user: object = Depends(get_current_user), db: Session = Depends(get_db)):
    """Export interaction records to a professionally styled PDF report using ReportLab."""
    query = db.query(Interaction)
    if current_user:
        query = query.filter(Interaction.user_id == current_user.id)
    interactions = query.order_by(Interaction.visit_date.desc()).all()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        name='TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=15
    )
    
    meta_style = ParagraphStyle(
        name='MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#4B5563'),
        spaceAfter=20
    )

    story = []
    
    # Header
    story.append(Paragraph("HCP Nexus AI - Interactions Report", title_style))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Records: {len(interactions)}", meta_style))
    story.append(Spacer(1, 10))
    
    # Table data setup
    table_data = [[
        Paragraph("<b>Date</b>", styles['Normal']),
        Paragraph("<b>Doctor</b>", styles['Normal']),
        Paragraph("<b>Hospital / Clinic</b>", styles['Normal']),
        Paragraph("<b>Products</b>", styles['Normal']),
        Paragraph("<b>Interest</b>", styles['Normal'])
    ]]
    
    for item in interactions:
        table_data.append([
            Paragraph(item.visit_date.strftime("%Y-%m-%d"), styles['Normal']),
            Paragraph(f"Dr. {item.doctor_name}", styles['Normal']),
            Paragraph(item.hospital, styles['Normal']),
            Paragraph(item.products, styles['Normal']),
            Paragraph(item.interest_level, styles['Normal'])
        ])
        
    t = Table(table_data, colWidths=[70, 110, 160, 130, 70])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E5E7EB')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D1D5DB')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    
    story.append(t)
    doc.build(story)
    
    buffer.seek(0)
    
    headers = {
        'Content-Disposition': 'attachment; filename="hcp_nexus_report.pdf"'
    }
    return StreamingResponse(buffer, media_type="application/pdf", headers=headers)
