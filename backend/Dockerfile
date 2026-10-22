# backend/Dockerfile
# Official Playwright Python image based on Ubuntu 22.04 (Jammy)
# Pre-packaged with all required OS dependencies, fonts, and Chromium for Playwright 1.51.0
FROM mcr.microsoft.com/playwright/python:v1.51.0-jammy

# Prevent Python from writing .pyc files and enable unbuffered output for real-time logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy backend requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python application dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create persistent storage directories for SQLite and screenshot evidence
RUN mkdir -p /app/data /app/evidence

# Copy backend application source code
COPY . .

# Expose internal FastAPI port
EXPOSE 8000

# Health check to ensure service readiness
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; resp = httpx.get('http://127.0.0.1:8000/health', timeout=3.0); exit(0 if resp.status_code == 200 else 1)"

# Start Uvicorn bound to 0.0.0.0 inside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
