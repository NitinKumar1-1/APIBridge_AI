"""APIBridge AI - Backend Entry Point

Provides core FastAPI application, root status endpoint, health check,
and the OpenAPI structural diff engine API.
"""

from pathlib import Path
from typing import List, Optional
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from diff_engine import DiffRequest, DiffSummary, OpenAPIDiffEngine
from compatibility import (
    AnalyzeFixesRequest,
    CompatibilityAnalysisResponse,
    analyze_and_generate_fixes,
)


class RootResponse(BaseModel):
    name: str
    version: str
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    service: str


class SamplesResponse(BaseModel):
    v1: str
    v2: str
    v1_filename: str
    v2_filename: str


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

diff_engine = OpenAPIDiffEngine()


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


@app.post("/api/diff", response_model=DiffSummary, tags=["Diff Engine"])
@app.post("/diff", response_model=DiffSummary, include_in_schema=False)
async def compute_diff(payload: DiffRequest) -> DiffSummary:
    """Computes deterministic structural difference between OpenAPI v1 and v2 specifications.

    Accepts JSON or YAML OpenAPI specifications and returns categorized breaking
    and non-breaking changes.
    """
    try:
        summary = diff_engine.compare(payload.spec_v1, payload.spec_v2)
        return summary
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Diff engine encountered an unexpected error: {str(exc)}",
        )


@app.post("/api/analyze-fixes", response_model=CompatibilityAnalysisResponse, tags=["Compatibility & Fixes"])
@app.post("/analyze-fixes", response_model=CompatibilityAnalysisResponse, include_in_schema=False)
async def analyze_compatibility_and_fixes(payload: AnalyzeFixesRequest) -> CompatibilityAnalysisResponse:
    """Analyzes backward compatibility, reasons over breaking changes, generates fixes,

    applies transformations to a sample payload, and validates against OpenAPI v2 schema.
    """
    try:
        diff_summary = diff_engine.compare(payload.spec_v1, payload.spec_v2)
        analysis_report = analyze_and_generate_fixes(
            diff_summary=diff_summary,
            v1_spec_raw=payload.spec_v1,
            v2_spec_raw=payload.spec_v2,
            sample_request=payload.sample_request,
            target_path=payload.target_path,
            target_method=payload.target_method,
        )
        return analysis_report
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Compatibility analyzer encountered an unexpected error: {str(exc)}",
        )


@app.get("/api/samples", response_model=SamplesResponse, tags=["Diff Engine"])
@app.get("/samples", response_model=SamplesResponse, include_in_schema=False)
async def get_sample_specs() -> SamplesResponse:
    """Returns sample OpenAPI v1 and v2 specifications demonstrating breaking and non-breaking changes."""
    samples_dir = Path(__file__).parent / "samples"
    v1_path = samples_dir / "v1_user_service.yaml"
    v2_path = samples_dir / "v2_user_service.yaml"

    if not v1_path.exists() or not v2_path.exists():
        raise HTTPException(status_code=404, detail="Sample OpenAPI files could not be found.")

    v1_content = v1_path.read_text(encoding="utf-8")
    v2_content = v2_path.read_text(encoding="utf-8")

    return SamplesResponse(
        v1=v1_content,
        v2=v2_content,
        v1_filename="v1_user_service.yaml",
        v2_filename="v2_user_service.yaml",
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
