FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY pyproject.toml uv.lock ./
RUN pip install --upgrade pip && \
    pip install uv && \
    uv pip install --system -e ".[browser,dev]"

# Copy source
COPY . .

# Create data directory
RUN mkdir -p data/logs data/raw

# Set environment
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["radar", "run"]
