from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
import os
import uuid

from .stt_service import STTService
from .llm_service import LLMService
from .tts_service import TTSService

app = FastAPI()

# Initialize services
stt = STTService()
llm = LLMService()
tts = TTSService()

# Ensure temp directories exist
UPLOAD_DIR = "temp_uploads"
OUTPUT_DIR = "temp_outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.post("/api/voice-process")
async def voice_process(file: UploadFile = File(...)):
    session_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_DIR, f"{session_id}_{file.filename}")
    output_audio_path = os.path.join(OUTPUT_DIR, f"{session_id}_response.wav")
    
    # 1. Save uploaded audio
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 2. STT: Speech to Text
        text_input = stt.transcribe(input_path)
        if not text_input:
            return {"error": "Could not understand audio"}

        # 3. LLM: Get Response
        ai_response = llm.generate_response(text_input)

        # 4. TTS: Text to Speech
        tts_success = tts.generate_audio(ai_response, output_audio_path)
        
        return {
            "user_text": text_input,
            "ai_text": ai_response,
            "audio_url": f"/api/audio/{session_id}_response.wav" if tts_success else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Audio not found")

# Serve UI
app.mount("/", StaticFiles(directory="static", html=True), name="static")

