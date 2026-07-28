FROM python:3.11-slim

# ffmpeg is required by the pipeline (clipping, silence removal, reformat, subtitles)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent data lives here (mount a volume at /app/data on the host)
RUN mkdir -p /app/uploads /app/output /app/static/avatars /app/static/brand

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Liveness probe hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT','8000')).status==200 else 1)"

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
