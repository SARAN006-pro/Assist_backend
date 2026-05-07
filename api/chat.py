from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from typing import Optional
import uuid
import logging
import asyncio
import time
from jose import JWTError, jwt
from core.orchestrator import Orchestrator
from core.session import session_manager
from config import settings

router = APIRouter()
orchestrator = Orchestrator()
logger = logging.getLogger("aria")


class CreateSessionRequest(BaseModel):
    email: str


class ChatMessage(BaseModel):
    message: str
    voice_mode: bool = False


def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token and return payload. Returns None for invalid tokens."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


@router.post("/sessions")
async def create_session(request: CreateSessionRequest):
    """Create a new chat session."""
    session_id = await session_manager.create(request.email)
    logger.info(f"Created session {session_id} for {request.email}")
    return {"session_id": session_id, "email": request.email}


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str):
    """Get message history for a session."""
    history = await session_manager.get_history(session_id)
    return {"session_id": session_id, "history": history}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    await session_manager.delete(session_id)
    logger.info(f"Deleted session {session_id}")
    return {"status": "deleted", "session_id": session_id}


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None)
):
    """WebSocket endpoint for streaming chat."""
    logger.info(f"WebSocket connection attempt for session {session_id}")

    email = "anonymous@aria.local"

    if token:
        payload = verify_token(token)
        if payload:
            email = payload.get("email", "anonymous@aria.local")
            logger.info(f"Authenticated WebSocket for {email}")
        else:
            logger.warning(f"Invalid token provided, using anonymous")

    await websocket.accept()
    logger.info(f"WebSocket connected for session {session_id}")

    # Send initial ready signal so Flutter stops showing "Connecting..."
    try:
        await websocket.send_json({"type": "connected", "session_id": session_id})
    except Exception:
        pass

    last_ping = time.time()
    PING_INTERVAL = 30  # seconds

    try:
        while True:
            # Non-blocking receive with timeout for heartbeat
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=PING_INTERVAL)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive on Railway (30s idle timeout)
                try:
                    await websocket.send_json({"type": "ping", "ts": time.time()})
                    logger.debug("WS ping sent | session=%s", session_id)
                except Exception:
                    logger.info("WS ping failed — client gone | session=%s", session_id)
                    break
                continue

            msg_type = data.get("type", "message")

            # Handle pong from client
            if msg_type == "pong":
                last_ping = time.time()
                continue

            # Handle chat message
            if msg_type == "message":
                user_message = data.get("message", "")
                voice_mode = data.get("voice_mode", False)

                logger.info(f"Received message from {email}: {user_message[:50]}...")

                # Send thinking indicator
                try:
                    await websocket.send_json({"type": "tool_start", "tool": "ai"})
                except Exception:
                    pass

                try:
                    # AI call with timeout (30s max)
                    async for chunk in orchestrator.stream(user_message, session_id, voice_mode):
                        await websocket.send_text(chunk)
                except asyncio.TimeoutError:
                    logger.error("AI API timed out | session=%s", session_id)
                    await websocket.send_json({
                        "type": "error",
                        "content": "AI service timed out. Please retry."
                    })
                except Exception as e:
                    logger.error("AI streaming error | session=%s | %s", session_id, e)
                    await websocket.send_json({
                        "type": "error",
                        "content": "AI service unavailable. Please retry."
                    })

            else:
                await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)  # Internal error
        except Exception:
            pass
    finally:
        logger.info(f"WS cleanup done | session={session_id}")