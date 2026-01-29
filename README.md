# Systems Bot - AI-Powered Slack IT Support Agent

An intelligent Slack bot for IT support powered by Google Gemini AI, running on AWS Lambda with FreshService and Microsoft Intune integrations.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Available Tools](#available-tools)
- [Observability](#observability)
- [Security](#security)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

---

## Overview

Systems Bot is an AI-powered Slack agent that helps users with IT support tasks. It leverages Google Gemini for natural language understanding and can interact with FreshService ITSM and Microsoft Intune for device management.

### Key Capabilities

- **Natural Language IT Support**: Users can describe issues in plain language
- **Ticket Management**: Create, update, search, and manage FreshService tickets
- **Asset Management**: Look up devices, software inventory, and contracts
- **Knowledge Base Search**: Find relevant solutions from FreshService KB
- **Service Catalog**: Browse and submit service requests with approval workflows
- **Problem Management**: Check for known issues and link incidents to problems
- **Device Management**: Reboot devices via Intune (with confirmation)

---

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   Slack     │────▶│  API Gateway    │────▶│  Lambda Handler  │
│   Events    │     │  (REST API)     │     │  (slack_events)  │
└─────────────┘     └─────────────────┘     └────────┬─────────┘
                                                      │
                                                      ▼ (async invoke)
                                            ┌──────────────────┐
                                            │  Message         │
                                            │  Processor       │
                                            └────────┬─────────┘
                                                     │
                    ┌────────────────────────────────┼────────────────────────────────┐
                    │                                │                                │
                    ▼                                ▼                                ▼
          ┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
          │  Gemini AI      │            │  FreshService   │            │  Microsoft      │
          │  (Orchestrator) │            │  API            │            │  Intune         │
          └─────────────────┘            └─────────────────┘            └─────────────────┘
```

### Technology Stack

| Component | Technology |
|-----------|------------|
| Runtime | AWS Lambda (Python 3.11) |
| API | Amazon API Gateway |
| Storage | Amazon DynamoDB |
| Secrets | AWS Secrets Manager |
| IaC | AWS SAM (CloudFormation) |
| AI | Google Gemini |
| ITSM | FreshService |
| MDM | Microsoft Intune |

---

## Features

### Ticket Operations
- Create tickets with automatic requester lookup
- Update ticket status, priority, and assignments
- Add notes and comments to existing tickets
- View ticket conversation history
- Search tickets by requester or agent

### Asset Management
- List assets assigned to users
- View asset details and specifications
- Get installed software inventory
- Check warranty and contract information

### Knowledge Base (Solutions)
- Search articles by keyword
- Browse by category and folder
- Get popular/trending articles
- Retrieve full article content

### Service Catalog
- Browse available service items
- View item details and required fields
- Submit service requests with approval routing
- Track request status and fulfillment

### Problem Management
- Search for known problems
- View problem details with root cause analysis
- Link tickets to known problems
- Get list of affected tickets

### Change Management
- List recent and upcoming changes
- View maintenance windows

### Device Management
- Reboot devices via Intune (with user confirmation)

---

## Project Structure

```
├── src/
│   ├── handlers/              # Lambda function handlers
│   │   ├── slack_events.py    # Slack event receiver
│   │   ├── message_processor.py # Async message processing
│   │   ├── slack_interactive.py # Button/modal interactions
│   │   └── health.py          # Health check endpoint
│   ├── core/                  # Business logic
│   │   ├── message_router.py  # Routes messages to handlers
│   │   ├── interactive_handler.py # Handles button clicks
│   │   └── triage_workflow.py # Triage decision flow
│   ├── integrations/          # External service integrations
│   │   ├── slack_client.py    # Slack API wrapper
│   │   ├── gemini_service.py  # Gemini AI service
│   │   ├── mcp_integration.py # MCP orchestrator (AI + tools)
│   │   ├── mcp_tools.py       # Unified tool interface
│   │   └── freshservice/      # FreshService modules
│   │       ├── client.py      # Base API client
│   │       ├── users.py       # User operations
│   │       ├── tickets.py     # Ticket operations
│   │       ├── assets.py      # Asset operations
│   │       ├── changes.py     # Change operations
│   │       ├── solutions.py   # Knowledge base operations
│   │       ├── service_catalog.py # Service catalog operations
│   │       ├── problems.py    # Problem management
│   │       └── tools.py       # Unified FreshService interface
│   ├── security/              # Security utilities
│   │   ├── signature.py       # Slack signature verification
│   │   ├── rate_limiter.py    # Rate limiting
│   │   ├── validators.py      # Input validation
│   │   ├── sanitizer.py       # Input sanitization
│   │   └── audit_logger.py    # Audit trail logging
│   ├── storage/               # Data persistence
│   │   ├── dynamodb_conversation.py # Conversation history
│   │   ├── dynamodb_triage.py # Triage session storage
│   │   └── auth_manager.py    # Authorization management
│   ├── observability/         # Monitoring and tracing
│   │   ├── metrics.py         # CloudWatch metrics
│   │   └── tracing.py         # Request tracing
│   ├── models/                # Data models
│   │   └── models.py          # Pydantic models
│   ├── config.py              # Configuration management
│   └── exceptions.py          # Custom exceptions
├── tests/                     # Test suite
│   └── unit/                  # Unit tests
│       ├── test_config.py
│       ├── test_exceptions.py
│       ├── test_security.py
│       └── test_freshservice_tools.py
├── events/                    # Sample events for local testing
├── examples/                  # Usage examples
├── template.yaml              # SAM/CloudFormation template
├── cloudwatch-alarms.yaml     # Optional monitoring stack
├── samconfig.toml             # SAM deployment config
├── Makefile                   # Common commands
├── requirements.txt           # Python dependencies
└── requirements-dev.txt       # Development dependencies
```

---

## Prerequisites

- **AWS CLI** configured with appropriate credentials
- **SAM CLI** installed (`pip install aws-sam-cli`)
- **Python 3.11**
- **Slack App** with Bot Token and Signing Secret
- **Google Gemini API Key**
- **FreshService** account with API key (optional)
- **Microsoft Intune** webhook configured (optional)

---

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd slack-agent-dev

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Configure Local Environment

```bash
# Copy example environment file
cp env.example.json env.json

# Edit with your values
# Required: SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, GEMINI_API_KEY
# Optional: FRESHSERVICE_API_KEY, FRESHSERVICE_DOMAIN, INTUNE_REBOOT_WEBHOOK_URL
```

### 3. Deploy

```bash
# Validate template
make validate

# Build the application
make build

# Deploy to dev environment
make deploy-dev
```

### 4. Configure Secrets

After deployment, add secrets to AWS Secrets Manager:

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

### 5. Configure Slack App

Point your Slack app's event subscription URL to:
```
https://<your-api-gateway-url>/slack/events
```

And interactive components URL to:
```
https://<your-api-gateway-url>/slack/interactive
```

---

## Configuration

### Required Secrets

| Secret | Description |
|--------|-------------|
| `SLACK_BOT_TOKEN` | Slack Bot OAuth token (xoxb-...) |
| `SLACK_SIGNING_SECRET` | Slack app signing secret for verification |
| `GEMINI_API_KEY` | Google Gemini API key |

### Optional Secrets

| Secret | Description |
|--------|-------------|
| `FRESHSERVICE_API_KEY` | FreshService API key |
| `FRESHSERVICE_DOMAIN` | FreshService domain (company.freshservice.com) |
| `INTUNE_REBOOT_WEBHOOK_URL` | Power Automate webhook for Intune reboot |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | dev | Environment name (dev/prod) |
| `RATE_LIMIT_MAX_REQUESTS` | 10 | Max requests per rate limit window |
| `RATE_LIMIT_WINDOW_SECONDS` | 60 | Rate limit window duration |
| `CONVERSATION_HISTORY_LIMIT` | 10 | Messages to include in AI context |
| `AUDIT_METRICS_ENABLED` | true | Enable CloudWatch audit metrics |
| `AUDIT_SAMPLE_RATE` | 0.1 | Metric sampling rate (0.0-1.0) |
| `METRICS_ENABLED` | true | Enable application metrics |
| `METRICS_FLUSH_SECONDS` | 60 | Auto-flush interval for metrics |

### Configuration Validation

The application validates configuration at startup:

```python
from src.config import Config, ConfigValidator

Config.load()
ConfigValidator.validate_and_log()  # Logs warnings, raises on errors
```

---

## Deployment

### Development Environment

```bash
# Build and deploy
sam build
sam deploy --config-env dev

# Or use Makefile
make deploy-dev
```

### Production Environment

```bash
# Build and deploy (will prompt for confirmation)
sam build
sam deploy --config-env prod

# Or use Makefile
make deploy-prod
```

### Deploy CloudWatch Monitoring (Optional)

```bash
aws cloudformation deploy \
  --template-file cloudwatch-alarms.yaml \
  --stack-name systems-bot-dev-monitoring \
  --parameter-overrides \
    Environment=dev \
    AlertEmail=your-email@company.com \
    HighCostThreshold=50000 \
  --capabilities CAPABILITY_IAM
```

### Verify Deployment

```bash
# Get health endpoint URL
aws cloudformation describe-stacks \
  --stack-name systems-bot-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`HealthEndpoint`].OutputValue' \
  --output text

# Test health
curl https://YOUR_API_URL/health

# Test detailed health (AWS services)
curl "https://YOUR_API_URL/health?detailed=true"

# Test full health (includes external APIs)
curl "https://YOUR_API_URL/health?detailed=true&external=true"
```

### Stack Outputs

After deployment, get all outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name systems-bot-dev \
  --query 'Stacks[0].Outputs'
```

**Available Outputs:**
- `ApiUrl` - Base API Gateway URL
- `SecretArn` - Secrets Manager ARN
- `AuditLogTableName` - Audit log table name
- `HealthEndpoint` - Basic health check URL
- `HealthDetailedEndpoint` - Detailed health check URL

---

## Available Tools

The AI agent has access to 29 tools across 7 categories:

### User Operations (2 tools)
| Tool | Description |
|------|-------------|
| `get_user_by_email` | Find FreshService user by email |
| `get_user_by_name` | Search users by name |

### Ticket Operations (6 tools)
| Tool | Description |
|------|-------------|
| `list_tickets` | List tickets by requester or agent |
| `get_ticket_by_id` | Get specific ticket details |
| `create_ticket` | Create a new ticket |
| `update_ticket` | Update ticket status/priority/assignment |
| `add_ticket_note` | Add comment to ticket |
| `get_ticket_conversations` | View ticket conversation history |

### Asset Operations (4 tools)
| Tool | Description |
|------|-------------|
| `list_assets` | List assets assigned to user |
| `get_asset_by_id` | Get asset details |
| `get_asset_software` | Get installed software inventory |
| `get_asset_contracts` | Get warranty/contract information |

### Knowledge Base (6 tools)
| Tool | Description |
|------|-------------|
| `search_solution_articles` | Search KB by keyword |
| `get_solution_article` | Get full article content |
| `list_solution_articles` | Browse articles in folder |
| `get_popular_articles` | Get trending articles |
| `list_solution_categories` | List KB categories |
| `list_solution_folders` | List folders in category |

### Service Catalog (5 tools)
| Tool | Description |
|------|-------------|
| `list_service_items` | Browse catalog items |
| `search_service_items` | Search catalog by keyword |
| `get_service_item` | Get item details and fields |
| `create_service_request` | Submit service request |
| `get_service_request_status` | Track request progress |

### Problem Management (5 tools)
| Tool | Description |
|------|-------------|
| `search_problems` | Search known problems |
| `list_problems` | List problems with filters |
| `get_problem_by_id` | Get problem details |
| `link_ticket_to_problem` | Associate ticket with problem |
| `get_problem_tickets` | Get tickets affected by problem |

### Device Management (1 tool)
| Tool | Description |
|------|-------------|
| `reboot_device` | Reboot device via Intune (requires confirmation) |

---

## Observability

### CloudWatch Metrics

**Namespaces:**
- `SystemsBot/Audit` - Audit event metrics
- `SystemsBot` - Application metrics

**Key Metrics:**

| Metric | Description |
|--------|-------------|
| `ToolInvocations` | Tool execution count by tool name |
| `ToolLatency` | Tool execution time (ms) |
| `ToolSuccessRate` | Tool success percentage |
| `Errors` | Error count by type and severity |
| `MessagesProcessed` | Message handling count |
| `APILatency` | External API latency |
| `APISuccessRate` | External API success rate |
| `AuditEvents` | Audit event count by action type |

### CloudWatch Alarms

When monitoring stack is deployed:

- **HighAuditVolumeAlarm** - Detects potential infinite loops (>50k events/day)
- **HighErrorRateAlarm** - Triggers on >100 errors/hour
- **APIFailureRateAlarm** - Triggers when API success <95%
- **MessageProcessorErrorAlarm** - Lambda errors >5 in 5 minutes
- **DynamoDBThrottleAlarm** - DynamoDB throttling detection

### Request Tracing

All requests include trace IDs for end-to-end tracking:

```python
from src.observability.tracing import set_trace_id, generate_trace_id

trace_id = generate_trace_id()
set_trace_id(trace_id)
# All logs will include [trace_id] prefix
```

### Health Checks

| Endpoint | Description |
|----------|-------------|
| `/health` | Basic health (fast, no external calls) |
| `/health?detailed=true` | AWS services health |
| `/health?detailed=true&external=true` | Full health including FreshService |

---

## Security

### Authentication & Authorization

- **Slack Signature Verification**: HMAC-SHA256 with constant-time comparison
- **Replay Attack Protection**: 5-minute timestamp validation
- **Per-User Rate Limiting**: Sliding window algorithm
- **Authorization Manager**: User/group-based access control

### Input Validation

- Email format and domain validation
- Ticket ID range validation
- SQL injection pattern detection
- Command injection prevention
- PII detection and redaction

### Audit Logging

- All tool executions logged to DynamoDB
- User attribution for all actions
- 365-day retention with TTL
- CloudWatch metrics integration
- Queryable by user ID or resource ID

### Sensitive Actions

- Device reboot requires user confirmation via Slack button
- Audit trail for all destructive operations
- Authorization fails closed

---

## Testing

### Setup

```bash
# Install test dependencies
pip install pytest pytest-cov

# Or using apt (Debian/Ubuntu)
sudo apt install python3-pytest python3-pytest-cov
```

### Run Tests

```bash
# Run all unit tests
python3 -m pytest tests/unit/ -v

# Run with coverage
python3 -m pytest tests/unit/ --cov=src --cov-report=html

# Run specific test file
python3 -m pytest tests/unit/test_config.py -v

# Run specific test
python3 -m pytest tests/unit/test_config.py::TestConfigValidator -v
```

### Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| test_config.py | 18 | Configuration validation |
| test_exceptions.py | 30+ | All exception types |
| test_security.py | 15+ | Security utilities |
| test_freshservice_tools.py | 20+ | FreshService integration |

---

## Troubleshooting

### Configuration Errors

**Problem:** `ConfigurationError` at startup

**Solution:** Check AWS Secrets Manager for required secrets

```bash
aws secretsmanager get-secret-value --secret-id systems-bot/dev
```

### Metrics Not Appearing

**Check:**
1. Lambda has `cloudwatch:PutMetricData` permission
2. Metrics enabled: `METRICS_ENABLED=true`
3. Flush metrics before Lambda exits

**Solution:**
```python
# At end of Lambda handler
metrics.flush()
```

### Health Check Timeout

**Solution:** Use tiered health checks

- `/health` - Fast, no external calls
- `/health?detailed=true` - AWS services only
- Increase Lambda timeout if needed:

```bash
aws lambda update-function-configuration \
  --function-name dev-health \
  --timeout 15
```

### High Costs

**Reduce costs:**
1. Lower sampling rate: `AUDIT_SAMPLE_RATE=0.01` (1%)
2. Disable metrics in dev: `METRICS_ENABLED=false`
3. Increase flush interval: `METRICS_FLUSH_SECONDS=120`

### Test Import Errors

**Problem:** `ModuleNotFoundError: No module named 'src'`

**Solution:** Run tests from project root: `python3 -m pytest tests/unit/`

### Audit Logs Not Being Created

**Check:**
1. Lambda has DynamoDB permissions for AuditLog table
2. Table exists: `aws dynamodb describe-table --table-name dev-AuditLog`
3. Check Lambda logs for DynamoDB errors

---

## Development

### Available Make Commands

```bash
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

### Adding New FreshService Operations

1. Create or update module in `src/integrations/freshservice/`
2. Add methods with `@retry_on_failure` decorator
3. Import in `tools.py` and add delegation methods
4. Update `execute_tool()` dispatcher in `mcp_tools.py`
5. Add FunctionDeclaration in `mcp_integration.py`
6. Add tests in `tests/unit/`

### Exception Types

| Exception | Use Case |
|-----------|----------|
| `AuthorizationError` | User not authorized |
| `ValidationError` | Input validation failure |
| `ToolExecutionError` | MCP tool execution failure |
| `ExternalAPIError` | External API call failure |
| `RateLimitError` | Rate limit exceeded |
| `QuotaExceededError` | API quota exceeded |
| `ConfigurationError` | Configuration error |
| `StorageError` | DynamoDB operation failure |

### Code Quality Standards

- Type hints on all new functions
- Docstrings for complex modules
- 80%+ test coverage target
- Input validation at boundaries
- No hardcoded secrets

---

## Cost Estimates

### Monthly Costs (1,000 requests/day)

| Component | Cost |
|-----------|------|
| DynamoDB (Audit + Conversations) | ~$1.50 |
| CloudWatch Metrics (with batching) | ~$0.75 |
| Lambda Invocations | ~$0.50 |
| API Gateway | ~$0.50 |
| **Total** | **~$3.25** |

### Cost Optimization Features

- **Metric Sampling**: 10% default sampling rate
- **Metric Batching**: Up to 20 metrics per API call
- **Tiered Health Checks**: External APIs only when requested
- **DynamoDB On-Demand**: Pay-per-request billing

---

## Environments

| Environment | Stack Name | Config |
|-------------|------------|--------|
| dev | systems-bot-dev | `--config-env dev` |
| prod | systems-bot-prod | `--config-env prod` |

---

## License

[Add your license information here]

---

## Support

For issues and feature requests, please open a GitHub issue.
