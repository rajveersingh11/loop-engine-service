# app/core/auditor.py
from pathlib import Path
import re
import subprocess
from typing import List, Dict, Optional, Any, TypedDict, Set

class Finding(TypedDict):
    level: str  # 'ok' | 'warn' | 'fail'
    message: str

class LoopSignals(TypedDict):
    stateFile: Dict[str, Any]
    loopConfig: Dict[str, Any]
    skills: Dict[str, Any]
    verifier: Dict[str, Any]
    triage: Dict[str, Any]
    agentsMd: Dict[str, Any]
    patterns: Dict[str, Any]
    safety: Dict[str, Any]
    starters: Dict[str, Any]
    github: Dict[str, Any]
    mcp: Dict[str, Any]
    worktreeEvidence: Dict[str, Any]
    registry: Dict[str, Any]
    cost: Dict[str, Any]
    loopActivity: Dict[str, Any]

class AuditResult(TypedDict):
    target: str
    score: int
    level: str
    assessment: str
    signals: LoopSignals
    findings: List[Finding]
    recommendations: List[str]

class Auditor:
    STATE_FILES = [
        'STATE.md',
        'pr-babysitter-state.md',
        'ci-sweeper-state.md',
        'post-merge-state.md',
        'dependency-sweeper-state.md',
        'changelog-drafter-state.md',
        'issue-triage-state.md',
    ]

    LOOP_SKILL_NAMES = [
        'loop-triage',
        'minimal-fix',
        'loop-verifier',
        'pr-review-triage',
        'ci-triage',
        'post-merge-scan',
        'dependency-triage',
        'rebase-and-clean',
        'changelog-scan',
        'draft-release-notes',
        'issue-triage',
    ]

    SAFETY_FILES = ['safety.md', 'docs/safety.md', 'SECURITY.md']
    MCP_FILES = ['.mcp.json', 'mcp.json', '.mcp/config.json']
    WORKTREE_HINTS = ['worktree', 'worktrees', 'git worktree']
    BUDGET_HINTS = [
        re.compile(r'budget', re.IGNORECASE),
        re.compile(r'max tokens', re.IGNORECASE),
        re.compile(r'token cap', re.IGNORECASE),
        re.compile(r'kill switch', re.IGNORECASE),
        re.compile(r'loop-pause-all', re.IGNORECASE),
    ]

    @staticmethod
    def _find_skills(root: Path) -> List[str]:
        dirs = [
            root / '.grok' / 'skills',
            root / '.claude' / 'skills',
            root / '.codex' / 'skills',
            root / 'skills',
        ]
        found: List[str] = []
        for d in dirs:
            if not d.exists() or not d.is_dir():
                continue
            for item in d.iterdir():
                if item.is_dir():
                    found.append(item.name)
                elif item.is_file() and item.name == 'SKILL.md':
                    found.append('root-skill')
        
        # Claude Code agents and Codex subagents can host the verifier role
        agent_dirs = [
            root / '.claude' / 'agents',
            root / '.codex' / 'agents',
        ]
        for d in agent_dirs:
            if not d.exists() or not d.is_dir():
                continue
            for item in d.iterdir():
                if not item.is_file():
                    continue
                base = item.stem
                if 'verifier' in base or base == 'loop-verifier':
                    found.append('loop-verifier')
        
        return found

    @staticmethod
    def _detect_loop_activity(root: Path) -> Dict[str, Any]:
        evidence: List[str] = []
        state_candidates = Auditor.STATE_FILES + ['STATE.md']

        # 1. Look for "Last run" timestamps or dated entries inside state files
        for sf in state_candidates:
            p = root / sf
            if p.exists() and p.is_file():
                try:
                    content = p.read_text(encoding='utf-8')
                    if re.search(r'last\s*run|last updated|^\s*-\s*\d{4}-\d{2}-\d{2}', content, re.IGNORECASE | re.MULTILINE) or \
                       re.search(r'triage|loop run|changelog drafter', content, re.IGNORECASE):
                        evidence.append(f"state:{sf}")
                except Exception:
                    pass

        # 2. Presence of run log artifacts
        log_hints = ['loop-run-log', 'run-log', 'loop.log', 'audit-report']
        try:
            for item in root.iterdir():
                if item.is_file() and any(hint in item.name.lower() for hint in log_hints):
                    evidence.append(f"log:{item.name}")
        except Exception:
            pass

        # 3. Workflow evidence
        wf_dir = root / '.github' / 'workflows'
        if wf_dir.exists() and wf_dir.is_dir():
            try:
                for item in wf_dir.iterdir():
                    if re.search(r'triage|changelog|daily|loop|audit|pr-babysit', item.name, re.IGNORECASE):
                        evidence.append('github:loop-workflows')
                        break
            except Exception:
                pass

        # 4. Git history scan
        try:
            result = subprocess.run(
                ['git', 'log', '--oneline', '-25', '--', '.'],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=1.5
            )
            if result.returncode == 0:
                log_output = result.stdout
                if re.search(r'state\.md|loop| t riage |changelog-drafter|post-merge|daily triage|audit', log_output, re.IGNORECASE):
                    first_line = log_output.splitlines()[0] if log_output.strip() else ""
                    evidence.append(f"git:{first_line[:60]}")
        except Exception:
            pass

        # 5. Check LOOP.md
        loop_p = root / 'LOOP.md'
        if loop_p.exists() and loop_p.is_file():
            try:
                content = loop_p.read_text(encoding='utf-8')
                if re.search(r'last run|cadence|scheduled|automation', content, re.IGNORECASE):
                    evidence.append('LOOP.md:active')
            except Exception:
                pass

        unique_evidence = list(dict.fromkeys(evidence))[:4]
        return {"present": len(unique_evidence) > 0, "evidence": unique_evidence}

    @staticmethod
    def compute_score(signals: LoopSignals) -> Dict[str, Any]:
        score = 10

        if signals['stateFile']['present']: score += 18
        if signals['triage']['present']: score += 14
        if signals['loopConfig']['present']: score += 9
        if signals['agentsMd']['present']: score += 9
        
        skill_count = signals['skills']['count']
        if skill_count >= 2: score += 14
        elif skill_count == 1: score += 7
        
        if signals['verifier']['present']: score += 14
        if signals['safety']['loopMdMentionsSafety']: score += 4
        if signals['safety']['safetyDocPresent']: score += 4
        if signals['github']['present']: score += 6
        if signals['github']['workflows']: score += 4
        if signals['mcp']['present']: score += 3
        if signals['worktreeEvidence']['present']: score += 3
        if signals['registry']['present']: score += 2
        if signals['cost']['budgetDoc']: score += 3
        if signals['cost']['runLog']: score += 3
        if signals['cost']['loopMdBudget']: score += 2
        if signals['cost']['budgetSkill']: score += 2
        if signals['loopActivity']['present']: score += 6

        score = min(100, max(0, score))

        cost_ready = (
            signals['cost']['budgetDoc'] and
            signals['cost']['runLog'] and
            signals['cost']['loopMdBudget']
        )
        has_real_activity = signals['loopActivity']['present']
        l3_ready = cost_ready and has_real_activity

        level = 'L0'
        if score >= 78 and signals['verifier']['present'] and signals['stateFile']['present'] and l3_ready:
            level = 'L3'
        elif score >= 58 and signals['triage']['present']:
            level = 'L2'
        elif score >= 38 and signals['stateFile']['present']:
            level = 'L1'
        else:
            level = 'L0'

        if score >= 82 and l3_ready:
            assessment = 'Strong loop readiness — good candidate for L3 with explicit gates.'
        elif score >= 82 and not cost_ready:
            assessment = 'Strong signals but missing cost observability (loop-budget.md, loop-run-log.md, LOOP.md budget) — add before L3.'
        elif score >= 82 and not has_real_activity:
            assessment = 'Strong structure but no proven loop runs yet — run one L1 cycle and commit state before L3.'
        elif score >= 62:
            assessment = 'Good foundation — add missing verifier + safety docs for L3.'
        elif score >= 42:
            assessment = 'Early loop setup — focus on L1 state + triage before enabling actions.'
        else:
            assessment = 'Not loop-ready — start with a starter from this repo (minimal-loop or pr-babysitter).'

        return {"score": score, "level": level, "assessment": assessment}

    @classmethod
    def audit_project(cls, target: str) -> AuditResult:
        root = Path(target).resolve()
        findings: List[Finding] = []
        recommendations: List[str] = []

        state_paths = [f for f in cls.STATE_FILES if (root / f).exists()]
        
        loop_md_path = root / 'LOOP.md'
        loop_md_present = loop_md_path.exists()
        
        agents_md_present = (root / 'AGENTS.md').exists() or (root / 'CLAUDE.md').exists()
        
        skill_names = cls._find_skills(root)
        loop_skills = [s for s in skill_names if s in cls.LOOP_SKILL_NAMES]
        
        verifier_present = 'loop-verifier' in skill_names
        triage_present = any(s in skill_names for s in [
            'loop-triage', 'pr-review-triage', 'ci-triage', 
            'dependency-triage', 'post-merge-scan', 'changelog-scan', 'issue-triage'
        ])

        loop_md_content = ""
        if loop_md_present:
            try:
                loop_md_content = loop_md_path.read_text(encoding='utf-8')
            except Exception:
                pass

        github_dir = root / '.github'
        github_present = github_dir.exists()
        workflows_present = (github_dir / 'workflows').exists()

        safety_doc_present = any((root / f).exists() for f in cls.SAFETY_FILES)
        if not safety_doc_present:
            safety_doc_present = (root / 'docs' / 'safety.md').exists()

        mcp_present = any((root / f).exists() for f in cls.MCP_FILES) or \
                      bool(re.search(r'MCP|mcp server|plugins & connectors', loop_md_content, re.IGNORECASE))

        worktree_evidence = False
        candidate_md = [
            'LOOP.md',
            'patterns/pr-babysitter.md',
            'starters/minimal-loop/LOOP.md',
            'starters/minimal-loop-claude/LOOP.md',
            'starters/minimal-loop-codex/LOOP.md',
            'docs/operating-loops.md',
        ]
        for c in candidate_md:
            p = root / c
            if p.exists():
                try:
                    txt = p.read_text(encoding='utf-8').lower()
                    if any(hint in txt for hint in cls.WORKTREE_HINTS):
                        worktree_evidence = True
                        break
                except Exception:
                    pass

        registry_present = (root / 'patterns' / 'registry.yaml').exists()
        
        budget_doc_present = (root / 'loop-budget.md').exists()
        run_log_present = (root / 'loop-run-log.md').exists()
        loop_md_budget = any(re.search(hint, loop_md_content) for hint in cls.BUDGET_HINTS)

        budget_skill_dirs = [
            root / 'skills' / 'loop-budget',
            root / '.grok' / 'skills' / 'loop-budget',
            root / '.claude' / 'skills' / 'loop-budget',
            root / '.codex' / 'skills' / 'loop-budget',
        ]
        budget_skill_present = any((d / 'SKILL.md').exists() for d in budget_skill_dirs)

        loop_activity = cls._detect_loop_activity(root)

        signals: LoopSignals = {
            "stateFile": {"present": len(state_paths) > 0, "paths": state_paths},
            "loopConfig": {"present": loop_md_present, "path": "LOOP.md" if loop_md_present else None},
            "skills": {"count": len(loop_skills), "loopSkills": loop_skills},
            "verifier": {"present": verifier_present},
            "triage": {"present": triage_present},
            "agentsMd": {"present": agents_md_present},
            "patterns": {"documented": loop_md_present},
            "safety": {
                "loopMdMentionsSafety": bool(re.search(r'gate|denylist|auto-merge|safety', loop_md_content, re.IGNORECASE)),
                "safetyDocPresent": safety_doc_present
            },
            "starters": {"used": 'loop-triage' in loop_skills},
            "github": {"present": github_present, "workflows": workflows_present},
            "mcp": {"present": mcp_present},
            "worktreeEvidence": {"present": worktree_evidence},
            "registry": {"present": registry_present},
            "cost": {
                "budgetDoc": budget_doc_present,
                "runLog": run_log_present,
                "loopMdBudget": loop_md_budget,
                "budgetSkill": budget_skill_present
            },
            "loopActivity": loop_activity,
        }

        # Findings and Recommendations
        if not signals['stateFile']['present']:
            findings.append({"level": "fail", "message": "No state file (STATE.md or pattern-specific state)."})
            recommendations.append("Copy starters/minimal-loop/STATE.md.example (or -claude / -codex variant) to STATE.md")
        else:
            findings.append({"level": "ok", "message": f"State file(s): {', '.join(state_paths)}"})

        if not signals['triage']['present']:
            findings.append({"level": "warn", "message": "No triage skill detected."})
            recommendations.append("Install loop-triage from starters/minimal-loop, minimal-loop-claude, or minimal-loop-codex")
        else:
            findings.append({"level": "ok", "message": "Triage skill present."})

        if not signals['verifier']['present']:
            findings.append({"level": "warn", "message": "No loop-verifier skill — maker/checker split incomplete."})
            recommendations.append("Add verifier: .grok/skills/loop-verifier, .claude/agents/loop-verifier.md, or .codex/agents/verifier.toml")
        else:
            findings.append({"level": "ok", "message": "Verifier skill present."})

        if not signals['loopConfig']['present']:
            findings.append({"level": "warn", "message": "No LOOP.md documenting cadence, limits, and gates."})
            recommendations.append("Copy starters/minimal-loop/LOOP.md and customize")

        if not signals['agentsMd']['present']:
            findings.append({"level": "warn", "message": "No AGENTS.md / CLAUDE.md for project conventions."})
            recommendations.append("Add AGENTS.md with build/test commands and review norms")

        if not signals['safety']['loopMdMentionsSafety']:
            findings.append({"level": "warn", "message": "LOOP.md does not mention safety gates or auto-merge policy."})
            recommendations.append("Document human gates per docs/safety.md in LOOP.md")

        if not signals['safety']['safetyDocPresent']:
            findings.append({"level": "warn", "message": "No safety.md or docs/safety.md found."})
            recommendations.append("Copy or create docs/safety.md (denylists, auto-merge policy, MCP scopes)")
        else:
            findings.append({"level": "ok", "message": "Safety documentation present."})

        if not signals['github']['present']:
            findings.append({"level": "warn", "message": "No .github/ directory (templates, workflows for dogfooding)."})
            recommendations.append("Add .github/ISSUE_TEMPLATE, PULL_REQUEST_TEMPLATE, and workflows (see this repo for examples)")
        elif not signals['github']['workflows']:
            findings.append({"level": "warn", "message": ".github/ exists but no workflows/ (CI dogfood opportunity)."})
            recommendations.append("Add GitHub Actions that run loop-audit and validate patterns (dogfood the reference)")
        else:
            findings.append({"level": "ok", "message": ".github/ with workflows present (strong dogfooding signal)."})

        if not signals['mcp']['present']:
            findings.append({"level": "warn", "message": "No MCP / connector config or mentions detected."})
            recommendations.append("Document MCP usage (or note \"MCP not required for this pattern\") in LOOP.md or skills")

        if not signals['worktreeEvidence']['present']:
            findings.append({"level": "warn", "message": "Little evidence of worktree usage in docs or state."})
            recommendations.append("Add worktree isolation notes to LOOP.md or pattern docs (see primitives and starters)")

        if not signals['registry']['present']:
            findings.append({"level": "warn", "message": "No patterns/registry.yaml (machine-readable index for future tools)."})
            recommendations.append("Add patterns/registry.yaml following the existing format")

        if not signals['cost']['budgetDoc']:
            findings.append({"level": "warn", "message": "No loop-budget.md — token caps and kill switch undocumented."})
            recommendations.append("Scaffold with loop-init or copy templates/loop-budget.md.template")
        else:
            findings.append({"level": "ok", "message": "loop-budget.md present."})

        if not signals['cost']['runLog']:
            findings.append({"level": "warn", "message": "No loop-run-log.md — run history not persisted."})
            recommendations.append("Copy templates/loop-run-log.md.template to loop-run-log.md")
        else:
            findings.append({"level": "ok", "message": "loop-run-log.md present."})

        if not signals['cost']['loopMdBudget']:
            findings.append({"level": "warn", "message": "LOOP.md does not mention budget, token caps, or kill switch."})
            recommendations.append("Add a Budget section to LOOP.md (see starters/*/LOOP.md)")

        if not signals['cost']['budgetSkill']:
            findings.append({"level": "warn", "message": "No loop-budget skill — budget checks are not automated at runtime."})
            recommendations.append("Add loop-budget skill via loop-init or templates/SKILL.md.loop-budget")
        else:
            findings.append({"level": "ok", "message": "loop-budget skill present."})

        if not signals['loopActivity']['present']:
            findings.append({"level": "warn", "message": "No evidence of actual loop runs detected (no \"Last run\" entries in state, loop-related git activity, or scheduled workflows yet)."})
            recommendations.append("Run one loop (report-only), update + commit STATE.md (or pattern state). This turns structure into proven usage.")
        else:
            findings.append({"level": "ok", "message": f"Loop activity detected — real usage signals present ({len(signals['loopActivity']['evidence'])} sources)."})

        score_details = cls.compute_score(signals)
        
        cost_ready = (
            signals['cost']['budgetDoc'] and
            signals['cost']['runLog'] and
            signals['cost']['loopMdBudget']
        )

        if score_details['score'] >= 78 and signals['verifier']['present'] and signals['stateFile']['present'] and not cost_ready:
            findings.append({
                "level": "warn",
                "message": "Score qualifies for L3 but cost observability is incomplete — capped at L2 until budget + run log + LOOP.md budget exist.",
            })

        if score_details['score'] >= 78 and signals['verifier']['present'] and signals['stateFile']['present'] and cost_ready and not signals['loopActivity']['present']:
            findings.append({
                "level": "warn",
                "message": "Score qualifies for L3 but no proven loop activity yet — capped at L2 until you run and commit at least one loop cycle.",
            })

        return {
            "target": str(root),
            "score": score_details['score'],
            "level": score_details['level'],
            "assessment": score_details['assessment'],
            "signals": signals,
            "findings": findings,
            "recommendations": recommendations,
        }
