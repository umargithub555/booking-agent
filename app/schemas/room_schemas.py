from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from app.db.models import RoomStatus

class RoomBase(BaseModel):
    room_number: str
    floor: Optional[int] = None
    status: RoomStatus = RoomStatus.ACTIVE

class RoomCreate(RoomBase):
    hotel_id: UUID
    room_type_id: UUID

class RoomUpdate(BaseModel):
    hotel_id: UUID
    room_number: Optional[str] = None
    floor: Optional[int] = None
    status: Optional[RoomStatus] = None
    room_type_id: Optional[UUID] = None

class RoomResponse(RoomBase):
    id: UUID
    hotel_id: UUID
    room_type_id: UUID
    
    model_config = ConfigDict(from_attributes=True)
