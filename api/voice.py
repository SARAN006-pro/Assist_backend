from fastapi import APIRouter, UploadFile, File, Query, Response
from voice.stt import STTService
from voice.tts import TTSService

router = APIRouter()
stt_service = STTService()
tts_service = TTSService()


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe uploaded audio file."""
    audio_bytes = await file.read()
    text = await stt_service.transcribe(audio_bytes)
    return {"text": text}


@router.get("/speak")
async def speak(text: str = Query(...)):
    """Get TTS audio for text."""
    audio_b64 = await tts_service.get_audio(text)
    return {"audio": audio_b64}