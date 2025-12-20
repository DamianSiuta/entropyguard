FROM python:3.10-slim

# Ensure stdout/stderr are unbuffered for better logging in containers
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies for scientific Python stack (numpy, pyarrow, faiss, torch, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# Create non-root user for security (hardening)
RUN useradd -m -u 1000 entropyguard && \
    chown -R entropyguard:entropyguard /app

# Create cache directory for HuggingFace models (fixes PermissionError in GitHub Actions)
ENV HF_HOME=/app/.cache/huggingface
RUN mkdir -p $HF_HOME && chown -R entropyguard:entropyguard /app

# Copy project metadata and source
COPY --chown=entropyguard:entropyguard pyproject.toml README.md ./
COPY --chown=entropyguard:entropyguard src ./src
COPY --chown=entropyguard:entropyguard scripts ./scripts

# Install the project as a package using pip (Poetry not required at runtime)
RUN pip install --upgrade pip && \
    pip install .

# Switch to non-root user
USER entropyguard

# Make CI entrypoint executable (for GitHub Actions)
RUN chmod +x /app/scripts/ci_entrypoint.py || true

# Default entrypoint: run the CI entrypoint (which handles both CLI and GitHub Actions)
# The CI entrypoint will detect if it's running in GitHub Actions mode
ENTRYPOINT ["python", "/app/scripts/ci_entrypoint.py"]


