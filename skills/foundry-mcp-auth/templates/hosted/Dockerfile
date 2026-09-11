FROM python:3.12-slim
WORKDIR /app
COPY templates/hosted/pyproject.toml /tmp/dependencies/pyproject.toml
RUN pip install --no-cache-dir /tmp/dependencies
COPY references/python/hosted_agent.py /app/hosted_agent.py
# Match the canonical Hosted image: Foundry mounts a writable session home for
# the default container identity. A fixed UID cannot create its session store.
EXPOSE 8088
CMD ["python", "hosted_agent.py"]
