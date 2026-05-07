# Railway Deployment Guide for ARIA Backend

This guide provides step-by-step instructions to deploy the ARIA FastAPI backend to Railway.

## Prerequisites

- GitHub account with [SARAN006-pro/Assist_backend](https://github.com/SARAN006-pro/Assist_backend) repository access
- Railway account at [railway.app](https://railway.app)
- Groq API key from [console.groq.com](https://console.groq.com)
- Generated SECRET_KEY (production)

## Step 1: Generate Required Secrets

### Generate a Strong SECRET_KEY

Run this command and save the output:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Example output:
```
abcdef1234567890abcdef1234567890ABCDEFGH_ijklmnop
```

### Get Groq API Key

1. Go to [https://console.groq.com](https://console.groq.com)
2. Sign in or create an account
3. Navigate to API Keys section
4. Create a new API key
5. Copy and save it

## Step 2: Create Railway Project

1. Go to [https://railway.app/dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy from GitHub"** option
4. Authorize Railway to access your GitHub account
5. Select repository: `SARAN006-pro/Assist_backend`
6. Select branch: `main`
7. Railway will auto-detect the Dockerfile and create a service

## Step 3: Add Redis Add-on

Redis is **CRITICAL** - the application cannot start without it.

1. In your Railway project dashboard
2. Click **"+ Add"** or **"Add Plugin"**
3. Select **"Redis"** from available plugins
4. Click **"Create"**
5. Railway automatically injects `REDIS_URL` environment variable

## Step 4: Configure Environment Variables

Railway dashboard automatically injects:
- `REDIS_URL` (from Redis add-on)
- `PORT` (injected by Railway, default 8000)

You must manually add:

| Variable | Value | Notes |
|----------|-------|-------|
| `APP_ENV` | `production` | Enables security checks |
| `GROQ_API_KEY` | `<your-key>` | From step 1.2 |
| `SECRET_KEY` | `<generated-key>` | From step 1.1 |
| `CORS_ORIGINS` | `["https://your-frontend.railway.app"]` | Include your frontend domain |
| `JWT_EXPIRE_MINUTES` | `10080` | 7 days in minutes |
| `LOG_LEVEL` | `INFO` | Change to `DEBUG` for troubleshooting |

### To Set Variables in Railway:

1. In project dashboard, click the **"Backend"** service
2. Click **"Variables"** tab
3. Click **"Add Variable"**
4. Enter each variable name and value from the table above
5. Click **"Save"**

Example `CORS_ORIGINS` value (single line):
```json
["https://your-frontend-domain.railway.app", "http://localhost:3000"]
```

### Security Notes:

- `APP_ENV=production` enables strict validation:
  - `SECRET_KEY` cannot be the default value
  - `CORS_ORIGINS` cannot include `localhost` or `http://`
  - Redis connection is mandatory (fail-fast if unavailable)
  
- Never use `CORS_ORIGINS: ["*"]` in production
- If your frontend is on Railway, get its public URL from Railway dashboard

## Step 5: Trigger Initial Deploy

Once all variables are configured:

1. Railway should auto-deploy after variable changes
2. Check deployment status in the **"Logs"** tab
3. Wait for build to complete (2-3 minutes typically)
4. Watch for "Build Complete" and service health checks

## Step 6: Verify Deployment

Once the service shows as **"Healthy"**:

### Get Your API URL

1. In Railway dashboard, click the **"Backend"** service
2. Find **"Public URL"** (looks like: `https://aria-backend-production.railway.app`)
3. Copy this URL

### Test Health Endpoint

```bash
curl https://your-railway-url/health

# Response (success):
{
  "status": "online",
  "service": "ARIA Backend",
  "redis": "connected",
  "model": "llama-3.1-70b-versatile",
  "version": "1.0.0",
  "environment": "production"
}
```

### Test API Documentation

Open in browser:
```
https://your-railway-url/docs
```

This shows interactive API documentation (Swagger UI).

## Step 7: Obtain Authentication Token

### For Testing via API

Use the anonymous endpoint to get started (no login required):

```bash
BACKEND_URL="https://your-railway-url"

# Create anonymous session
curl -X POST "$BACKEND_URL/auth/anonymous" \
  -H "Content-Type: application/json"

# Response:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Save the `token` for use in chat endpoints.

### Chat Example

```bash
BACKEND_URL="https://your-railway-url"
TOKEN="<token-from-above>"
SESSION_ID="<session-id-from-above>"

# Test chat via WebSocket (requires WebSocket client)
# Or use the interactive API docs at /docs

# Via REST (simpler for initial test):
# The API has WebSocket-only chat - test via /docs UI
```

## Step 8: Connect Your Frontend

Update your frontend to use the Railway backend URL:

```javascript
// Frontend code
const BACKEND_URL = "https://your-railway-url";

// For WebSocket chat
const ws = new WebSocket(
  `wss://your-railway-url/chat/ws/chat/${sessionId}?token=${token}`
);
```

### CORS Configuration

If your frontend is on a different domain, ensure it's in `CORS_ORIGINS`:

1. Get your frontend Railway URL (or deployed domain)
2. Update `CORS_ORIGINS` in Railway backend variables
3. Redeploy (happens automatically when variables change)

## Troubleshooting

### 502 Bad Gateway / Service Unavailable

**Cause**: Application failed to start

**Solution**:
1. Check **Logs** tab for errors
2. Most common: Missing GROQ_API_KEY or SECRET_KEY
3. Or Redis add-on not attached
4. Add missing variables and redeploy

```
# In logs, look for:
"ERROR: GROQ_API_KEY not configured"
"redis: connection refused"
```

### Redis Connection Failed

**Cause**: Redis add-on not attached

**Solution**:
1. In Railway project, click **"+ Add"**
2. Select **"Redis"** plugin
3. Wait for Redis to become healthy (shows as "Running")
4. Redeploy backend service

### CORS Errors in Frontend

**Symptom**: Browser console shows CORS error when calling API

**Solution**:
1. Add your frontend URL to `CORS_ORIGINS` variable
2. Format: `["https://your-domain.com"]`
3. If multiple origins: `["https://domain1.com", "https://domain2.com"]`
4. Redeploy backend

### App Works Locally but Not on Railway

**Common Issues**:
- Missing GROQ_API_KEY (set in Railway variables)
- Redis not attached (see "Redis Connection Failed" above)
- CORS_ORIGINS pointing to localhost (change to production domain)
- SECRET_KEY using default value (generate new key)

### View Real-time Logs

In Railway dashboard:
1. Click **"Backend"** service
2. Click **"Logs"** tab
3. Logs stream in real-time
4. Search by message or filter by level

## Performance & Monitoring

### Check Service Health

Railway dashboard shows:
- **CPU Usage**: Should be <50% at rest
- **Memory Usage**: Typically 100-200MB
- **Status**: Should show "Running"

### Enable Debug Logging

For troubleshooting, temporarily set:
```
LOG_LEVEL=DEBUG
```

Then redeploy and check logs.

### Monitor Rate Limiting

Default: 100 requests per 60 seconds per IP

If you hit rate limits, increase in Railway variables:
```
RATE_LIMIT_REQUESTS=200
RATE_LIMIT_WINDOW_SECONDS=60
```

## Scaling

### Increase Resources

Railway scales automatically. To manually increase:

1. Click **"Backend"** service
2. Click **"Settings"**
3. Adjust **"Memory"** or **"vCPU"** (if using paid plan)
4. Redeploy

### Add More Replicas

For high availability (requires Railway paid plan):
1. In service settings, increase **"Instances"** to 2 or more
2. Railway load-balances across replicas

## Updating the Backend

### Automatic Deployment

Railway auto-deploys when you push to `main` branch:

```bash
# In your local Assist_backend repo
git add .
git commit -m "feat: add new endpoint"
git push origin main

# Railway automatically builds and deploys within 1-2 minutes
# Watch deployment progress in Railway dashboard
```

### Check Deployment Status

After pushing:
1. Go to Railway dashboard
2. Click **"Backend"** service  
3. Look for new build in the deployments list
4. Status: "Building" → "Deploying" → "Running"

## Rollback

To revert to a previous version:

1. In Railway dashboard, click **"Backend"**
2. Click **"Deployments"** tab
3. Find the previous successful deployment
4. Click the three-dot menu next to it
5. Select **"Rollback"**

## Cleanup

### Delete Service

To completely remove from Railway:

1. Click **"Backend"** service
2. Click **"Settings"**
3. Scroll to bottom
4. Click **"Delete Service"** (this keeps your code in GitHub)

### Delete Redis

To remove Redis add-on:

1. In project, find **"Redis"** plugin
2. Click three-dot menu
3. Select **"Remove"**

**Warning**: Deleting Redis will clear all chat session history.

## Next Steps

- [API Documentation](https://your-railway-url/docs) - Interactive Swagger UI
- [Frontend Integration Guide](../frontend-integration.md) - Connect your frontend
- [Monitoring & Alerts](https://railway.app/docs/reference/observability) - Set up alerts

## Support

For issues:

1. Check [Railway Documentation](https://railway.app/docs)
2. Review logs in Railway dashboard
3. Check [Groq API Status](https://status.groq.com)
4. Check GitHub repository issues

## Summary

Your ARIA Backend is now deployed on Railway with:

✅ Auto-scaling FastAPI service  
✅ Redis session persistence  
✅ Groq AI LLM integration  
✅ JWT authentication  
✅ WebSocket support  
✅ System monitoring tools  
✅ File management capabilities  
✅ Web search integration  

**API URL**: `https://your-railway-url`  
**Docs**: `https://your-railway-url/docs`  
**Health Check**: `https://your-railway-url/health`
