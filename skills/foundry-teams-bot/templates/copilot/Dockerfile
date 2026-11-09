FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all bot files (add .dockerignore to exclude __pycache__, .env, etc.)
COPY . .

# invocation_custody.py requires an existing owner-private absolute directory.
# This path is ephemeral: mount a durable volume here for recovery across
# container replacement.
ENV BOT_OPERATION_DIR=/var/lib/bot-operations
RUN install -d -m 700 "$BOT_OPERATION_DIR"

EXPOSE 80
CMD ["python", "app.py"]
