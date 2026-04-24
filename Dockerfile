FROM python:3.11-slim

LABEL maintainer="SMF Works <michael@smfworks.com>"
LABEL org.opencontainers.image.source="https://github.com/smfworks/smf-swarm"
LABEL org.opencontainers.image.description="SMF Swarm — Agent-powered predictive analysis pipeline"

# Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install package
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Create config and output directories
RUN mkdir -p /root/.config/smf-swarm /root/smf-swarm/output /root/smf-swarm/memory

# Default port for the web UI
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import smf_swarm; print('OK')" || exit 1

ENTRYPOINT ["smf-swarm"]
CMD ["web", "--host", "0.0.0.0", "--port", "8080"]
