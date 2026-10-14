# syntax=docker/dockerfile:1
# One image recipe for the Python services. Built in CI for linux/amd64 only (SPEC §16).
#   docker build -f docker/service.Dockerfile \
#     --build-arg PACKAGE=advisor-api --build-arg SERVICE_DIR=services/api \
#     --build-arg SERVICE_CMD="uvicorn advisor_api.main:app --host 0.0.0.0 --port \$PORT" .
ARG PYTHON_IMAGE=python:3.12.15-slim-trixie

FROM ${PYTHON_IMAGE} AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
ARG PACKAGE
ARG SERVICE_DIR

# Dependencies first, so code changes don't reinstall them. uv validates the lock
# against every workspace member, so all member pyproject files are copied.
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/
COPY services/api/pyproject.toml services/api/
COPY services/worker/pyproject.toml services/worker/
COPY services/mcp/pyproject.toml services/mcp/
COPY ingestion/pyproject.toml ingestion/
COPY evals/pyproject.toml evals/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-workspace --package "${PACKAGE}"

COPY packages/core packages/core
COPY ${SERVICE_DIR} ${SERVICE_DIR}
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --package "${PACKAGE}"

FROM ${PYTHON_IMAGE}
ARG SERVICE_CMD
ARG SOURCE_TREE=unknown
LABEL org.opencontainers.image.source="https://github.com/Purvav0511/plant-advisor" \
      dev.plant-advisor.tree="${SOURCE_TREE}"
RUN useradd --create-home --uid 10001 app
COPY --from=build --chown=app:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    SOURCE_TREE=${SOURCE_TREE} \
    SERVICE_CMD=${SERVICE_CMD}
USER app
EXPOSE 8080
# Cloud Run (or ECS) sets PORT. SERVICE_CMD is fixed at build time; eval expands the
# $PORT inside it at start.
CMD ["sh", "-c", "eval exec \"$SERVICE_CMD\""]
