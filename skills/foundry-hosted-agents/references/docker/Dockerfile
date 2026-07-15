# Canonical hosted-agent Dockerfile.
#
# Source of truth for the prose example in
# `../../SKILL.md § Dockerfile`.
#
# Container image for a Foundry hosted agent (GA container-deploy path).
# `azd deploy` builds this remotely in Azure Container Registry by
# default — no local Docker needed. Use `azd ai agent run` when you
# intentionally want to build and run the agent locally.

FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/
COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project && rm -rf /root/.cache
COPY container.py .
COPY copilot-instructions.md .
EXPOSE 8088
CMD [".venv/bin/python", "container.py"]
