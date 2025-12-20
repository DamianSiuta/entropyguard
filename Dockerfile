FROM python:3.10-slim

# Set env vars
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# 1. Install system dependencies (Root)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    git \
 && rm -rf /var/lib/apt/lists/*

# 2. Create user (UID 1000)
RUN useradd -m -u 1000 entropyguard

# 3. Create cache directory with correct permissions
RUN mkdir -p $HF_HOME && chown -R entropyguard:entropyguard /app

# 4. Copy project files AND set ownership immediately (Atomic Copy)
# Copy essential files first
COPY --chown=entropyguard:entropyguard pyproject.toml README.md ./
COPY --chown=entropyguard:entropyguard src ./src
COPY --chown=entropyguard:entropyguard scripts ./scripts

# 5. Install dependencies (Root installs to global site-packages, readable by all)
RUN pip install --upgrade pip && \
    pip install .

# 6. Verify entrypoint exists and is executable
RUN ls -la /app/scripts/ci_entrypoint.py && \
    chmod +x /app/scripts/ci_entrypoint.py

# 7. Switch to non-root user
USER entropyguard

# 8. Entrypoint (use absolute path)
ENTRYPOINT ["python", "/app/scripts/ci_entrypoint.py"]
