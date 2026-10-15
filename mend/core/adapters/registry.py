"""Ecosystem Adapter Registry for MEND.

Discovers and selects the appropriate ecosystem adapter for a target repository.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from .base import (
    BaseEcosystemAdapter,
    EcosystemDetectionResult,
    EcosystemType,
    SupportLevel,
)
from .python_adapter import PythonEcosystemAdapter
from .javascript_adapter import JavaScriptEcosystemAdapter


class UnsupportedEcosystemAdapter(BaseEcosystemAdapter):
    """Fallback adapter for unsupported repository ecosystems."""

    @property
    def ecosystem_type(self) -> EcosystemType:
        return EcosystemType.UNSUPPORTED

    @property
    def display_name(self) -> str:
        return "Unsupported Ecosystem"

    @property
    def support_level(self) -> SupportLevel:
        return SupportLevel.UNSUPPORTED

    def detect(self, target_path: Path) -> Optional[EcosystemDetectionResult]:
        return EcosystemDetectionResult(
            ecosystem=self.ecosystem_type,
            display_name=self.display_name,
            support_level=self.support_level,
            detected_manifests=[],
            capabilities=None,  # type: ignore
            limitations=[
                "No recognized dependency manifests (pyproject.toml, requirements.txt, or package.json) found in target directory.",
                "Ecosystem is unsupported by MEND in this release.",
            ],
        )

    def scan_manifests(self, target_path: Path) -> List:
        return []

    def scan_code_imports(self, target_path: Path) -> Tuple[List[Path], int, List]:
        return [], 0, []

    def evaluate_rules(self, scan_result: Any) -> List:
        return []

    def get_limitations(self) -> List[str]:
        return ["Unsupported repository ecosystem. No dependency manifests detected."]


# Registry of known adapters ordered by specialization priority
ADAPTERS: List[BaseEcosystemAdapter] = [
    PythonEcosystemAdapter(),
    JavaScriptEcosystemAdapter(),
]


def detect_ecosystem(target_path: Path | str) -> Tuple[BaseEcosystemAdapter, EcosystemDetectionResult]:
    """Inspect directory and return the highest-priority matching adapter and detection result."""
    p = Path(target_path).resolve()
    for adapter in ADAPTERS:
        detection = adapter.detect(p)
        if detection is not None:
            return adapter, detection

    unsupported = UnsupportedEcosystemAdapter()
    return unsupported, unsupported.detect(p)  # type: ignore


def get_adapter_for_path(target_path: Path | str) -> BaseEcosystemAdapter:
    """Convenience helper to retrieve just the adapter instance."""
    adapter, _ = detect_ecosystem(target_path)
    return adapter
