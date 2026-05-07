# ARIA — Production Reliability Checklist & Deployment Guide

## Root Cause Analysis

### Why it works on WiFi but fails on mobile data

| Symptom | Root Cause |
|---------|------------|
| HTTP 500 | Backend crashes during request processing — unhandled exception |
| Works on WiFi, fails on mobile | Mobile IPs hit Railway cold-start more often; longer RTT exposes timeout bugs |
| "Connecting..." forever | WebSocket never confirmed connected; no state recovery |
| Red error banner with Dio stack trace | `validateStatus` was set to throw on 5xx instead of handling gracefully |

---

## Files Modified

### Backend

| File | Change |
|------|--------|
| `main.py` | Global exception handler, WebSocket lifecycle, Redis graceful failure, /health rich response |
| `middleware.py` | ProductionMiddleware: request-ID tracing, duration logging, catches all unhandled exceptions |
| `requirements.txt` | Pinned versions, added uvicorn[standard] for WebSocket support |
| `Procfile` | Correct PORT binding, workers, timeout-keep-alive |
| `railway.json` | Health check, restart policy |
| `core/session.py` | Redis graceful failure - runs without Redis |
| `api/chat.py` | WebSocket lifecycle, ping/pong heartbeat, AI timeout |
| `core/orchestrator.py` | 30s timeout on AI API calls |

### Flutter

| File | Change |
|------|--------|
| `lib/services/api_service.dart` | Dio timeouts (20s connect, 60s receive), retry interceptor, structured error parsing |
| `lib/services/websocket_service.dart` | Auto-reconnect, exponential backoff, heartbeat ping, message queue |
| `lib/widgets/connection_status_banner.dart` | Real-time connection state UI (replacing silent failures) |
| `lib/features/chat/chat_provider.dart` | Updated to use new production services |
| `android/app/src/main/res/xml/network_security_config.xml` | Enforce HTTPS-only, trust system CAs |
| `android/app/src/main/AndroidManifest.xml` | Add networkSecurityConfig, INTERNET, ACCESS_NETWORK_STATE permissions |

---

## Deployment Verification Steps

### Step 1 — Fix Railway environment variables

Go to Railway Dashboard → your service → Variables. Verify:
```
PORT          = (set by Railway automatically — do NOT hardcode)
REDIS_URL     = redis://... (or leave empty to disable Redis)
GROQ_API_KEY  = your Groq API key
SECRET_KEY    = a secure random string
```

### Step 2 — Verify PORT binding in Procfile

```bash
# ✅ Correct
uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 75

# ❌ Wrong — Railway assigns a random port, not 8000
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Step 3 — Test health endpoint

```bash
curl https://your-app.railway.app/health
# Expected: {"status":"online","redis":"connected" or "disconnected",...}
```

### Step 4 — Test chat endpoint with curl (bypass Flutter)

```bash
curl -X POST https://your-app.railway.app/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"email": "test@aria.local"}'
# Expected: {"session_id":"...","email":"test@aria.local"}
```

### Step 5 — Check Railway logs

In Railway Dashboard → Logs, look for:
- `💥 UNHANDLED EXCEPTION` — exact crash with traceback
- `X-Request-ID` — trace specific failing requests
- Redis errors on startup

### Step 6 — Test on mobile data

1. Disable WiFi on phone
2. Enable mobile data
3. Open ARIA
4. Watch connection banner: Connecting → Connected (should happen within 20s)
5. Send a message
6. Check Railway logs for the request

### Step 7 — Flutter build

```bash
# Android APK
flutter build apk --release

# Windows EXE
flutter build windows --release
```

---

## Production Reliability Checklist

### Backend

- [x] All route handlers wrapped in try/except
- [x] Global exception handler registered
- [x] ProductionMiddleware added to app
- [x] Redis failure handled gracefully (app runs without it)
- [x] AI API call has asyncio.wait_for timeout (30s)
- [x] WebSocket disconnect handled without crash
- [x] PORT binding uses $PORT env var
- [x] /health returns 200 even in degraded mode
- [x] Railway restart policy set to on_failure
- [ ] All env vars set in Railway dashboard

### Flutter

- [x] Dio connectTimeout ≥ 20s (Railway cold start)
- [x] Dio receiveTimeout ≥ 60s (AI streaming responses)
- [x] Retry interceptor active (3 retries, exponential backoff)
- [x] WebSocket uses WSS:// (never WS://)
- [x] WebSocket auto-reconnects on disconnect
- [x] Heartbeat ping every 25s (prevents Railway 30s idle close)
- [x] Connection state shown in UI (no silent failures)
- [x] Messages queued when disconnected and flushed on reconnect
- [x] android:networkSecurityConfig set in manifest
- [x] android:usesCleartextTraffic="false" in manifest
- [ ] API_BASE_URL and WS_BASE_URL set via environment or --dart-define

---

## Common 500 Root Causes — Quick Fix Table

| Error | Fix |
|-------|-----|
| `KeyError: 'REDIS_URL'` | Add REDIS_URL to Railway env vars OR use `os.getenv()` with default |
| `AttributeError: NoneType` | Add null checks before using optional values |
| `Connection refused: redis` | Redis service not running in Railway, or wrong URL |
| `TimeoutError` from AI API | Wrap AI call with `asyncio.wait_for(call, timeout=30)` |
| `WebSocketDisconnect` unhandled | Wrap WS loop in `try/except WebSocketDisconnect` |
| `422 Unprocessable Entity` | Request body field name mismatch — check Pydantic model vs Flutter payload |