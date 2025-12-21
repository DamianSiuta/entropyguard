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

# 5. Upgrade pip and install build tools (as root)
RUN pip install --upgrade pip setuptools wheel build

# 6. Install dependencies (Root installs to global site-packages, readable by all)
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
    tqdm>=4.66.0 || \
    (echo "=== DEPENDENCY INSTALL FAILED ===" && exit 1)

# 7. Install poetry-core for build backend
RUN pip install --no-cache-dir poetry-core

# 8. Install the package itself (editable mode for development, or regular install)
# Try regular install first, if it fails, try editable mode
RUN pip install --no-cache-dir . || \
    (echo "=== Regular install failed, trying editable mode ===" && \
     pip install --no-cache-dir -e .) || \
    (echo "=== PIP INSTALL FAILED ===" && \
     echo "=== pyproject.toml ===" && \
     cat /app/pyproject.toml && \
     echo "=== Directory structure ===" && \
     find /app -type f -name "*.py" | head -20 && \
     echo "=== Testing import ===" && \
     python -c "import sys; sys.path.insert(0, '/app/src'); import entropyguard" && \
     exit 1)

# 9. Verify package is installed and importable
RUN python -c "import entropyguard; print(f'✅ EntropyGuard {entropyguard.__version__} installed successfully')" || \
    (echo "=== PACKAGE NOT IMPORTABLE ===" && \
     echo "=== Python path ===" && \
     python -c "import sys; print('\n'.join(sys.path))" && \
     echo "=== Installed packages ===" && \
     pip list | grep -i entropy || echo "entropyguard not found" && \
     exit 1)

# 10. Verify entrypoint exists and set permissions
RUN test -f /app/scripts/ci_entrypoint.py && \
    chmod +x /app/scripts/ci_entrypoint.py && \
    echo "Entrypoint verified" || \
    (echo "ERROR: ci_entrypoint.py not found!" && \
     ls -la /app/scripts/ && \
     exit 1)

# 11. Switch to non-root user
USER entropyguard

# 12. Entrypoint (use absolute path)
ENTRYPOINT ["python", "/app/scripts/ci_entrypoint.py"]
