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
# Copy essential files explicitly to avoid issues with .dockerignore
COPY --chown=entropyguard:entropyguard pyproject.toml README.md ./
COPY --chown=entropyguard:entropyguard src ./src
COPY --chown=entropyguard:entropyguard scripts ./scripts

# 5. Debug: List files to verify copy worked
RUN echo "=== Files in /app ===" && \
    ls -la /app && \
    echo "=== Files in /app/scripts ===" && \
    ls -la /app/scripts && \
    echo "=== pyproject.toml exists ===" && \
    test -f /app/pyproject.toml && echo "YES" || echo "NO"

# 6. Install dependencies (Root installs to global site-packages, readable by all)
RUN pip install --upgrade pip && \
    pip install --verbose . || \
    (echo "=== PIP INSTALL FAILED ===" && \
     echo "=== Contents of /app ===" && \
     ls -la /app && \
     echo "=== Contents of pyproject.toml ===" && \
     cat /app/pyproject.toml && \
     exit 1)

# 7. Verify entrypoint exists and set permissions
RUN test -f /app/scripts/ci_entrypoint.py && \
    chmod +x /app/scripts/ci_entrypoint.py && \
    echo "=== Entrypoint verified ===" || \
    (echo "ERROR: ci_entrypoint.py not found!" && \
     ls -la /app/scripts/ && \
     exit 1)

# 8. Switch to non-root user
USER entropyguard

# 9. Entrypoint (use absolute path)
ENTRYPOINT ["python", "/app/scripts/ci_entrypoint.py"]
