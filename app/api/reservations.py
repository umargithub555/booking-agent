from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload
from sqlalchemy import cast, Date
from typing import List
from uuid import UUID
from datetime import datetime, timezone
from app.utils.helper import generate_confirmation_code
from app.db.connection import get_db
from app.db.models import ( 
    Reservation, ReservationGuest, RoomInventory, Room, RoomType, 
    ReservationStatus, UserRole, User
)
from app.schemas.reservation_schemas import (
    ReservationCreate, ReservationUpdate, ReservationResponse
)
from app.auth.authentication import get_current_User, role_required

router = APIRouter(tags=["Reservations"], prefix="/reservations")

@router.post("/", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    data: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_User)
):
    """
    Creates a new reservation. 
    IDs (hotel_id, room_id) are passed in the body.
    """
    if data.checkout_date <= data.checkin_date:
        raise HTTPException(status_code=400, detail="Checkout must be after checkin")

    # 1. Verify room exists and belongs to the hotel
    room_query = (
        select(Room)
        .options(selectinload(Room.room_type))
        .filter(Room.id == data.room_id, Room.hotel_id == data.hotel_id)
    )
    room_result = await db.execute(room_query)
    room = room_result.scalars().first()
    
    if not room:
        raise HTTPException(
            status_code=404, 
            detail="Room not found or does not belong to the specified hotel."
        )

    # 2. Check availability — autobegin starts a real BEGIN on first execute(),
    # so with_for_update() works correctly without calling db.begin() manually.
    inventory_query = (
        select(RoomInventory)
        .filter(
            RoomInventory.room_id == data.room_id,
            RoomInventory.inventory_date >= data.checkin_date,
            RoomInventory.inventory_date < data.checkout_date,
            RoomInventory.is_available.is_(True)
        )
        .with_for_update()
    )
    inventory_result = await db.execute(inventory_query)
    inventory_records = inventory_result.scalars().all()

    requested_days = (data.checkout_date - data.checkin_date).days
    if len(inventory_records) < requested_days:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Room is not available. Requested {requested_days} nights "
                f"(from {data.checkin_date} to {data.checkout_date}), "
                f"but only {len(inventory_records)} available days found."
            )
        )

    # 3. Calculate price and mark inventory as booked
    total_amount = 0
    for record in inventory_records:
        price = record.price_override if record.price_override is not None else room.room_type.base_price
        total_amount += price
        record.is_available = False

    # 4. Create Reservation
    new_reservation = Reservation(
        user_id=current_user.id,
        hotel_id=data.hotel_id,
        room_id=data.room_id,
        checkin_date=data.checkin_date,
        checkout_date=data.checkout_date,
        guest_count=data.guest_count,
        status=ReservationStatus.CONFIRMED,
        total_amount=total_amount,
        currency=room.room_type.currency,
        confirmation_code=generate_confirmation_code(),
        special_requests=data.special_requests
    )
    db.add(new_reservation)
    await db.flush()  # Get ID for guests before adding them

    # 5. Add Guests
    for guest_data in data.guests:
        guest = ReservationGuest(
            reservation_id=new_reservation.id,
            **guest_data.model_dump()
        )
        db.add(guest)

    await db.commit()

    # 6. Re-fetch with guests eagerly loaded for the response
    result = await db.execute(
        select(Reservation)
        .options(selectinload(Reservation.guests))
        .filter(Reservation.id == new_reservation.id)
    )
    return result.scalars().first()



@router.get("/my", response_model=List[ReservationResponse])
async def list_my_reservations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_User)
):
    """List current user's reservations."""
    result = await db.execute(
        select(Reservation)
        .options(selectinload(Reservation.guests))
        .filter(Reservation.user_id == current_user.id)
        .order_by(Reservation.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{res_id}", response_model=ReservationResponse)
async def get_reservation(
    res_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_User)
):
    """Get reservation details. ID in path."""
    result = await db.execute(
        select(Reservation)
        .options(selectinload(Reservation.guests))
        .filter(Reservation.id == res_id)
    )
    res = result.scalars().first()
    
    if not res:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    # Only Admin or Owner can view
    if res.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to view this reservation")
        
    return res


@router.delete("/{res_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_reservation(
    res_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_User)
):
    """Cancels a reservation and frees inventory. ID in path."""
    result = await db.execute(select(Reservation).filter(Reservation.id == res_id))
    res = result.scalars().first()

    if not res:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    if res.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this reservation")

    if res.status == ReservationStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Reservation is already cancelled")

    # 1. Update status
    res.status = ReservationStatus.CANCELLED
    res.cancelled_at = datetime.now(timezone.utc)

    # 2. Free up inventory
    await db.execute(
        update(RoomInventory)
        .filter(
            RoomInventory.room_id == res.room_id,
            RoomInventory.inventory_date >= res.checkin_date,
            RoomInventory.inventory_date < res.checkout_date
        )
        .values(is_available=True)
    )

    await db.commit()
    return None


@router.patch("/{res_id}", response_model=ReservationResponse)
async def update_reservation_status(
    res_id: UUID,
    data: ReservationUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    """Admin endpoint to update status. ID in path."""
    result = await db.execute(
        select(Reservation)
        .options(selectinload(Reservation.guests))
        .filter(Reservation.id == res_id)
    )
    res = result.scalars().first()

    if not res:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if data.status:
        res.status = data.status

    await db.commit()
    await db.refresh(res)
    return res
