# app/api/models.py
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Dict, Optional, Any, Literal

# Shared Constants
VALID_LEVELS = ["L1", "L2", "L3"]
VALID_PATTERNS = [
    "pr-babysitter",
    "daily-triage",
    "ci-sweeper",
    "post-merge-cleanup",
    "dependency-sweeper",
    "changelog-drafter",
    "issue-triage"
]

# --- Audit Models ---

class AuditRequest(BaseModel):
    target_path: str = Field(..., description="The local filesystem path to audit.")

class FindingModel(BaseModel):
    level: Literal["ok", "warn", "fail"]
    message: str

class AuditResponse(BaseModel):
    target: str
    score: int
    level: Literal["L0", "L1", "L2", "L3"]
    assessment: str
    signals: Dict[str, Any]
    findings: List[FindingModel]
    recommendations: List[str]

# --- Init Models ---

class InitRequest(BaseModel):
    pattern_id: str = Field(..., description="The ID of the loop pattern to scaffold.")
    target_dir: str = Field(".", description="The directory where the loop will be scaffolded.")
    project_name: str = Field("My Loop Project", description="The name of the project.")

    @field_validator("pattern_id")
    @classmethod
    def validate_pattern_id(cls, v: str) -> str:
        if v.lower() not in VALID_PATTERNS:
            raise ValueError(f"Pattern '{v}' is not supported. Valid patterns: {', '.join(VALID_PATTERNS)}")
        return v.lower()

class InitResponse(BaseModel):
    message: str
    created_files: Dict[str, str]

# --- Cost Models ---

class CostRequest(BaseModel):
    pattern_id: str = Field(..., description="The ID of the pattern for cost estimation.")
    level: str = Field("L1", description="The readiness level (L1, L2, L3).")
    runs_per_day: int = Field(24, ge=1, le=288, description="Number of runs per day.")
    sample_context: Optional[str] = Field(None, description="Sample text to calibrate token counts.")
    model: str = Field("gpt-4o", description="The LLM model to use for token calculation.")

    @field_validator("pattern_id")
    @classmethod
    def validate_pattern_id(cls, v: str) -> str:
        if v.lower() not in VALID_PATTERNS:
            raise ValueError(f"Pattern '{v}' is not supported.")
        return v.lower()

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        if v.upper() not in VALID_LEVELS:
            raise ValueError(f"Level must be one of {', '.join(VALID_LEVELS)}")
        return v.upper()

class ScenarioSpendModel(BaseModel):
    tokens_per_run: int
    tokens_per_day: int
    tokens_per_month: int

class CostResponse(BaseModel):
    pattern_id: str
    pattern_name: str
    level: str
    runs_per_day: int
    daily_cap: int
    scenarios: Dict[str, ScenarioSpendModel]
    realistic_monthly_total: int
    assumptions: str
    warnings: List[str]

# --- Run Models ---

class RunRequest(BaseModel):
    pattern_id: str = Field(..., description="The ID of the pattern to run.")
    target_dir: str = Field(".", description="The working directory for the loop.")
    dry_run: bool = Field(True, description="If true, simulates the run without making changes.")

    @field_validator("pattern_id")
    @classmethod
    def validate_pattern_id(cls, v: str) -> str:
        if v.lower() not in VALID_PATTERNS:
            raise ValueError(f"Pattern '{v}' is not supported.")
        return v.lower()

class RunResponse(BaseModel):
    status: str
    logs: List[str]
    actions_taken: List[str]
    tokens_used: int
    state_updated: bool
