# 🏨 LuxeStay AI — Agentic Hotel Booking System

LuxeStay AI is a high-performance, open-source agentic AI system designed to handle hotel reservations via a voice-first interface. It leverages state-of-the-art local models for Speech-to-Text (STT), Large Language Model (LLM) reasoning, and Text-to-Speech (TTS).

---

## 🚀 Current Phase: Voice-to-Voice Loop
The project is currently in **Phase 1**, featuring a fully functional voice-interaction pipeline with a premium glassmorphic web UI.

### Technology Stack
- **STT**: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Base model)
- **LLM**: [LM Studio](https://lmstudio.ai/) 
- **TTS**: [Kokoro-ONNX](https://github.com/thewh1teagle/kokoro-onnx) (v0.19)
- **Backend**: FastAPI (Python 3.10+)
- **Frontend**: Vanilla HTML5, CSS3 (Glassmorphism), and JavaScript

---

## 🛠️ Setup Instructions

### 1. Prerequisites
Ensure you have Python installed, then run the following:
```powershell
pip install fastapi uvicorn faster-whisper kokoro-onnx onnxruntime-gpu python-multipart requests numpy soundfile
```
*(Use `onnxruntime` if you do not have an NVIDIA GPU).*

### 2. LLM Setup (LM Studio)
1.  Download and install [LM Studio](https://lmstudio.ai/).
2.  Search for and download **`Any lightweight model`**.
3.  Navigate to the **Local Server** tab, select the model, and **Start Server** on port `1234`.

### 3. TTS Setup (Kokoro)
1.  Create a `models/` directory in the root of this project.
2.  Download `kokoro-v0_19.onnx` or `kokoro.onnx` and `voices.bin` from the [Kokoro-ONNX Releases](https://github.com/thewh1teagle/kokoro-onnx/releases).
3.  Place both files inside the `models/` folder.

---

## 🏃 How to Run

1.  **Start the Backend**:
    ```powershell
    python run.py
    ```
2.  **Access the UI**:
    Open your browser and go to `http://localhost:8000`.

3.  **Interact**:
    Click the microphone icon and speak. The system will transcribe your voice, generate a concierge response via LM Studio, and speak back to you using Kokoro.

---

## 🗺️ Roadmap
- [x] Phase 1: Voice-to-Voice Loop & UI
- [ ] Phase 2: PostgreSQL Integration & Room Schema
- [ ] Phase 3: LangGraph Agent Orchestration (Booking Logic)
- [ ] Phase 4: Go Microservices for Real-time Availability
- [ ] Phase 5: Production Deployment (Docker & LiveKit)

---

## 📜 License
Open Source - MIT
