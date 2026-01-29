"""
Request tracing module for correlation and end-to-end tracking.

Provides correlation ID generation and context propagation for tracking
requests across distributed components and logging systems.
"""

import logging
import uuid
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger(__name__)

# Context variable for storing trace ID across async calls
_trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)


class RequestTracer:
    """
    Add correlation IDs for request tracing.
    
    Enables end-to-end tracking of requests across Lambda invocations,
    API calls, and log aggregation systems.
    """

    @staticmethod
    def generate_trace_id() -> str:
        """
        Generate a new trace ID.
        
        Returns:
            8-character trace ID
        """
        return str(uuid.uuid4())[:8]

    @staticmethod
    def generate_span_id() -> str:
        """
        Generate a span ID for nested operations.
        
        Returns:
            8-character span ID
        """
        return str(uuid.uuid4())[:8]

    @staticmethod
    def set_trace_id(trace_id: str) -> None:
        """
        Set the trace ID for the current context.
        
        Args:
            trace_id: Trace ID to set
        """
        _trace_id_var.set(trace_id)
        logger.debug(f"Set trace_id: {trace_id}")

    @staticmethod
    def get_trace_id() -> Optional[str]:
        """
        Get the trace ID for the current context.
        
        Returns:
            Current trace ID or None
        """
        return _trace_id_var.get()

    @staticmethod
    def clear_trace_id() -> None:
        """Clear the trace ID from the current context."""
        _trace_id_var.set(None)

    @staticmethod
    def inject_trace_id(log_record: logging.LogRecord) -> None:
        """
        Inject trace ID into a log record.
        
        Args:
            log_record: Log record to modify
        """
        trace_id = _trace_id_var.get()
        if trace_id:
            log_record.trace_id = trace_id


class TraceContextFilter(logging.Filter):
    """
    Logging filter to add trace ID to all log records.
    
    Usage:
        handler = logging.StreamHandler()
        handler.addFilter(TraceContextFilter())
        logger.addHandler(handler)
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add trace_id to the log record.
        
        Args:
            record: Log record to filter
            
        Returns:
            Always True (don't filter out)
        """
        trace_id = _trace_id_var.get()
        record.trace_id = trace_id if trace_id else 'no-trace'
        return True


class TracedOperation:
    """
    Context manager for tracing an operation with its own span.
    
    Usage:
        with TracedOperation('api_call', service='FreshService') as span:
            # perform operation
            span.set_attribute('endpoint', '/api/tickets')
            span.set_attribute('status_code', 200)
    """

    def __init__(self, operation_name: str, **attributes):
        """
        Initialize traced operation.
        
        Args:
            operation_name: Name of the operation
            **attributes: Initial attributes for the span
        """
        self.operation_name = operation_name
        self.span_id = RequestTracer.generate_span_id()
        self.trace_id = RequestTracer.get_trace_id()
        self.attributes = attributes
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        """Start the span."""
        import time
        self.start_time = time.time()
        
        logger.debug(
            f"[{self.trace_id}:{self.span_id}] Starting {self.operation_name}",
            extra={'trace_id': self.trace_id, 'span_id': self.span_id}
        )
        
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End the span."""
        import time
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000
        
        status = 'error' if exc_type else 'success'
        
        log_msg = (
            f"[{self.trace_id}:{self.span_id}] Completed {self.operation_name} "
            f"in {duration_ms:.2f}ms - {status}"
        )
        
        extra = {
            'trace_id': self.trace_id,
            'span_id': self.span_id,
            'duration_ms': duration_ms,
            'status': status,
            **self.attributes
        }
        
        if exc_type:
            logger.error(log_msg, extra=extra, exc_info=(exc_type, exc_val, exc_tb))
        else:
            logger.info(log_msg, extra=extra)
        
        return False  # Don't suppress exceptions

    def set_attribute(self, key: str, value: any) -> None:
        """
        Set an attribute on the span.
        
        Args:
            key: Attribute name
            value: Attribute value
        """
        self.attributes[key] = value


def setup_trace_logging(logger_instance: logging.Logger) -> None:
    """
    Configure a logger to include trace IDs.
    
    Args:
        logger_instance: Logger to configure
    """
    # Add filter to include trace_id in all log records
    trace_filter = TraceContextFilter()
    logger_instance.addFilter(trace_filter)
    
    # Update format to include trace_id
    for handler in logger_instance.handlers:
        current_format = handler.formatter._fmt if handler.formatter else None
        if current_format and 'trace_id' not in current_format:
            new_format = f"[%(trace_id)s] {current_format}"
            handler.setFormatter(logging.Formatter(new_format))


def get_trace_id() -> Optional[str]:
    """
    Get the current trace ID.
    
    Returns:
        Current trace ID or None
    """
    return RequestTracer.get_trace_id()


def set_trace_id(trace_id: str) -> None:
    """
    Set the trace ID for the current context.
    
    Args:
        trace_id: Trace ID to set
    """
    RequestTracer.set_trace_id(trace_id)


def generate_trace_id() -> str:
    """
    Generate a new trace ID.
    
    Returns:
        New trace ID
    """
    return RequestTracer.generate_trace_id()


def traced_operation(operation_name: str, **attributes):
    """
    Decorator for tracing function calls.
    
    Usage:
        @traced_operation('process_message', component='handler')
        async def process_message(msg):
            # function body
            pass
    
    Args:
        operation_name: Name of the operation
        **attributes: Initial attributes for the span
        
    Returns:
        Decorator function
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            with TracedOperation(operation_name, **attributes):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            with TracedOperation(operation_name, **attributes):
                return func(*args, **kwargs)
        
        # Return appropriate wrapper based on whether function is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
