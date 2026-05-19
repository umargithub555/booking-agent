from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, extract
from typing import List, Optional
from uuid import UUID
from datetime import date, timedelta

from app.db.connection import get_db
from app.db.models import Hotel, Room, RoomType, RoomInventory, UserRole
from app.schemas.inventory_schemas import (
    InventoryBulkCreate, InventoryUpdate, InventoryResponse, AvailabilityResponse
)
from app.auth.authentication import role_required

router = APIRouter(tags=["Inventory"], prefix="/inventory")

@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_seed_inventory(
    data: InventoryBulkCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    """
    Bulk seeds inventory for a specific room across a date range.
    Note: room_id is passed in the body.
    """
    # Verify room exists
    room_result = await db.execute(select(Room).filter(Room.id == data.room_id))
    room = room_result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    current_date = data.start_date
    inventory_items = []
    
    while current_date <= data.end_date:
        # Check if record already exists to avoid duplicates (UPSERT logic could be used but here we just skip/fail)
        # For simplicity in this script, we'll just prepare the objects
        item = RoomInventory(
            room_id=data.room_id,
            inventory_date=current_date,
            is_available=data.is_available,
            price_override=data.base_price
        )
        inventory_items.append(item)
        current_date += timedelta(days=1)

    try:
        db.add_all(inventory_items)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Error seeding inventory: {str(e)}")

    return {"msg": f"Seeded {len(inventory_items)} inventory days for room {data.room_id}"}


@router.get("/room/{room_id}", response_model=List[InventoryResponse])
async def get_room_inventory(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    """Get all inventory records for a specific room ID in path."""
    result = await db.execute(select(RoomInventory).filter(RoomInventory.room_id == room_id).order_by(RoomInventory.inventory_date))
    return result.scalars().all()


@router.patch("/{inventory_id}", response_model=InventoryResponse)
async def update_inventory_record(
    inventory_id: UUID,
    data: InventoryUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    """Update a specific inventory record by its ID in path."""
    result = await db.execute(select(RoomInventory).filter(RoomInventory.id == inventory_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)

    await db.commit()
    await db.refresh(record)
    return record


@router.get("/availability", response_model=List[AvailabilityResponse])
async def search_availability(
    hotel_id: UUID = Query(...),
    checkin: date = Query(...),
    checkout: date = Query(...),
    guests: int = Query(1),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for available rooms in a hotel for a given date range.
    Uses query parameters for all IDs and filters.
    """
    if checkout <= checkin:
        raise HTTPException(status_code=400, detail="Checkout must be after checkin")

    requested_days = (checkout - checkin).days
    
    # Complex query to find rooms that are available for ALL days in the range
    # 1. Join Room -> RoomType -> Hotel
    # 2. Filter by hotel_id, max_guests >= guests
    # 3. Filter by inventory_date in [checkin, checkout-1] AND is_available = True
    # 4. Group by Room.id and check if count == requested_days
    
    query = (
        select(
            Room.id.label("room_id"),
            Room.room_number,
            RoomType.name.label("room_type_name"),
            Hotel.id.label("hotel_id"),
            Hotel.name.label("hotel_name"),
            RoomType.base_price,
            RoomType.currency,
            func.count(RoomInventory.id).label("available_count"),
            func.sum(func.coalesce(RoomInventory.price_override, RoomType.base_price)).label("total_price")
        )
        .join(RoomType, Room.room_type_id == RoomType.id)
        .join(Hotel, Room.hotel_id == Hotel.id)
        .join(RoomInventory, Room.id == RoomInventory.room_id)
        .filter(
            Hotel.id == hotel_id,
            RoomType.max_guests >= guests,
            RoomInventory.inventory_date >= checkin,
            RoomInventory.inventory_date < checkout,
            RoomInventory.is_available == True
        )
        .group_by(Room.id, RoomType.id, Hotel.id)
        .having(func.count(RoomInventory.id) == requested_days)
    )

    result = await db.execute(query)
    rows = result.all()

    # Get available dates for each room to satisfy the schema (optional but helpful)
    # Since we already filtered by 'having count == requested_days', we know they are all available
    # but the response wants the list.
    
    availability = []
    for row in rows:
        availability.append({
            "hotel_id": row.hotel_id,
            "hotel_name": row.hotel_name,
            "room_id": row.room_id,
            "room_number": row.room_number,
            "room_type_name": row.room_type_name,
            "total_price": row.total_price,
            "currency": row.currency,
            "available_dates": [checkin + timedelta(days=i) for i in range(requested_days)]
        })

    return availability
