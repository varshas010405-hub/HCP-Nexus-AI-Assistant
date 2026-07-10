from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List, Optional

# --- DOCTOR SCHEMAS ---
class DoctorBase(BaseModel):
    name: str = Field(..., example="Dr. Sarah Connor")
    hospital: str = Field(..., example="General Medical Center")
    specialization: str = Field(..., example="Cardiology")
    department: str = Field(..., example="Cardiovascular Diseases")

class DoctorCreate(DoctorBase):
    pass

class DoctorResponse(DoctorBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- PRODUCT SCHEMAS ---
class ProductBase(BaseModel):
    name: str = Field(..., example="CardioPlus")
    category: str = Field(..., example="Cardiovascular")
    description: Optional[str] = Field(None, example="Beta-blocker for hypertension management.")

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int

    class Config:
        from_attributes = True

# --- INTERACTION SCHEMAS ---
class InteractionBase(BaseModel):
    doctor_name: str
    hospital: str
    specialization: str
    department: str
    visit_date: date
    products: str  # Comma separated or stringified list
    summary: Optional[str] = None
    notes: Optional[str] = None
    interest_level: str  # High, Medium, Low
    followup_date: Optional[date] = None

class InteractionCreate(InteractionBase):
    user_id: Optional[int] = None
    doctor_id: Optional[int] = None

class InteractionUpdate(BaseModel):
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    hospital: Optional[str] = None
    specialization: Optional[str] = None
    department: Optional[str] = None
    visit_date: Optional[date] = None
    products: Optional[str] = None
    summary: Optional[str] = None
    notes: Optional[str] = None
    interest_level: Optional[str] = None
    followup_date: Optional[date] = None

class InteractionResponse(InteractionBase):
    id: int
    user_id: int
    doctor_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- USER SCHEMAS ---
class UserBase(BaseModel):
    name: str = Field(..., example="Varsha Kaushik")
    email: str = Field(..., example="varsha.kaushik@nexuspharma.com")
    role: str = Field(..., example="Sales Representative")
    region: str = Field(..., example="Northeast Region")

class UserCreate(UserBase):
    pass

class UserLogin(BaseModel):
    name: str = Field(..., example="Varsha Kaushik")
    email: str = Field(..., example="varsha.kaushik@nexuspharma.com")
    role: Optional[str] = Field(None, example="Sales Representative")
    region: Optional[str] = Field(None, example="Northeast Region")

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- FOLLOWUP SCHEMAS ---
class FollowUpBase(BaseModel):
    date: date
    action_item: str
    status: str = "Pending"  # Pending, Completed

class FollowUpCreate(FollowUpBase):
    interaction_id: int
    doctor_id: int

class FollowUpResponse(FollowUpBase):
    id: int
    interaction_id: int
    doctor_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- CHAT ASSISTANT SCHEMAS ---
class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []  # List of {"role": "user"|"assistant", "content": "text"}
    model_override: Optional[str] = None

class ExtractedDetails(BaseModel):
    doctor_name: Optional[str] = None
    hospital: Optional[str] = None
    specialization: Optional[str] = None
    department: Optional[str] = None
    visit_date: Optional[str] = None
    products: Optional[List[str]] = None
    summary: Optional[str] = None
    action_items: Optional[List[str]] = None
    interest_level: Optional[str] = None
    followup_date: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    extracted_fields: Optional[ExtractedDetails] = None
    tool_triggered: Optional[str] = None

# --- DASHBOARD SCHEMAS ---
class RecentInteraction(BaseModel):
    id: int
    doctor_name: str
    hospital: str
    visit_date: date
    interest_level: str
    products: str

class UpcomingFollowUp(BaseModel):
    id: int
    doctor_name: str
    date: date
    action_item: str
    status: str

class DashboardStats(BaseModel):
    total_hcps: int
    todays_visits: int
    upcoming_followups_count: int
    pending_tasks_count: int
    recent_interactions: List[RecentInteraction]
    upcoming_followups: List[UpcomingFollowUp]
