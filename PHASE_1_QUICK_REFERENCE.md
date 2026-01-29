# Phase 1 Quick Reference Guide

## Cost-Optimized Configuration Templates

### 🟢 Production (Recommended)
**Balance between observability and cost**

```python
# src/config.py or initialization
from src.security.audit_logger import AuditLogger
from src.observability.metrics import initialize_metrics

# Audit with 10% metric sampling
audit_logger = AuditLogger(
    table_name="prod-AuditLog",
    retention_days=365,
    enable_metrics=True,
    metric_sample_rate=0.1  # Critical events always logged
)

# Metrics with auto-batching
metrics = initialize_metrics(
    namespace="SystemsBot",
    enable_metrics=True,
    auto_flush_seconds=60
)

# Monthly cost: ~$2/1k requests
```

### 🟡 Development
**Minimal costs for testing**

```python
# Disable metrics completely
audit_logger = AuditLogger(
    table_name="dev-AuditLog",
    retention_days=30,
    enable_metrics=False
)

metrics = initialize_metrics(
    namespace="SystemsBot-Dev",
    enable_metrics=False
)

# Monthly cost: ~$0.90/1k requests
```

### 🔴 High Traffic (>10k/day)
**Aggressive cost optimization**

```python
# 1% metric sampling
audit_logger = AuditLogger(
    table_name="prod-AuditLog",
    retention_days=365,
    enable_metrics=True,
    metric_sample_rate=0.01  # 1% sampling
)

# Longer flush intervals
metrics = initialize_metrics(
    namespace="SystemsBot",
    enable_metrics=True,
    auto_flush_seconds=120  # 2 minutes
)

# Monthly cost: ~$10/10k requests
```

---

## Usage Examples

### Audit Logging

```python
from src.security.audit_logger import AuditLogger, ActionType, Outcome

audit = AuditLogger()

# Log tool execution
audit.log_tool_call(
    user_id="U12345",
    tool_name="create_ticket",
    parameters={"subject": "Issue", "priority": 2},
    outcome=Outcome.SUCCESS,
    response_summary="Ticket #12345 created"
)

# Log auth check
audit.log_auth_check(
    user_id="U12345",
    action="update_ticket",
    outcome=Outcome.DENIED,
    reason="User not in authorized group"
)

# Query audit trail
user_history = audit.get_user_audit_trail(
    user_id="U12345",
    days=7,
    limit=50
)
```

### Metrics Collection

```python
from src.observability.metrics import get_metrics_collector

metrics = get_metrics_collector()

# Record tool invocation
metrics.record_tool_invocation(
    tool_name="search_kb",
    success=True,
    duration_ms=234.5,
    user_id="U12345"
)

# Record error
metrics.record_error(
    error_type="ValidationError",
    component="ticket_validator",
    severity="ERROR"
)

# Measure operation duration
with metrics.measure_duration('api_call', [{'Name': 'Service', 'Value': 'FreshService'}]):
    # perform operation
    result = api_client.get_ticket(123)

# Manual flush (optional, auto-flushes every 60s)
metrics.flush()
```

### Request Tracing

```python
from src.observability.tracing import set_trace_id, generate_trace_id, TracedOperation

# At handler entry
trace_id = generate_trace_id()
set_trace_id(trace_id)

# All logs will include trace_id automatically
logger.info("Processing message")  # [abc12345] Processing message

# Trace specific operations
with TracedOperation('tool_execution', tool='search_kb') as span:
    result = execute_tool()
    span.set_attribute('result_count', len(result))
```

### Input Validation

```python
from src.security.validators import InputValidator, ValidationError

validator = InputValidator()

try:
    # Validate email
    validator.validate_email(
        "user@company.com",
        allowed_domains=["company.com"]
    )
    
    # Validate ticket ID
    ticket_id = validator.validate_ticket_id("12345")
    
    # Sanitize user input
    safe_text = validator.sanitize_user_input(user_message)
    
    # Validate custom fields
    custom_fields = validator.validate_custom_fields({
        "department": "IT",
        "location": "Building A"
    })
    
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    # Handle validation error
```

### Health Checks

```python
# Basic health (fast, no external calls)
GET /health

# Detailed health (AWS services only)
GET /health?detailed=true

# Full health (includes FreshService API)
GET /health?detailed=true&external=true

# Response example:
{
  "status": "healthy",
  "environment": "prod",
  "version": "1.0.0",
  "checks": {
    "dynamodb": {
      "status": "healthy",
      "response_time_ms": 12.3
    },
    "freshservice": {
      "status": "skipped",
      "message": "Use ?external=true to check"
    }
  }
}
```

---

## Integration Checklist

### ✅ Lambda Handler Setup

```python
import logging
from src.observability.tracing import set_trace_id, generate_trace_id, setup_trace_logging
from src.observability.metrics import get_metrics_collector
from src.security.audit_logger import AuditLogger

# Setup logging with trace IDs
logger = logging.getLogger()
setup_trace_logging(logger)

def lambda_handler(event, context):
    # Generate trace ID
    trace_id = generate_trace_id()
    set_trace_id(trace_id)
    
    # Get metrics and audit instances
    metrics = get_metrics_collector()
    audit = AuditLogger()
    
    try:
        # Your handler logic
        result = process_event(event)
        
        # Record success
        metrics.record_message_processed(
            message_type="slack_event",
            processing_time_ms=123.4,
            success=True
        )
        
        return result
        
    except Exception as e:
        # Record error
        metrics.record_error(
            error_type=type(e).__name__,
            component="lambda_handler",
            severity="ERROR"
        )
        raise
    
    finally:
        # Flush metrics before Lambda exits
        metrics.flush()
```

