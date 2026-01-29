# Phase 1 Infrastructure & Deployment Guide

## Infrastructure Changes Summary

### ✅ What Was Updated

#### 1. CloudFormation Template (template.yaml)
- **Added:** AuditLog DynamoDB table with GSIs
- **Added:** CloudWatch PutMetricData permissions to all Lambda functions
- **Added:** DynamoDB DescribeTable permissions to Health function
- **Added:** Secrets Manager DescribeSecret permission to Health function
- **Updated:** All Lambda functions now have access to AuditLog table
- **Added:** New CloudFormation outputs for monitoring

#### 2. New CloudWatch Alarms Template (cloudwatch-alarms.yaml)
- Optional monitoring stack
- Cost control alarms
- Error rate monitoring
- API failure detection
- Pre-built CloudWatch dashboard

---

## Deployment Instructions

### Prerequisites
- AWS SAM CLI installed
- AWS credentials configured
- Python 3.12 runtime available

### Step 1: Deploy Main Application Stack

#### Development Environment
```bash
# Build the application
sam build

# Deploy to dev
sam deploy --config-env dev

# Or with guided deployment
sam deploy --guided \
  --stack-name systems-bot-dev \
  --parameter-overrides Environment=dev
```

#### Production Environment
```bash
# Build the application
sam build

# Deploy to prod (will ask for confirmation)
sam deploy --config-env prod
```

### Step 2: Deploy CloudWatch Alarms (Optional but Recommended)

```bash
# Deploy alarms stack
aws cloudformation deploy \
  --template-file cloudwatch-alarms.yaml \
  --stack-name systems-bot-dev-monitoring \
  --parameter-overrides \
    Environment=dev \
    AlertEmail=your-email@company.com \
    HighCostThreshold=50000 \
  --capabilities CAPABILITY_IAM

# For production
aws cloudformation deploy \
  --template-file cloudwatch-alarms.yaml \
  --stack-name systems-bot-prod-monitoring \
  --parameter-overrides \
    Environment=prod \
    AlertEmail=ops-team@company.com \
    HighCostThreshold=100000 \
  --capabilities CAPABILITY_IAM
```

### Step 3: Verify Deployment

```bash
# Get the health endpoint
aws cloudformation describe-stacks \
  --stack-name systems-bot-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`HealthEndpoint`].OutputValue' \
  --output text

# Test basic health
curl https://YOUR_API_URL/health

# Test detailed health (AWS services only)
curl "https://YOUR_API_URL/health?detailed=true"

# Test full health (includes external APIs)
curl "https://YOUR_API_URL/health?detailed=true&external=true"
```

---

## New DynamoDB Table: AuditLog

### Schema
```yaml
TableName: ${Environment}-AuditLog
BillingMode: PAY_PER_REQUEST
Attributes:
  PK: ACTION#<ActionType>          # Partition key
  SK: <timestamp>#<uuid>           # Sort key
  user_id: <slack_user_id>         # GSI partition key
  resource_id: <ticket/asset_id>   # GSI partition key
  timestamp: <ISO8601>             # GSI sort key
  audit_id: <uuid>
  action_type: <enum>
  outcome: <enum>
  sensitive: <boolean>
  details: <json>
  ttl: <unix_timestamp>            # Auto-delete after 365 days

Indexes:
  - UserIndex: user_id + timestamp
  - ResourceIndex: resource_id + timestamp
```

### Cost Estimate
- **Storage:** $0.25/GB per month
- **Reads/Writes:** Pay per request
- **Expected:** ~$0.90/month for 1,000 requests/day

---

## IAM Permissions Added

### All Lambda Functions
```yaml
- cloudwatch:PutMetricData  # For metrics collection
- dynamodb:PutItem          # For audit logs
- dynamodb:Query            # For audit trail queries
- dynamodb:GetItem          # For audit lookups
```

### Health Function Additional
```yaml
- dynamodb:DescribeTable        # For health checks
- secretsmanager:DescribeSecret # For health checks
```

---

## CloudWatch Metrics Created

### Namespaces
- `SystemsBot/Audit` - Audit event metrics
- `SystemsBot` - Application metrics

