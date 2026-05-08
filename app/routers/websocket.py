"""app/routers/websocket.py — WebSocket with heartbeat, disconnect safety, and ping/pong."""
import asyncio
import json
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.routers.chat import _ai_call

logger = logging.getLogger("aria.ws")
router = APIRouter()
_sessions: dict[str, WebSocket] = {}
PING_EVERY = 25   # seconds — must be < Railway's 60s idle timeout
RECV_TIMEOUT = 35 # wait this long before sending a ping


@router.websocket("/ws/chat/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    _sessions[session_id] = websocket
    logger.info("WS connected | session=%s total=%d", session_id, len(_sessions))

    try:
        await _safe_send(websocket, {"type": "connected", "session_id": session_id, "ts": time.time()})
        await _loop(websocket, session_id)
    except WebSocketDisconnect as e:
        logger.info("WS disconnect | session=%s code=%s", session_id, e.code)
    except Exception as e:
        logger.error("WS crash | session=%s %s", session_id, e, exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        _sessions.pop(session_id, None)
        logger.info("WS cleanup | session=%s remaining=%d", session_id, len(_sessions))


async def _loop(ws: WebSocket, sid: str):
    while True:
        try:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=RECV_TIMEOUT)
        except asyncio.TimeoutError:
            try:
                await ws.send_text(json.dumps({"type": "ping", "ts": time.time()}))
            except Exception:
                break
            continue

        try:
            data = json.loads(raw)
        except Exception:
            await _safe_send(ws, {"type": "error", "message": "Invalid JSON"})
            continue

        t = data.get("type", "")
        if t == "ping":
            await _safe_send(ws, {"type": "pong", "ts": time.time()})
        elif t == "pong":
            pass
        elif t == "message":
            content = (data.get("content") or "").strip()
            if not content:
                await _safe_send(ws, {"type": "error", "message": "content required"})
                continue
            await _safe_send(ws, {"type": "processing"})
            try:
                reply = await _ai_call(content)
                await _safe_send(ws, {"type": "reply", "content": reply, "ts": time.time()})
            except Exception as e:
                await _safe_send(ws, {"type": "error", "message": f"AI error: {type(e).__name__}"})
        else:
            await _safe_send(ws, {"type": "error", "message": f"Unknown type: {t}"})


async def _safe_send(ws: WebSocket, data: dict):
    try:
        await ws.send_text(json.dumps(data))
    except Exception as e:
        logger.warning("WS send failed: %s", e)