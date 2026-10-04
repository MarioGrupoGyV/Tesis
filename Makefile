.DEFAULT_GOAL := help
PYTHON ?= python
.PHONY: help check-s0 up migrate seed-demo restart down train-demo test demo backup
help:
	@echo "S1 DEMO: up, migrate, seed-demo, restart, down; check-s0 conserva validaciones."
	@echo "train-demo/demo/backup: fases posteriores. test: pytest con base de prueba configurada."
check-s0:
	$(PYTHON) infra/check_s0.py
up migrate seed-demo restart down:
	$(PYTHON) infra/s1.py $@
test:
	$(PYTHON) infra/test_s1.py prepare-db
	$(PYTHON) infra/test_s1.py pytest
train-demo demo backup:
	@echo "Pendiente de S3-S6; fuera de Sprint 1."
	@exit 1
