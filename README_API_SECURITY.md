# Credit Scoring API - Security Guide

## Quick Start

### Local Development (No Authentication)

1. **Install dependencies:**
```bash
pip install -r requirements_serving.txt
```

2. **Run the API:**
```bash
python src/models/serving/app.py
```

3. **Make a prediction:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "features": {
      "feature1": 1.0,
      "feature2": 2.5,
      "feature3": -0.3
    }
  }'
```

4. **Check health:**
```bash
curl http://localhost:8000/health
```

### Production Deployment (With Authentication)

1. **Set environment variables:**
```bash
export API_KEY="your-secure-random-key-here"
export ALLOWED_ORIGINS="https://yourdomain.com"
export MODEL_PATH="/app/model_dir"
```

2. **Build Docker image:**
```bash
docker build -t credit-scoring-api .
```

3. **Run container:**
```bash
docker run -d \
  -p 8000:8000 \
  -e API_KEY="your-secure-key" \
  -e ALLOWED_ORIGINS="https://yourdomain.com" \
  --name credit-api \
  credit-scoring-api
```

4. **Make authenticated prediction:**
```bash
curl -X POST https://yourdomain.com/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-key" \
  -d '{
    "features": {
      "feature1": 1.0,
      "feature2": 2.5,
      "feature3": -0.3
    }
  }'
```

## Security Features

### ✅ Input Validation
- Maximum 300 features per request
- All values must be numeric (int/float)
- No NaN or Inf values allowed
- Empty feature dictionaries rejected

### ✅ Authentication (Optional)
- API key via `X-API-Key` header
- Enable by setting `API_KEY` environment variable
- Disabled by default for development

### ✅ Error Handling
- Generic error messages to clients
- Detailed logging internally
- No sensitive information exposed

### ✅ Container Security
- Runs as non-root user
- Health checks enabled
- Minimal base image
- Clean package cache

### ✅ Monitoring
- Health endpoint: `/health`
- Structured logging
- Audit trail for predictions

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | No | None | API key for authentication (disabled if not set) |
| `ALLOWED_ORIGINS` | No | * | Comma-separated list of allowed CORS origins |
| `MODEL_PATH` | No | /app/model_dir | Path to ML model directory |

### Example Configuration

Create a `.env` file (never commit this):
```bash
API_KEY=my-secret-api-key-32-chars-long
ALLOWED_ORIGINS=https://app.example.com,https://dashboard.example.com
MODEL_PATH=/app/model_dir
```

## API Endpoints

### POST /predict
Predict credit risk for a customer.

**Request:**
```json
{
  "features": {
    "feature1": 1.0,
    "feature2": 2.5,
    "feature3": -0.3
  }
}
```

**Response (Success):**
```json
{
  "decision": "APPROVE",
  "risk_score": 0.35,
  "top_risk_factors": [
    ["feature2", 0.15],
    ["feature1", 0.10],
    ["feature3", -0.05]
  ]
}
```

**Response (Error):**
```json
{
  "detail": "Invalid input data"
}
```

### GET /health
Check service health status.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "explainer_loaded": true
}
```

## Testing

### Run Tests
```bash
pip install -r requirements_test.txt
pytest tests/test_api_security.py -v
```

### Validate Docker Security
```bash
./validate_docker_security.sh
```

## Security Best Practices

1. **Always use HTTPS in production**
2. **Enable API key authentication** (`API_KEY` env var)
3. **Configure specific CORS origins** (not `*`)
4. **Implement rate limiting** (at reverse proxy level)
5. **Monitor logs and health endpoint**
6. **Rotate API keys regularly**
7. **Run vulnerability scans** (`pip-audit`, `safety`)
8. **Keep dependencies updated**

## Troubleshooting

### Authentication Issues
- Ensure `X-API-Key` header is set correctly
- Check if `API_KEY` environment variable is configured
- Verify API key matches exactly

### Model Loading Errors
- Check `MODEL_PATH` environment variable
- Ensure model files exist at specified path
- Check file permissions

### Health Check Failures
- Verify model and explainer are loaded
- Check application logs
- Ensure container is running as expected

## More Information

- See `SECURITY.md` for comprehensive security documentation
- See `SECURITY_FIXES_SUMMARY.md` for details on security fixes
- See `tests/test_api_security.py` for usage examples

## Support

For security issues, please refer to `SECURITY.md` for reporting procedures.
