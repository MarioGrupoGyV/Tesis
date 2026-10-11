FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS retrospective
COPY backend/requirements-retrospective.txt /tmp/requirements-retrospective.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r /tmp/requirements-retrospective.txt && python -m pip check

FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
COPY --from=retrospective /usr/local/ /opt/retrospective/
COPY backend/requirements-retrospective.txt /opt/retrospective/requirements-retrospective.txt
ENV RETROSPECTIVE_PYTHON=/opt/retrospective/bin/python3.12
RUN LD_LIBRARY_PATH=/opt/retrospective/lib /opt/retrospective/bin/python3.12 -I -c "import sys,platform,sklearn,numpy,scipy,joblib; assert sys.prefix == '/opt/retrospective'; assert (platform.python_version(),sklearn.__version__,numpy.__version__,scipy.__version__,joblib.__version__)==('3.12.14','1.8.0','2.3.5','1.17.0','1.5.3')"
COPY backend/app/ /app/app/
COPY backend/migrations/ /app/migrations/
COPY backend/alembic.ini /app/alembic.ini
RUN useradd --create-home --uid 10001 app
RUN mkdir -p /var/lib/riesgo/imports && chown app:app /var/lib/riesgo/imports && chmod 700 /var/lib/riesgo/imports
RUN mkdir -p /var/lib/riesgo/ml && chown app:app /var/lib/riesgo/ml && chmod 700 /var/lib/riesgo/ml
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
