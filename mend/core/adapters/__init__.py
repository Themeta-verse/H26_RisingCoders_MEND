"""Ecosystem Adapters for MEND (Migration Evidence & Dependency Navigator).

Provides modular, non-overclaiming support for different repository ecosystems:
- Python (Full support: pyproject.toml, requirements.txt, AST imports, sandbox pytest verification)
- JavaScript / Node.js (Partial support: package.json, package-lock.json, regex/AST imports; candidate sandbox execution explicitly unsupported)
"""

from .base import (
    BaseEcosystemAdapter,
    EcosystemDetectionResult,
    EcosystemType,
    SupportLevel,
)
from .python_adapter import PythonEcosystemAdapter
from .javascript_adapter import JavaScriptEcosystemAdapter
from .registry import detect_ecosystem, get_adapter_for_path

__all__ = [
    "BaseEcosystemAdapter",
    "EcosystemDetectionResult",
    "EcosystemType",
    "SupportLevel",
    "PythonEcosystemAdapter",
    "JavaScriptEcosystemAdapter",
    "detect_ecosystem",
    "get_adapter_for_path",
]
