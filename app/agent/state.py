
from typing import Annotated, Dict, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Full conversation history (LangGraph manages append-only updates)
    messages: Annotated[list, add_messages]

    # Authenticated user context (injected at session start)
    user_id: Optional[str]
    user_name: Optional[str]

    # Hotel discovery cache — populated by search_hotels, persists for the whole session
    # Maps hotel name (str) → hotel_id (str) so the LLM can look up IDs without re-searching
    searched_hotels: Optional[Dict[str, str]]

    # Collected booking intent (filled progressively during the conversation)
    hotel_id: Optional[str]       # UUID of the currently focused hotel
    hotel_name: Optional[str]     # Human-readable name of the currently focused hotel
    room_id: Optional[str]        # UUID of the selected room
    checkin_date: Optional[str]   # ISO format: YYYY-MM-DD
    checkout_date: Optional[str]  # ISO format: YYYY-MM-DD
    guest_count: Optional[int]

    # Completed booking result
    reservation_id: Optional[str]
    confirmation_code: Optional[str]

    # Draft food order (dictionary of item name -> details like quantity, price)
    draft_order: Optional[Dict]

















# 4. Get Reservation Details


# @tool
# async def get_reservation_details(reservation_id: str) -> dict:
#     """
#     Retrieve details of an existing reservation by its ID.
#     Use this when the user asks about their booking status or details.
#     """
#     async with AsyncSessionLocal() as db:
#         result = await db.execute(
#             select(Reservation)
#             .options(selectinload(Reservation.guests))
#             .filter(Reservation.id == uuid.UUID(reservation_id))
#         )
#         res = result.scalars().first()

#     if not res:
#         return {"error": "Reservation not found."}

#     return {
#         "reservation_id": str(res.id),
#         "confirmation_code": res.confirmation_code,
#         "status": res.status.value,
#         "checkin_date": str(res.checkin_date),
#         "checkout_date": str(res.checkout_date),
#         "total_amount": float(res.total_amount) if res.total_amount else None,
#         "currency": res.currency,
#         "special_requests": res.special_requests,
#     }



# # 5. Cancel Reservation


# @tool
# async def cancel_reservation(
#     reservation_id: str,
#     config: Annotated[RunnableConfig, InjectedToolArg],
# ) -> dict:
#     """
#     Cancel an existing reservation and free up the inventory.
#     Only call this after the user explicitly confirms they want to cancel.
#     """
#     user_id = config.get("configurable", {}).get("user_id")
#     if not user_id:
#         return {"error": "User context is missing. Please log in first."}

#     from sqlalchemy import update
#     from datetime import datetime, timezone

#     async with AsyncSessionLocal() as db:
#         result = await db.execute(
#             select(Reservation).filter(Reservation.id == uuid.UUID(reservation_id))
#         )
#         res = result.scalars().first()

#         if not res:
#             return {"error": "Reservation not found."}

#         if str(res.user_id) != user_id:
#             return {"error": "You are not authorized to cancel this reservation."}

#         if res.status == ReservationStatus.CANCELLED:
#             return {"error": "This reservation is already cancelled."}

#         res.status = ReservationStatus.CANCELLED
#         res.cancelled_at = datetime.now(timezone.utc)

#         # Free inventory
#         await db.execute(
#             update(RoomInventory)
#             .filter(
#                 RoomInventory.room_id == res.room_id,
#                 RoomInventory.inventory_date >= res.checkin_date,
#                 RoomInventory.inventory_date < res.checkout_date
#             )
#             .values(is_available=True)
#         )
#         await db.commit()

#     return {
#         "success": True,
#         "reservation_id": reservation_id,
#         "message": f"Reservation {res.confirmation_code} has been successfully cancelled."
#     }


# # 6. Get Hotel Details (General Pricing and Room Types)


# @tool
# async def get_hotel_details(hotel_id: str) -> dict:
#     """
#     Retrieve details of a specific hotel by its UUID.
#     Returns the hotel's details including name, address, description, rating,
#     and a list of all its room types with their standard base prices per night.
#     Use this when the user asks about the rooms, amenities, general pricing, or details of a hotel
#     without specifying travel dates.
#     """
#     try:
#         hotel_uuid = uuid.UUID(hotel_id)
#     except ValueError:
#         return {"error": "Invalid hotel_id format. Must be a UUID string."}

