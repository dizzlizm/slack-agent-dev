"""
Comprehensive audit logging for compliance and security tracking.

This module provides audit logging capabilities for tracking all system actions,
including tool calls, authentication checks, authorization decisions, and data access.
Logs are stored in DynamoDB with CloudWatch integration for real-time monitoring.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions that can be audited."""
    TOOL_CALL = "TOOL_CALL"
    AUTH_CHECK = "AUTH_CHECK"
    AUTH_FAILURE = "AUTH_FAILURE"
    TICKET_CREATE = "TICKET_CREATE"
    TICKET_UPDATE = "TICKET_UPDATE"
    TICKET_VIEW = "TICKET_VIEW"
    ASSET_VIEW = "ASSET_VIEW"
    USER_LOOKUP = "USER_LOOKUP"
    KB_SEARCH = "KB_SEARCH"
    APPROVAL_REQUEST = "APPROVAL_REQUEST"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_DENIED = "APPROVAL_DENIED"
    RATE_LIMIT_HIT = "RATE_LIMIT_HIT"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    ERROR = "ERROR"


class Outcome(Enum):
    """Possible outcomes for audited actions."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"
    PENDING = "PENDING"


class AuditLogger:
    """
    Comprehensive audit logging for compliance.
    
    Stores audit logs in DynamoDB with TTL and provides CloudWatch integration
    for real-time monitoring and alerting.
    
    COST CONTROLS:
    - Metrics sampling: Only 10% of events send CloudWatch metrics by default
    - Batched DynamoDB writes available
    - Configurable audit levels to reduce noise
    """

    def __init__(
        self,
        table_name: Optional[str] = None,
        retention_days: int = 365,
        enable_metrics: bool = True,
        metric_sample_rate: float = 0.1  # Only 10% send metrics by default
    ):
        """
        Initialize audit logger.
        
        Args:
            table_name: Name of the DynamoDB audit table
            retention_days: Number of days to retain audit logs
            enable_metrics: Whether to send CloudWatch metrics
            metric_sample_rate: Percentage of events to send metrics (0.0-1.0)
                               Critical events (failures, denials) always send metrics
        """
        self.table_name = table_name or "slack-agent-dev-AuditLog"
        self.retention_days = retention_days
        self.enable_metrics = enable_metrics
        self.metric_sample_rate = metric_sample_rate
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(self.table_name)
        self.cloudwatch = boto3.client('cloudwatch') if enable_metrics else None

    def log_action(
        self,
        action_type: ActionType,
        user_id: str,
        details: Dict[str, Any],
        outcome: Outcome,
        sensitive: bool = False,
        resource_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> str:
        """
        Log an action to the audit trail.
        
        Args:
            action_type: Type of action being audited
            user_id: Slack user ID performing the action
            details: Additional details about the action (will be sanitized if sensitive)
            outcome: Result of the action
            sensitive: Whether the action involves sensitive data
            resource_id: ID of the resource being accessed (ticket ID, asset ID, etc.)
            error_message: Error message if outcome is FAILURE
            
        Returns:
            Audit log ID (UUID)
        """
        audit_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        ttl = int((datetime.utcnow() + timedelta(days=self.retention_days)).timestamp())

        # Sanitize details if sensitive
        sanitized_details = self._sanitize_details(details) if sensitive else details

        audit_entry = {
            'PK': f"ACTION#{action_type.value}",
            'SK': f"{timestamp}#{audit_id}",
            'audit_id': audit_id,
            'action_type': action_type.value,
            'user_id': user_id,
            'timestamp': timestamp,
            'outcome': outcome.value,
            'sensitive': sensitive,
            'details': json.dumps(sanitized_details),
            'ttl': ttl
        }

        if resource_id:
            audit_entry['resource_id'] = resource_id

        if error_message:
            audit_entry['error_message'] = error_message

        try:
            self.table.put_item(Item=audit_entry)
            
            # Log to CloudWatch for real-time monitoring
            logger.info(
                f"Audit: {action_type.value} by {user_id} - {outcome.value}",
                extra={
                    'audit_id': audit_id,
                    'action_type': action_type.value,
                    'user_id': user_id,
                    'outcome': outcome.value,
                    'sensitive': sensitive
                }
            )

            # Send CloudWatch metric (sampled to reduce costs)
            if self.enable_metrics:
                self._send_metric_sampled(action_type, outcome)

            return audit_id

        except ClientError as e:
            logger.error(f"Failed to write audit log: {e}")
            # Critical: audit logging failure should be visible
            raise

    def log_tool_call(
        self,
        user_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        outcome: Outcome,
        response_summary: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> str:
        """
        Log an MCP tool invocation.
        
        Args:
            user_id: Slack user ID
            tool_name: Name of the tool being called
            parameters: Tool parameters (will be sanitized)
            outcome: Result of the tool call
            response_summary: Brief summary of the response
            error_message: Error message if failed
            
        Returns:
            Audit log ID
        """
        details = {
            'tool_name': tool_name,
            'parameters': parameters,
            'response_summary': response_summary
        }

        return self.log_action(
            action_type=ActionType.TOOL_CALL,
            user_id=user_id,
            details=details,
            outcome=outcome,
            sensitive=self._is_sensitive_tool(tool_name),
            error_message=error_message
        )

    def log_auth_check(
        self,
        user_id: str,
        action: str,
        outcome: Outcome,
        reason: Optional[str] = None
    ) -> str:
        """
        Log an authorization check.
        
        Args:
            user_id: Slack user ID
            action: Action being authorized
            outcome: Whether authorization was granted
            reason: Reason for denial if applicable
            
        Returns:
            Audit log ID
        """
        details = {
            'action': action,
            'reason': reason
        }

        action_type = (
            ActionType.AUTH_FAILURE if outcome == Outcome.DENIED
            else ActionType.AUTH_CHECK
        )

        return self.log_action(
            action_type=action_type,
            user_id=user_id,
            details=details,
            outcome=outcome
        )

    def get_user_audit_trail(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for a specific user.
        
        Args:
            user_id: Slack user ID
            days: Number of days to look back
            limit: Maximum number of entries to return
            
        Returns:
            List of audit entries
        """
        try:
            response = self.table.query(
                IndexName='UserIndex',
                KeyConditionExpression='user_id = :uid AND #ts >= :cutoff',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':uid': user_id,
                    ':cutoff': (datetime.utcnow() - timedelta(days=days)).isoformat()
                },
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            return response.get('Items', [])

        except ClientError as e:
            logger.error(f"Failed to query user audit trail: {e}")
            return []

    def get_action_audit_trail(
        self,
        action_type: ActionType,
        days: int = 7,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for a specific action type.
        
        Args:
            action_type: Type of action to query
            days: Number of days to look back
            limit: Maximum number of entries to return
            
        Returns:
            List of audit entries
        """
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND SK >= :cutoff',
                ExpressionAttributeValues={
                    ':pk': f"ACTION#{action_type.value}",
                    ':cutoff': cutoff
                },
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            return response.get('Items', [])

        except ClientError as e:
            logger.error(f"Failed to query action audit trail: {e}")
            return []

    def get_resource_audit_trail(
        self,
        resource_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for a specific resource (ticket, asset, etc.).
        
        Args:
            resource_id: Resource identifier
            limit: Maximum number of entries to return
            
        Returns:
            List of audit entries
        """
        try:
            response = self.table.query(
                IndexName='ResourceIndex',
                KeyConditionExpression='resource_id = :rid',
                ExpressionAttributeValues={':rid': resource_id},
                Limit=limit,
                ScanIndexForward=False
            )
            return response.get('Items', [])

        except ClientError as e:
            logger.error(f"Failed to query resource audit trail: {e}")
            return []

    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive information from audit details.
        
        Args:
            details: Original details dictionary
            
        Returns:
            Sanitized details
        """
        sanitized = details.copy()
        
        # List of sensitive field names to redact
        sensitive_fields = [
            'password', 'secret', 'token', 'api_key', 'ssn',
            'credit_card', 'auth', 'private_key'
        ]
        
        for key in list(sanitized.keys()):
            if any(field in key.lower() for field in sensitive_fields):
                sanitized[key] = '[REDACTED]'
        
        return sanitized

    def _is_sensitive_tool(self, tool_name: str) -> bool:
        """
        Determine if a tool involves sensitive operations.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if tool is considered sensitive
        """
        sensitive_tools = [
            'update_ticket',
            'create_ticket',
            'add_ticket_note',
            'password_reset',
            'access_request',
            'reboot_device'
        ]
        return tool_name in sensitive_tools

    def _send_metric_sampled(self, action_type: ActionType, outcome: Outcome) -> None:
        """
        Send CloudWatch metric for this audit event (with sampling).
        
        COST OPTIMIZATION: Only sends metrics for a sample of events to reduce
        CloudWatch API calls and costs. Failures and auth denials always send metrics.
        
        Args:
            action_type: Type of action
            outcome: Result of the action
        """
        # Always send metrics for failures and auth issues (critical)
        critical_event = (
            outcome in [Outcome.FAILURE, Outcome.DENIED] or
            action_type in [ActionType.AUTH_FAILURE, ActionType.ERROR, ActionType.RATE_LIMIT_HIT]
        )
        
        # Sample non-critical events
        if not critical_event:
            import random
            if random.random() > self.metric_sample_rate:
                return  # Skip this metric to save costs
        
        try:
            if self.cloudwatch:
                self.cloudwatch.put_metric_data(
                    Namespace='SystemsBot/Audit',
                    MetricData=[
                        {
                            'MetricName': 'AuditEvents',
                            'Value': 1,
                            'Unit': 'Count',
                            'Dimensions': [
                                {'Name': 'ActionType', 'Value': action_type.value},
                                {'Name': 'Outcome', 'Value': outcome.value}
                            ]
                        }
                    ]
                )
        except Exception as e:
            # Don't fail audit logging if CloudWatch is unavailable
            logger.warning(f"Failed to send CloudWatch metric: {e}")
