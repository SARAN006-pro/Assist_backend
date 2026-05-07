# Voice STT service - requires whisper package
# Will be lazy-loaded to avoid import errors if not installed


class STTService:
    def __init__(self, model_name: str = "base"):
        self.model = None
        self.model_name = model_name

    def load(self):
        """Load Whisper model."""
        if self.model is None:
            try:
                import whisper
                self.model = whisper.load_model(self.model_name)
            except ImportError:
                raise ImportError("Whisper not installed. Run: pip install openai-whisper")

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes to text."""
        self.load()

        import tempfile
        import os

        # Write audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            import whisper
            result = self.model.transcribe(temp_path)
            return result["text"].strip()
        except Exception as e:
            return f"Transcription error: {str(e)}"
        finally:
            os.unlink(temp_path)