### Key Metrics
| Metric Name | Namespace | Dimensions | Description |
|-------------|-----------|------------|-------------|
| AuditEvents | SystemsBot/Audit | ActionType, Outcome | Count of audit events |
| ToolInvocations | SystemsBot | ToolName, Status | Tool execution count |
| ToolLatency | SystemsBot | ToolName | Tool execution time (ms) |
| ToolSuccessRate | SystemsBot | ToolName | Tool success percentage |
| Errors | SystemsBot | ErrorType, Component, Severity | Error count |
| MessagesProcessed | SystemsBot | MessageType, Status | Message count |
| APILatency | SystemsBot | Service, Endpoint | External API latency |
| APISuccessRate | SystemsBot | Service | External API success rate |
| HealthCheck | SystemsBot | Service, Status | Health check results |

---

## CloudWatch Alarms Configured

### Cost Control
- **HighAuditVolumeAlarm**: Triggers when audit events >50k/day (configurable)
  - *Purpose:* Detect potential infinite loops or misconfiguration
  - *Action:* SNS notification

### Reliability
- **HighErrorRateAlarm**: Triggers when errors >100/hour
- **APIFailureRateAlarm**: Triggers when API success rate <95%
- **MessageProcessorErrorAlarm**: Lambda function errors >5 in 5 minutes
- **MessageProcessorThrottleAlarm**: Lambda function throttled
- **DynamoDBThrottleAlarm**: DynamoDB throttled operations

---

## CloudWatch Dashboard

Auto-created dashboard includes:
- Tool invocation volume and success rate
- Tool latency (avg, min, max)
- Error counts and audit events
- External API latency
- Lambda metrics (invocations, errors, duration)
- Recent error logs

**Access:** CloudWatch Console → Dashboards → `{env}-systems-bot-monitoring`

---

## Configuration Updates Needed

### Environment Variables (Optional)

Add to Lambda configuration for custom behavior:

```yaml
Environment:
  Variables:
    AUDIT_METRICS_ENABLED: "true"      # Enable/disable CloudWatch metrics
    AUDIT_SAMPLE_RATE: "0.1"           # 10% sampling rate
    METRICS_ENABLED: "true"            # Enable/disable all metrics
    METRICS_FLUSH_SECONDS: "60"        # Auto-flush interval
    ENABLE_TRACING: "true"             # Enable request tracing
```

### In Application Code

Update your handler initialization:

```python
import os
from src.security.audit_logger import AuditLogger
from src.observability.metrics import initialize_metrics

# Initialize with environment-based config
audit_logger = AuditLogger(
    table_name=f"{os.environ['ENVIRONMENT']}-AuditLog",
    enable_metrics=os.environ.get('AUDIT_METRICS_ENABLED', 'true').lower() == 'true',
    metric_sample_rate=float(os.environ.get('AUDIT_SAMPLE_RATE', '0.1'))
)

metrics = initialize_metrics(
    namespace="SystemsBot",
    enable_metrics=os.environ.get('METRICS_ENABLED', 'true').lower() == 'true',
    auto_flush_seconds=int(os.environ.get('METRICS_FLUSH_SECONDS', '60'))
)
```

---

## Rollback Plan

### If Issues Arise

1. **Disable Metrics via Environment Variables**
   ```bash
   aws lambda update-function-configuration \
     --function-name dev-message-processor \
     --environment "Variables={METRICS_ENABLED=false,AUDIT_METRICS_ENABLED=false}"
   ```

2. **Rollback to Previous Stack**
   ```bash
   sam deploy --config-env dev --no-confirm-changeset
   # Then manually deploy previous version
   ```

3. **Delete Alarms Stack**
   ```bash
   aws cloudformation delete-stack \
     --stack-name systems-bot-dev-monitoring
   ```

---

## Migration from Existing Deployment

### If You Have Existing Stack

1. **Backup Current Configuration**
   ```bash
   aws cloudformation get-template \
     --stack-name systems-bot-dev \
     --query TemplateBody > backup-template.yaml
   ```

2. **Deploy Updated Stack**
   ```bash
   sam build
   sam deploy --config-env dev
   ```
   
   CloudFormation will:
   - Create new AuditLog table
   - Update Lambda IAM roles
   - Add CloudWatch permissions
   - **No downtime** - rolling deployment

3. **Verify New Resources**
   ```bash
   # Check table created
   aws dynamodb describe-table --table-name dev-AuditLog
   
   # Check Lambda permissions
   aws lambda get-policy --function-name dev-message-processor
   ```

### No Existing Stack
Just follow normal deployment instructions above.

---

## Testing Infrastructure

### 1. Test DynamoDB Table
```bash
# List tables
aws dynamodb list-tables

# Describe audit table
aws dynamodb describe-table --table-name dev-AuditLog

# Should show:
# - Table exists
# - 2 GSIs (UserIndex, ResourceIndex)
# - TTL enabled on 'ttl' attribute
```

