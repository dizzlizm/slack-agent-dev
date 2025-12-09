# Systems Bot Makefile
# Common commands for development and deployment

.PHONY: help install install-dev lint test package deploy-dev deploy-prod terraform-init terraform-plan clean

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
	@echo "Packaging:"
	@echo "  make package      - Create Lambda deployment package"
	@echo "  make clean        - Remove build artifacts"
	@echo ""
	@echo "Terraform:"
	@echo "  make tf-init-dev  - Initialize Terraform for dev"
	@echo "  make tf-init-prod - Initialize Terraform for prod"
	@echo "  make tf-plan-dev  - Plan dev infrastructure changes"
	@echo "  make tf-plan-prod - Plan prod infrastructure changes"
	@echo "  make tf-apply-dev - Apply dev infrastructure changes"
	@echo "  make tf-fmt       - Format Terraform files"
	@echo ""
	@echo "Local Development:"
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

# Create Lambda deployment package
package: clean
	@echo "Creating Lambda deployment package..."
	mkdir -p package
	$(PIP) install -r requirements.txt -t package/
	cd package && zip -r ../lambda.zip .
	zip -g lambda.zip -r src/
	@echo "Created lambda.zip"

# Clean build artifacts
clean:
	rm -rf package/
	rm -f lambda.zip
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf __pycache__/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Terraform commands - Dev
tf-init-dev:
	cd infra/environments/dev && terraform init

tf-plan-dev:
	cd infra/environments/dev && terraform plan -var="lambda_s3_bucket=$(LAMBDA_S3_BUCKET)"

tf-apply-dev:
	cd infra/environments/dev && terraform apply -var="lambda_s3_bucket=$(LAMBDA_S3_BUCKET)"

# Terraform commands - Prod
tf-init-prod:
	cd infra/environments/prod && terraform init

tf-plan-prod:
	cd infra/environments/prod && terraform plan -var="lambda_s3_bucket=$(LAMBDA_S3_BUCKET)"

tf-apply-prod:
	cd infra/environments/prod && terraform apply -var="lambda_s3_bucket=$(LAMBDA_S3_BUCKET)"

# Format Terraform files
tf-fmt:
	terraform fmt -recursive infra/

# Local development (requires .env file with configuration)
run-local:
	@echo "Running bot locally..."
	@if [ ! -f .env ]; then echo "Error: .env file not found. Copy .env.example and configure."; exit 1; fi
	ENVIRONMENT=local python -m src.local_runner
