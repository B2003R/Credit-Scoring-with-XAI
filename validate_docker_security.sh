#!/bin/bash
# Docker Security Validation Script

echo "=== Docker Security Validation ==="
echo ""

# Check 1: Non-root user
echo "[✓] Check 1: Non-root user configuration"
if grep -q "USER appuser" Dockerfile; then
    echo "    PASS: Container runs as non-root user"
else
    echo "    FAIL: Container running as root"
    exit 1
fi

# Check 2: Health check
echo "[✓] Check 2: Health check configuration"
if grep -q "HEALTHCHECK" Dockerfile; then
    echo "    PASS: Health check configured"
else
    echo "    FAIL: No health check configured"
    exit 1
fi

# Check 3: Minimal base image
echo "[✓] Check 3: Minimal base image"
if grep -q "python:3.10-slim" Dockerfile; then
    echo "    PASS: Using slim Python image"
else
    echo "    WARN: Not using slim base image"
fi

# Check 4: Clean package cache
echo "[✓] Check 4: Package cache cleanup"
if grep -q "rm -rf /var/lib/apt/lists" Dockerfile; then
    echo "    PASS: APT cache cleaned"
else
    echo "    WARN: APT cache not cleaned"
fi

# Check 5: Build arg for model path
echo "[✓] Check 5: Configurable model path"
if grep -q "ARG MODEL_ARTIFACT_PATH" Dockerfile; then
    echo "    PASS: Model path is configurable"
else
    echo "    WARN: Model path is hardcoded"
fi

# Check 6: File ownership
echo "[✓] Check 6: File ownership"
if grep -q "chown -R appuser:appuser" Dockerfile; then
    echo "    PASS: Files owned by non-root user"
else
    echo "    WARN: File ownership not set"
fi

echo ""
echo "=== Docker Security Validation Complete ==="
echo "All critical security checks passed!"
