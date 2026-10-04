FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements-dev.txt
COPY backend/ ./backend/
COPY infra/run_linux_tests.py ./infra/run_linux_tests.py
RUN useradd --create-home --uid 10001 tester
USER tester
CMD ["python", "infra/run_linux_tests.py"]
