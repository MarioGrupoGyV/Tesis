FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements-dev.txt
COPY backend/ ./backend/
COPY infra/run_backend_tests.py ./infra/run_backend_tests.py
COPY infra/study.py infra/review_accounts.py infra/windows_credentials.py infra/review_endpoints.py infra/runtime_snapshot.py ./infra/
RUN useradd --create-home --uid 10001 tester
USER tester
CMD ["python", "infra/run_backend_tests.py"]
