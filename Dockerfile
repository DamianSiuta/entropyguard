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

# Copy project metadata and source
COPY pyproject.toml README.md ./
COPY src ./src

# Install the project as a package using pip (Poetry not required at runtime)
RUN pip install --upgrade pip && \
    pip install .

# Default entrypoint: run the EntropyGuard CLI
ENTRYPOINT ["python", "-m", "entropyguard.cli.main"]


