from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from decimal import Decimal
from uuid import UUID

class RoomTypeBase(BaseModel):
    hotel_id: UUID
    name: str
    description: Optional[str] = None
    max_guests: int
    base_price: Decimal
    currency: str = "USD"
    amenities: List[str] = []

class RoomTypeCreate(RoomTypeBase):
    pass

class RoomTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_guests: Optional[int] = None
    base_price: Optional[Decimal] = None
    currency: Optional[str] = None
    amenities: Optional[List[str]] = None

class RoomTypeResponse(RoomTypeBase):
    id: UUID
    total_physical_rooms: int = 0
    
    model_config = ConfigDict(from_attributes=True)