#     async with AsyncSessionLocal() as db:
#         hotel_result = await db.execute(
#             select(Hotel).filter(Hotel.id == hotel_uuid, Hotel.deleted_at.is_(None))
#         )
#         hotel = hotel_result.scalars().first()
#         if not hotel:
#             return {"error": "Hotel not found."}

#         room_types_result = await db.execute(
#             select(RoomType).filter(RoomType.hotel_id == hotel_uuid)
#         )
#         room_types = room_types_result.scalars().all()

#     return {
#         "hotel_id": str(hotel.id),
#         "name": hotel.name,
#         "city": hotel.city,
#         "country": hotel.country,
#         "address": hotel.address,
#         "rating": float(hotel.rating) if hotel.rating else None,
#         "description": hotel.description,
#         "room_types": [
#             {
#                 "room_type_id": str(rt.id),
#                 "name": rt.name,
#                 "description": rt.description,
#                 "max_guests": rt.max_guests,
#                 "base_price": float(rt.base_price),
#                 "currency": rt.currency,
#                 "amenities": rt.amenities or [],
#             }
#             for rt in room_types
#         ]
#     }


# # 7. Get Alternative Available Dates

# @tool
# async def get_alternative_available_dates(
#     hotel_id: str,
#     start_date: str,
#     guests: int = 1
# ) -> list[dict]:
#     """
#     Retrieve alternative dates and room availability for the next 14 days starting from start_date.
#     Use this when the user's requested dates are unavailable to offer alternative booking dates.
#     hotel_id: UUID of the hotel.
#     start_date: The requested check-in date in YYYY-MM-DD format.
#     guests: Number of guests (default 1).
#     """
#     try:
#         start = date.fromisoformat(start_date)
#     except ValueError:
#         return [{"error": "Invalid date format. Use YYYY-MM-DD."}]

#     end = start + timedelta(days=14)

#     async with AsyncSessionLocal() as db:
#         query = (
#             select(
#                 RoomInventory.inventory_date,
#                 RoomType.name.label("room_type_name"),
#                 func.min(func.coalesce(RoomInventory.price_override, RoomType.base_price)).label("daily_price"),
#                 RoomType.currency,
#                 func.count(Room.id).label("available_count")
#             )
#             .join(Room, RoomInventory.room_id == Room.id)
#             .join(RoomType, Room.room_type_id == RoomType.id)
#             .join(Hotel, Room.hotel_id == Hotel.id)
#             .filter(
#                 Hotel.id == uuid.UUID(hotel_id),
#                 RoomType.max_guests >= guests,
#                 RoomInventory.inventory_date >= start,
#                 RoomInventory.inventory_date < end,
#                 RoomInventory.is_available.is_(True)
#             )
#             .group_by(RoomInventory.inventory_date, RoomType.id, RoomType.name, RoomType.currency)
#             .order_by(RoomInventory.inventory_date, RoomType.name)
#         )
#         result = await db.execute(query)
#         rows = result.all()

#     if not rows:
#         return [{"message": "No alternative dates with available rooms were found in the next 14 days."}]

#     # Group by date for a cleaner structured response
#     by_date = defaultdict(list)
#     for row in rows:
#         d_str = str(row.inventory_date)
#         by_date[d_str].append({
#             "room_type": row.room_type_name,
#             "daily_price": float(row.daily_price),
#             "currency": row.currency,
#             "available_rooms": row.available_count
#         })

#     return [
#         {
#             "date": d,
#             "available_options": options
#         }
#         for d, options in sorted(by_date.items())
#     ]




# @tool
# async def get_daily_menu(hotel_id: str, menu_date: str) -> dict:
#     """
#     Retrieve the daily food menu for a specific hotel on a given date.
#     hotel_id: UUID of the hotel.
#     menu_date: Date in YYYY-MM-DD format.
#     Returns the JSON menu data containing categories (e.g., breakfast, dinner) and item prices.
#     """
#     try:
#         hotel_uuid = uuid.UUID(hotel_id)
#         parsed_date = date.fromisoformat(menu_date)
#     except ValueError:
#         return {"error": "Invalid input format. Ensure hotel_id is a UUID and date is YYYY-MM-DD."}

#     async with AsyncSessionLocal() as db:
#         result = await db.execute(
#             select(DailyMenu).filter(
#                 DailyMenu.hotel_id == hotel_uuid,
#                 DailyMenu.menu_date == parsed_date
#             )
#         )
#         daily_menu = result.scalars().first()

#     if not daily_menu:
#         return {"message": f"No menu has been posted for {menu_date} at this hotel yet."}

