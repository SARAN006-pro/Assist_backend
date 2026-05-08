"""app/routers/chat.py — Chat endpoint. Every failure returns structured error, never raw 500."""
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from app.core.config import settings

logger = logging.getLogger("aria.chat")
router = APIRouter(prefix="/api", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    context: Optional[list] = None

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message cannot be blank")
        return v.strip()


class ChatResponse(BaseModel):
    reply: str
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    model: Optional[str] = None


async def _ai_call(message: str) -> str:
    """Call AI provider. Falls back to echo if no key is configured."""

    if settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.AI_MODEL,
                    messages=[{"role": "user", "content": message}],
                    max_tokens=1024,
                ),
                timeout=settings.AI_TIMEOUT,
            )
            return resp.choices[0].message.content or ""
        except asyncio.TimeoutError:
            raise HTTPException(504, f"AI timed out after {settings.AI_TIMEOUT}s")
        except Exception as e:
            logger.error("OpenAI error: %s", e, exc_info=True)
            raise HTTPException(502, f"AI error: {type(e).__name__}")

    if settings.ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            resp = await asyncio.wait_for(
                client.messages.create(
                    model=settings.AI_MODEL or "claude-3-haiku-20240307",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": message}],
                ),
                timeout=settings.AI_TIMEOUT,
            )
            return resp.content[0].text
        except asyncio.TimeoutError:
            raise HTTPException(504, f"AI timed out after {settings.AI_TIMEOUT}s")
        except Exception as e:
            logger.error("Anthropic error: %s", e, exc_info=True)
            raise HTTPException(502, f"AI error: {type(e).__name__}")

    # No key configured — return echo so app stays functional
    logger.warning("No AI key configured, returning echo")
    return f"[ARIA Echo — set OPENAI_API_KEY in Railway] {message}"


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request):
    rid = getattr(request.state, "request_id", "no-id")
    logger.info("chat | id=%s len=%d", rid, len(body.message))
    try:
        reply = await _ai_call(body.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("chat unexpected | id=%s %s", rid, e, exc_info=True)
        raise HTTPException(500, f"Unexpected: {type(e).__name__}")
    return ChatResponse(reply=reply, session_id=body.session_id,
                        request_id=rid, model=settings.AI_MODEL)