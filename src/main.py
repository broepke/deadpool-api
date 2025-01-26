from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import deadpool
from src.models.deadpool import RoutesResponse

app = FastAPI(
    title="Deadpool API",
    description="API for Deadpool data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(deadpool.router)

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
