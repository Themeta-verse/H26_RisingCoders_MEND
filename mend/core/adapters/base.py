"""Base Ecosystem Adapter Specification for MEND.

Defines the contract for repository discovery, ecosystem detection,
manifest scanning, source usage inspection, rule evaluation, and honest capability boundaries.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class EcosystemType(str, enum.Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    UNSUPPORTED = "unsupported"


class SupportLevel(str, enum.Enum):
    FULL = "full"          # Manifests + Source AST + Rules + Gemma Advisory + Sandbox Candidate Verification
    PARTIAL = "partial"    # Manifests + Source Scanning + Rules; Sandbox verification explicitly not available
    UNSUPPORTED = "unsupported"


@dataclass
class EcosystemCapabilities:
    manifest_parsing: bool = True
    code_usage_analysis: bool = True
    deterministic_rules: bool = True
    ai_advisory: bool = True
    candidate_sandbox_verification: bool = False
    drift_detection: bool = True


@dataclass
class EcosystemDetectionResult:
    ecosystem: EcosystemType
    display_name: str
    support_level: SupportLevel
    detected_manifests: List[str]
    capabilities: EcosystemCapabilities
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ecosystem": self.ecosystem.value,
            "display_name": self.display_name,
            "support_level": self.support_level.value,
            "detected_manifests": self.detected_manifests,
            "capabilities": asdict(self.capabilities),
            "limitations": self.limitations,
        }


class BaseEcosystemAdapter(ABC):
    """Abstract base class for all ecosystem adapters in MEND."""

    @property
    @abstractmethod
    def ecosystem_type(self) -> EcosystemType:
        """The primary ecosystem type identifier."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """User-facing ecosystem name (e.g. 'Python / PEP 508' or 'JavaScript / Node.js')."""
        pass

    @property
    @abstractmethod
    def support_level(self) -> SupportLevel:
        """Honest support level: full, partial, or unsupported."""
        pass

    @abstractmethod
    def detect(self, target_path: Path) -> Optional[EcosystemDetectionResult]:
        """Detect whether this adapter applies to the given directory."""
        pass

    @abstractmethod
    def scan_manifests(self, target_path: Path) -> List[Any]:
        """Scan dependency declarations from ecosystem-specific manifests."""
        pass

    @abstractmethod
    def scan_code_imports(self, target_path: Path) -> Tuple[List[Path], int, List[Any]]:
        """Inspect source files for import / require statements."""
        pass

    @abstractmethod
    def evaluate_rules(self, scan_result: Any) -> List[Any]:
        """Evaluate deterministic resilience rules for this ecosystem."""
        pass

    @abstractmethod
    def get_limitations(self) -> List[str]:
        """Explicit boundary disclosures and limitations."""
        pass
