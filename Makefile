.DEFAULT_GOAL := help
PYTHON ?= python
.PHONY: help check-s0 up migrate seed-demo restart down train-demo test test-s1 demo backup
help:
	@echo "S2 DEMO: up, migrate, seed-demo, restart, down; check-s0 conserva validaciones."
	@echo "test: suite completa en Linux aislado; test-s1: regresion local S1."
check-s0:
	$(PYTHON) infra/check_s0.py
up migrate seed-demo restart down:
	$(PYTHON) infra/s1.py $@
test:
	docker compose -f infra/compose.test.yaml build tester
	docker compose -f infra/compose.test.yaml run --rm tester
test-s1:
	$(PYTHON) infra/test_s1.py prepare-db
	$(PYTHON) infra/test_s1.py pytest
train-demo demo backup:
	@echo "Pendiente de S3-S6; fuera de Sprint 2."
	@exit 1
