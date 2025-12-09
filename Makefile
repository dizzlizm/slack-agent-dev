# Systems Bot Makefile
# Common commands for development and deployment

.PHONY: help install install-dev lint test build deploy-dev deploy-prod validate clean

# Default target
help:
	@echo "Systems Bot - Available Commands"
	@echo "=================================="
	@echo ""
	@echo "Development:"
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install dev dependencies (includes test/lint tools)"
	@echo "  make lint         - Run linters (flake8, mypy)"
	@echo "  make test         - Run test suite"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo ""
	@echo "SAM (Serverless Application Model):"
	@echo "  make validate     - Validate SAM template"
	@echo "  make build        - Build SAM application"
	@echo "  make deploy-dev   - Deploy to dev environment"
	@echo "  make deploy-prod  - Deploy to prod environment"
	@echo "  make logs-dev     - Tail logs for dev slack-events function"
	@echo "  make local-api    - Start local API Gateway for testing"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean        - Remove build artifacts"
	@echo "  make run-local    - Run bot locally (requires .env file)"
	@echo ""

# Python environment
PYTHON := python3
PIP := pip3
VENV := .venv

# Install production dependencies
install:
	$(PIP) install -r requirements.txt

# Install dev dependencies
install-dev: install
	$(PIP) install -r requirements-dev.txt

# Run linters
lint:
	flake8 src tests --max-line-length=120
	mypy src --ignore-missing-imports

# Run tests
test:
	pytest tests/ -v

# Run tests with coverage
test-cov:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# Validate SAM template
validate:
	sam validate --lint

# Build SAM application
build:
	sam build

# Deploy to dev environment
deploy-dev: build
	sam deploy --config-env dev

# Deploy to prod environment (requires confirmation)
deploy-prod: build
	sam deploy --config-env prod

# Tail logs for dev slack-events function
logs-dev:
	sam logs -n SlackEventsFunction --stack-name systems-bot-dev --tail

# Tail logs for prod slack-events function
logs-prod:
	sam logs -n SlackEventsFunction --stack-name systems-bot-prod --tail

# Start local API Gateway for testing
local-api: build
	sam local start-api --env-vars env.json

# Invoke function locally
local-invoke: build
	sam local invoke SlackEventsFunction --event events/slack-event.json

# Clean build artifacts
clean:
	rm -rf .aws-sam/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf __pycache__/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Local development (requires .env file with configuration)
run-local:
	@echo "Running bot locally..."
	@if [ ! -f .env ]; then echo "Error: .env file not found. Copy .env.example and configure."; exit 1; fi
	ENVIRONMENT=local python -m src.local_runner
