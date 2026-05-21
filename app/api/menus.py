from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.db.connection import get_db
from app.db.models import DailyMenu, Hotel, UserRole
from app.schemas.menu_schemas import DailyMenuCreate, DailyMenuUpdate, DailyMenuResponse
from app.auth.authentication import role_required

router = APIRouter(tags=["Menus"], prefix="/menu")

@router.get("/hotel/{hotel_id}", response_model=List[DailyMenuResponse])
async def list_daily_menus(
    hotel_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """List all daily menus for a specific hotel."""
    result = await db.execute(
        select(DailyMenu).filter(DailyMenu.hotel_id == hotel_id)
    )
    return result.scalars().all()

@router.get("/{menu_id}", response_model=DailyMenuResponse)
async def get_daily_menu(
    menu_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details of a specific daily menu."""
    result = await db.execute(
        select(DailyMenu).filter(DailyMenu.id == menu_id)
    )
    menu = result.scalars().first()
    if not menu:
        raise HTTPException(status_code=404, detail="Daily menu not found")
    return menu

@router.post("/create", response_model=DailyMenuResponse, status_code=status.HTTP_201_CREATED)
async def create_daily_menu(
    menu_data: DailyMenuCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    """Create a new daily menu for a hotel (Admin only)."""
    # Verify hotel exists
    hotel_result = await db.execute(
        select(Hotel).filter(Hotel.id == menu_data.hotel_id, Hotel.deleted_at == None)
    )
    if not hotel_result.scalars().first():
        raise HTTPException(status_code=404, detail="Hotel not found")

    # Check if a menu already exists for this hotel and date to enforce uniqueness
    existing_result = await db.execute(
        select(DailyMenu).filter(
            DailyMenu.hotel_id == menu_data.hotel_id,
            DailyMenu.menu_date == menu_data.menu_date
        )
    )
    if existing_result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail=f"A daily menu already exists for hotel {menu_data.hotel_id} on {menu_data.menu_date}"
        )

    new_menu = DailyMenu(**menu_data.model_dump())
    db.add(new_menu)
    await db.commit()
    await db.refresh(new_menu)
    return new_menu

@router.patch("/{menu_id}", response_model=DailyMenuResponse)
async def update_daily_menu(
    menu_id: UUID,
    menu_data: DailyMenuUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    """Update today's menu layout (Admin only)."""
    result = await db.execute(
        select(DailyMenu).filter(DailyMenu.id == menu_id)
    )
    menu = result.scalars().first()
    if not menu:
        raise HTTPException(status_code=404, detail="Daily menu not found")

    update_data = menu_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(menu, key, value)

    await db.commit()
    await db.refresh(menu)
    return menu

@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_daily_menu(
    menu_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(role_required([UserRole.ADMIN]))
):
    """Delete a daily menu (Admin only)."""
    result = await db.execute(
        select(DailyMenu).filter(DailyMenu.id == menu_id)
    )
    menu = result.scalars().first()
    if not menu:
        raise HTTPException(status_code=404, detail="Daily menu not found")

    await db.delete(menu)
    await db.commit()
    return None
