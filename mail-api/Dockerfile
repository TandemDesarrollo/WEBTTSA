FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

COPY mail-api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY mail-api/app.py ./

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/healthz', timeout=2).close()" || exit 1

CMD ["python", "app.py"]
