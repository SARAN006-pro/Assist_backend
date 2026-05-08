"""app/models/schemas.py — Pydantic request/response models."""
from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    context: Optional[list] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    model: Optional[str] = None