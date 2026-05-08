FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all bot files (add .dockerignore to exclude __pycache__, .env, etc.)
COPY . .

EXPOSE 80
CMD ["python", "app.py"]
