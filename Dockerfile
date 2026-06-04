FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy slim production requirements (excludes chromadb/sentence-transformers to stay under 512MB)
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy source code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY pyproject.toml .

# Create data directory for ChromaDB and SQLite
RUN mkdir -p data/chroma_db

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Run the webhook server
CMD ["python", "-m", "uvicorn", "src.webhook.app:app", "--host", "0.0.0.0", "--port", "8000"]
