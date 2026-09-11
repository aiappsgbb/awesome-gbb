FROM python:3.12-slim
WORKDIR /app
COPY templates/pyproject.toml /tmp/dependencies/pyproject.toml
RUN pip install --no-cache-dir /tmp/dependencies
COPY references/python/ /app/references/python/
USER 65532:65532
EXPOSE 8080
CMD ["python", "-m", "references.python.delegated_server"]
