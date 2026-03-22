FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.110.0 \
    uvicorn==0.29.0 \
    httpx==0.27.0 \
    feedparser==6.0.11 \
    pyyaml==6.0.1 \
    pydantic==2.7.0

COPY feed_manager.py .

EXPOSE 8080

CMD ["uvicorn", "feed_manager:app", "--host", "0.0.0.0", "--port", "8080"]
