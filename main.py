import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.connection import get_db
from app.db.models import User, UserRole, UserStatus
from app.utils.helper import hash_password
from app.api.hotels import router as hotel_router
from app.api.inventory import router as inventory_router
from app.api.reservations import router as reservation_router
from app.api.agent import router as agent_router
from app.api.menus import router as menu_router
from app.auth import registration


# ── Lifespan: runs once per worker at startup / shutdown ────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly warm up the TTS singleton so the first voice request has no
    # extra latency and the "Kokoro TTS loaded" message appears only here.
    from app.services.tts_service import TTSService
    _tts_warmup = TTSService()
    print(f"🚀 {settings.APP_NAME} is ready.")
    yield
    print("👋 Server shutting down.")


app = FastAPI(lifespan=lifespan)

# ── CORS – required for ngrok (browser fetches from a different origin) ───────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hotel_router)
app.include_router(inventory_router)
app.include_router(reservation_router)
app.include_router(agent_router)
app.include_router(menu_router)
app.include_router(registration.router)






@app.get("/health-check")
def health_check():
    return {
        "status": 200,
        "app_name": settings.APP_NAME,
        "app_description": settings.APP_DESCRIPTION,
        "environment": settings.ENVIRONMENT
    }








@app.post("/seed-admin", status_code=status.HTTP_201_CREATED)
async def seed_admin(db: AsyncSession = Depends(get_db)):
    """
    Seeds a default administrative user. 
    In production, protect this endpoint or delete it after the first run.
    """
    
    # 1. Check if an admin already exists to prevent duplicates
    result = await db.execute(select(User).filter(User.role == UserRole.ADMIN))
    admin_exists = result.scalars().first()

    if admin_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin user already initialized."
        )

    # 2. Create the Admin object
    new_admin = User(
        full_name="System Administrator",
        email="admin123@gmail.com",
        password=hash_password("admin123"), # ALWAYS hash passwords
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE
    )

    try:
        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)
        return {"message": "Admin user created successfully", "id": new_admin.id}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Database error: {str(e)}"
        )






@app.get("/agent-ui", response_class=FileResponse)
async def agent_ui():
    return FileResponse("static/agent_test.html")








# Serve UI 
app.mount("/", StaticFiles(directory="static", html=True), name="static")
