from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID

class HotelBase(BaseModel):
    name: str
    city: str
    country: str
    address: Optional[str] = None
    rating: Optional[float] = None
    description: Optional[str] = None

class HotelCreate(HotelBase):
    pass

class HotelUpdate(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    rating: Optional[float] = None
    description: Optional[str] = None

class HotelResponse(HotelBase):
    id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)