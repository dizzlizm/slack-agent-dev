# Systems Bot - AWS Lambda Version

AI-powered Slack bot for IT support, running on AWS Lambda.

## Architecture

- **Runtime:** AWS Lambda (Python 3.11)
- **API:** Amazon API Gateway
- **Storage:** Amazon DynamoDB
- **Secrets:** AWS Secrets Manager
- **IaC:** AWS SAM (CloudFormation)

## Project Structure

```
aws/
├── src/
│   ├── handlers/          # Lambda function handlers
│   │   ├── slack_events.py
│   │   ├── slack_interactive.py
│   │   └── health.py
│   ├── security/          # Security utilities
│   ├── storage/           # DynamoDB adapters
│   ├── core/              # Business logic
│   └── config.py          # Configuration
├── tests/                 # Test suite
├── events/                # Sample events for local testing
├── template.yaml          # SAM/CloudFormation template
├── samconfig.toml         # SAM deployment config
├── Makefile              # Common commands
└── requirements.txt      # Python dependencies
```

## Quick Start

### Prerequisites

- AWS CLI configured with credentials
- SAM CLI installed (`pip install aws-sam-cli`)
- Python 3.11

### Deploy

```bash
# Validate template
make validate

# Deploy to dev
make deploy-dev

# Deploy to prod
make deploy-prod
```

### Local Testing

```bash
# Copy example env file
cp env.example.json env.json
# Edit env.json with your values

# Start local API
make local-api

# Or invoke a function directly
make local-invoke
```

### Configure Secrets

After first deploy, add secrets to AWS Secrets Manager:

```bash
aws secretsmanager put-secret-value \
  --secret-id systems-bot/dev \
  --secret-string '{
    "SLACK_BOT_TOKEN": "xoxb-...",
    "SLACK_SIGNING_SECRET": "...",
    "GEMINI_API_KEY": "...",
    "FRESHSERVICE_API_KEY": "...",
    "FRESHSERVICE_DOMAIN": "yourcompany.freshservice.com"
  }'
```

## Available Commands

```
make help           # Show all commands
make validate       # Validate SAM template
make build          # Build SAM application
make deploy-dev     # Deploy to dev environment
make deploy-prod    # Deploy to prod environment
make logs-dev       # Tail dev Lambda logs
make test           # Run tests
make lint           # Run linters
make clean          # Remove build artifacts
```

## Environments

| Environment | Stack Name | Config |
|-------------|------------|--------|
| dev | systems-bot-dev | `--config-env dev` |
| prod | systems-bot-prod | `--config-env prod` |
