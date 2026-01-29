# Phase 4 Quick Reference Guide

## Configuration Validation

### Usage
```python
# At application startup (Lambda handler, etc.)
from src.config import Config, ConfigValidator

Config.load()
ConfigValidator.validate_and_log()  # Validates and logs warnings/errors
```

### What It Validates
- ✅ Required secrets: SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, GEMINI_API_KEY
- ✅ Optional secrets: FRESHSERVICE_API_KEY, FRESHSERVICE_DOMAIN, INTUNE_REBOOT_WEBHOOK_URL
- ✅ Numeric settings must be positive (rate limits, history limits)
- ✅ FreshService consistency (domain + API key must both be present/absent)
- ✅ Channel IDs are non-empty strings
- ✅ Empty/whitespace strings treated as missing

### Output Examples
```
✓ Configuration validation passed
Enabled integrations: Gemini, FreshService
⚠ Optional configuration missing: INTUNE_REBOOT_WEBHOOK_URL (Intune device management will be disabled)
```

---

## New Exception Types

### ToolExecutionError
**Use Case:** MCP tool execution failures

```python
from src.exceptions import ToolExecutionError

try:
    result = self._tickets.create_ticket(...)
except Exception as e:
    raise ToolExecutionError(
        tool_name="create_ticket",
        message=str(e),
        recoverable=True  # False if permanent failure
    )
```

**Attributes:**
- `tool_name` (str): Name of the tool that failed
- `recoverable` (bool): Whether error is transient

---

### ValidationError
**Use Case:** Input validation failures

```python
from src.exceptions import ValidationError

def validate_email(email: str):
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        raise ValidationError(
            field="email",
            message="Invalid email format"
        )
```

**Attributes:**
- `field` (str): Name of the field that failed validation

---

### QuotaExceededError
**Use Case:** API quota limits exceeded

```python
from src.exceptions import QuotaExceededError

if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 3600))
    raise QuotaExceededError(
        service="Gemini",
        retry_after=retry_after  # Optional, in seconds
    )
```

**Attributes:**
- `service` (str): Name of the service with quota exceeded
- `retry_after` (Optional[int]): Seconds until retry allowed

---

### ConfigurationError
**Use Case:** Configuration errors detected at startup

```python
from src.exceptions import ConfigurationError

if not api_key:
    raise ConfigurationError("Missing API key in configuration")
```

**Attributes:** None (just the message)

---

## Exception Hierarchy

```
Exception
  └─ BotException (base for all bot exceptions)
       ├─ AuthorizationError
       ├─ IntegrationNotConfiguredError
       ├─ InvalidCommandError
       ├─ StorageError
       ├─ ExternalAPIError
       ├─ RateLimitError
       ├─ SessionNotFoundError
       ├─ ToolExecutionError          [NEW]
       ├─ ValidationError              [NEW]
       ├─ QuotaExceededError           [NEW]
       └─ ConfigurationError           [NEW]
```

**All exceptions have:**
- `user_friendly_message` - Suitable for display in Slack
- Context attributes - Relevant error details
- Type hints - Complete type annotations

---

## Running Tests

### Installation
```bash
# Option 1: Virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install pytest pytest-cov

# Option 2: System-wide (requires elevated permissions)
pip3 install --break-system-packages pytest pytest-cov

# Option 3: Use apt (Debian/Ubuntu)
sudo apt install python3-pytest python3-pytest-cov
```

### Run All Tests
```bash
python3 -m pytest tests/unit/ -v
```

### Run Specific Test File
```bash
python3 -m pytest tests/unit/test_config.py -v
python3 -m pytest tests/unit/test_exceptions.py -v
python3 -m pytest tests/unit/test_freshservice_tools.py -v
```

### Run with Coverage
```bash
python3 -m pytest tests/unit/ --cov=src --cov-report=html
```

### Run Single Test
```bash
python3 -m pytest tests/unit/test_config.py::TestConfigValidator::test_missing_required_config_raises_error -v
```

---

## Test Files Overview

### test_config.py (18 tests)
**Tests:**
- Environment variable loading
- Table name prefixing
- Integration enabled checks
- ConfigValidator required secret validation
- ConfigValidator optional secret warnings
- Invalid configuration detection
- Empty/whitespace string handling

