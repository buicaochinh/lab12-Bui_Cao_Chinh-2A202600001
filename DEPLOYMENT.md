# Deployment Information

## Public URL
https://lab12-buicaochinh-2a202600001-production.up.railway.app

## Platform
Railway

## Test Commands

### Health Check
```bash
curl https://lab12-buicaochinh-2a202600001-production.up.railway.app/health
# Expected: {"status": "ok", "uptime_seconds": ...}
```

### Readiness Check
```bash
curl https://lab12-buicaochinh-2a202600001-production.up.railway.app/ready
# Expected: {"status": "ready"}
```

### API Test (with authentication)
```bash
curl -X POST https://lab12-buicaochinh-2a202600001-production.up.railway.app/ask \
  -H "X-API-Key: this-is-api-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "question": "Hello, how are you today?"}'
```

## Environment Variables Set
- `PORT`: 8000
- `REDIS_URL`: redis://redis:6379/0
- `AGENT_API_KEY`: this-is-api-key
- `LOG_LEVEL`: INFO
- `ENVIRONMENT`: production

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.jpg)
- [Test results](screenshots/test_result.jpg)
