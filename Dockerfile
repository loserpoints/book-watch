# Built on uv's own image so the container resolves dependencies exactly as
# `uv sync` does locally — same lockfile, same versions, no pip in the middle.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Dependencies first, in their own layer: they change rarely, the source
# changes constantly, and this way a code edit does not reinstall the world.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# README and LICENSE are referenced by pyproject, so the build needs them.
COPY README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

CMD ["uvicorn", "book_watch.web.main:app", "--host", "0.0.0.0", "--port", "8080"]