**Key Assertions:**
- Missing required config raises ConfigurationError
- Optional missing config returns warnings
- FreshService partial config raises error
- Invalid numeric settings raise errors

### test_exceptions.py (30+ tests)
**Tests:**
- All 12 exception types
- User-friendly message generation
- Exception attributes
- Inheritance hierarchy
- Message formatting

**Key Assertions:**
- All exceptions inherit from BotException
- All have user_friendly_message attribute
- Context attributes are set correctly
- Default parameters work as expected

### test_freshservice_tools.py (20+ tests)
**Tests:**
- Tool initialization
- execute_tool() dispatch
- Requester email lookup
- Invalid parameters/tool names
- Phase 2 tool operations
- Asset enhancements
- Problem management

**Key Assertions:**
- All 7 tool modules initialized
- All Phase 2 tools registered
- Original tools still work
- Error handling for invalid inputs

---

## Integration Checklist

### For Lambda Handlers
```python
# handlers/slack_events.py
from src.config import Config, ConfigValidator
from src.exceptions import ConfigurationError

def lambda_handler(event, context):
    try:
        Config.load()
        ConfigValidator.validate_and_log()
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return {"statusCode": 500, "body": "Configuration error"}
    
    # ... rest of handler
```

### For Error Handling
```python
from src.exceptions import ToolExecutionError, ValidationError

try:
    # Execute tool
    result = tools.execute_tool(tool_name, params)
except ValidationError as e:
    # Handle validation error (user input problem)
    return f"Invalid input: {e.user_friendly_message}"
except ToolExecutionError as e:
    # Handle tool execution error
    if e.recoverable:
        return f"Temporary error: {e.user_friendly_message}"
    else:
        return f"Permanent error: {e.user_friendly_message}"
except Exception as e:
    # Fallback for unexpected errors
    return "An unexpected error occurred"
```

---

## Type Hints Quick Reference

### Function Return Types
```python
def validate_all() -> List[str]:
    """Returns list of warnings."""
    pass

def validate_and_log() -> None:
    """Returns nothing."""
    pass
```

### Optional Parameters
```python
from typing import Optional

def __init__(self, retry_after: Optional[int] = None) -> None:
    self.retry_after = retry_after
```

### Type Aliases
```python
from typing import List, Dict, Any, Optional

# Common patterns
warnings: List[str] = []
config: Dict[str, Any] = {}
value: Optional[str] = None
```

---

## Best Practices

### Configuration Validation
✅ DO: Call `ConfigValidator.validate_and_log()` at startup  
❌ DON'T: Skip validation and fail during user interactions

### Exception Handling
✅ DO: Use specific exception types for specific errors  
❌ DON'T: Catch `Exception` broadly without re-raising

### Testing
✅ DO: Run tests before committing code  
❌ DON'T: Skip tests when adding new tools/features

### Type Hints
✅ DO: Add type hints to all new functions  
❌ DON'T: Use `Any` type without good reason

### Documentation
✅ DO: Add docstrings to complex modules  
❌ DON'T: Leave code undocumented for future developers

---

## Troubleshooting

### ConfigurationError at Startup
**Problem:** Missing required configuration  
**Solution:** Check AWS Secrets Manager or environment variables

### Test Import Errors
**Problem:** `ModuleNotFoundError: No module named 'src'`  
**Solution:** Run tests from project root: `python3 -m pytest tests/unit/`

### Pytest Not Found
**Problem:** `python3: No module named pytest`  
**Solution:** Install pytest (see Installation section above)

### Type Hint Errors
**Problem:** `NameError: name 'Optional' is not defined`  
**Solution:** Add `from typing import Optional` at top of file

---

## Summary

Phase 4 delivered:
- ✅ 4 new exception types with full type hints
- ✅ ConfigValidator for startup validation
- ✅ 68+ tests across 3 test files
- ✅ Enhanced documentation for 2 major modules
- ✅ Type hints for all exception classes
- ✅ Zero breaking changes to existing code

All code compiles without errors and is ready for deployment.