#     return {
#         "hotel_id": hotel_id,
#         "menu_date": menu_date,
#         "menu_data": daily_menu.menu_data
#     }



# @tool(args_schema=PlaceOrderInput)
# async def place_order(
#     reservation_id: str,
#     items: list[OrderItemInput],
#     special_notes: str = "",
#     config: Annotated[RunnableConfig, InjectedToolArg] = None
# ) -> dict:
#     """
#     Place a room service food order for an active reservation.
#     """
#     user_id = config.get("configurable", {}).get("user_id") if config else None
#     if not user_id:
#         return {"error": "User context is missing. Please log in first."}

#     try:
#         res_uuid = uuid.UUID(reservation_id)
#         user_uuid = uuid.UUID(user_id)
#     except ValueError:
#         return {"error": "Invalid reservation_id format. Must be a UUID."}

#     if not items:
#         return {"error": "Order cannot be empty. Please specify items to order."}

#     async with AsyncSessionLocal() as db:
#         # Verify reservation exists and belongs to the user
#         res_result = await db.execute(
#             select(Reservation).filter(
#                 Reservation.id == res_uuid,
#                 Reservation.user_id == user_uuid
#             )
#         )
#         res = res_result.scalars().first()
#         if not res:
#             return {"error": "Reservation not found or you are not authorized to place orders for it."}

#         # Production Grade Validations
#         if res.status != ReservationStatus.CONFIRMED:
#             return {"error": f"Cannot place room service order. Your reservation status is '{res.status.value}', it must be 'confirmed'."}

#         today = date.today()
#         if today < res.checkin_date or today > res.checkout_date:
#             return {"error": f"Cannot place order for today ({today}). Your reservation is active from {res.checkin_date} to {res.checkout_date}."}

#         # Fetch today's menu for this hotel to calculate total securely
#         menu_result = await db.execute(
#             select(DailyMenu).filter(
#                 DailyMenu.hotel_id == res.hotel_id,
#                 DailyMenu.menu_date == today
#             )
#         )
#         daily_menu = menu_result.scalars().first()
        
#         total_amount = 0.0
#         final_items = {}
#         menu_data = daily_menu.menu_data if daily_menu else {}

#         # Flatten the menu_data to make lookup easier
#         flat_menu = {}
#         for category, cat_items in menu_data.items():
#             if isinstance(cat_items, dict):
#                 for item_name, details in cat_items.items():
#                     flat_menu[item_name.lower()] = details

#         for item in items:
#             item_name = item.item_name
#             qty = item.qty
#             item_lower = item_name.lower()
            
#             # Default fallback if menu doesn't exist yet
#             price = 15.00
#             description = ""
#             if item_lower in flat_menu:
#                 price = float(flat_menu[item_lower].get("price", 15.00))
#                 description = flat_menu[item_lower].get("description", "")
            
#             total_amount += price * qty
#             final_items[item_name] = {
#                 "qty": qty,
#                 "price": price,
#                 "description": description
#             }

#         # Create Order
#         new_order = Order(
#             reservation_id=res_uuid,
#             items=final_items,
#             total_amount=total_amount,
#             status=OrderStatus.PENDING,
#             special_notes=special_notes if special_notes else None
#         )
#         db.add(new_order)
#         await db.commit()
#         await db.refresh(new_order)

#         return {
#             "success": True,
#             "order_id": str(new_order.id),
#             "status": "pending",
#             "total_amount": total_amount,
#             "items": final_items,
#             "message": f"Order placed successfully! Order ID is {new_order.id}. Total amount is ${total_amount:.2f}."
#         }


# @tool
# async def get_order_status(order_id: str) -> dict:
#     """
#     Check the current status and details of a room service order by its ID.
#     order_id: UUID of the order.
#     """
#     try:
#         order_uuid = uuid.UUID(order_id)
#     except ValueError:
#         return {"error": "Invalid order_id format. Must be a UUID."}

#     async with AsyncSessionLocal() as db:
#         result = await db.execute(
#             select(Order).filter(Order.id == order_uuid)
#         )
#         order = result.scalars().first()

#     if not order:
#         return {"error": "Order not found."}

#     return {
#         "order_id": str(order.id),
#         "reservation_id": str(order.reservation_id),
#         "status": order.status.value,
#         "total_amount": float(order.total_amount),
#         "items": order.items,
#         "special_notes": order.special_notes,
#         "created_at": str(order.created_at)
#     }
