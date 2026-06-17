# python_backend/tests/test_core/test_cost_estimator.py
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.core.cost_estimator import CostEstimator

@pytest.fixture
def mock_registry(tmp_path):
    registry = {
        "patterns": [
            {
                "id": "test-pattern",
                "name": "Test Pattern",
                "cadence": "1h",
                "token_cost": "medium",
                "cost": {
                    "tokens_noop": 1000,
                    "tokens_report": 5000,
                    "tokens_action": 10000,
                    "suggested_daily_cap": 50000,
                    "early_exit_required": True
                }
            }
        ]
    }
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps(registry), encoding='utf-8')
    return registry_file

def test_cost_estimator_init(mock_registry):
    with patch.object(CostEstimator, "_load_registry", return_value=json.loads(mock_registry.read_text())):
        estimator = CostEstimator("test-pattern", "L1")
        assert estimator.pattern["id"] == "test-pattern"
        
        with pytest.raises(ValueError):
            CostEstimator("invalid-pattern", "L1")
        
        with pytest.raises(ValueError):
            CostEstimator("test-pattern", "L4")

def test_estimate_monthly_spend(mock_registry):
    with patch.object(CostEstimator, "_load_registry", return_value=json.loads(mock_registry.read_text())):
        estimator = CostEstimator("test-pattern", "L2")
        breakdown = estimator.estimate_monthly_spend(runs_per_day=24)
        
        assert breakdown["pattern_id"] == "test-pattern"
        assert breakdown["runs_per_day"] == 24
        assert "noop" in breakdown["scenarios"]
        assert breakdown["realistic_monthly_total"] > 0

@patch("tiktoken.encoding_for_model")
def test_estimate_with_tiktoken(mock_encoding, mock_registry):
    mock_enc = MagicMock()
    mock_enc.encode.return_value = [1, 2, 3] # 3 tokens
    mock_encoding.return_value = mock_enc
    
    with patch.object(CostEstimator, "_load_registry", return_value=json.loads(mock_registry.read_text())):
        estimator = CostEstimator("test-pattern", "L1")
        breakdown = estimator.estimate_monthly_spend(runs_per_day=10, sample_context="test")
        
        # Check that assumptions mention the adjustment
        assert "+3 tokens" in breakdown["assumptions"]
        # Check that tokens per run increased (1000 + 3)
        assert breakdown["scenarios"]["noop"]["tokens_per_run"] == 1003
