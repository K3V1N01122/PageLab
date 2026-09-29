# Imagen de la aplicación (backend + archivos del frontend).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    APP_ENV=production FRONTEND_DIR=/app/frontend UPLOAD_DIR=/data/uploads

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

RUN useradd --create-home --uid 10001 app && mkdir -p /data/uploads && chown -R app:app /data
USER app

EXPOSE 8000
# Al arrancar: migraciones; si DEMO_MODE=true, datos demo (no duplica) e imágenes demo.
# El puerto sale de $PORT (lo fijan Render y otras plataformas) o 8000 por defecto.
CMD ["sh", "-c", "python manage.py migrate && if [ \"$DEMO_MODE\" = \"true\" ]; then python manage.py seed-demo --force; fi && exec gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-4} --timeout 30 --access-logfile - --forwarded-allow-ips='*'"]
