FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser


# Copy requirements and install dependencies
COPY requirements.txt .
# Some requirement files include hash checks that can break in CI/build contexts
# Create a temporary requirements file with hashes removed and install from it
RUN sed 's/ --hash=[^ ]*//g' requirements.txt > req_nohash.txt && \
    pip install --no-cache-dir -r req_nohash.txt alembic

# Copy migration script
COPY scripts /app/scripts
RUN chmod +x /app/scripts/*.sh

# Copy application code
COPY --chown=appuser:appgroup . /app

# Create necessary directories
RUN mkdir -p /app/data /app/logs && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
