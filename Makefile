.DEFAULT_GOAL := help
PYTHON ?= python
.PHONY: help check-s0 up migrate seed-demo train-demo test demo backup
help:
	@echo "S0: estructura y contratos. Consulte README.md para preparar el entorno."
	@echo "check-s0: valida contratos; up/migrate/seed-demo/train-demo/test/demo/backup pendientes."
check-s0:
	$(PYTHON) infra/check_s0.py
up migrate seed-demo train-demo test demo backup:
	@echo "Pendiente de S1-S6. Sprint 0 no inicia servicios ni modifica datos."
	@exit 1
