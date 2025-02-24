import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.routers import deadpool, reporting
from src.models.deadpool import RoutesResponse
from src.middleware.logging import LoggingMiddleware
from src.utils.logging import cwlogger

# Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Deadpool API",
    description="API for Deadpool data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add logging middleware first
app.add_middleware(LoggingMiddleware)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to ensure all errors are logged."""
    cwlogger.error(
        "UNHANDLED_ERROR",
        "An unhandled error occurred",
        error=exc,
        data={
            "path": request.url.path,
            "method": request.method
        }
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred"}
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://deadpool.dataknowsall.com",  # Production frontend
        "http://localhost:5173",  # Vite default port
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(deadpool.router)
app.include_router(reporting.router)  # Add reporting router

@app.get("/", response_model=RoutesResponse)
async def get_routes():
    """
    Get all available API routes.
    """
    routes = []
    for route in app.routes:
        # Skip the root endpoint itself and internal FastAPI routes
        if route.path != "/" and not route.path.startswith("/openapi") and not route.path.startswith("/docs"):
            routes.append({"path": route.path, "name": route.name})
    return {"message": "Successfully retrieved available routes", "routes": routes}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
