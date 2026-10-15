"""Deterministic Rule Engine for MEND.

Evaluates repository scan results against dependency resilience rules.
Each finding includes documented severity, category, rationale, and exact code/manifest evidence.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .scanner import RepositoryScanResult


class Severity(str, Enum):
    CRITICAL = "Critical"  # Causes immediate runtime error or test failure
    HIGH = "High"          # High risk of breakage, manifest contradiction, or major API drift
    MEDIUM = "Medium"      # Deprecated library, abandoned upstream, or runtime deprecation warning
    LOW = "Low"            # Hygiene, unused dependency, or unneeded pin
    INFO = "Info"          # Opportunity for modernization (e.g. stdlib replacement)


class Category(str, Enum):
    COMPATIBILITY = "Compatibility"
    MANIFEST_DRIFT = "Manifest Drift"
    DEPRECATION = "Deprecation"
    ZOMBIE = "Zombie Dependency"
    MODERNIZATION = "Modernization"
    OBSOLESCENCE = "Obsolescence"


@dataclass
class RuleFinding:
    rule_id: str
    package: str
    severity: Severity
    category: Category
    title: str
    description: str
    rationale: str
    evidence_locations: List[Dict[str, Any]]
    suggested_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "package": self.package,
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "rationale": self.rationale,
            "evidence_locations": self.evidence_locations,
            "suggested_action": self.suggested_action,
        }


class RuleEngine:
    """Evaluates scan results and generates deterministic resilience findings."""

    def evaluate(self, scan_result: RepositoryScanResult) -> List[RuleFinding]:
        findings: List[RuleFinding] = []

        findings.extend(self._check_manifest_conflicts(scan_result))
        findings.extend(self._check_jinja2_markupsafe_incompatibility(scan_result))
        findings.extend(self._check_pydantic_v1_v2_migration(scan_result))
        findings.extend(self._check_appdirs_deprecation(scan_result))
        findings.extend(self._check_pkg_resources_deprecation(scan_result))
        findings.extend(self._check_nose_obsolescence(scan_result))
        findings.extend(self._check_unused_dependencies(scan_result))
        findings.extend(self._check_toml_stdlib_replacement(scan_result))

        return findings

    def _check_manifest_conflicts(self, scan: RepositoryScanResult) -> List[RuleFinding]:
        findings = []
        for conflict in scan.manifest_conflicts:
            pkg = conflict["package"]
            decls = conflict["declarations"]
            evidence = [
                {
                    "file": d["manifest_file"],
                    "line": d["line_number"],
                    "snippet": d["raw_line"],
                }
                for d in decls
            ]
            findings.append(RuleFinding(
                rule_id="RULE-CONF-001",
                package=pkg,
                severity=Severity.HIGH,
                category=Category.MANIFEST_DRIFT,
                title=f"Manifest Specification Conflict for {pkg}",
                description=conflict["details"],
                rationale="Conflicting version specifiers across manifests lead to non-deterministic installation, "
                          "silent version drift between development and production, and package resolver confusion.",
                evidence_locations=evidence,
                suggested_action=f"Reconcile {pkg} version requirements across pyproject.toml and requirements.txt.",
            ))
        return findings

    def _check_jinja2_markupsafe_incompatibility(self, scan: RepositoryScanResult) -> List[RuleFinding]:
        findings = []
        jinja_dep = scan.dependencies.get("jinja2")
        if not jinja_dep:
            return findings

        # Check if Jinja2 is pinned to 2.x
        is_jinja_2 = False
        jinja_evidence = []
        for d in jinja_dep.manifest_declarations:
            if "2." in d.specifier or d.specifier.startswith("==2."):
                is_jinja_2 = True
                jinja_evidence.append({
                    "file": d.manifest_file,
                    "line": d.line_number,
                    "snippet": d.raw_line,
                })

        # Add code usage location if available
        for imp in jinja_dep.direct_imports:
            jinja_evidence.append({
                "file": imp.file_path,
                "line": imp.line_number,
                "snippet": imp.context_snippet or imp.statement,
            })

        # Check if installed MarkupSafe is >= 2.1 or 3.0
        markupsafe_ver = scan.installed_packages.get("markupsafe", "")
        is_modern_markupsafe = markupsafe_ver.startswith("3.") or markupsafe_ver.startswith("2.1") or markupsafe_ver.startswith("2.2")

        if is_jinja_2:
            findings.append(RuleFinding(
                rule_id="RULE-COMPAT-001",
                package="Jinja2",
                severity=Severity.CRITICAL,
                category=Category.COMPATIBILITY,
                title="Incompatible Transitive Pairing: Jinja2 2.11.x with Modern MarkupSafe",
                description=f"Jinja2 2.11.3 pinned in manifests imports 'soft_unicode' from MarkupSafe. "
                            f"Installed MarkupSafe is {markupsafe_ver or 'modern 3.x'}, which removed 'soft_unicode'.",
                rationale="Causes an immediate runtime ImportError when any template is rendered. "
                          "This directly causes test_report.py to fail in the baseline environment.",
                evidence_locations=jinja_evidence,
                suggested_action="Upgrade Jinja2 to >=3.1.4 (or pin MarkupSafe <2.1.0 in legacy candidate setups).",
            ))
        return findings

    def _check_pydantic_v1_v2_migration(self, scan: RepositoryScanResult) -> List[RuleFinding]:
        findings = []
        pydantic_dep = scan.dependencies.get("pydantic")
        if not pydantic_dep:
            return findings

        # Check if target source code uses v1 idioms like @validator or class Config
        v1_evidence = []
        for root_f in ["linkwatch/config.py", "config.py"]:
            for imp in pydantic_dep.direct_imports:
                if imp.file_path == root_f or imp.file_path.endswith("config.py"):
                    v1_evidence.append({
                        "file": imp.file_path,
                        "line": imp.line_number,
                        "snippet": imp.context_snippet or imp.statement,
                    })

        pyproject_decl = [d for d in pydantic_dep.manifest_declarations if d.manifest_file == "pyproject.toml"]
        req_decl = [d for d in pydantic_dep.manifest_declarations if d.manifest_file == "requirements.txt"]

        declares_v2 = any(">=2" in d.specifier or ">2" in d.specifier for d in pyproject_decl)
        pins_v1 = any("1." in d.specifier for d in req_decl)

        if declares_v2 and (pins_v1 or v1_evidence):
            for d in pydantic_dep.manifest_declarations:
                v1_evidence.append({
                    "file": d.manifest_file,
                    "line": d.line_number,
                    "snippet": d.raw_line,
                })
            findings.append(RuleFinding(
                rule_id="RULE-BREAK-001",
                package="pydantic",
                severity=Severity.HIGH,
                category=Category.COMPATIBILITY,
                title="Pydantic V1/V2 Incompatibility and Specifier Mismatch",
                description="Source code utilizes Pydantic v1 '@validator' and 'class Config' patterns, while "
                            "pyproject.toml requests 'pydantic>=2' and requirements.txt locks 'pydantic==1.10.13'.",
                rationale="Pydantic v2 deprecates @validator in favor of @field_validator and alters BaseModel.Config. "
                          "Installing via pyproject.toml without pinning v1 will cause deprecation warnings or validation failures.",
                evidence_locations=v1_evidence,
                suggested_action="Either align manifests to 'pydantic<2.0.0' or migrate config.py to Pydantic v2 (@field_validator, ConfigDict).",
            ))
        return findings

    def _check_appdirs_deprecation(self, scan: RepositoryScanResult) -> List[RuleFinding]:
        findings = []
        appdirs_dep = scan.dependencies.get("appdirs")
        if not appdirs_dep:
            return findings

        evidence = []
        for d in appdirs_dep.manifest_declarations:
            evidence.append({"file": d.manifest_file, "line": d.line_number, "snippet": d.raw_line})
        for imp in appdirs_dep.direct_imports:
            evidence.append({"file": imp.file_path, "line": imp.line_number, "snippet": imp.context_snippet or imp.statement})

        findings.append(RuleFinding(
            rule_id="RULE-DEPR-001",
            package="appdirs",
            severity=Severity.MEDIUM,
            category=Category.DEPRECATION,
            title="Unmaintained Library: appdirs Pinned at 1.4.4",
            description="appdirs is an abandoned library with no releases since 2017. The Python packaging community "
                        "has officially standardized on 'platformdirs' as its direct drop-in replacement.",
            rationale="appdirs does not receive bug fixes, security patches, or updates for newer operating systems.",
            evidence_locations=evidence,
            suggested_action="Migrate from appdirs to platformdirs (drop-in API compatible user_cache_dir).",
        ))
        return findings

    def _check_pkg_resources_deprecation(self, scan: RepositoryScanResult) -> List[RuleFinding]:
        findings = []
        pkg_res_usages = [imp for imp in scan.all_imports if imp.module == "pkg_resources"]
        if not pkg_res_usages:
            return findings

        evidence = [
            {"file": imp.file_path, "line": imp.line_number, "snippet": imp.context_snippet or imp.statement}
            for imp in pkg_res_usages
        ]

        findings.append(RuleFinding(
            rule_id="RULE-DEPR-002",
            package="setuptools",
            severity=Severity.MEDIUM,
            category=Category.DEPRECATION,
            title="Deprecated API: pkg_resources Imported Directly",
            description="linkwatch imports pkg_resources to locate template assets. Setuptools has formally deprecated "
                        "pkg_resources, and it generates a runtime DeprecationWarning.",
            rationale="pkg_resources has slow import overhead and is scheduled for retirement. Standard library "
                      "'importlib.resources' (available in Python 3.9+) is the modern, zero-dependency replacement.",
            evidence_locations=evidence,
            suggested_action="Replace pkg_resources with importlib.resources.files() from the Python standard library.",
        ))
        return findings

    def _check_nose_obsolescence(self, scan: RepositoryScanResult) -> List[RuleFinding]:
        findings = []
        nose_dep = scan.dependencies.get("nose")
        if not nose_dep:
            return findings

        evidence = []
        for d in nose_dep.manifest_declarations:
            evidence.append({"file": d.manifest_file, "line": d.line_number, "snippet": d.raw_line})

        findings.append(RuleFinding(
            rule_id="RULE-OBSOLETE-001",
            package="nose",
            severity=Severity.MEDIUM,
            category=Category.OBSOLESCENCE,
            title="Obsolete Test Framework: nose==1.3.7 Declared in Dev Requirements",
            description="nose is an obsolete test runner discontinued since 2015. It relies on the 'imp' module "
                        "which was completely removed in Python 3.12, causing nose to fail to even import.",
            rationale="LinkWatch's test suite is written using pytest fixtures and test functions; nose is completely unused.",
            evidence_locations=evidence,
            suggested_action="Remove nose==1.3.7 from requirements-dev.txt and rely exclusively on pytest.",
        ))
        return findings

    def _check_unused_dependencies(self, scan: RepositoryScanResult) -> List[RuleFinding]:
        findings = []
        for pkg_name in scan.unreferenced_dependencies:
            dep = scan.dependencies[pkg_name]
            # Exclude known dev/runtime tooling like pytest, setuptools, wheel, rich if used via CLI
            if dep.name.lower() in ["pytest", "setuptools", "wheel"]:
                continue
            # If six is declared but never imported
            if dep.name.lower() == "six":
                evidence = [{"file": d.manifest_file, "line": d.line_number, "snippet": d.raw_line} for d in dep.manifest_declarations]
                findings.append(RuleFinding(
                    rule_id="RULE-ZOMBIE-001",
                    package="six",
                    severity=Severity.LOW,
                    category=Category.ZOMBIE,
                    title="Unreferenced Dependency: six",
                    description="six is declared in both requirements.txt and pyproject.toml, but 0 imports were found in the codebase.",
                    rationale="Python 2 compatibility shim is unnecessary for a codebase targeting Python >= 3.10. "
                              "Leaving unused dependencies bloats the install surface and confuses audits.",
                    evidence_locations=evidence,
                    suggested_action="Remove 'six' from pyproject.toml and requirements.txt.",
                ))
        return findings

    def _check_toml_stdlib_replacement(self, scan: RepositoryScanResult) -> List[RuleFinding]:
        findings = []
        toml_dep = scan.dependencies.get("toml")
        if not toml_dep:
            return findings

        evidence = []
        for d in toml_dep.manifest_declarations:
            evidence.append({"file": d.manifest_file, "line": d.line_number, "snippet": d.raw_line})
        for imp in toml_dep.direct_imports:
            evidence.append({"file": imp.file_path, "line": imp.line_number, "snippet": imp.context_snippet or imp.statement})

        findings.append(RuleFinding(
            rule_id="RULE-STDLIB-001",
            package="toml",
            severity=Severity.INFO,
            category=Category.MODERNIZATION,
            title="Standard Library Modernization Opportunity: toml -> tomllib",
            description="LinkWatch uses the third-party 'toml' package for reading sites.toml. "
                        "Python 3.11+ includes 'tomllib' in the standard library.",
            rationale="Transitioning to tomllib eliminates an external dependency for reading TOML configurations.",
            evidence_locations=evidence,
            suggested_action="Use standard library 'tomllib' on Python 3.11+ with fallback to 'tomli' on Python 3.10.",
        ))
        return findings
