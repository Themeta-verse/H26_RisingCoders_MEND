"""Core scanning, rule evaluation, model client, and candidate verification modules."""

from .scanner import DependencyScanner, RepositoryScanResult
from .rules import RuleEngine, RuleFinding, Severity, Category
from .model_client import GemmaModelClient, MigrationRecommendation
from .candidate_runner import CandidateRunner, TestExecutionResult
from .capsule import DependencyCapsuleGenerator

__all__ = [
    "DependencyScanner",
    "RepositoryScanResult",
    "RuleEngine",
    "RuleFinding",
    "Severity",
    "Category",
    "GemmaModelClient",
    "MigrationRecommendation",
    "CandidateRunner",
    "TestExecutionResult",
    "DependencyCapsuleGenerator",
]
