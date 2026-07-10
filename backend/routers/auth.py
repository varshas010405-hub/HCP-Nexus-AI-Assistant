from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.models.models import User
from backend.schemas.schemas import UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

AUTH_HEADER = "X-User-Id"


def get_current_user_optional(x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not x_user_id:
        return None
    try:
        user_id = int(x_user_id)
    except ValueError:
        return None
    return db.query(User).filter(User.id == user_id).first()


def get_current_user(x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing authentication header")
    try:
        user_id = int(x_user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authentication header")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/login", response_model=UserResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    # Simplified login by email; if user does not exist, create one.
    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user:
        user = User(
            name=payload.name,
            email=payload.email,
            role=payload.role or "",
            region=payload.region or ""
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
def update_me(payload: UserLogin, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.name = payload.name
    current_user.email = payload.email
    current_user.role = payload.role or current_user.role
    current_user.region = payload.region or current_user.region
    db.commit()
    db.refresh(current_user)
    return current_user
