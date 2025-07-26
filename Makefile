.PHONY: help setup install test run clean lint format check

# Default target
help:
	@echo "Available commands:"
	@echo "  setup     - Set up virtual environment and install dependencies"
	@echo "  install   - Install dependencies in current environment"
	@echo "  test      - Run tests"
	@echo "  run       - Run the MCP server"
	@echo "  clean     - Clean up generated files"
	@echo "  lint      - Run linting checks"
	@echo "  format    - Format code with black"
	@echo "  check     - Run all checks (lint, format, test)"

# Set up virtual environment and install dependencies
setup:
	@echo "Setting up virtual environment..."
	python3 -m venv venv
	@echo "Installing dependencies..."
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt
	@echo "Setup complete! Activate with: source venv/bin/activate"

# Install dependencies in current environment
install:
	pip install -r requirements.txt

# Run tests
test:
	@echo "Running tests..."
	python -m pytest tests/ -v --tb=short

# Run the MCP server
run:
	@echo "Starting MCP server..."
	python terminal_mcp_server.py

# Run the MCP server in readonly mode (recommended)
run-safe:
	@echo "Starting MCP server in readonly mode (recommended)..."
	MCP_TERMINAL_READONLY=1 python terminal_mcp_server.py

# Run health check
health:
	@echo "Running health check..."
	python health_check.py

# Clean up generated files
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	@echo "Cleanup complete!"

# Run linting checks
lint:
	@echo "Running linting checks..."
	flake8 terminal_mcp_server.py
	pylint terminal_mcp_server.py

# Format code with black
format:
	@echo "Formatting code..."
	black terminal_mcp_server.py

# Run all checks
check: lint format test
	@echo "All checks passed!"

# Development setup with additional tools
dev-setup: setup
	@echo "Installing development dependencies..."
	. venv/bin/activate && pip install black flake8 pylint pytest
	@echo "Development setup complete!" 