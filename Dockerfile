

FROM python:3.12.3

WORKDIR /app

# Install system dependencies
# Full python image has build utils, but we might still need some specific libs 
# kept minimal here as the base image is robust.
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt1-dev \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for cache
COPY back/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --default-timeout=100

# Copy application code
COPY back /app/back

# Set PYTHONPATH
ENV PYTHONPATH=/app/back
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["fastapi", "run", "back/main.py", "--port", "8000", "--host", "0.0.0.0"]
