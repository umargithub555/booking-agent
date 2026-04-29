import os
import io
import base64
import soundfile as sf


class TTSService:
    def __init__(self, model_path="models/kokoro-v1.0.onnx", voices_path="models/voices-v1.0.bin"):
        self.model_path = model_path
        self.voices_path = voices_path
        self.kokoro = None

    def _lazy_init(self):
        if self.kokoro is None:
            try:
                from kokoro_onnx import Kokoro
                if os.path.exists(self.model_path) and os.path.exists(self.voices_path):
                    self.kokoro = Kokoro(self.model_path, self.voices_path)
                    print("✓ Kokoro TTS loaded.")
                else:
                    print(f"⚠ Kokoro model files not found:\n  {self.model_path}\n  {self.voices_path}")
            except ImportError:
                print("⚠ kokoro-onnx not installed.")

    def generate_audio_base64(self, text: str, voice="af_jessica") -> str | None:
        """Generate audio for a sentence and return as base64-encoded WAV string."""
        self._lazy_init()
        if not self.kokoro:
            return None
        try:
            samples, sample_rate = self.kokoro.create(text, voice=voice, speed=1.0, lang="en-us")
            buffer = io.BytesIO()
            sf.write(buffer, samples, sample_rate, format="WAV")
            buffer.seek(0)
            return base64.b64encode(buffer.read()).decode("utf-8")
        except Exception as e:
            print(f"TTS error: {e}")
            return None
