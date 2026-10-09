"""APIBridge AI - Backend Entry Point

Provides core FastAPI application, root status endpoint, and health check.
"""

from typing import List
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class RootResponse(BaseModel):
    name: str
    version: str
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    service: str


app = FastAPI(
    title="APIBridge AI",
    description="Autonomous API Breaking-Change Detection & WebAssembly Adapter Engine",
    version="0.1.0",
)

# Configure CORS for local development (e.g., React/Vite on port 5173)
raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
allowed_origins: List[str] = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=RootResponse, tags=["General"])
async def root() -> RootResponse:
    """Root endpoint returning service identity and status."""
    return RootResponse(
        name="APIBridge AI",
        version="0.1.0",
        status="running",
        message="APIBridge AI backend is operational",
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint to verify backend service readiness."""
    return HealthResponse(
        status="healthy",
        service="apibridge-backend",
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
