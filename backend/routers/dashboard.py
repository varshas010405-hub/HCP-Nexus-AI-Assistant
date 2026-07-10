from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date
from backend.database import get_db
from backend.models.models import Doctor, Interaction, FollowUp
from backend.routers.auth import get_current_user_optional
from backend.schemas.schemas import DashboardStats, RecentInteraction, UpcomingFollowUp

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("", response_model=DashboardStats)
def get_dashboard_data(current_user: object = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    """Fetch aggregated KPIs and recent activities for the home dashboard."""
    query_filter = []
    if current_user:
        query_filter.append(Interaction.user_id == current_user.id)

    # Count totals
    total_hcps = db.query(Doctor).count()
    
    today = date.today()
    todays_visits_query = db.query(Interaction).filter(Interaction.visit_date == today)
    if current_user:
        todays_visits_query = todays_visits_query.filter(Interaction.user_id == current_user.id)
    todays_visits = todays_visits_query.count()
    
    upcoming_followups_query = db.query(FollowUp).filter(
        FollowUp.date >= today,
        FollowUp.status == "Pending"
    )
    if current_user:
        upcoming_followups_query = upcoming_followups_query.join(Interaction).filter(Interaction.user_id == current_user.id)
    upcoming_followups_count = upcoming_followups_query.count()
    
    pending_tasks_query = db.query(FollowUp).filter(FollowUp.status == "Pending")
    if current_user:
        pending_tasks_query = pending_tasks_query.join(Interaction).filter(Interaction.user_id == current_user.id)
    pending_tasks_count = pending_tasks_query.count()
    
    # Recent interactions (limit 5)
    recent_query = db.query(Interaction).order_by(Interaction.visit_date.desc(), Interaction.created_at.desc())
    if current_user:
        recent_query = recent_query.filter(Interaction.user_id == current_user.id)
    recent_db = recent_query.limit(5).all()
    recent_interactions = [
        RecentInteraction(
            id=inter.id,
            doctor_name=inter.doctor_name,
            hospital=inter.hospital,
            visit_date=inter.visit_date,
            interest_level=inter.interest_level,
            products=inter.products
        )
        for inter in recent_db
    ]
    
    # Upcoming followups list (limit 5)
    followups_query = db.query(FollowUp).join(Interaction).join(Doctor).filter(
        FollowUp.status == "Pending"
    )
    if current_user:
        followups_query = followups_query.filter(Interaction.user_id == current_user.id)
    followups_db = followups_query.order_by(FollowUp.date.asc()).limit(5).all()
    
    upcoming_followups = [
        UpcomingFollowUp(
            id=f.id,
            doctor_name=db.query(Doctor).filter(Doctor.id == f.doctor_id).first().name,
            date=f.date,
            action_item=f.action_item,
            status=f.status
        )
        for f in followups_db
    ]
    
    return DashboardStats(
        total_hcps=total_hcps,
        todays_visits=todays_visits,
        upcoming_followups_count=upcoming_followups_count,
        pending_tasks_count=pending_tasks_count,
        recent_interactions=recent_interactions,
        upcoming_followups=upcoming_followups
    )
