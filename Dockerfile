FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# 1. Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    git \
 && rm -rf /var/lib/apt/lists/*

# 2. Create user
RUN useradd -m -u 1000 entropyguard

# 3. Setup directories & permissions (PRE-COPY)
RUN mkdir -p $HF_HOME && chown -R entropyguard:entropyguard /app

# 4. Copy files
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts

# 5. Install dependencies (Global pip is fine in container)
RUN pip install --upgrade pip && \
    pip install .

# 6. Fix permissions (POST-COPY) - Critical step!
# Ensure entropyguard owns everything we just copied/installed in /app
RUN chown -R entropyguard:entropyguard /app

# 7. Switch user
USER entropyguard

# 8. Entrypoint
ENTRYPOINT ["python", "scripts/ci_entrypoint.py"]
