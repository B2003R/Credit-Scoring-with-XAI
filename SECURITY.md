# Security Documentation

## Security Improvements Implemented

This document outlines the security enhancements made to the Credit Scoring with XAI application.

### 🔐 API Security

#### 1. Input Validation
- **Feature Dictionary Size Limit**: Maximum 300 features to prevent DoS attacks
- **Value Validation**: All feature values must be numeric, non-NaN, and non-Infinite
- **Type Checking**: Strict type validation using Pydantic models
- **Empty Input Protection**: Prevents empty feature dictionaries

#### 2. Authentication
- **API Key Authentication**: Optional API key-based authentication via `X-API-Key` header
- **Environment Variable Configuration**: API key stored in environment variable `API_KEY`
- **Development Mode**: Authentication can be disabled by not setting `API_KEY` environment variable

**Usage:**
```bash
# Enable authentication
export API_KEY="your-secure-api-key"

# Make authenticated request
curl -X POST http://localhost:8000/predict \
  -H "X-API-Key: your-secure-api-key" \
  -H "Content-Type: application/json" \
  -d '{"features": {...}}'
```

#### 3. Error Handling
- **Generic Error Messages**: Clients receive generic error messages
- **Detailed Internal Logging**: Full error details logged internally for debugging
- **Structured Logging**: Using Python's logging module with timestamps and levels
- **Audit Trail**: All predictions logged with relevant metadata (without sensitive data)

#### 4. Security Headers
- **CORS Configuration**: Configurable allowed origins via `ALLOWED_ORIGINS` environment variable
- **Method Restrictions**: Only POST and GET methods allowed
- **Credentials Support**: Proper CORS credentials handling

### 🐳 Docker Security

#### 1. Non-Root User
- **Dedicated User**: Application runs as non-root user `appuser` (UID 1000)
- **File Permissions**: All application files owned by `appuser`
- **Privilege Separation**: Reduces attack surface and privilege escalation risks

#### 2. Health Checks
- **Built-in Health Endpoint**: `/health` endpoint for container orchestration
- **Docker Health Check**: Automated health monitoring with curl
- **Configuration**: 30s interval, 10s timeout, 3 retries

#### 3. Minimal Attack Surface
- **Slim Base Image**: Using Python 3.10-slim to reduce image size
- **Minimal Dependencies**: Only required system packages installed
- **Clean Package Cache**: APT cache cleaned to reduce image size

#### 4. Configurable Model Path
- **Build Arguments**: Model artifact path configurable via Docker build arg
- **Environment Variables**: Runtime model path configurable via `MODEL_PATH`

**Usage:**
```bash
# Build with custom model path
docker build --build-arg MODEL_ARTIFACT_PATH=path/to/model -t credit-api .

# Run with environment variables
docker run -e API_KEY="secret" -e MODEL_PATH="/app/model" -p 8000:8000 credit-api
```

### 📦 Dependency Management

#### 1. Version Pinning
- **All Dependencies Pinned**: Version ranges specified for all dependencies
- **Regular Updates**: Dependencies should be reviewed and updated regularly
- **Security Scanning**: Use `pip-audit` or `safety` to scan for vulnerabilities

**Scan for vulnerabilities:**
```bash
pip install pip-audit
pip-audit -r requirements_serving.txt
```

#### 2. Separate Requirement Files
- **requirements.txt**: Training dependencies
- **requirements_serving.txt**: Production serving dependencies (minimal footprint)

### 🔍 Monitoring & Logging

#### 1. Structured Logging
- **Log Levels**: INFO, WARNING, ERROR with appropriate usage
- **Timestamps**: All logs include timestamps
- **Context Information**: Logs include relevant context without sensitive data

#### 2. Health Endpoint
- **Status Check**: `/health` endpoint returns application status
- **Model Validation**: Confirms model and explainer are loaded
- **Integration**: Can be used with monitoring systems (Prometheus, DataDog, etc.)

### 🛡️ Best Practices for Production

#### Required Actions Before Production:

1. **Enable Authentication**
   ```bash
   export API_KEY="$(openssl rand -hex 32)"
   ```

2. **Configure CORS**
   ```bash
   export ALLOWED_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"
   ```

3. **Use HTTPS/TLS**
   - Deploy behind a reverse proxy (nginx, traefik) with TLS
   - Never expose the API directly without HTTPS

4. **Rate Limiting**
   - Implement rate limiting at reverse proxy level
   - Consider using services like Cloudflare, AWS WAF, or nginx rate limiting

5. **Secrets Management**
   - Use secrets management systems (AWS Secrets Manager, HashiCorp Vault)
   - Never commit `.env` files to version control
   - Rotate API keys regularly

6. **Monitoring**
   - Set up log aggregation (ELK Stack, Splunk, CloudWatch)
   - Monitor for unusual access patterns
   - Set up alerts for failed authentication attempts

7. **Regular Security Audits**
   - Run dependency vulnerability scans regularly
   - Perform penetration testing
   - Review access logs

8. **Data Privacy**
   - Ensure GDPR/CCPA compliance for credit data
   - Implement data retention policies
   - Consider data anonymization for logs

#### Recommended Architecture:

```
Internet → [Cloudflare/WAF] → [Load Balancer] → [Reverse Proxy with TLS] → [Credit API Container]
                                                          ↓
                                                    [Monitoring & Logging]
```

### 📋 Security Checklist

#### Pre-Production
- [ ] Enable API key authentication (`API_KEY` environment variable set)
- [ ] Configure CORS with specific allowed origins
- [ ] Set up HTTPS/TLS termination
- [ ] Implement rate limiting
- [ ] Configure log aggregation and monitoring
- [ ] Set up health check monitoring
- [ ] Scan dependencies for vulnerabilities
- [ ] Review and test error handling
- [ ] Document incident response procedures

#### Production Maintenance
- [ ] Regular dependency updates and vulnerability scans
- [ ] Log review and analysis (weekly/monthly)
- [ ] API key rotation (quarterly)
- [ ] Security audit (annually)
- [ ] Backup and disaster recovery testing
- [ ] Performance and capacity monitoring
- [ ] Compliance reviews (GDPR, PCI-DSS if applicable)

### 🚨 Known Limitations

1. **No Built-in Rate Limiting**: Must be implemented at reverse proxy level
2. **Simple API Key Auth**: Consider upgrading to OAuth2/JWT for production
3. **No Request Size Limit**: Should be configured at reverse proxy level
4. **No Model Versioning**: Consider implementing model version tracking
5. **No Adversarial Attack Detection**: Consider adding input anomaly detection

### 📚 Additional Resources

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

### 🔄 Security Updates

This document should be reviewed and updated whenever:
- New security features are added
- Vulnerabilities are discovered and fixed
- Production deployment architecture changes
- Compliance requirements change

---

**Last Updated**: 2024
**Version**: 1.0
