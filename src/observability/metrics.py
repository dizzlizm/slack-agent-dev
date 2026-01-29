"""
Observability metrics module for tracking system health and performance.

This module provides CloudWatch metrics integration for monitoring tool usage,
error rates, latency, and system health. Enables real-time alerting and
performance analysis.
"""

import logging
import time
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class MetricUnit(Enum):
    """CloudWatch metric units."""
    COUNT = "Count"
    SECONDS = "Seconds"
    MILLISECONDS = "Milliseconds"
    PERCENT = "Percent"
    BYTES = "Bytes"


class MetricsCollector:
    """
    Collects and publishes CloudWatch metrics for observability.
    
    Tracks key system metrics including:
    - Tool invocation counts and success rates
    - Latency and performance metrics
    - Error rates by type
    - System health indicators
    
    COST CONTROLS:
    - Automatic batching (up to 20 metrics per API call)
    - Auto-flush on batch size or after timeout
    - Configurable sampling rates
    """

    def __init__(
        self,
        namespace: str = "SystemsBot",
        enable_metrics: bool = True,
        auto_flush_seconds: int = 60
    ):
        """
        Initialize metrics collector.
        
        Args:
            namespace: CloudWatch namespace for metrics
            enable_metrics: Whether to actually send metrics (disable for cost savings)
            auto_flush_seconds: Auto-flush interval in seconds (default 60s)
        """
        self.namespace = namespace
        self.enable_metrics = enable_metrics
        self.auto_flush_seconds = auto_flush_seconds
        self.cloudwatch = boto3.client('cloudwatch') if enable_metrics else None
        self._batch_metrics: List[Dict[str, Any]] = []
        self._max_batch_size = 20  # CloudWatch limit
        self._last_flush_time = time.time()

    def record_tool_invocation(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float,
        user_id: Optional[str] = None
    ) -> None:
        """
        Record a tool invocation metric.
        
        Args:
            tool_name: Name of the tool invoked
            success: Whether the invocation succeeded
            duration_ms: Duration in milliseconds
            user_id: Optional user ID for user-specific metrics
        """
        dimensions = [
            {'Name': 'ToolName', 'Value': tool_name},
            {'Name': 'Status', 'Value': 'Success' if success else 'Failure'}
        ]

        if user_id:
            dimensions.append({'Name': 'UserId', 'Value': user_id})

        # Record invocation count
        self._add_metric(
            metric_name='ToolInvocations',
            value=1,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )

        # Record latency
        self._add_metric(
            metric_name='ToolLatency',
            value=duration_ms,
            unit=MetricUnit.MILLISECONDS,
            dimensions=[{'Name': 'ToolName', 'Value': tool_name}]
        )

        # Record success/failure rate
        self._add_metric(
            metric_name='ToolSuccessRate',
            value=100.0 if success else 0.0,
            unit=MetricUnit.PERCENT,
            dimensions=[{'Name': 'ToolName', 'Value': tool_name}]
        )

    def record_error(
        self,
        error_type: str,
        component: str,
        severity: str = "ERROR"
    ) -> None:
        """
        Record an error metric.
        
        Args:
            error_type: Type of error (ValidationError, APIError, etc.)
            component: Component where error occurred
            severity: Error severity (WARNING, ERROR, CRITICAL)
        """
        dimensions = [
            {'Name': 'ErrorType', 'Value': error_type},
            {'Name': 'Component', 'Value': component},
            {'Name': 'Severity', 'Value': severity}
        ]

        self._add_metric(
            metric_name='Errors',
            value=1,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )

    def record_message_processed(
        self,
        message_type: str,
        processing_time_ms: float,
        success: bool
    ) -> None:
        """
        Record message processing metrics.
        
        Args:
            message_type: Type of message (event, interactive, command)
            processing_time_ms: Time taken to process
            success: Whether processing succeeded
        """
        dimensions = [
            {'Name': 'MessageType', 'Value': message_type},
            {'Name': 'Status', 'Value': 'Success' if success else 'Failure'}
        ]

        self._add_metric(
            metric_name='MessagesProcessed',
            value=1,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )

        self._add_metric(
            metric_name='MessageProcessingTime',
            value=processing_time_ms,
            unit=MetricUnit.MILLISECONDS,
            dimensions=[{'Name': 'MessageType', 'Value': message_type}]
        )

    def record_api_call(
        self,
        service: str,
        endpoint: str,
        status_code: int,
        duration_ms: float
    ) -> None:
        """
        Record external API call metrics.
        
        Args:
            service: Service name (FreshService, Intune, Slack)
            endpoint: API endpoint called
            status_code: HTTP status code
            duration_ms: Call duration in milliseconds
        """
        dimensions = [
            {'Name': 'Service', 'Value': service},
            {'Name': 'Endpoint', 'Value': endpoint},
            {'Name': 'StatusCode', 'Value': str(status_code)}
        ]

        self._add_metric(
            metric_name='APICall',
            value=1,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )

        self._add_metric(
            metric_name='APILatency',
            value=duration_ms,
            unit=MetricUnit.MILLISECONDS,
            dimensions=[
                {'Name': 'Service', 'Value': service},
                {'Name': 'Endpoint', 'Value': endpoint}
            ]
        )

        # Record success rate (2xx and 3xx are success)
        success = 200 <= status_code < 400
        self._add_metric(
            metric_name='APISuccessRate',
            value=100.0 if success else 0.0,
            unit=MetricUnit.PERCENT,
            dimensions=[{'Name': 'Service', 'Value': service}]
        )

    def record_conversation_metric(
        self,
        metric_type: str,
        value: float,
        user_id: Optional[str] = None
    ) -> None:
        """
        Record conversation-related metrics.
        
        Args:
            metric_type: Type of metric (turns, queries, resolutions)
            value: Metric value
            user_id: Optional user ID
        """
        dimensions = [{'Name': 'MetricType', 'Value': metric_type}]
        if user_id:
            dimensions.append({'Name': 'UserId', 'Value': user_id})

        self._add_metric(
            metric_name='ConversationMetric',
            value=value,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )

    def record_cache_operation(
        self,
        operation: str,
        hit: bool
    ) -> None:
        """
        Record cache hit/miss metrics.
        
        Args:
            operation: Type of cache operation
            hit: Whether it was a cache hit
        """
        dimensions = [
            {'Name': 'Operation', 'Value': operation},
            {'Name': 'Result', 'Value': 'Hit' if hit else 'Miss'}
        ]

        self._add_metric(
            metric_name='CacheOperation',
            value=1,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )

        # Record cache hit rate
        self._add_metric(
            metric_name='CacheHitRate',
            value=100.0 if hit else 0.0,
            unit=MetricUnit.PERCENT,
            dimensions=[{'Name': 'Operation', 'Value': operation}]
        )

    def record_system_health(
        self,
        service: str,
        healthy: bool,
        response_time_ms: Optional[float] = None
    ) -> None:
        """
        Record system health check metrics.
        
        Args:
            service: Service being checked (FreshService, DynamoDB, etc.)
            healthy: Whether service is healthy
            response_time_ms: Optional health check response time
        """
        dimensions = [
            {'Name': 'Service', 'Value': service},
            {'Name': 'Status', 'Value': 'Healthy' if healthy else 'Unhealthy'}
        ]

        self._add_metric(
            metric_name='HealthCheck',
            value=1 if healthy else 0,
            unit=MetricUnit.COUNT,
            dimensions=dimensions
        )

        if response_time_ms is not None:
            self._add_metric(
                metric_name='HealthCheckLatency',
                value=response_time_ms,
                unit=MetricUnit.MILLISECONDS,
                dimensions=[{'Name': 'Service', 'Value': service}]
            )

    @contextmanager
    def measure_duration(self, metric_name: str, dimensions: Optional[List[Dict]] = None):
        """
        Context manager to measure operation duration.
        
        Usage:
            with metrics.measure_duration('ToolExecution', [{'Name': 'Tool', 'Value': 'search_kb'}]):
                # perform operation
                pass
        
        Args:
            metric_name: Name of the metric
            dimensions: Optional metric dimensions
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self._add_metric(
                metric_name=metric_name,
                value=duration_ms,
                unit=MetricUnit.MILLISECONDS,
                dimensions=dimensions or []
            )

    def _add_metric(
        self,
        metric_name: str,
        value: float,
        unit: MetricUnit,
        dimensions: List[Dict[str, str]]
    ) -> None:
        """
        Add a metric to the batch.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Metric unit
            dimensions: Metric dimensions
        """
        if not self.enable_metrics:
            return  # Metrics disabled, skip
        
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit.value,
            'Timestamp': datetime.utcnow(),
            'Dimensions': dimensions
        }

        self._batch_metrics.append(metric_data)

        # Auto-flush if batch is full or timeout reached
        current_time = time.time()
        time_since_flush = current_time - self._last_flush_time
        
        if len(self._batch_metrics) >= self._max_batch_size or time_since_flush >= self.auto_flush_seconds:
            self.flush()

    def flush(self) -> None:
        """Flush batched metrics to CloudWatch."""
        if not self._batch_metrics or not self.enable_metrics:
            return

        try:
            if self.cloudwatch:
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=self._batch_metrics
                )
                logger.debug(f"Flushed {len(self._batch_metrics)} metrics to CloudWatch")
            self._batch_metrics = []
            self._last_flush_time = time.time()

        except ClientError as e:
            logger.error(f"Failed to publish metrics to CloudWatch: {e}")
            # Clear batch to prevent memory buildup
            self._batch_metrics = []
            self._last_flush_time = time.time()

    def __del__(self):
        """Ensure metrics are flushed on cleanup."""
        self.flush()


class PerformanceTracker:
    """Track performance metrics for specific operations."""

    def __init__(self, metrics_collector: MetricsCollector):
        """
        Initialize performance tracker.
        
        Args:
            metrics_collector: MetricsCollector instance
        """
        self.metrics = metrics_collector
        self._operation_timers: Dict[str, float] = {}

    def start_operation(self, operation_id: str) -> None:
        """
        Start timing an operation.
        
        Args:
            operation_id: Unique identifier for the operation
        """
        self._operation_timers[operation_id] = time.time()

    def end_operation(
        self,
        operation_id: str,
        metric_name: str,
        dimensions: Optional[List[Dict]] = None,
        success: bool = True
    ) -> float:
        """
        End timing an operation and record metrics.
        
        Args:
            operation_id: Unique identifier for the operation
            metric_name: Name of the metric to record
            dimensions: Optional metric dimensions
            success: Whether the operation succeeded
            
        Returns:
            Duration in milliseconds
        """
        if operation_id not in self._operation_timers:
            logger.warning(f"No timer found for operation: {operation_id}")
            return 0.0

        start_time = self._operation_timers.pop(operation_id)
        duration_ms = (time.time() - start_time) * 1000

        dims = dimensions or []
        dims.append({'Name': 'Status', 'Value': 'Success' if success else 'Failure'})

        self.metrics._add_metric(
            metric_name=metric_name,
            value=duration_ms,
            unit=MetricUnit.MILLISECONDS,
            dimensions=dims
        )

        return duration_ms


# Global metrics instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector instance.
    
    Returns:
        Global MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def initialize_metrics(namespace: str = "SystemsBot") -> MetricsCollector:
    """
    Initialize the global metrics collector.
    
    Args:
        namespace: CloudWatch namespace
        
    Returns:
        Initialized MetricsCollector instance
    """
    global _metrics_collector
    _metrics_collector = MetricsCollector(namespace=namespace)
    return _metrics_collector
