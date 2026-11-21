FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# Only the dependencies used by the current chat application are needed.
# Versions match uv.lock; RAG/training dependencies are not part of this image.
RUN pip install --no-cache-dir \
    openai==1.109.1 \
    pydantic==2.11.10 \
    python-dotenv==1.2.3 \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY config.py ./config.py
COPY backend/main.py ./backend/main.py
COPY frontend/index.html ./frontend/index.html

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/', timeout=3).close()"

CMD ["python", "-m", "backend.main"]
