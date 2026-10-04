FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
COPY backend/app/ /app/app/
COPY backend/migrations/ /app/migrations/
COPY backend/alembic.ini /app/alembic.ini
RUN useradd --create-home --uid 10001 app
RUN mkdir -p /var/lib/riesgo/imports && chown app:app /var/lib/riesgo/imports && chmod 700 /var/lib/riesgo/imports
RUN mkdir -p /var/lib/riesgo/ml && chown app:app /var/lib/riesgo/ml && chmod 700 /var/lib/riesgo/ml
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
