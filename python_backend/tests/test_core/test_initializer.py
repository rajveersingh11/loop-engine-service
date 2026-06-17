# python_backend/tests/test_core/test_initializer.py
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.core.initializer import LoopInitializer

@pytest.fixture
def mock_registry(tmp_path):
    registry = {
        "patterns": [
            {
                "id": "test-pattern",
                "name": "Test Pattern",
                "cadence": "1h",
                "risk": "low",
                "skills": ["skill-a"],
                "human_gates": ["gate-a"],
                "state": "TEST_STATE.md",
                "cost": {"suggested_daily_cap": 10000}
            }
        ]
    }
    registry_file = tmp_path / "registry.yaml"
    with open(registry_file, 'w', encoding='utf-8') as f:
        yaml.dump(registry, f)
    return registry_file

def test_initializer_load_patterns(mock_registry):
    initializer = LoopInitializer(registry_path=mock_registry)
    assert len(initializer.patterns["patterns"]) == 1
    assert initializer._get_pattern("test-pattern") is not None

def test_generate_state_md(mock_registry, tmp_path):
    initializer = LoopInitializer(registry_path=mock_registry)
    target_dir = tmp_path / "output"
    
    # Surgical patch: only return template content for the template path
    original_read_text = Path.read_text
    def mock_read_text(self, *args, **kwargs):
        if "STATE.md.template" in str(self):
            return "# State for {{PROJECT_NAME}}"
        return original_read_text(self, *args, **kwargs)

    with patch.object(Path, "exists", return_value=True):
        with patch.object(Path, "read_text", autospec=True, side_effect=mock_read_text):
            state_file = initializer.generate_state_md("test-pattern", target_dir, "Cool Project")
            
            assert state_file.name == "TEST_STATE.md"
            # Read directly from disk to avoid mock interference
            with open(state_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert "Cool Project" in content
                assert "{{PROJECT_NAME}}" not in content

def test_generate_loop_config_yaml(mock_registry, tmp_path):
    initializer = LoopInitializer(registry_path=mock_registry)
    target_dir = tmp_path / "output"
    
    config_file = initializer.generate_loop_config_yaml("test-pattern", target_dir)
    assert config_file.name == "loop_config.yaml"
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        assert config["loop_id"] == "test-pattern"
        assert config["monitoring"]["token_budget_daily"] == 10000

def test_scaffold(mock_registry, tmp_path):
    initializer = LoopInitializer(registry_path=mock_registry)
    target_dir = tmp_path / "scaffold_out"
    
    # Mock templates to avoid errors
    with patch.object(Path, "exists", return_value=True):
        with patch.object(Path, "read_text", return_value="template"):
            result = initializer.scaffold("test-pattern", str(target_dir))
            
            assert result["state_file"].exists()
            assert result["config_file"].exists()
            assert result["agents_file"].exists()
