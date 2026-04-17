# Deployment Information

## Public URL
https://my-agent-railway-production.up.railway.app

## Platform
Railway

## Test Commands

### Health Check
```bash
curl https://my-agent-railway-production.up.railway.app/health
# Expected: {"status": "ok", "uptime_seconds": ...}
```

### Readiness Check
```bash
curl https://my-agent-railway-production.up.railway.app/ready
# Expected: {"status": "ready", "ready": true, ...}
```

### API Test (with authentication)
```bash
curl -X POST https://my-agent-railway-production.up.railway.app/ask \
  -H "X-API-Key: my-secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello, how are you today?"}'
```

## Environment Variables Set
- `PORT`: 8000
- `REDIS_URL`: redis://redis:6379/0
- `AGENT_API_KEY`: my-secret-key-123
- `LOG_LEVEL`: info
- `ENVIRONMENT`: production

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
