import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..utils.logging import cwlogger, Timer

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and responses."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID and set in logger
        request_id = str(uuid.uuid4())
        cwlogger.set_request_id(request_id)
        
        # Log request
        await self._log_request(request, request_id)
        
        # Time the request processing
        with Timer() as timer:
            try:
                response = await call_next(request)
                await self._log_response(request, response, timer.elapsed_ms)
                return response
            except Exception as e:
                # Log error and re-raise
                cwlogger.error(
                    "REQUEST_ERROR",
                    "Error processing request",
                    error=e,
                    data={
                        "path": request.url.path,
                        "method": request.method,
                        "elapsed_ms": timer.elapsed_ms
                    }
                )
                raise
            finally:
                # Clear request ID after request is complete
                cwlogger.set_request_id(None)
                
    async def _log_request(self, request: Request, request_id: str) -> None:
        """Log incoming request details."""
        # Get query params
        query_params = dict(request.query_params)
        
        # Get client info
        client_host = request.client.host if request.client else None
        
        # Log request details
        cwlogger.info(
            "REQUEST",
            f"Incoming {request.method} request to {request.url.path}",
            data={
                "method": request.method,
                "path": request.url.path,
                "query_params": query_params,
                "client_ip": client_host,
                "user_agent": request.headers.get("user-agent"),
                "request_id": request_id
            }
        )
        
    async def _log_response(
        self,
        request: Request,
        response: Response,
        elapsed_ms: float
    ) -> None:
        """Log response details."""
        cwlogger.info(
            "RESPONSE",
            f"Response for {request.method} {request.url.path}",
            data={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms
            }
        )