FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    PORT=8080

WORKDIR $APP_HOME
COPY . $APP_HOME

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir fastapi==0.120.0 uvicorn==0.38.0 starlette==0.48.0 \
        apscheduler==3.11.0 python-dotenv==1.0.1 python-multipart==0.0.20 requests==2.32.3

EXPOSE 8080
CMD ["python","-X","utf8","-m","uvicorn","server_unified:app","--host","0.0.0.0","--port","8080"]
