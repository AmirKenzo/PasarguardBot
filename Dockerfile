FROM python:3.14-slim-bookworm

ARG VERSION=dev
ARG REVISION=unknown

LABEL org.opencontainers.image.title="PasarguardBot" \
      org.opencontainers.image.description="PasarguardBot Telegram management bot" \
      org.opencontainers.image.source="https://github.com/AmirKenzo/PasarguardBot" \
      org.opencontainers.image.url="https://github.com/AmirKenzo/PasarguardBot" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_SYNC=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libffi-dev \
        libssl-dev \
        mariadb-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

RUN mkdir -p /app/logs /app/sessions

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uv", "run", "main.py"]
