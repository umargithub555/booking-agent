from pydantic import BaseModel, ConfigDict
from typing import Dict, Any
from datetime import datetime, date
from uuid import UUID

class DailyMenuBase(BaseModel):
    hotel_id: UUID
    menu_date: date
    menu_data: Dict[str, Any]

class DailyMenuCreate(DailyMenuBase):
    pass

class DailyMenuUpdate(BaseModel):
    menu_data: Dict[str, Any]

class DailyMenuResponse(DailyMenuBase):
    id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
