FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt-get/lists/*

# Copy requirements and install python packages
COPY backend/api/requirements.txt /app/backend/api/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/api/requirements.txt

# Copy backend application code
COPY backend /app/backend
COPY services /app/services

ENV PYTHONPATH=/app:/app/services:/app/services/gis/src:/app/services/audio/src:/app/services/dispatch_notifications/src

EXPOSE 8000

CMD ["python", "-m", "backend.api.server"]
