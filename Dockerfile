FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências primeiro, para o cache do Docker reaproveitar esta camada.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home app
USER app

EXPOSE 8080
# --proxy-headers: o IP real do usuário (limite de tentativas de login) vem do proxy do Fly.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips=*"]
