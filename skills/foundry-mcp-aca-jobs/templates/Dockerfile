FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

WORKDIR /srv

COPY --from=ghcr.io/astral-sh/uv:0.12.6@sha256:88bc6eb1ccd4b82efd0e1b530caffabddf50dc2bf612e66c14ea25b8ee8a4d3d /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
COPY app ./app

RUN uv sync --frozen --no-dev --no-editable
ENV PATH="/srv/.venv/bin:$PATH"
RUN python -m py_compile app/*.py

RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8080

CMD ["python", "-m", "app.mcp_server"]
