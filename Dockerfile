FROM python:3.10-slim

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

CMD ["sh", "-c", "exec python -m uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8600}"]
ENV PORT=8600
EXPOSE 8600
