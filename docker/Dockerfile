FROM python:3.11-slim

WORKDIR /app

# Set PYTHONPATH to include the app directory
ENV PYTHONPATH=/app

# Install Poetry (must match the major version that generated poetry.lock)
RUN pip install --no-cache-dir "poetry==2.2.1"

# Copy only dependency files first for better caching
COPY pyproject.toml poetry.lock* /app/

# Install runtime dependencies into the system interpreter.
# --no-root: the project source is copied afterwards and made importable via PYTHONPATH.
# --only main: keep dev/test tooling out of the runtime image.
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --only main

# Copy rest of the source code
COPY . /app/

# Default command (will be overridden by Docker Compose)
CMD ["python", "src/main.py"] 
