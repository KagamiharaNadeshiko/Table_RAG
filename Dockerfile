# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# System dependencies for building/science libs and MySQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ pkg-config \
    default-libmysqlclient-dev libssl-dev \
    libopenblas-dev \
    curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install -U pip setuptools wheel && \
    pip install -r requirements.txt

# Copy project
COPY . .

# Expose FastAPI and Flask ports
EXPOSE 8000 5000

# Default LLM endpoint (overridabble at runtime)
ENV OLLAMA_BASE_URL=http://ollama:11434

# Start both services via orchestrator
CMD ["python", "start_services.py"]


