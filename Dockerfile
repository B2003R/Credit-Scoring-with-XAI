# Use a lightweight Python base
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for LightGBM compilation sometimes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy requirements (Create a serving-specific requirements.txt first!)
COPY requirements_serving.txt .
RUN pip install --no-cache-dir -r requirements_serving.txt

# Copy the app code
COPY src/models/serving/app.py src/models/serving/app.py

# CRITICAL: Copy the MLflow data (Database + Artifacts)
# In production, you'd use a remote S3 bucket, but for local POC, we copy files.
# Use build arg to make model path configurable
ARG MODEL_ARTIFACT_PATH=mlruns/1/models/m-fdbdff88c508418cb934d65500714941/artifacts
COPY ${MODEL_ARTIFACT_PATH} /app/model_dir

# Change ownership of copied files to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the API port
EXPOSE 8000

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

# Run the app
CMD ["python", "src/models/serving/app.py"]