### 2. Test Lambda Permissions
```bash
# Get Lambda policy
aws lambda get-policy --function-name dev-message-processor | jq .

# Should include:
# - cloudwatch:PutMetricData
# - dynamodb access to AuditLog
```

### 3. Test Health Endpoint
```bash
# Basic health
curl https://YOUR_API/health | jq .

# Detailed health (includes DynamoDB check)
curl "https://YOUR_API/health?detailed=true" | jq .

# Full health (includes external APIs)
curl "https://YOUR_API/health?detailed=true&external=true" | jq .
```

### 4. Test Audit Logging
```bash
# Trigger a Slack event or use AWS SDK
import boto3
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('dev-AuditLog')

# Query recent events
response = table.query(
    KeyConditionExpression='PK = :pk',
    ExpressionAttributeValues={':pk': 'ACTION#TOOL_CALL'},
    Limit=10,
    ScanIndexForward=False
)
print(response['Items'])
```

### 5. Test CloudWatch Metrics
```bash
# List metrics
aws cloudwatch list-metrics --namespace SystemsBot

# Get metric statistics
aws cloudwatch get-metric-statistics \
  --namespace SystemsBot \
  --metric-name ToolInvocations \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

---

## Cost Monitoring

### Check Costs After 24 Hours

```bash
# Check CloudWatch API calls
aws cloudwatch get-metric-statistics \
  --namespace AWS/Usage \
  --metric-name CallCount \
  --dimensions Name=Service,Value=CloudWatch Name=Type,Value=API \
  --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum

# Check DynamoDB usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=dev-AuditLog \
  --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum
```

### Set Up Cost Alerts

```bash
# Enable AWS Budgets
aws budgets create-budget \
  --account-id YOUR_ACCOUNT_ID \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

---

## Troubleshooting

### Issue: Metrics Not Appearing in CloudWatch

**Check:**
1. Lambda has `cloudwatch:PutMetricData` permission
2. Metrics are enabled in code: `enable_metrics=True`
3. Metrics are being flushed: Add `metrics.flush()` before Lambda return

**Solution:**
```python
# At end of Lambda handler
try:
    metrics.flush()
except Exception as e:
    logger.warning(f"Failed to flush metrics: {e}")
```

### Issue: Audit Logs Not Being Created

**Check:**
1. Lambda has DynamoDB permissions for AuditLog table
2. Table exists: `aws dynamodb describe-table --table-name dev-AuditLog`
3. Check Lambda logs for DynamoDB errors

**Solution:**
```bash
# Verify permissions
aws lambda get-policy --function-name dev-message-processor | grep AuditLog
```

### Issue: High Costs

**Check:**
1. Current sample rate: Should be 0.1 (10%)
2. Metrics volume: `aws cloudwatch list-metrics --namespace SystemsBot | wc -l`
3. Audit event volume: Query `SystemsBot/Audit` metrics

**Solution:**
```python
# Reduce sampling
audit_logger = AuditLogger(metric_sample_rate=0.01)  # 1%

# Or disable metrics
audit_logger = AuditLogger(enable_metrics=False)
metrics = MetricsCollector(enable_metrics=False)
```

### Issue: Health Check Timing Out

**Check:**
1. Remove external API checks: Use `/health?detailed=true` without `&external=true`
2. Check network connectivity to FreshService
3. Review Lambda timeout settings

**Solution:**
```bash
# Increase timeout if needed
aws lambda update-function-configuration \
  --function-name dev-health \
  --timeout 15
```

---

## Next Steps After Deployment

1. ✅ Verify all resources created
2. ✅ Test each health endpoint
3. ✅ Trigger a test Slack message to generate audit logs
4. ✅ Check CloudWatch dashboard after 1 hour
5. ✅ Review costs after 24 hours
6. ✅ Set up SNS email subscription for alarms
7. ✅ Adjust sample rates if needed
8. ⏭️ Proceed to Phase 2 implementation

---

## Stack Outputs Reference

After deployment, get outputs:
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
- `AlarmTopicArn` - SNS topic for alarms (if monitoring stack deployed)
- `DashboardURL` - CloudWatch dashboard URL (if monitoring stack deployed)

---

**Deployment Date:** January 29, 2026  
**Version:** Phase 1 with Cost Controls  
**Infrastructure Status:** ✅ Complete
