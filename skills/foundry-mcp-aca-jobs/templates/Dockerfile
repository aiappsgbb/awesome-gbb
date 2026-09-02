FROM python:3.12-slim

WORKDIR /srv

COPY pyproject.toml .
COPY app ./app

RUN pip install --no-cache-dir .
RUN python -m py_compile app/*.py

RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8080

CMD ["python", "-m", "app.mcp_server"]
