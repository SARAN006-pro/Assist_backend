# ARIA Backend API

FastAPI-based backend for the ARIA (Autonomous Resource & Intelligence Assistant) platform. Deployed on Railway with Redis session storage.

## Features

- **FastAPI** for modern async API development
- **JWT Authentication** with secure token management
- **WebSocket Support** for real-time chat streaming
- **Redis Sessions** for multi-user support
- **Rate Limiting** and security headers
- **CORS** configured for production deployments
- **Admin Tools** - file management, system monitoring, process control, Docker integration
- **Groq AI Integration** for LLM capabilities

## Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- Redis running locally (`redis://localhost:6379`)
- Groq API key

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys and settings

# Run development server
uvicorn main:app --reload
```

Access the API at `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`

## Environment Variables

**Required for all environments:**
- `GROQ_API_KEY` - Your Groq API key from https://console.groq.com
- `SECRET_KEY` - Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `REDIS_URL` - Redis connection string

**Production-specific:**
- `APP_ENV=production`
- `CORS_ORIGINS=["https://your-frontend-domain"]`
- `LOG_LEVEL=WARNING`

See `.env.example` for all available options.

## Railway Deployment

### Prerequisites
- GitHub repository connected to Railway
- Railway Redis add-on attached

### Deploy Steps

1. **Connect Repository**
   - Go to https://railway.app/dashboard
   - Create new project → Deploy from GitHub
   - Select `SARAN006-pro/Assist_backend`
   - Enable auto-deploy from `main` branch

2. **Add Redis Add-on**
   - In Railway project → Plugins → Add Redis
   - Redis URL will be auto-injected as `REDIS_URL`

3. **Set Environment Variables** (in Railway Dashboard)
   ```
   APP_ENV=production
   GROQ_API_KEY=<your-key>
   SECRET_KEY=<generated-secret>
   CORS_ORIGINS=["https://your-frontend.com"]
   JWT_EXPIRE_MINUTES=10080
   LOG_LEVEL=INFO
   ```

4. **Deploy**
   - Railway auto-builds and deploys from `Dockerfile`
   - Check logs in Railway dashboard
   - Your API will be available at `https://<railway-domain>.railway.app`

### Health Check
```bash
curl https://<railway-domain>.railway.app/health
```

## API Endpoints

### Authentication
- `POST /auth/register` - Create new user
- `POST /auth/login` - Get JWT token
- `POST /auth/anonymous` - Anonymous session

### Chat
- `POST /chat/sessions` - Create chat session
- `GET /chat/sessions/{id}/history` - Get message history
- `DELETE /chat/sessions/{id}` - Delete session
- `WS /chat/ws/chat/{id}?token=<jwt>` - WebSocket streaming chat

### System
- `GET /system/metrics` - CPU, RAM, disk stats
- `GET /system/processes` - Top processes
- `WS /system/ws/system/live` - Live metrics stream

### Files
- `POST /files/upload` - Upload file
- `GET /files/list?path=/` - List directory
- `POST /files/read` - Read file content
- `POST /files/write` - Write file

### Voice
- `POST /voice/transcribe` - Audio to text
- `GET /voice/speak?text=...` - Text to speech

## Development

### Run Tests
```bash
pytest tests/ -v
```

### Code Quality
```bash
black .
ruff check .
```

### Docker Local Build
```bash
docker build -t aria-backend:latest .
docker run -e GROQ_API_KEY=xxx -e REDIS_URL=redis://localhost:6379 -p 8000:8000 aria-backend:latest
```

## Troubleshooting

### `redis: connection refused`
- Ensure Redis is running (`redis-cli ping`)
- Or use a managed Redis (Railway add-on)

### `GROQ_API_KEY not found`
- Set the environment variable before starting
- Check `.env` file in development

### WebSocket connection fails in production
- Ensure CORS_ORIGINS includes your frontend domain
- Railway supports WebSockets by default

## Security Notes

- Change `SECRET_KEY` in production (Railway env vars)
- Use HTTPS/WSS in production (Railway handles this)
- Keep `GROQ_API_KEY` secret (never commit to git)
- Rate limiting is enabled by default
- Security headers are enforced in production

## License

Proprietary - ARIA Backend
