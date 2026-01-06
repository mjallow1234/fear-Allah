"""
Structured Logging Module (Phase 8.1)
Provides request-scoped logging with request_id propagation.
"""
import logging
import uuid
import time
import json
from contextvars import ContextVar
from typing import Optional, Any, Dict
from functools import wraps

from app.core.config import settings

# Context variable for request-scoped data
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
request_start_var: ContextVar[Optional[float]] = ContextVar('request_start', default=None)


def get_request_id() -> Optional[str]:
    """Get current request ID from context."""
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set request ID in context."""
    request_id_var.set(request_id)


def generate_request_id() -> str:
    """Generate a new unique request ID."""
    return str(uuid.uuid4())[:8]


class StructuredLogger:
    """
    Structured JSON logger with request context support.
    Logs in JSON format for production, human-readable for development.
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name
        self._is_json = settings.APP_ENV == 'production'
    
    def _build_log_record(
        self,
        level: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
    ) -> Dict[str, Any]:
        """Build a structured log record."""
        record = {
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'level': level,
            'logger': self.name,
            'message': message,
            'env': settings.APP_ENV,
        }
        
        # Add request context if available
        request_id = get_request_id()
        if request_id:
            record['request_id'] = request_id
        
        # Add duration if request start is available
        start = request_start_var.get()
        if start:
            record['duration_ms'] = round((time.time() - start) * 1000, 2)
        
        # Add extra fields
        if extra:
            record['context'] = extra
        
        # Add error info
        if error:
            record['error'] = {
                'type': type(error).__name__,
                'message': str(error),
            }
        
        return record
    
    def _format_message(self, record: Dict[str, Any]) -> str:
        """Format log record for output."""
        if self._is_json:
            return json.dumps(record, default=str)
        
        # Human-readable format for development
        parts = [
            f"[{record.get('request_id', '-')}]",
            f"[{record['env']}]",
            record['message'],
        ]
        
        if 'context' in record:
            parts.append(f"| {record['context']}")
        
        if 'error' in record:
            parts.append(f"| error={record['error']['type']}: {record['error']['message']}")
        
        if 'duration_ms' in record:
            parts.append(f"| {record['duration_ms']}ms")
        
        return ' '.join(parts)
    
    def debug(self, message: str, **extra):
        """Log debug message."""
        record = self._build_log_record('DEBUG', message, extra if extra else None)
        self.logger.debug(self._format_message(record))
    
    def info(self, message: str, **extra):
        """Log info message."""
        record = self._build_log_record('INFO', message, extra if extra else None)
        self.logger.info(self._format_message(record))
    
    def warning(self, message: str, **extra):
        """Log warning message."""
        record = self._build_log_record('WARNING', message, extra if extra else None)
        self.logger.warning(self._format_message(record))
    
    def error(self, message: str, error: Optional[Exception] = None, **extra):
        """Log error message."""
        record = self._build_log_record('ERROR', message, extra if extra else None, error)
        self.logger.error(self._format_message(record))
    
    def critical(self, message: str, error: Optional[Exception] = None, **extra):
        """Log critical message."""
        record = self._build_log_record('CRITICAL', message, extra if extra else None, error)
        self.logger.critical(self._format_message(record))


def get_logger(name: str = 'fear-allah') -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


# Pre-configured loggers for different domains
api_logger = get_logger('fear-allah.api')
automation_logger = get_logger('fear-allah.automation')
sales_logger = get_logger('fear-allah.sales')
inventory_logger = get_logger('fear-allah.inventory')
orders_logger = get_logger('fear-allah.orders')
ws_logger = get_logger('fear-allah.websocket')
db_logger = get_logger('fear-allah.database')


def log_operation(operation: str, logger: Optional[StructuredLogger] = None):
    """
    Decorator for logging function entry/exit with timing.
    
    Usage:
        @log_operation("create_order", orders_logger)
        async def create_order(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            log = logger or api_logger
            start = time.time()
            log.debug(f"{operation} started")
            try:
                result = await func(*args, **kwargs)
                duration = round((time.time() - start) * 1000, 2)
                log.info(f"{operation} completed", duration_ms=duration)
                return result
            except Exception as e:
                duration = round((time.time() - start) * 1000, 2)
                log.error(f"{operation} failed", error=e, duration_ms=duration)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            log = logger or api_logger
            start = time.time()
            log.debug(f"{operation} started")
            try:
                result = func(*args, **kwargs)
                duration = round((time.time() - start) * 1000, 2)
                log.info(f"{operation} completed", duration_ms=duration)
                return result
            except Exception as e:
                duration = round((time.time() - start) * 1000, 2)
                log.error(f"{operation} failed", error=e, duration_ms=duration)
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
