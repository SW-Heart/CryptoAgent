
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for psycopg2)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for cache
COPY back/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY back /app/back

# Set PYTHONPATH
ENV PYTHONPATH=/app/back
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["fastapi", "run", "back/main.py", "--port", "8000", "--host", "0.0.0.0"]
