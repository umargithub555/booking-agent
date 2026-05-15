from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import List, Optional
from uuid import UUID

from app.db.connection import get_db
from app.db.models import Hotel, RoomType, Room, UserRole
from app.schemas.hotel_schemas import HotelCreate, HotelUpdate, HotelResponse
from app.schemas.room_type_schemas import RoomTypeCreate, RoomTypeUpdate, RoomTypeResponse
from app.schemas.room_schemas import RoomCreate, RoomUpdate, RoomResponse
from app.auth.authentication import role_required

router = APIRouter(tags=["Hotels"], prefix="/hotel")

# --- HOTELS ---

@router.get("/", response_model=List[HotelResponse])
async def list_hotels(
    city: Optional[str] = None,
    country: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Hotel).filter(Hotel.deleted_at == None)
    if city:
        query = query.filter(Hotel.city == city)
    if country:
        query = query.filter(Hotel.country == country)
    
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/create", response_model=HotelResponse, status_code=status.HTTP_201_CREATED)
async def create_hotel(
    hotel_data: HotelCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    new_hotel = Hotel(**hotel_data.model_dump())
    db.add(new_hotel)
    await db.commit()
    await db.refresh(new_hotel)
    return new_hotel

@router.get("/hotels/{hotel_id}", response_model=HotelResponse)
async def get_hotel(hotel_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hotel).filter(Hotel.id == hotel_id, Hotel.deleted_at == None))
    hotel = result.scalars().first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel

@router.patch("/{hotel_id}", response_model=HotelResponse)
async def update_hotel(
    hotel_id: UUID,
    hotel_data: HotelUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    result = await db.execute(select(Hotel).filter(Hotel.id == hotel_id, Hotel.deleted_at == None))
    hotel = result.scalars().first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    update_data = hotel_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(hotel, key, value)
    
    await db.commit()
    await db.refresh(hotel)
    return hotel

@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotel(
    hotel_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    result = await db.execute(select(Hotel).filter(Hotel.id == hotel_id, Hotel.deleted_at == None))
    hotel = result.scalars().first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    from datetime import datetime, timezone
    hotel.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return None

# --- ROOM TYPES ---

@router.get("/{hotel_id}/room-types", response_model=List[RoomTypeResponse])
async def list_room_types(hotel_id: UUID, db: AsyncSession = Depends(get_db)):
    query = (
        select(
            RoomType,
            func.count(Room.id).label("total_physical_rooms")
        )
        .outerjoin(Room, RoomType.id == Room.room_type_id)
        .filter(RoomType.hotel_id == hotel_id)
        .group_by(RoomType.id)
    )
    result = await db.execute(query)
    
    room_types = []
    for row in result.all():
        rt = row.RoomType
        rt.total_physical_rooms = row.total_physical_rooms
        room_types.append(rt)
        
    return room_types

@router.post("/room-types", response_model=RoomTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_room_type(
    room_type_data: RoomTypeCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    # Verify hotel exists
    result = await db.execute(select(Hotel).filter(Hotel.id == room_type_data.hotel_id, Hotel.deleted_at == None))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Hotel not found")
        
    new_room_type = RoomType(**room_type_data.model_dump())
    db.add(new_room_type)
    await db.commit()
    await db.refresh(new_room_type)
    return new_room_type

@router.get("/hotels/{hotel_id}/room-types/{type_id}", response_model=RoomTypeResponse)
async def get_room_type(hotel_id: UUID, type_id: UUID, db: AsyncSession = Depends(get_db)):
    query = (
        select(
            RoomType,
            func.count(Room.id).label("total_physical_rooms")
        )
        .outerjoin(Room, RoomType.id == Room.room_type_id)
        .filter(RoomType.id == type_id, RoomType.hotel_id == hotel_id)
        .group_by(RoomType.id)
    )
    result = await db.execute(query)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Room Type not found")
    
    rt = row.RoomType
    rt.total_physical_rooms = row.total_physical_rooms
    return rt

@router.patch("/hotels/{hotel_id}/room-types/{type_id}", response_model=RoomTypeResponse)
async def update_room_type(
    hotel_id: UUID,
    type_id: UUID,
    room_type_data: RoomTypeUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    result = await db.execute(select(RoomType).filter(RoomType.id == type_id, RoomType.hotel_id == hotel_id))
    room_type = result.scalars().first()
    if not room_type:
        raise HTTPException(status_code=404, detail="Room Type not found")
    
    update_data = room_type_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(room_type, key, value)
    
    await db.commit()
    
    # Re-fetch with count for the response
    query = (
        select(
            RoomType,
            func.count(Room.id).label("total_physical_rooms")
        )
        .outerjoin(Room, RoomType.id == Room.room_type_id)
        .filter(RoomType.id == type_id)
        .group_by(RoomType.id)
    )
    result = await db.execute(query)
    row = result.first()
    rt = row.RoomType
    rt.total_physical_rooms = row.total_physical_rooms
    return rt

@router.delete("/{hotel_id}/room-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room_type(
    hotel_id: UUID,
    type_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    result = await db.execute(select(RoomType).filter(RoomType.id == type_id, RoomType.hotel_id == hotel_id))
    room_type = result.scalars().first()
    if not room_type:
        raise HTTPException(status_code=404, detail="Room Type not found")
    
    await db.delete(room_type)
    await db.commit()
    return None

# --- ROOMS ---

@router.get("/{hotel_id}/rooms", response_model=List[RoomResponse])
async def list_rooms(hotel_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Room).filter(Room.hotel_id == hotel_id, Room.deleted_at == None))
    return result.scalars().all()

@router.post("/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    room_data: RoomCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    # Verify hotel exists
    hotel_result = await db.execute(select(Hotel).filter(Hotel.id == room_data.hotel_id, Hotel.deleted_at == None))
    if not hotel_result.scalars().first():
        raise HTTPException(status_code=404, detail="Hotel not found")
        
    # Verify room type exists and belongs to hotel
    type_result = await db.execute(select(RoomType).filter(RoomType.id == room_data.room_type_id, RoomType.hotel_id == room_data.hotel_id))
    if not type_result.scalars().first():
        raise HTTPException(status_code=404, detail="Room Type not found for this hotel")

    new_room = Room(**room_data.model_dump())
    db.add(new_room)
    await db.commit()
    await db.refresh(new_room)
    return new_room

@router.get("/{hotel_id}/rooms/{room_id}", response_model=RoomResponse)
async def get_room(hotel_id: UUID, room_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Room).filter(Room.id == room_id, Room.hotel_id == hotel_id, Room.deleted_at == None))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

@router.patch("/rooms/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: UUID,
    room_data: RoomUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    result = await db.execute(select(Room).filter(Room.id == room_id, Room.hotel_id == room_data.hotel_id, Room.deleted_at == None))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # If room type is being updated, verify it exists for this hotel
    if room_data.room_type_id:
        type_result = await db.execute(select(RoomType).filter(RoomType.id == room_data.room_type_id, RoomType.hotel_id == room_data.hotel_id))
        if not type_result.scalars().first():
            raise HTTPException(status_code=404, detail="Room Type not found for this hotel")

    update_data = room_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(room, key, value)
    
    await db.commit()
    await db.refresh(room)
    return room

@router.delete("/{hotel_id}/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    hotel_id: UUID,
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    result = await db.execute(select(Room).filter(Room.id == room_id, Room.hotel_id == hotel_id, Room.deleted_at == None))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    from datetime import datetime, timezone
    room.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return None
