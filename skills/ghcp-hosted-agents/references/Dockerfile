FROM python:3.12-slim

RUN pip install uv
WORKDIR /app
COPY . .

RUN uv pip install --system --compile-bytecode .

# SDK 2.0 Python wheels do not bundle the native runtime. Stage it at build
# time into a fixed directory: Foundry hosted agents run with
# HOME=/home/session, so a build-time ~/.cache is not found at run time.
ENV COPILOT_CLI_EXTRACT_DIR=/opt/copilot-runtime
RUN python -m copilot download-runtime --in-process && chmod -R a+rX /opt/copilot-runtime
ENV COPILOT_SKIP_CLI_DOWNLOAD=1

EXPOSE 8088
CMD ["python", "container.py"]
