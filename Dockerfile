FROM python:3.12-slim

# ffmpeg for video assembly; DejaVu font for burned-in captions (libass).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV OUTPUT_DIR=/app/outputs \
    PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
