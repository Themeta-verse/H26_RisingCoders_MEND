"""Python Ecosystem Adapter for MEND.

Provides FULL support for Python environments:
- Manifest parsing: pyproject.toml (PEP 621, Poetry, Flit), requirements.txt, requirements-dev.txt
- Source usage analysis: Python AST import parser (ast.Import, ast.ImportFrom)
- Deterministic rules: Jinja2/MarkupSafe breaking split, Pydantic v1->v2, unpinned specs, zombie deps, manifest conflicts
- Local AI recommendations: Gemma 4 via Ollama
- Candidate verification: Isolated filesystem sandbox with pytest execution
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import (
    BaseEcosystemAdapter,
    EcosystemCapabilities,
    EcosystemDetectionResult,
    EcosystemType,
    SupportLevel,
)
from mend.core.scanner import DependencyScanner, ManifestDeclaration, CodeUsageLocation, RepositoryScanResult
from mend.core.rules import RuleEngine, RuleFinding


class PythonEcosystemAdapter(BaseEcosystemAdapter):
    """Full-support adapter for Python repositories."""

    @property
    def ecosystem_type(self) -> EcosystemType:
        return EcosystemType.PYTHON

    @property
    def display_name(self) -> str:
        return "Python (PEP 508 / PyPI)"

    @property
    def support_level(self) -> SupportLevel:
        return SupportLevel.FULL

    def detect(self, target_path: Path) -> Optional[EcosystemDetectionResult]:
        detected_manifests = []
        for manifest_name in ["pyproject.toml", "requirements.txt", "requirements-dev.txt", "setup.py", "Pipfile"]:
            if (target_path / manifest_name).is_file():
                detected_manifests.append(manifest_name)

        # Also check for any .py files
        has_python_files = any(target_path.glob("*.py")) or any(target_path.glob("*/*.py"))

        if not detected_manifests and not has_python_files:
            return None

        return EcosystemDetectionResult(
            ecosystem=self.ecosystem_type,
            display_name=self.display_name,
            support_level=self.support_level,
            detected_manifests=detected_manifests,
            capabilities=EcosystemCapabilities(
                manifest_parsing=True,
                code_usage_analysis=True,
                deterministic_rules=True,
                ai_advisory=True,
                candidate_sandbox_verification=True,
                drift_detection=True,
            ),
            limitations=self.get_limitations(),
        )

    def scan_manifests(self, target_path: Path) -> List[ManifestDeclaration]:
        scanner = DependencyScanner(target_path)
        return scanner._scan_manifests()

    def scan_code_imports(self, target_path: Path) -> Tuple[List[Path], int, List[CodeUsageLocation]]:
        scanner = DependencyScanner(target_path)
        return scanner._scan_code_imports()

    def evaluate_rules(self, scan_result: RepositoryScanResult) -> List[RuleFinding]:
        engine = RuleEngine(scan_result)
        return engine.evaluate_all()

    def get_limitations(self) -> List[str]:
        return [
            "Analysis bounded to static AST parsing and declared Python package manifests.",
            "Dynamic runtime imports, exec() calls, or C-extension behaviors are not analyzed.",
            "Candidate verification executed in isolated sandbox virtualenvs with system packages.",
            "AI-generated migration steps must be reviewed by engineers prior to deployment.",
        ]
