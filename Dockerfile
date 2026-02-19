FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy project metadata and sources (include README for packaging metadata)
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Install genrepo (builds wheel via PEP 517 backend specified in pyproject)
RUN pip install --upgrade pip && \
    pip install .

# Default entrypoint runs the CLI
ENTRYPOINT ["genrepo"]
CMD ["--help"]
