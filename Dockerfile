# Dockerfile for the Service Booking Agent

# ---------- Stage 1: Build the React frontend ----------
FROM node:18-bullseye-slim AS frontend-builder

WORKDIR /frontend

# Install dependencies and build static assets
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Build the Python runtime image ----------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    FIREBASE_SERVICE_ACCOUNT=/app/credentials/firebase-service-account.json.json

WORKDIR /app

# Install system dependencies required for builds and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Copy the freshly built React assets from the frontend stage
COPY --from=frontend-builder /frontend/build ./frontend/build

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port used by Gunicorn/Flask
EXPOSE 8080

# Health check against the API endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["sh", "-c", "curl -f http://localhost:${PORT:-8080}/api/health || exit 1"]

# Start the application with Gunicorn
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 120 app:app"]
