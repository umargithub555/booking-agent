import shutil
import os
import uuid
import json
import asyncio
from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.connection import get_db
from app.db.models import User, UserRole, UserStatus
from app.services.stt_service import STTService
from app.services.llm_service import LLMService
from app.services.tts_service import TTSService
from app.utils.helper import hash_password, is_sentence_end, clean_for_tts
from app.api.hotels import router as hotel_router
from app.api.inventory import router as inventory_router
from app.api.reservations import router as reservation_router
from app.api.agent import router as agent_router
from app.auth import registration


app = FastAPI()
app.include_router(hotel_router)
app.include_router(inventory_router)
app.include_router(reservation_router)
app.include_router(agent_router)
app.include_router(registration.router)

stt = STTService()
llm = LLMService()
tts = TTSService()

UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)








app.include_router(registration.router)




@app.get("/health-check")
def health_check():
    return {
        "status": 200,
        "app_name": settings.APP_NAME,
        "app_description": settings.APP_DESCRIPTION,
        "environment": settings.ENVIRONMENT
    }









@app.post("/api/voice-stream")
async def voice_stream(file: UploadFile = File(...)):
    # ... session setup ...
    session_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_DIR, f"{session_id}.wav")

    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    async def event_stream():
        loop = asyncio.get_event_loop()
        try:
            # ── 1. STT ──────────────────────────────────────────────────────
            text_input = await loop.run_in_executor(None, stt.transcribe, input_path)
            if not text_input:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Could not understand audio'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'user_text', 'text': text_input})}\n\n"

            # ── 2. Stream LLM + 3. TTS per sentence ─────────────────────────
            sentence_buffer = ""
            async for token in llm.stream_response(text_input):
                yield f"data: {json.dumps({'type': 'ai_token', 'token': token})}\n\n"
                sentence_buffer += token

                if is_sentence_end(sentence_buffer):
                    sentence = sentence_buffer.strip()
                    sentence_buffer = ""
                    
                    # Clean the text for voice, but keep 'sentence' original for UI
                    voice_text = clean_for_tts(sentence)
                    audio_b64 = await loop.run_in_executor(
                        None, tts.generate_audio_base64, voice_text
                    )
                    if audio_b64:
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': audio_b64, 'text': sentence})}\n\n"

            # Flush any remaining text
            if sentence_buffer.strip():
                final_sentence = sentence_buffer.strip()
                voice_text = clean_for_tts(final_sentence)
                audio_b64 = await loop.run_in_executor(
                    None, tts.generate_audio_base64, voice_text
                )
                if audio_b64:
                    yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': audio_b64, 'text': final_sentence})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if os.path.exists(input_path):
                os.remove(input_path)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )






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

















# Serve UI 
app.mount("/", StaticFiles(directory="static", html=True), name="static")
