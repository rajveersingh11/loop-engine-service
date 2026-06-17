# app/core/initializer.py
from pathlib import Path
import yaml
from typing import Dict, Any, List, Optional

class LoopInitializer:
    def __init__(self, registry_path: Optional[Path] = None):
        """
        Initialize the LoopInitializer with an optional path to the pattern registry.
        """
        if registry_path is None:
            # Default to the monorepo's loop-init registry
            registry_path = Path(__file__).resolve().parent.parent.parent.parent / "tools" / "loop-init" / "registry.yaml"
        
        self.registry_path = registry_path
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> Dict[str, Any]:
        """Loads the patterns from the registry YAML file."""
        if not self.registry_path.exists():
            return {"patterns": []}
        
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception:
            return {"patterns": []}

    def _get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a pattern definition by its ID."""
        for p in self.patterns.get("patterns", []):
            if p["id"] == pattern_id:
                return p
        return None

    def generate_state_md(self, pattern_id: str, target_dir: Path, project_name: str = "My Project") -> Path:
        """
        Generates a STATE.md file based on the pattern and template.
        """
        pattern = self._get_pattern(pattern_id)
        if not pattern:
            raise ValueError(f"Pattern '{pattern_id}' not found.")

        state_filename = pattern.get("state", "STATE.md")
        target_path = target_dir / state_filename

        template_path = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "STATE.md.template"
        
        if template_path.exists():
            content = template_path.read_text(encoding='utf-8')
            content = content.replace("{{PROJECT_NAME}}", project_name)
        else:
            # Fallback basic content if template is missing
            content = f"# Loop State — {project_name}\n\nLast run: (set by loop)\n\n## High Priority\n\n## Watch List\n"

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding='utf-8')
        return target_path

    def generate_loop_config_yaml(self, pattern_id: str, target_dir: Path) -> Path:
        """
        Generates a loop configuration YAML file for the specific pattern.
        """
        pattern = self._get_pattern(pattern_id)
        if not pattern:
            raise ValueError(f"Pattern '{pattern_id}' not found.")

        # Create a simplified config for the specific loop instance
        config = {
            "loop_id": pattern["id"],
            "name": pattern["name"],
            "cadence": pattern["cadence"],
            "risk_level": pattern["risk"],
            "enabled_skills": pattern["skills"],
            "human_gates": pattern["human_gates"],
            "monitoring": {
                "state_file": pattern["state"],
                "token_budget_daily": pattern["cost"]["suggested_daily_cap"]
            }
        }

        target_path = target_dir / "loop_config.yaml"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, sort_keys=False)
        
        return target_path

    def scaffold(self, pattern_id: str, target_dir: str, project_name: str = "My Project") -> Dict[str, Path]:
        """
        Scaffolds a new loop by generating necessary files.
        """
        target_path = Path(target_dir).resolve()
        
        state_file = self.generate_state_md(pattern_id, target_path, project_name)
        config_file = self.generate_loop_config_yaml(pattern_id, target_path)
        
        # Also generate AGENTS.md as a bonus (matching JS loop-init behavior)
        agents_path = target_path / "AGENTS.md"
        if not agents_path.exists():
            agents_content = (
                f"# AGENTS.md\n\n"
                f"## Project: {project_name}\n\n"
                "## Test commands\n"
                "npm test\n"
                "npm run lint\n\n"
                "## Loop conventions\n"
                "- Report-only week one (L1) before enabling auto-fix (L2)\n"
                "- See LOOP.md for cadence and human gates\n"
            )
            agents_path.write_text(agents_content, encoding='utf-8')

        return {
            "state_file": state_file,
            "config_file": config_file,
            "agents_file": agents_path
        }
