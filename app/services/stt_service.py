from faster_whisper import WhisperModel
import os

class STTService:
    def __init__(self, model_size="base"):
        # Run on GPU if available, else CPU
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio_path: str):
        segments, info = self.model.transcribe(audio_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        return text.strip()
