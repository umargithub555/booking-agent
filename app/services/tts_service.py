import os
import io
import base64
import soundfile as sf

# ── Module-level singleton ────────────────────────────────────────────────────
# Ensures Kokoro is loaded ONCE per Python process, regardless of how many
# TTSService objects are created or which uvicorn worker handles the request.
_kokoro_instance = None
_kokoro_init_attempted = False


def _load_kokoro(model_path: str, voices_path: str):
    """Load Kokoro into the module-level singleton (idempotent)."""
    global _kokoro_instance, _kokoro_init_attempted
    if _kokoro_init_attempted:
        return  # Already tried – skip silently

    _kokoro_init_attempted = True
    try:
        from kokoro_onnx import Kokoro  # type: ignore
        if os.path.exists(model_path) and os.path.exists(voices_path):
            _kokoro_instance = Kokoro(model_path, voices_path)
            print("✓ Kokoro TTS loaded.")
        else:
            print(
                f"⚠ Kokoro model files not found:\n"
                f"  {model_path}\n"
                f"  {voices_path}"
            )
    except ImportError:
        print("⚠ kokoro-onnx not installed – TTS disabled.")


class TTSService:
    def __init__(
        self,
        model_path: str = "models/kokoro-v1.0.onnx",
        voices_path: str = "models/voices-v1.0.bin",
    ):
        self.model_path = model_path
        self.voices_path = voices_path
        # Attempt eager initialisation so startup logs are predictable.
        _load_kokoro(model_path, voices_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_audio_base64(self, text: str, voice: str = "af_heart") -> str | None:
        """Generate audio for *text* and return a base64-encoded WAV string.

        Returns ``None`` if Kokoro is unavailable or TTS fails.
        """
        if _kokoro_instance is None:
            return None
        try:
            samples, sample_rate = _kokoro_instance.create(
                text, voice=voice, speed=1.0, lang="en-us"
            )
            buf = io.BytesIO()
            sf.write(buf, samples, sample_rate, format="WAV")
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("utf-8")
        except Exception as exc:
            print(f"TTS error: {exc}")
            return None
