FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS retrospective
COPY backend/requirements-retrospective.txt /tmp/requirements-retrospective.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r /tmp/requirements-retrospective.txt && python -m pip check

FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements-dev.txt
COPY --from=retrospective /usr/local/ /opt/retrospective/
COPY backend/requirements-retrospective.txt /opt/retrospective/requirements-retrospective.txt
ENV RETROSPECTIVE_PYTHON=/opt/retrospective/bin/python3.12
COPY backend/ ./backend/
COPY infra/run_backend_tests.py ./infra/run_backend_tests.py
COPY infra/study.py infra/review_accounts.py infra/windows_credentials.py infra/review_endpoints.py infra/runtime_snapshot.py ./infra/
COPY infra/operator_profiles.py infra/runtime_target.py ./infra/
COPY infra/convert_real_excel.py infra/load_closings.py infra/load_identities.py infra/run_real_study.py infra/prepare_demo_period.py infra/compare_real_summaries.py infra/export_spss.py ./infra/
RUN useradd --create-home --uid 10001 tester
USER tester
CMD ["python", "infra/run_backend_tests.py"]
