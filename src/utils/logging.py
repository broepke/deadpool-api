import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import sys

# Configure the root logger for Lambda environment
root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(message)s'))  # Raw message format for JSON
root.addHandler(handler)
root.setLevel(logging.INFO)

logger = root  # Use root logger to ensure Lambda captures all logs

class CloudWatchLogger:
    """
    Utility class for structured logging compatible with CloudWatch Insights.
    """
    
    def __init__(self):
        self._request_id: Optional[str] = None
        
    def set_request_id(self, request_id: str) -> None:
        """Set the request ID for the current context."""
        self._request_id = request_id
        
    def get_request_id(self) -> Optional[str]:
        """Get the current request ID."""
        return self._request_id
        
    def _format_log(
        self,
        level: str,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ) -> str:
        """Format log entry as JSON string."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": self._request_id or str(uuid.uuid4()),
            "level": level,
            "event_type": event_type,
            "message": message,
        }
        
        if data:
            log_entry["data"] = data
        if context:
            log_entry["context"] = context
        if error:
            log_entry["error"] = {
                "type": error.__class__.__name__,
                "message": str(error),
                "traceback": getattr(error, '__traceback__', None)
            }
            
        return json.dumps(log_entry)
    
    def info(
        self,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an INFO level message."""
        logger.info(self._format_log("INFO", event_type, message, data, context))
        
    def warning(
        self,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a WARNING level message."""
        logger.warning(self._format_log("WARNING", event_type, message, data, context))
        
    def error(
        self,
        event_type: str,
        message: str,
        error: Optional[Exception] = None,
        data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an ERROR level message."""
        logger.error(
            self._format_log("ERROR", event_type, message, data, context, error)
        )
        
    def debug(
        self,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a DEBUG level message."""
        logger.debug(self._format_log("DEBUG", event_type, message, data, context))

# Create a global logger instance
cwlogger = CloudWatchLogger()

class Timer:
    """Context manager for timing operations."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, *args):
        self.end_time = time.time()
        
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0