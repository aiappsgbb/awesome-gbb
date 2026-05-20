FROM python:3.12-slim

RUN pip install uv
WORKDIR /app
COPY . .

RUN uv pip install --system --compile-bytecode .

EXPOSE 8088
CMD ["python", "container.py"]
