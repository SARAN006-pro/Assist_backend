import base64
import io
import re


class TTSService:
    def __init__(self):
        self.engine = None

    def _get_engine(self):
        """Get pyttsx3 engine, lazy loading."""
        if self.engine is None:
            try:
                import pyttsx3
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', 150)
                self.engine.setProperty('volume', 0.9)
            except ImportError:
                raise ImportError("pyttsx3 not installed. Run: pip install pyttsx3")
        return self.engine

    def _clean_text(self, text: str) -> str:
        """Clean text for TTS - remove code blocks and file paths."""
        # Remove code blocks
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`[^`]+`', '', text)
        # Remove file paths
        text = re.sub(r'/[\w/.-]+', '', text)
        # Keep sentences under 100 chars
        sentences = text.split('.')
        cleaned = []
        for sent in sentences:
            if len(sent) > 100:
                sent = sent[:97] + "..."
            cleaned.append(sent)
        return '.'.join(cleaned)

    async def speak(self, text: str) -> bytes:
        """Speak text and return audio bytes."""
        cleaned = self._clean_text(text)
        engine = self._get_engine()

        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        engine.save_to_file(cleaned, temp_path)
        engine.runAndWait()

        with open(temp_path, "rb") as f:
            audio_bytes = f.read()

        os.unlink(temp_path)
        return audio_bytes

    async def get_audio(self, text: str) -> str:
        """Get base64 encoded audio for sending to Flutter."""
        audio_bytes = await self.speak(text)
        return base64.b64encode(audio_bytes).decode("utf-8")