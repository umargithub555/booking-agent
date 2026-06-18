
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from datetime import date, timedelta
from typing import Annotated, Optional
import uuid
from app.utils.helper import generate_confirmation_code
from pydantic import BaseModel, Field
from app.db.connection import AsyncSessionLocal
from app.db.models import (
    Hotel, Room, RoomType, RoomInventory, Reservation,
    ReservationGuest, ReservationStatus, DailyMenu, Order, OrderStatus
)
from collections import defaultdict




class OrderItemInput(BaseModel):
    item_name: str = Field(..., description="Name of the food item, e.g., 'steak' or 'pancakes'")
    qty: int = Field(1, description="Quantity of this item to order")

class PlaceOrderInput(BaseModel):
    reservation_id: str = Field(..., description="UUID of the reservation to link the order to.")
    items: list[OrderItemInput] = Field(..., description="List of items to order")
    special_notes: str = Field("", description="Special cooking or delivery requests (optional).")







# 1. Search Hotels by City or Country


@tool
async def search_all_hotels() -> dict:
    """
    Fetch a complete overview of ALL hotels in the system across every country and city.
    Use this tool when the user asks any of the following:
    - "What countries do you have hotels in?"
    - "Which cities do you cover?"
    - "Show me all available hotels"
    - "Do you have hotels in [country]?" (when unsure)
    - "Where can I book a hotel?"
    - "What destinations are available?"
    Returns a summary of distinct countries, distinct cities, and the full hotel list.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Hotel).filter(Hotel.deleted_at.is_(None)))
        all_hotels = result.scalars().all()

    if not all_hotels:
        return {"message": "No hotels found in the system yet."}

    hotels_list = [
        {
            "hotel_id": str(h.id),
            "name": h.name,
            "city": h.city,
            "country": h.country,
            "rating": float(h.rating) if h.rating else None,
            "description": h.description,
        }
        for h in all_hotels
    ]

    distinct_countries = sorted(set(h["country"] for h in hotels_list if h["country"]))
    distinct_cities = sorted(set(h["city"] for h in hotels_list if h["city"]))

    return {
        "total_hotels": len(hotels_list),
        "countries_available": distinct_countries,
        "cities_available": distinct_cities,
        "hotels": hotels_list,
    }



@tool
async def search_hotels(location: str) -> list[dict]:
    """
    Search for available hotels by city or country.
    Returns a list of hotels with their IDs, names, ratings, and descriptions.

    Examples:
    - "London"
    - "Pakistan"
    - "Dubai"

    Always call this first when the user mentions a destination.
    """

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Hotel).filter(
                or_(
                    Hotel.city.ilike(f"%{location}%"),
                    Hotel.country.ilike(f"%{location}%")
                ),
                Hotel.deleted_at.is_(None)
            )
        )

        hotels = result.scalars().all()

    if not hotels:
        return [{"message": f"No hotels found for '{location}'."}]

    return [
        {
            "hotel_id": str(h.id),
            "name": h.name,
            "city": h.city,
            "country": h.country,
            "rating": float(h.rating) if h.rating else None,
            "description": h.description,
        }
        for h in hotels
    ]


# 2. Check Room Availability


@tool
async def search_available_rooms(
    hotel_id: str,
    checkin_date: str,
    checkout_date: str,
    guests: int = 1
) -> list[dict]:
    """
    Search for available rooms in a specific hotel for a date range.
    hotel_id: UUID of the hotel.
    checkin_date: Check-in date in YYYY-MM-DD format.
    checkout_date: Check-out date in YYYY-MM-DD format.
    guests: Number of guests (default 1).
    Returns a list of available rooms with pricing details.
    """
    try:
        checkin = date.fromisoformat(checkin_date)
        checkout = date.fromisoformat(checkout_date)
    except ValueError:
        return [{"error": "Invalid date format. Use YYYY-MM-DD."}]

    if checkout <= checkin:
        return [{"error": "Checkout date must be after checkin date."}]

    requested_days = (checkout - checkin).days

    async with AsyncSessionLocal() as db:
        query = (
            select(
                Room.id.label("room_id"),
                Room.room_number,
                RoomType.name.label("room_type_name"),
                RoomType.max_guests,
                Hotel.id.label("hotel_id"),
                Hotel.name.label("hotel_name"),
                RoomType.currency,
                func.count(RoomInventory.id).label("available_count"),
                func.sum(
                    func.coalesce(RoomInventory.price_override, RoomType.base_price)
                ).label("total_price")
            )
            .join(RoomType, Room.room_type_id == RoomType.id)
            .join(Hotel, Room.hotel_id == Hotel.id)
            .join(RoomInventory, Room.id == RoomInventory.room_id)
            .filter(
                Hotel.id == uuid.UUID(hotel_id),
                RoomType.max_guests >= guests,
                RoomInventory.inventory_date >= checkin,
                RoomInventory.inventory_date < checkout,
                RoomInventory.is_available.is_(True)
            )
            .group_by(Room.id, RoomType.id, Hotel.id)
            .having(func.count(RoomInventory.id) == requested_days)
        )
        result = await db.execute(query)
        rows = result.all()

    if not rows:
        return [{"message": "No rooms available for the selected dates and guest count."}]

    return [
        {
            "room_id": str(row.room_id),
            "room_number": row.room_number,
            "room_type": row.room_type_name,
            "hotel_name": row.hotel_name,
            "max_guests": row.max_guests,
            "total_price": float(row.total_price),
            "currency": row.currency,
            "nights": requested_days,
        }
        for row in rows
    ]



# 3. Create Reservation


@tool
async def create_reservation(
    hotel_id: str,
    room_id: str,
    checkin_date: str,
    checkout_date: str,
    guest_count: int,
    guest_full_name: str,
    config: Annotated[RunnableConfig, InjectedToolArg],
    guest_email: str = "",
    special_requests: str = "",
) -> dict:
    """
    Book a room for a user. Call this ONLY after confirming all details with the user.
    hotel_id: UUID of the hotel.
    room_id: UUID of the specific room to book.
    checkin_date / checkout_date: Dates in YYYY-MM-DD format.
    guest_count: Number of guests.
    guest_full_name: Full name of the primary guest.
    guest_email: Email for the primary guest (optional).
    special_requests: Special requests for the hotel (optional).
    """
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return {"error": "User context is missing. Please log in first."}

    db_guest_email = guest_email if guest_email != "" else None
    db_special_requests = special_requests if special_requests != "" else None

    try:
        checkin = date.fromisoformat(checkin_date)
        checkout = date.fromisoformat(checkout_date)
        room_uuid = uuid.UUID(room_id)
        hotel_uuid = uuid.UUID(hotel_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError as e:
        return {"error": f"Invalid input: {str(e)}"}

    async with AsyncSessionLocal() as db:
        # Fetch room with room type eagerly loaded
        room_result = await db.execute(
            select(Room)
            .options(selectinload(Room.room_type))
            .filter(Room.id == room_uuid, Room.hotel_id == hotel_uuid)
        )
        room = room_result.scalars().first()
        if not room:
            return {"error": "Room not found or does not belong to the specified hotel."}

        # Check and lock inventory
        requested_days = (checkout - checkin).days
        inventory_result = await db.execute(
            select(RoomInventory)
            .filter(
                RoomInventory.room_id == room_uuid,
                RoomInventory.inventory_date >= checkin,
                RoomInventory.inventory_date < checkout,
                RoomInventory.is_available.is_(True)
            )
            .with_for_update()
        )
        inventory_records = inventory_result.scalars().all()

        if len(inventory_records) < requested_days:
            return {
                "error": f"Room is no longer available. Only {len(inventory_records)} of {requested_days} days are free."
            }

        # Calculate price & mark as booked
        total_amount = sum(
            r.price_override if r.price_override is not None else room.room_type.base_price
            for r in inventory_records
        )
        for record in inventory_records:
            record.is_available = False

        # Create reservation
        new_res = Reservation(
            user_id=user_uuid,
            hotel_id=hotel_uuid,
            room_id=room_uuid,
            checkin_date=checkin,
            checkout_date=checkout,
            guest_count=guest_count,
            status=ReservationStatus.CONFIRMED,
            total_amount=total_amount,
            currency=room.room_type.currency,
            confirmation_code=generate_confirmation_code(),
            special_requests=db_special_requests,
        )
        db.add(new_res)
        await db.flush()

        # Add primary guest
        db.add(ReservationGuest(
            reservation_id=new_res.id,
            full_name=guest_full_name,
            email=db_guest_email,
        ))

        await db.commit()

        return {
            "success": True,
            "reservation_id": str(new_res.id),
            "confirmation_code": new_res.confirmation_code,
            "room_number": room.room_number,
            "checkin_date": checkin_date,
            "checkout_date": checkout_date,
            "total_amount": float(total_amount),
            "currency": room.room_type.currency,
            "status": "confirmed",
            "message": (
                f"Booking confirmed! Your confirmation code is {new_res.confirmation_code}. "
                f"Room {room.room_number} is reserved from {checkin_date} to {checkout_date}."
            )
        }




# All tools collected for easy import
ALL_TOOLS = [
    search_all_hotels,
    search_hotels,
    # get_hotel_details,
    search_available_rooms,
    create_reservation,
    # get_reservation_details,
    # cancel_reservation,
    # get_alternative_available_dates,
    # get_daily_menu,
    # place_order,
    # get_order_status,
]
