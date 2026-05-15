from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID
from decimal import Decimal
from app.db.models import ReservationStatus

class ReservationGuestBase(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None

class ReservationCreate(BaseModel):
    hotel_id: UUID
    room_id: UUID
    checkin_date: date
    checkout_date: date
    guest_count: int
    special_requests: Optional[str] = None
    guests: List[ReservationGuestBase] = []

class ReservationUpdate(BaseModel):
    status: Optional[ReservationStatus] = None

class ReservationResponse(BaseModel):
    id: UUID
    user_id: UUID
    hotel_id: UUID
    room_id: UUID
    checkin_date: date
    checkout_date: date
    guest_count: int
    status: ReservationStatus
    total_amount: Optional[Decimal] = None
    currency: str
    confirmation_code: Optional[str] = None
    special_requests: Optional[str] = None
    created_at: datetime
    guests: List[ReservationGuestBase]
    
    model_config = ConfigDict(from_attributes=True)
