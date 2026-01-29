# Systems Bot Improvement Plan

## Executive Summary

This document outlines a comprehensive improvement plan for the Systems Bot Slack agent. The plan focuses on expanding the FreshService MCP toolset, adding real-world use cases, enhancing security, improving operational capabilities, and optimizing the codebase for maintainability and performance.

---

## Table of Contents

1. [Current State Assessment](#current-state-assessment)
2. [FreshService MCP Toolset Expansion](#freshservice-mcp-toolset-expansion)
3. [Real-World Use Case Enhancements](#real-world-use-case-enhancements)
4. [Security Improvements](#security-improvements)
5. [Codebase Quality Improvements](#codebase-quality-improvements)
6. [Operational Enhancements](#operational-enhancements)
7. [Implementation Roadmap](#implementation-roadmap)

---

## Current State Assessment

### Strengths
- Well-organized modular architecture with clear separation of concerns
- Comprehensive security layer (HMAC verification, rate limiting, authorization)
- Flexible MCP toolset with 15 tools (14 FreshService + 1 Intune)
- Multi-environment support (dev/prod) with AWS SAM
- DynamoDB for scalable persistence with TTL cleanup
- Async Lambda processing to handle Slack timeouts

### Areas for Improvement
- FreshService tools lack ticket updates and workflow automation
- Limited real-world IT scenarios (password resets, access requests, etc.)
- No audit logging for compliance
- Missing observability (CloudWatch metrics/alarms)
- Test coverage needs expansion
- Error handling could be more granular

---

## FreshService MCP Toolset Expansion

### Priority 1: Ticket Management Enhancement

#### 1.1 Update Ticket Tool
**File:** `src/integrations/freshservice/tickets.py`

```python
def update_ticket(
    ticket_id: int,
    status: Optional[int] = None,
    priority: Optional[int] = None,
    description: Optional[str] = None,
    agent_id: Optional[int] = None,
    group_id: Optional[int] = None,
    custom_fields: Optional[dict] = None
) -> dict:
    """Update an existing ticket's properties."""
```

**Use Cases:**
- Escalate ticket priority based on user feedback
- Update ticket status after troubleshooting
- Reassign tickets to different agents/groups

#### 1.2 Add Ticket Note/Reply Tool
**File:** `src/integrations/freshservice/tickets.py`

```python
def add_ticket_note(
    ticket_id: int,
    body: str,
    private: bool = True,
    notify_emails: Optional[List[str]] = None
) -> dict:
    """Add a note or reply to an existing ticket."""
```

**Use Cases:**
- Document troubleshooting steps taken
- Add internal notes for ticket history
- Send updates to requesters

#### 1.3 Ticket Conversation History Tool
**File:** `src/integrations/freshservice/tickets.py`

```python
def get_ticket_conversations(
    ticket_id: int,
    include_private: bool = True
) -> List[dict]:
    """Get all conversations/notes on a ticket."""
```

**Use Cases:**
- Review previous troubleshooting attempts
- Understand full ticket context before responding

### Priority 2: Service Catalog Integration

#### 2.1 List Service Items Tool
**File:** `src/integrations/freshservice/service_catalog.py` (new)

```python
def list_service_items(
    category_id: Optional[int] = None,
    search_query: Optional[str] = None
) -> List[dict]:
    """List available service catalog items."""
```

**Use Cases:**
- Help users find the right service request form
- Browse available IT services

#### 2.2 Create Service Request Tool
**File:** `src/integrations/freshservice/service_catalog.py`

```python
def create_service_request(
    service_item_id: int,
    requester_email: str,
    requested_for_email: Optional[str] = None,
    custom_fields: Optional[dict] = None
) -> dict:
    """Submit a service request from the catalog."""
```

**Use Cases:**
- New employee equipment requests
- Software license requests
- Access provisioning requests

### Priority 3: Problem Management

#### 3.1 List Problems Tool
**File:** `src/integrations/freshservice/problems.py` (new)

```python
def list_problems(
    status: Optional[int] = None,
    priority: Optional[int] = None,
    limit: int = 10
) -> List[dict]:
    """List known problems affecting services."""
```

**Use Cases:**
- Check for known issues before creating tickets
- Inform users about ongoing problems

#### 3.2 Link Ticket to Problem Tool
```python
def link_ticket_to_problem(
    ticket_id: int,
    problem_id: int
) -> dict:
    """Associate a ticket with a known problem."""
```

### Priority 4: Asset Management Enhancement

#### 4.1 Asset Software Inventory Tool
**File:** `src/integrations/freshservice/assets.py`

```python
def get_asset_software(
    asset_id: int
) -> List[dict]:
    """Get software installed on an asset."""
```

#### 4.2 Asset Contracts/Warranties Tool
```python
def get_asset_contracts(
    asset_id: int
) -> List[dict]:
    """Get warranty and contract info for an asset."""
```

**Use Cases:**
- Check if device is under warranty before repair
- Verify software licensing compliance

### Priority 5: Workflow Automation

#### 5.1 Trigger Automation Rule Tool
**File:** `src/integrations/freshservice/automations.py` (new)

```python
def trigger_workflow(
    workflow_id: int,
    context: dict
) -> dict:
    """Trigger a predefined workflow automation."""
```

**Use Cases:**
- Password reset workflows
- Onboarding automation
- Standard change implementations

---

## Real-World Use Case Enhancements

### 1. Password Reset Workflow

**Current Gap:** No password reset capability

**Proposed Implementation:**

```python
# src/core/workflows/password_reset.py

class PasswordResetWorkflow:
    """Multi-step password reset with verification."""

    async def initiate(self, user_email: str) -> dict:
        """Start password reset process."""
        # 1. Verify user identity via Slack
        # 2. Check for recent reset attempts (security)
        # 3. Trigger reset via Active Directory/Intune
        # 4. Create audit ticket in FreshService
        # 5. Notify user with temporary password/link

    async def verify_identity(self, user_id: str, verification_code: str) -> bool:
        """Verify user identity before reset."""
```

**MCP Tool Addition:**
```python
def initiate_password_reset(
    user_email: str,
    reason: str
) -> dict:
    """Start password reset workflow with audit trail."""
```

### 2. Access Request Workflow

**Current Gap:** No access provisioning

**Proposed Implementation:**

```python
# src/core/workflows/access_request.py

class AccessRequestWorkflow:
    """Handle software/system access requests."""

    async def request_access(
        self,
        user_email: str,
        system_name: str,
        access_level: str,
        business_justification: str
    ) -> dict:
        """Create access request with approval workflow."""
        # 1. Validate system exists in catalog
        # 2. Check if user already has access
        # 3. Create service request in FreshService
        # 4. Notify approvers
        # 5. Track approval status
```

**MCP Tool Additions:**
```python
def request_system_access(
    system_name: str,
    access_level: str,
    justification: str
) -> dict:
    """Submit access request for approval."""

def check_access_status(
    request_id: int
) -> dict:
    """Check status of pending access request."""
```

### 3. Device Troubleshooting Workflow

**Current Gap:** Basic reboot only

**Proposed Enhancements:**

```python
# Enhanced IntuneTools in src/integrations/mcp_tools.py

class IntuneTools:
    def get_device_status(self, serial_number: str) -> dict:
        """Get device health, compliance, and last check-in."""

    def sync_device(self, serial_number: str) -> dict:
        """Force Intune policy sync."""

    def get_device_apps(self, serial_number: str) -> List[dict]:
        """Get installed apps and pending installations."""

    def trigger_app_install(self, serial_number: str, app_id: str) -> dict:
        """Push app installation to device."""
```

### 4. Incident Response Workflow

**Current Gap:** No incident classification/routing

**Proposed Implementation:**

```python
# src/core/workflows/incident_response.py

class IncidentResponseWorkflow:
    """Automated incident classification and routing."""

    async def classify_incident(self, description: str) -> dict:
        """Use AI to classify incident type and severity."""
        # 1. Analyze description with Gemini
        # 2. Match to known problem patterns
        # 3. Suggest category and priority
        # 4. Identify relevant KB articles

    async def auto_route(self, ticket_id: int, classification: dict) -> dict:
        """Route ticket to appropriate team based on classification."""
```

### 5. User Onboarding Support

**Current Gap:** No onboarding assistance

**Proposed Implementation:**

```python
def get_onboarding_checklist(
    department: str,
    role: str
) -> dict:
    """Get personalized onboarding checklist for new employee."""
    # Returns checklist of:
    # - Required software
    # - Access requests needed
    # - Training links
    # - Equipment to expect
```

### 6. Proactive Outage Communication

**Current Gap:** Reactive only

**Proposed Enhancement:**

```python
# src/core/proactive_alerts.py

class ProactiveAlertService:
    """Monitor for issues and proactively notify affected users."""

    async def check_for_alerts(self) -> List[dict]:
        """Check FreshService for active incidents/changes."""

    async def notify_affected_users(self, alert: dict) -> None:
        """Proactively message users about ongoing issues."""
```

---

## Security Improvements

### 1. Audit Logging

**Current Gap:** No comprehensive audit trail

**Proposed Implementation:**

```python
# src/security/audit_logger.py

class AuditLogger:
    """Comprehensive audit logging for compliance."""

    def log_action(
        self,
        action_type: str,  # TOOL_CALL, AUTH_CHECK, TICKET_CREATE, etc.
        user_id: str,
        details: dict,
        outcome: str,  # SUCCESS, FAILURE, DENIED
        sensitive: bool = False
    ) -> None:
        """Log action to audit table and CloudWatch."""
```

**DynamoDB Table:** `{env}-AuditLog`
- PK: `ACTION#{action_type}`
- SK: `{timestamp}#{uuid}`
- GSI: `UserIndex` on `user_id`
- TTL: 365 days (compliance retention)

### 2. Sensitive Action Approval

**Current Gap:** Only reboot requires confirmation

**Proposed Enhancement:**

```python
# src/security/approval_manager.py

class ApprovalManager:
    """Multi-level approval for sensitive actions."""

    SENSITIVE_ACTIONS = {
        'reboot_device': 'user_confirm',
        'create_ticket': 'auto',
        'update_ticket': 'auto',
        'password_reset': 'manager_approve',
        'access_request': 'manager_approve',
        'bulk_operations': 'admin_approve'
    }

    async def request_approval(
        self,
        action: str,
        requester: str,
        context: dict
    ) -> ApprovalResult:
        """Get appropriate approval for action."""
```

### 3. Input Validation Enhancement

**Current Gap:** Basic sanitization only

**Proposed Enhancement:**

```python
# src/security/validators.py

class InputValidator:
    """Comprehensive input validation."""

    def validate_email(self, email: str) -> bool:
        """Validate email format and domain."""

    def validate_ticket_id(self, ticket_id: int) -> bool:
        """Validate ticket ID format and range."""

    def validate_serial_number(self, serial: str) -> bool:
        """Validate device serial number format."""

    def sanitize_user_input(self, text: str) -> str:
        """Remove potential injection attempts."""
```

### 4. Secret Rotation Support

**Current Gap:** Static secrets

**Proposed Enhancement:**

```python
# src/config.py additions

class Config:
    _secret_refresh_time: Optional[datetime] = None
    SECRET_REFRESH_INTERVAL = timedelta(hours=1)

    @classmethod
    def refresh_secrets_if_needed(cls) -> None:
        """Refresh secrets from Secrets Manager periodically."""
```

### 5. Data Classification

**Current Gap:** All data treated equally

**Proposed Enhancement:**

```python
# src/security/data_classifier.py

class DataClassifier:
    """Classify data sensitivity for handling."""

    PII_PATTERNS = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b[A-Z]{2}\d{6}\b',      # Employee ID
    ]

    def classify(self, text: str) -> DataClassification:
        """Classify text sensitivity level."""

    def redact_pii(self, text: str) -> str:
        """Redact PII from text for logging."""
```

---

## Codebase Quality Improvements

### 1. Test Coverage Expansion

**Current Gap:** Minimal tests in `tests/unit/test_security.py`

**Proposed Test Structure:**

```
tests/
├── unit/
│   ├── test_security.py           # Existing
│   ├── test_config.py             # Config loading and validation
│   ├── test_message_router.py     # Routing logic
│   ├── test_mcp_orchestrator.py   # Tool execution
│   ├── test_freshservice_tools.py # Each FS tool
│   ├── test_models.py             # Data model validation
│   └── test_validators.py         # Input validation
├── integration/
│   ├── test_slack_events.py       # Lambda handler
│   ├── test_dynamodb_storage.py   # Storage operations
│   └── test_freshservice_api.py   # API integration (mocked)
└── fixtures/
    ├── slack_events.json          # Sample events
    ├── freshservice_responses.json
    └── gemini_responses.json
```

**Coverage Target:** 80%+

### 2. Type Hints and Documentation

**Current Gap:** Inconsistent typing

**Proposed Enhancement:**

```python
# Add comprehensive type hints throughout

from typing import TypedDict, Literal, Optional

class TicketInfo(TypedDict):
    id: int
    subject: str
    status: Literal['open', 'pending', 'resolved', 'closed']
    priority: Literal[1, 2, 3, 4]
    requester_id: int

def create_ticket(
    subject: str,
    description: str,
    requester_email: str,
    priority: Literal[1, 2, 3, 4] = 2
) -> TicketInfo:
    """
    Create a new ticket in FreshService.

    Args:
        subject: Brief ticket title
        description: Detailed issue description
        requester_email: Email of the person reporting
        priority: 1=Low, 2=Medium, 3=High, 4=Urgent

    Returns:
        Created ticket information including ID

    Raises:
        ExternalAPIError: If FreshService API call fails
        ValidationError: If inputs are invalid
    """
```

### 3. Error Handling Refinement

**Current Gap:** Generic exception handling

**Proposed Enhancement:**

```python
# src/exceptions.py additions

class ToolExecutionError(BotException):
    """Error during MCP tool execution."""
    def __init__(self, tool_name: str, message: str, recoverable: bool = True):
        self.tool_name = tool_name
        self.recoverable = recoverable
        super().__init__(f"Tool '{tool_name}' failed: {message}")

class ValidationError(BotException):
    """Input validation failure."""
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation failed for '{field}': {message}")

class QuotaExceededError(BotException):
    """API quota exceeded."""
    def __init__(self, service: str, retry_after: Optional[int] = None):
        self.service = service
        self.retry_after = retry_after
        super().__init__(f"{service} quota exceeded")
```

### 4. Configuration Validation

**Current Gap:** Runtime failures for missing config

**Proposed Enhancement:**

```python
# src/config.py additions

class ConfigValidator:
    """Validate configuration at startup."""

    REQUIRED_SECRETS = ['SLACK_BOT_TOKEN', 'SLACK_SIGNING_SECRET', 'GEMINI_API_KEY']
    OPTIONAL_SECRETS = ['FRESHSERVICE_API_KEY', 'INTUNE_WEBHOOK_URL']

    @classmethod
    def validate_all(cls) -> List[str]:
        """Validate all configuration and return warnings."""
        warnings = []
        for secret in cls.REQUIRED_SECRETS:
            if not getattr(Config, secret, None):
                raise ConfigurationError(f"Missing required: {secret}")
        for secret in cls.OPTIONAL_SECRETS:
            if not getattr(Config, secret, None):
                warnings.append(f"Optional config missing: {secret}")
        return warnings
```

### 5. Code Documentation

**Proposed:** Add module-level docstrings and update README

```python
# src/integrations/mcp_integration.py

"""
MCP (Model Context Protocol) Integration Module

This module implements the GeminiMCPOrchestrator which connects Google Gemini AI
with IT service tools (FreshService, Intune) using the MCP pattern.

The orchestrator:
1. Receives user queries with context (email, conversation history)
2. Presents available tools to Gemini with schemas
3. Executes tool calls and feeds results back
4. Iterates until Gemini provides a final response

Architecture:
    User Query -> Gemini (with tools) -> Tool Execution -> Gemini -> Response

Key Classes:
    GeminiMCPOrchestrator: Main orchestrator combining AI with tools

Usage:
    orchestrator = GeminiMCPOrchestrator()
    response = await orchestrator.process_query(
        query="Check my open tickets",
        user_email="user@company.com"
    )
"""
```

---

## Operational Enhancements

### 1. CloudWatch Observability

**Current Gap:** Basic logging only

**Proposed Enhancement:**

```python
# src/observability/metrics.py

class MetricsPublisher:
    """Publish custom metrics to CloudWatch."""

    def record_tool_execution(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool
    ) -> None:
        """Record tool execution metrics."""

    def record_ai_latency(
        self,
        model: str,
        duration_ms: float,
        tokens_used: int
    ) -> None:
        """Record AI call latency and token usage."""

    def record_user_interaction(
        self,
        interaction_type: str,  # message, button_click, etc.
        user_id: str
    ) -> None:
        """Record user interaction metrics."""
```

**CloudWatch Alarms:**
- Error rate > 5% in 5 minutes
- P99 latency > 30 seconds
- Rate limit hits > 10/minute
- Tool failure rate > 10%

### 2. Health Check Enhancement

**Current Gap:** Basic connectivity check

**Proposed Enhancement:**

```python
# src/handlers/health.py enhancements

def comprehensive_health_check() -> dict:
    """Comprehensive health check for all dependencies."""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'components': {
            'secrets_manager': check_secrets_access(),
            'dynamodb': check_dynamodb_connectivity(),
            'freshservice': check_freshservice_api(),
            'gemini': check_gemini_api(),
            'slack': check_slack_api()
        },
        'version': Config.VERSION,
        'environment': Config.ENVIRONMENT
    }
```

### 3. Graceful Degradation

**Current Gap:** Binary success/failure

**Proposed Enhancement:**

```python
# src/core/degradation.py

class DegradationManager:
    """Handle service degradation gracefully."""

    SERVICE_STATUS = {}

    @classmethod
    def mark_degraded(cls, service: str, reason: str) -> None:
        """Mark a service as degraded."""
        cls.SERVICE_STATUS[service] = {'status': 'degraded', 'reason': reason}

    @classmethod
    def get_available_tools(cls) -> List[str]:
        """Get list of tools based on service availability."""
        available = []
        if cls.SERVICE_STATUS.get('freshservice', {}).get('status') != 'down':
            available.extend(FRESHSERVICE_TOOLS)
        if cls.SERVICE_STATUS.get('intune', {}).get('status') != 'down':
            available.extend(INTUNE_TOOLS)
        return available
```

### 4. Request Tracing

**Current Gap:** No correlation IDs

**Proposed Enhancement:**

```python
# src/observability/tracing.py

import uuid

class RequestTracer:
    """Add correlation IDs for request tracing."""

    @staticmethod
    def generate_trace_id() -> str:
        return str(uuid.uuid4())[:8]

    @staticmethod
    def inject_trace_id(logger, trace_id: str) -> None:
        """Inject trace ID into all log messages."""

# Usage in handlers
trace_id = RequestTracer.generate_trace_id()
logger.info(f"[{trace_id}] Processing message from {user_id}")
```

### 5. Conversation Analytics

**Current Gap:** No usage analytics

**Proposed Enhancement:**

```python
# src/analytics/conversation_analytics.py

class ConversationAnalytics:
    """Track conversation patterns and tool usage."""

    def record_query(
        self,
        user_id: str,
        query_type: str,  # ticket, asset, kb_search, etc.
        tools_used: List[str],
        resolution: str  # answered, escalated, ticket_created
    ) -> None:
        """Record query for analytics."""

    def get_popular_queries(self, days: int = 7) -> List[dict]:
        """Get most common query types."""

    def get_tool_usage_stats(self, days: int = 7) -> dict:
        """Get tool usage statistics."""
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
**Focus:** Security and observability groundwork

| Task | Priority | Effort |
|------|----------|--------|
| Add audit logging infrastructure | High | 3 days |
| Implement CloudWatch metrics | High | 2 days |
| Add request tracing | Medium | 1 day |
| Enhance health checks | Medium | 1 day |
| Add comprehensive input validation | High | 2 days |

### Phase 2: FreshService Expansion (Week 3-4)
**Focus:** Core tool expansion

| Task | Priority | Effort |
|------|----------|--------|
| Add ticket update tool | High | 2 days |
| Add ticket notes/conversations tool | High | 2 days |
| Add service catalog tools | Medium | 3 days |
| Add problem management tools | Medium | 2 days |
| Unit tests for new tools | High | 2 days |

### Phase 3: Real-World Workflows (Week 5-6)
**Focus:** Practical use cases

| Task | Priority | Effort |
|------|----------|--------|
| Password reset workflow | High | 3 days |
| Access request workflow | High | 3 days |
| Enhanced device troubleshooting | Medium | 2 days |
| Incident classification | Medium | 2 days |

### Phase 4: Code Quality (Week 7-8)
**Focus:** Maintainability

| Task | Priority | Effort |
|------|----------|--------|
| Comprehensive type hints | Medium | 2 days |
| Module documentation | Medium | 2 days |
| Test coverage to 80%+ | High | 4 days |
| Error handling refinement | Medium | 2 days |

### Phase 5: Advanced Features (Week 9-10)
**Focus:** Operational excellence

| Task | Priority | Effort |
|------|----------|--------|
| Graceful degradation | Medium | 2 days |
| Conversation analytics | Low | 2 days |
| Proactive alerts | Low | 3 days |
| User onboarding support | Low | 2 days |

---

## Success Metrics

### Tool Usage
- [ ] 25+ MCP tools available (currently 15)
- [ ] 90%+ tool execution success rate
- [ ] <2s average tool response time

### Security
- [ ] 100% of actions audit logged
- [ ] Zero PII in logs
- [ ] Sensitive actions require approval

### Quality
- [ ] 80%+ test coverage
- [ ] 100% type hint coverage
- [ ] Zero critical security findings

### Operations
- [ ] <5% error rate
- [ ] P99 latency <30s
- [ ] 99.9% uptime

---

## File Changes Summary

### New Files to Create
```
src/
├── security/
│   ├── audit_logger.py
│   ├── validators.py
│   └── approval_manager.py
├── integrations/freshservice/
│   ├── service_catalog.py
│   ├── problems.py
│   └── automations.py
├── core/workflows/
│   ├── __init__.py
│   ├── password_reset.py
│   ├── access_request.py
│   └── incident_response.py
├── observability/
│   ├── __init__.py
│   ├── metrics.py
│   └── tracing.py
└── analytics/
    └── conversation_analytics.py

tests/
├── unit/
│   ├── test_config.py
│   ├── test_message_router.py
│   ├── test_mcp_orchestrator.py
│   ├── test_freshservice_tools.py
│   └── test_validators.py
└── integration/
    ├── test_slack_events.py
    └── test_dynamodb_storage.py
```

### Files to Modify
```
src/
├── config.py                    # Add validation, secret refresh
├── exceptions.py                # Add new exception types
├── integrations/
│   ├── mcp_integration.py       # Add new tools, metrics
│   ├── mcp_tools.py             # Register new tools
│   └── freshservice/
│       ├── tickets.py           # Add update, notes tools
│       └── assets.py            # Add software, contracts tools
├── handlers/
│   └── health.py                # Enhanced health checks
└── security/
    └── sanitizer.py             # Enhanced validation
```

---

## Appendix: Tool Schemas for New FreshService Tools

### update_ticket
```json
{
  "name": "update_ticket",
  "description": "Update an existing ticket's status, priority, or assignment",
  "parameters": {
    "type": "object",
    "properties": {
      "ticket_id": {"type": "integer", "description": "The ticket ID to update"},
      "status": {"type": "integer", "description": "New status (2=Open, 3=Pending, 4=Resolved, 5=Closed)"},
      "priority": {"type": "integer", "description": "New priority (1=Low, 2=Medium, 3=High, 4=Urgent)"},
      "agent_id": {"type": "integer", "description": "Assign to agent ID"},
      "group_id": {"type": "integer", "description": "Assign to group ID"}
    },
    "required": ["ticket_id"]
  }
}
```

### add_ticket_note
```json
{
  "name": "add_ticket_note",
  "description": "Add a note or reply to an existing ticket",
  "parameters": {
    "type": "object",
    "properties": {
      "ticket_id": {"type": "integer", "description": "The ticket ID"},
      "body": {"type": "string", "description": "Note content in HTML or plain text"},
      "private": {"type": "boolean", "description": "If true, note is internal only"}
    },
    "required": ["ticket_id", "body"]
  }
}
```

### request_system_access
```json
{
  "name": "request_system_access",
  "description": "Submit an access request for a system or application",
  "parameters": {
    "type": "object",
    "properties": {
      "system_name": {"type": "string", "description": "Name of system to access"},
      "access_level": {"type": "string", "enum": ["read", "write", "admin"]},
      "justification": {"type": "string", "description": "Business reason for access"}
    },
    "required": ["system_name", "access_level", "justification"]
  }
}
```

---

*Document Version: 1.0*
*Created: 2026-01-29*
*Branch: claude/plan-git-agent-improvements-3xoNl*
