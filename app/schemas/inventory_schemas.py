from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import date
from uuid import UUID
from decimal import Decimal

class InventoryBase(BaseModel):
    is_available: bool = True
    price_override: Optional[Decimal] = None

class InventoryBulkCreate(BaseModel):
    room_id: UUID
    start_date: date
    end_date: date
    base_price: Optional[Decimal] = None
    is_available: bool = True

class InventoryUpdate(BaseModel):
    is_available: Optional[bool] = None
    price_override: Optional[Decimal] = None

class InventoryResponse(InventoryBase):
    id: UUID
    room_id: UUID
    inventory_date: date
    
    model_config = ConfigDict(from_attributes=True)

class AvailabilityResponse(BaseModel):
    hotel_id: UUID
    hotel_name: str
    room_id: UUID
    room_number: str
    room_type_name: str
    total_price: Decimal
    currency: str
    available_dates: List[date]
