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
COPY --chown=entropyguard:entropyguard pyproject.toml README.md ./
COPY --chown=entropyguard:entropyguard src ./src
COPY --chown=entropyguard:entropyguard scripts ./scripts

# 5. Upgrade pip first (as root)
RUN pip install --upgrade pip setuptools wheel

# 6. Install dependencies (Root installs to global site-packages, readable by all)
# Install in two steps: first dependencies, then the package itself
RUN pip install --no-cache-dir \
    polars>=0.20.0 \
    pyarrow>=15.0.0 \
    fastexcel>=0.11.6 \
    torch>=2.1.0 \
    faiss-cpu>=1.7.4 \
    numpy>=1.24.0 \
    pydantic>=2.5.0 \
    typing-extensions>=4.8.0 \
    sentence-transformers>=2.0.0 \
    tqdm>=4.66.0

# 7. Install the package itself
RUN pip install --no-cache-dir .

# 8. Verify entrypoint exists and set permissions
RUN test -f /app/scripts/ci_entrypoint.py && \
    chmod +x /app/scripts/ci_entrypoint.py && \
    echo "Entrypoint verified" || \
    (echo "ERROR: ci_entrypoint.py not found!" && \
     ls -la /app/scripts/ && \
     exit 1)

# 9. Switch to non-root user
USER entropyguard

# 10. Entrypoint (use absolute path)
ENTRYPOINT ["python", "/app/scripts/ci_entrypoint.py"]
