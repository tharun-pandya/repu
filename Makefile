PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
.DEFAULT_GOAL := help
.PHONY: help watch install test test-ui lint run model-check eval-dev local-model-test clean
help:
	@echo "Targets: install test test-ui lint run model-check eval-dev local-model-test watch DIR=<folder> clean"
install:
	python -m venv .venv && $(PY) -m pip install -r requirements-dev.txt && cd frontend && npm install
test:
	$(PY) -m pytest -q && $(PY) -m unittest backend.tests.test_core
test-ui:
	cd frontend && npm test
lint:
	$(PY) -m ruff check .
run:
	$(PY) -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
model-check:
	curl -s localhost:8000/api/model/status?deep=true
eval-dev:
	$(PY) -m evaluation.evaluate --split dev --mode pipeline
local-model-test:
	REPU_LOCAL_MODEL_TEST=1 $(PY) -m pytest -m local_model -s
clean:
	rm -rf .pytest_cache .ruff_cache frontend/node_modules
watch:
	$(PY) -m backend.app.watch $(DIR)
