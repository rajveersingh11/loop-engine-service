# app/api/routes.py
from fastapi import APIRouter, HTTPException
from app.api.models import (
    AuditRequest, AuditResponse,
    InitRequest, InitResponse,
    CostRequest, CostResponse,
    RunRequest, RunResponse
)
from app.core.auditor import Auditor
from app.core.cost_estimator import CostEstimator
from app.core.initializer import LoopInitializer

router = APIRouter(prefix="/api/v1")

@router.post("/audit", response_model=AuditResponse)
async def audit_endpoint(request: AuditRequest):
    """Audits a project path for loop readiness."""
    result = Auditor.audit_project(request.target_path)
    return result

@router.post("/init", response_model=InitResponse)
async def init_endpoint(request: InitRequest):
    """Scaffolds a new loop engineering pattern."""
    initializer = LoopInitializer()
    files = initializer.scaffold(request.pattern_id, request.target_dir, request.project_name)
    return {
        "message": f"Successfully scaffolded {request.pattern_id} loop.",
        "created_files": {k: str(v) for k, v in files.items()}
    }

@router.post("/cost", response_model=CostResponse)
async def cost_endpoint(request: CostRequest):
    """Estimates monthly token spend for a loop pattern."""
    estimator = CostEstimator(request.pattern_id, request.level)
    result = estimator.estimate_monthly_spend(
        runs_per_day=request.runs_per_day,
        model=request.model,
        sample_context=request.sample_context
    )
    return result

@router.post("/run", response_model=RunResponse)
async def run_endpoint(request: RunRequest):
    """
    Executes a loop cycle. 
    Note: Core execution logic (Runner) to be implemented in Phase 3.
    Currently returns a simulation/stub.
    """
    return {
        "status": "success" if not request.dry_run else "simulated",
        "logs": [f"Scanning {request.target_dir} for {request.pattern_id} signals..."],
        "actions_taken": [] if request.dry_run else ["Updated state with simulation result"],
        "tokens_used": 1200 if request.dry_run else 5000,
        "state_updated": not request.dry_run
    }
