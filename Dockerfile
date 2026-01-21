# ===========================================
# Stage 1: Build Frontend (React + Vite)
# ===========================================
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

# Copy package files first for better caching
COPY agno-chat-ui/package*.json ./

# Install dependencies
RUN npm ci --silent

# Copy source code
COPY agno-chat-ui/ ./

# Set production API URL (will be same origin, proxied by Nginx)
# Must use ARG + inline env for Vite to pick it up at build time
ARG VITE_API_BASE_URL=""

# Build the React app with empty API URL
RUN VITE_API_BASE_URL="" npm run build


# ===========================================
# Stage 2: Build Backend (Python FastAPI)
# ===========================================
FROM python:3.12.3 AS backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nginx \
    libxml2-dev \
    libxslt1-dev \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for cache
COPY back/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --default-timeout=100

# Copy backend code
COPY back /app/back

# Copy frontend build from stage 1
COPY --from=frontend-build /app/frontend/dist /app/static

# Copy Nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Set environment
ENV PYTHONPATH=/app/back
ENV PYTHONUNBUFFERED=1

# Expose port 80 (Nginx) and 8000 (FastAPI internal)
EXPOSE 80

# Create startup script
RUN echo '#!/bin/bash\n\
    nginx\n\
    exec fastapi run back/main.py --port 8000 --host 0.0.0.0' > /app/start.sh && chmod +x /app/start.sh

# Run both Nginx and FastAPI
CMD ["/app/start.sh"]
