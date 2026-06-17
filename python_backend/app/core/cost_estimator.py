# app/core/cost_estimator.py
from typing import TypedDict, List, Dict, Any, Optional
from pathlib import Path
import json
import math
import tiktoken

class ScenarioSpend(TypedDict):
    tokens_per_run: int
    tokens_per_day: int
    tokens_per_month: int

class MonthlySpendBreakdown(TypedDict):
    pattern_id: str
    pattern_name: str
    level: str
    runs_per_day: int
    daily_cap: int
    scenarios: Dict[str, ScenarioSpend]
    realistic_monthly_total: int
    assumptions: str
    warnings: List[str]

class CostEstimator:
    def __init__(self, pattern_name: str, level: str):
        """
        Initialize the CostEstimator with a pattern and readiness level.
        
        Args:
            pattern_name: The name or ID of the pattern (e.g., 'PR Babysitter' or 'pr-babysitter').
            level: The readiness level ('L1', 'L2', 'L3').
        """
        self.pattern_name = pattern_name
        self.level = level
        self.registry_data = self._load_registry()
        self.pattern = self._find_pattern(pattern_name)
        
        if not self.pattern:
            raise ValueError(f"Pattern '{pattern_name}' not found in registry.")
        
        if level not in ['L1', 'L2', 'L3']:
            raise ValueError("Level must be one of 'L1', 'L2', 'L3'.")

    def _load_registry(self) -> Dict[str, Any]:
        # Attempt to find registry.json relative to this file
        # Root is 3 levels up: app/core/cost_estimator.py -> app/core/ -> app/ -> python_backend/ -> root
        potential_paths = [
            Path(__file__).resolve().parent.parent.parent.parent / "tools" / "loop-cost" / "registry.json",
            Path.cwd() / "tools" / "loop-cost" / "registry.json",
            Path.cwd().parent / "tools" / "loop-cost" / "registry.json"
        ]
        
        for p in potential_paths:
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
        
        # Fallback if not found (might happen in different envs)
        return {"patterns": []}

    def _find_pattern(self, name_or_id: str) -> Optional[Dict[str, Any]]:
        for p in self.registry_data.get("patterns", []):
            if p["id"] == name_or_id.lower() or p["name"].lower() == name_or_id.lower():
                return p
        return None

    def _get_realistic_mix(self) -> Dict[str, Any]:
        early_exit = self.pattern["cost"]["early_exit_required"]
        
        if self.level == 'L1':
            return {
                "noop": 0.9 if early_exit else 0.6,
                "report": 0.1 if early_exit else 0.4,
                "action": 0,
                "assumptions": 'L1: 90% early-exit, 10% triage' if early_exit else 'L1: 60% no-op, 40% triage'
            }
        elif self.level == 'L2':
            return {
                "noop": 0.85 if early_exit else 0.5,
                "report": 0.1 if early_exit else 0.3,
                "action": 0.05 if early_exit else 0.2,
                "assumptions": 'L2: 85% early-exit, 10% triage, 5% action' if early_exit else 'L2: 50% no-op, 30% triage, 20% action'
            }
        else: # L3
            return {
                "noop": 0.4,
                "report": 0.35,
                "action": 0.25,
                "assumptions": 'L3: 40% no-op, 35% triage, 25% action (unattended)'
            }

    def estimate_monthly_spend(
        self, 
        runs_per_day: int, 
        model: str = "gpt-4o", 
        sample_context: Optional[str] = None
    ) -> MonthlySpendBreakdown:
        """
        Estimate the monthly token spend based on run frequency.
        
        Args:
            runs_per_day: Number of times the loop runs per day.
            model: The LLM model to use for token counting (via tiktoken).
            sample_context: Optional text to represent a typical "noop" or "report" run.
                           If provided, tiktoken will count these tokens to refine the estimate.
        """
        cost = self.pattern["cost"]
        mix = self._get_realistic_mix()
        
        # Base costs from registry
        tokens_noop = cost["tokens_noop"]
        tokens_report = cost["tokens_report"]
        tokens_action = cost["tokens_action"]

        # If sample_context is provided, use tiktoken to calculate a more accurate base cost
        # We'll assume the sample_context represents a "noop" run's input/output overhead
        tiktoken_adjustment = 0
        if sample_context:
            try:
                encoding = tiktoken.encoding_for_model(model)
                tiktoken_adjustment = len(encoding.encode(sample_context))
                # Add the counted tokens to the base costs to reflect actual context size
                tokens_noop += tiktoken_adjustment
                tokens_report += tiktoken_adjustment
                tokens_action += tiktoken_adjustment
            except Exception:
                # Fallback if model not found or tiktoken fails
                pass

        scenarios = {}
        for scenario, tokens in [("noop", tokens_noop), ("report", tokens_report), ("action", tokens_action)]:
            daily = tokens * runs_per_day
            scenarios[scenario] = {
                "tokens_per_run": tokens,
                "tokens_per_day": daily,
                "tokens_per_month": daily * 30
            }

        realistic_per_run = (
            tokens_noop * mix["noop"] +
            tokens_report * mix["report"] +
            tokens_action * mix["action"]
        )
        realistic_daily = int(realistic_per_run * runs_per_day)
        realistic_monthly = realistic_daily * 30

        warnings = []
        if cost["early_exit_required"] and not sample_context:
            warnings.append("Early-exit triage is required for this pattern.")
        
        # Check actual field name from registry.json read earlier
        suggested_cap = cost.get("suggested_daily_cap", 0)
        if realistic_daily > suggested_cap:
            warnings.append(f"Realistic daily estimate ({realistic_daily}) exceeds suggested cap ({suggested_cap}).")
        
        if runs_per_day >= 96:
            warnings.append(f"High frequency ({runs_per_day} runs/day) - ensure early-exit is efficient.")

        return {
            "pattern_id": self.pattern["id"],
            "pattern_name": self.pattern["name"],
            "level": self.level,
            "runs_per_day": runs_per_day,
            "daily_cap": suggested_cap,
            "scenarios": scenarios,
            "realistic_monthly_total": realistic_monthly,
            "assumptions": mix["assumptions"] + (f" (+{tiktoken_adjustment} tokens from sample context)" if tiktoken_adjustment > 0 else ""),
            "warnings": warnings
        }
