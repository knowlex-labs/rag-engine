"""
Structured logging with trace_id and user_id tracking
"""
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from typing import Optional

# Context variables to store trace_id and user_id per request
trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class ContextualFilter(logging.Filter):
    """
    Logging filter to inject trace_id and user_id into log records
    """
    def filter(self, record):
        record.trace_id = trace_id_var.get() or "N/A"
        record.user_id = user_id_var.get() or "N/A"
        return True


class CustomFormatter(logging.Formatter):
    """
    Custom formatter with structured output including trace_id and user_id
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }

    def format(self, record):
        # Get timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        # Get log level with color
        level = record.levelname
        colored_level = f"{self.COLORS.get(level, '')}{level:8}{self.COLORS['RESET']}"

        # Get trace_id and user_id from record
        trace_id = getattr(record, 'trace_id', 'N/A')
        user_id = getattr(record, 'user_id', 'N/A')

        # Get logger name (module)
        logger_name = record.name

        # Get message
        message = record.getMessage()

        # Format: [timestamp] LEVEL | traceId: xxx | userId: xxx | module.name | message
        log_line = f"[{timestamp}] {colored_level} | traceId: {trace_id} | userId: {user_id} | {logger_name} | {message}"

        # Add exception info if present
        if record.exc_info:
            log_line += "\n" + self.formatException(record.exc_info)

        return log_line


def setup_logging(log_level: str = "INFO"):
    """
    Setup structured logging for the application

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    # Add custom formatter
    formatter = CustomFormatter()
    console_handler.setFormatter(formatter)

    # Add contextual filter
    contextual_filter = ContextualFilter()
    console_handler.addFilter(contextual_filter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return root_logger


def set_trace_id(trace_id: str):
    """Set trace_id for current request context"""
    trace_id_var.set(trace_id)


def set_user_id(user_id: str):
    """Set user_id for current request context"""
    user_id_var.set(user_id)


def get_trace_id() -> Optional[str]:
    """Get trace_id from current request context"""
    return trace_id_var.get()


def get_user_id() -> Optional[str]:
    """Get user_id from current request context"""
    return user_id_var.get()


def clear_context():
    """Clear trace_id and user_id from current request context"""
    trace_id_var.set(None)
    user_id_var.set(None)
