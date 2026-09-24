FROM ghcr.io/astral-sh/uv:0.12.17 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock README.md ./
COPY ai-service/ ./ai-service/
RUN uv sync --locked --no-dev --no-editable && useradd --create-home extractor
USER extractor
CMD ["/app/.venv/bin/python", "-m", "transcriber_id.service"]