### ✅ Tool Execution Wrapper

```python
from src.observability.tracing import TracedOperation
from src.observability.metrics import get_metrics_collector
from src.security.audit_logger import AuditLogger, ActionType, Outcome

async def execute_tool_with_observability(tool_name, parameters, user_id):
    metrics = get_metrics_collector()
    audit = AuditLogger()
    
    with TracedOperation('tool_execution', tool=tool_name) as span:
        start_time = time.time()
        
        try:
            # Execute tool
            result = await execute_tool(tool_name, parameters)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Record success
            metrics.record_tool_invocation(
                tool_name=tool_name,
                success=True,
                duration_ms=duration_ms,
                user_id=user_id
            )
            
            audit.log_tool_call(
                user_id=user_id,
                tool_name=tool_name,
                parameters=parameters,
                outcome=Outcome.SUCCESS,
                response_summary=f"Returned {len(result)} items"
            )
            
            span.set_attribute('result_count', len(result))
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Record failure
            metrics.record_tool_invocation(
                tool_name=tool_name,
                success=False,
                duration_ms=duration_ms,
                user_id=user_id
            )
            
            audit.log_tool_call(
                user_id=user_id,
                tool_name=tool_name,
                parameters=parameters,
                outcome=Outcome.FAILURE,
                error_message=str(e)
            )
            
            raise
```

---

## Cost Monitoring

### CloudWatch Dashboard Queries

```sql
-- Daily audit event count
SELECT SUM(AuditEvents) 
FROM SystemsBot/Audit 
WHERE ActionType != 'TOOL_CALL' 
GROUP BY ActionType

-- Metric API call volume
SELECT COUNT(*) as metric_calls
FROM CloudWatch/PutMetricData
WHERE Namespace = 'SystemsBot'

-- Average tool latency
SELECT AVG(ToolLatency) 
FROM SystemsBot 
GROUP BY ToolName
```

### Cost Alarms

```yaml
# Alert if audit volume is too high
AuditVolumeAlarm:
  MetricName: AuditEvents
  Threshold: 50000  # per day
  ComparisonOperator: GreaterThanThreshold
  
# Alert if metric API calls spike
MetricVolumeAlarm:
  MetricName: PutMetricData
  Threshold: 10000  # per day
  ComparisonOperator: GreaterThanThreshold
```

---

## Environment Variables

```bash
# Recommended environment variables
AUDIT_METRICS_ENABLED=true
AUDIT_SAMPLE_RATE=0.1
METRICS_ENABLED=true
METRICS_FLUSH_SECONDS=60
ENABLE_TRACING=true
HEALTH_EXTERNAL_CHECKS=false
```

---

## Troubleshooting

### Metrics Not Appearing

```python
# 1. Check if metrics are enabled
metrics = get_metrics_collector()
print(f"Metrics enabled: {metrics.enable_metrics}")

# 2. Manually flush
metrics.flush()

# 3. Check CloudWatch permissions
# IAM policy needs: cloudwatch:PutMetricData
```

### High Costs

```python
# 1. Reduce sampling rate
audit = AuditLogger(metric_sample_rate=0.01)  # 1%

# 2. Disable metrics in dev
metrics = initialize_metrics(enable_metrics=False)

# 3. Increase flush interval
metrics = MetricsCollector(auto_flush_seconds=120)
```

### Trace IDs Not Showing

```python
# Setup trace logging for your logger
from src.observability.tracing import setup_trace_logging

logger = logging.getLogger(__name__)
setup_trace_logging(logger)

# Ensure trace ID is set
from src.observability.tracing import set_trace_id, generate_trace_id
set_trace_id(generate_trace_id())
```

---

## Performance Tuning

### Minimize Latency

```python
# Use context managers for automatic timing
with metrics.measure_duration('operation'):
    perform_operation()

# Batch validations
validator = InputValidator()
errors = []
for field in fields:
    try:
        validator.validate_field(field)
    except ValidationError as e:
        errors.append(e)
```

### Reduce Memory Usage

```python
# Flush metrics more frequently in high-traffic scenarios
metrics = MetricsCollector(auto_flush_seconds=30)

# Limit audit query results
audit.get_user_audit_trail(user_id, days=7, limit=20)
```

---

## Best Practices

### ✅ DO

- Enable sampling in production (10% is good default)
- Use tiered health checks
- Flush metrics at end of Lambda execution
- Log critical events always (failures, auth denials)
- Validate all user inputs
- Generate trace IDs at handler entry

### ❌ DON'T

- Send individual CloudWatch metrics (use batching)
- Check external APIs on every health check
- Log passwords or tokens (auto-redacted but still)
- Skip input validation for "trusted" sources
- Disable audit logging entirely (needed for compliance)
- Forget to flush metrics before Lambda timeout

---

## Next Steps

1. ✅ Review cost analysis: [PHASE_1_COST_ANALYSIS.md](PHASE_1_COST_ANALYSIS.md)
2. ✅ Update CloudFormation with AuditLog table
3. ✅ Integrate into existing handlers
4. ✅ Set up CloudWatch alarms
5. ✅ Monitor costs for first week
6. ⏭️ Proceed to Phase 2: FreshService MCP Expansion
