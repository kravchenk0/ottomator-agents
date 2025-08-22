# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
# Improve pip reliability in CI/builds
ENV PIP_DEFAULT_TIMEOUT=60
ENV PIP_RETRIES=10

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash lightrag && \
    chown -R lightrag:lightrag /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip --retries ${PIP_RETRIES} --default-timeout ${PIP_DEFAULT_TIMEOUT} && \
    pip install --no-cache-dir -r requirements.txt --retries ${PIP_RETRIES} --default-timeout ${PIP_DEFAULT_TIMEOUT}

# Copy application code (исключаем секреты и ненужные файлы)
COPY app/ ./app/
COPY tools/ ./tools/
COPY config.yaml ./
COPY start_api.sh ./

# Create necessary directories
RUN mkdir -p /app/documents /app/logs && \
    chown -R lightrag:lightrag /app

# Switch to non-root user
USER lightrag

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - правильный путь к модулю с оптимизациями
CMD ["uvicorn", "app.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "uvloop", "--access-log"] 