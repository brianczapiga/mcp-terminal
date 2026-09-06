.PHONY: help check-python setup install test run run-safe health clean lint format check dev-setup

VENV := .venv
PYTHON := $(VENV)/bin/python
PYTHON_BIN ?= python3

help:
	@echo "Available commands:"
	@echo "  setup      Create .venv and install the project with dev tools"
	@echo "  install    Create .venv (if needed) and install the project into it (same as setup)"
	@echo "  test       Run the test suite"
	@echo "  run        Run the MCP server"
	@echo "  run-safe   Run with terminal writes disabled"
	@echo "  health     Run the health check"
	@echo "  clean      Remove project-generated build and cache artifacts"
	@echo "  lint       Run Ruff lint checks"
	@echo "  format     Format code with Ruff"
	@echo "  check      Run lint, format check, types, tests, and package build"

check-python:
	@command -v "$(PYTHON_BIN)" >/dev/null 2>&1 || { echo "$(PYTHON_BIN) is unavailable"; exit 1; }
	@"$(PYTHON_BIN)" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' || { echo "Python 3.10 or newer is required"; exit 1; }

setup: check-python
	@if command -v uv >/dev/null 2>&1; then \
		uv venv --python "$(PYTHON_BIN)" $(VENV); \
		uv pip install --python $(PYTHON) -e '.[dev]'; \
	else \
		"$(PYTHON_BIN)" -m venv $(VENV); \
		$(PYTHON) -m pip install -e '.[dev]'; \
	fi
	@echo "Setup complete. Use $(PYTHON) or tools in $(VENV)/bin directly."

install: setup

test:
	$(VENV)/bin/pytest

run:
	$(PYTHON) -m terminal_mcp

run-safe:
	MCP_TERMINAL_READONLY=1 $(PYTHON) -m terminal_mcp

health:
	$(PYTHON) health_check.py

clean:
	rm -rf build dist htmlcov .coverage .pytest_cache .mypy_cache .ruff_cache
	rm -rf terminal_mcp_server.egg-info terminal_mcp/__pycache__ terminal_mcp/backends/__pycache__ tests/__pycache__ tests/contract/__pycache__ tests/unit/__pycache__

lint:
	$(VENV)/bin/ruff check .

format:
	$(VENV)/bin/ruff format .

check:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
	$(VENV)/bin/mypy terminal_mcp tests
	$(VENV)/bin/pytest -m "not smoke"
	$(PYTHON) -m build --no-isolation

dev-setup: setup
