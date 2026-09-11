FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for ReportLab & PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy full application code
COPY . /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV REQUIRE_USER_KEY_OR_PROMO=False

EXPOSE 8080

# Launch Uvicorn server for production
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
