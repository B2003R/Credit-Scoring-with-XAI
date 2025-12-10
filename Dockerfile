# Use a lightweight Python base
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for LightGBM compilation sometimes)
RUN apt-get update && apt-get install -y libgomp1

# Copy requirements (Create a serving-specific requirements.txt first!)
COPY requirements_serving.txt .
RUN pip install --no-cache-dir -r requirements_serving.txt

# Copy the app code
COPY src/models/serving/app.py src/models/serving/app.py
# CRITICAL: Copy the MLflow data (Database + Artifacts)
# In production, you'd use a remote S3 bucket, but for local POC, we copy files.
COPY mlruns/1/models/m-fdbdff88c508418cb934d65500714941/artifacts /app/model_dir
# (Note: Check where your artifacts are stored. If in 'mlruns' folder, copy that.)

# Expose the API port
EXPOSE 8000

# Run the app
CMD ["python", "src/models/serving/app.py"]