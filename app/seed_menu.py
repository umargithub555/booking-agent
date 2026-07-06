import asyncio
from datetime import date
from sqlalchemy import select
from db.connection import AsyncSessionLocal
from db.models import Hotel, DailyMenu



async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Hotel))
        hotels = res.scalars().all()
        if not hotels:
            print("No hotels seeded! Run standard seeds first.")
            return

        today = date.today()
        dummy_menu = {
            "breakfast": {
                "pancakes": {"price": 12.00, "description": "Fluffy buttermilk pancakes with maple syrup"},
                "omelette": {"price": 15.00, "description": "3-egg omelette with cheese, ham, and toast"},
                "french toast": {"price": 13.50, "description": "Brioche bread dipped in rich custard, toasted golden brown"},
                "coffee": {"price": 4.50, "description": "Freshly brewed house blend coffee"}
            },
            "lunch": {
                "caesar salad": {"price": 16.00, "description": "Crisp romaine, parmesan, croutons, and creamy Caesar dressing"},
                "club sandwich": {"price": 18.50, "description": "Triple-decker sandwich with turkey, bacon, lettuce, and tomato"},
                "burger": {"price": 20.00, "description": "Gourmet beef patty with cheddar cheese, fries, and house sauce"}
            },
            "dinner": {
                "pasta": {"price": 25.00, "description": "Truffle mushroom fettuccine in white wine sauce"},
                "steak": {"price": 45.00, "description": "8oz Ribeye steak cooked to order with mashed potatoes"},
                "salmon": {"price": 35.00, "description": "Pan-seared Atlantic salmon with asparagus and wild rice"}
            }
        }

        for hotel in hotels:
            # Check if menu already exists
            menu_res = await db.execute(
                select(DailyMenu).filter(
                    DailyMenu.hotel_id == hotel.id,
                    DailyMenu.menu_date == today
                )
            )
            existing_menu = menu_res.scalars().first()
            if existing_menu:
                print(f"Daily menu already exists for {hotel.name} on {today}. Skipping.")
                continue

            menu = DailyMenu(
                hotel_id=hotel.id,
                menu_date=today,
                menu_data=dummy_menu
            )
            db.add(menu)
            print(f"Seeded today's menu for hotel: {hotel.name}")
        
        await db.commit()
        print("Successfully committed daily menus!")

if __name__ == "__main__":
    asyncio.run(main())
