# python_backend/tests/test_core/test_auditor.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.core.auditor import Auditor

@pytest.fixture
def mock_root(tmp_path):
    """Creates a mock project structure."""
    (tmp_path / "STATE.md").write_text("last run: 2026-06-17", encoding='utf-8')
    (tmp_path / "LOOP.md").write_text("# Loop Configuration\n\nsafety gates", encoding='utf-8')
    (tmp_path / "skills" / "loop-triage").mkdir(parents=True)
    (tmp_path / "skills" / "loop-triage" / "SKILL.md").touch()
    (tmp_path / "skills" / "loop-verifier").mkdir(parents=True)
    (tmp_path / "skills" / "loop-verifier" / "SKILL.md").touch()
    return tmp_path

def test_find_skills(mock_root):
    skills = Auditor._find_skills(mock_root)
    assert "loop-triage" in skills
    assert "loop-verifier" in skills

@patch("subprocess.run")
def test_detect_loop_activity(mock_run, mock_root):
    # Mock git log
    mock_run.return_value = MagicMock(returncode=0, stdout="a1b2c3d state.md update\n")
    
    activity = Auditor._detect_loop_activity(mock_root)
    assert activity["present"] is True
    assert any("state:STATE.md" in e for e in activity["evidence"])
    assert any("git:a1b2c3d" in e for e in activity["evidence"])

def test_compute_score():
    signals = {
        "stateFile": {"present": True},
        "triage": {"present": True},
        "loopConfig": {"present": True},
        "agentsMd": {"present": True},
        "skills": {"count": 2},
        "verifier": {"present": True},
        "safety": {"loopMdMentionsSafety": True, "safetyDocPresent": True},
        "github": {"present": True, "workflows": True},
        "mcp": {"present": True},
        "worktreeEvidence": {"present": True},
        "registry": {"present": True},
        "cost": {
            "budgetDoc": True,
            "runLog": True,
            "loopMdBudget": True,
            "budgetSkill": True
        },
        "loopActivity": {"present": True}
    }
    result = Auditor.compute_score(signals)
    assert result["score"] >= 78
    assert result["level"] == "L3"

@patch("subprocess.run")
def test_audit_project(mock_run, mock_root):
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    
    result = Auditor.audit_project(str(mock_root))
    assert result["score"] > 0
    assert "target" in result
    assert len(result["findings"]) > 0
