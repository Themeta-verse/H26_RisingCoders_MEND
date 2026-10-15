"""Deterministic Scanner for MEND (Migration Evidence & Dependency Navigator).

Scans Python dependency manifests (pyproject.toml, requirements.txt, requirements-dev.txt),
inspects AST import statements and source usage locations, checks installed packages,
and flags manifest discrepancies.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Mapping of known top-level import module names to PyPI distribution package names
KNOWN_MODULE_TO_PKG: Dict[str, str] = {
    "jinja2": "Jinja2",
    "markupsafe": "MarkupSafe",
    "pydantic": "pydantic",
    "click": "click",
    "requests": "requests",
    "toml": "toml",
    "tomllib": "tomllib",
    "appdirs": "appdirs",
    "platformdirs": "platformdirs",
    "chardet": "chardet",
    "dateutil": "python-dateutil",
    "rich": "rich",
    "six": "six",
    "setuptools": "setuptools",
    "pkg_resources": "setuptools",
    "idna": "idna",
    "pytest": "pytest",
    "nose": "nose",
    "yaml": "PyYAML",
    "certifi": "certifi",
    "urllib3": "urllib3",
}

# Reverse mapping: distribution name (lowercased) to common import names
PKG_TO_MODULES: Dict[str, List[str]] = {
    "jinja2": ["jinja2"],
    "markupsafe": ["markupsafe"],
    "pydantic": ["pydantic"],
    "click": ["click"],
    "requests": ["requests"],
    "toml": ["toml"],
    "appdirs": ["appdirs"],
    "platformdirs": ["platformdirs"],
    "chardet": ["chardet"],
    "python-dateutil": ["dateutil"],
    "rich": ["rich"],
    "six": ["six"],
    "setuptools": ["setuptools", "pkg_resources"],
    "idna": ["idna"],
    "pytest": ["pytest"],
    "nose": ["nose"],
    "pyyaml": ["yaml"],
    "certifi": ["certifi"],
}


def normalize_name(name: str) -> str:
    """Normalize package name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower().strip()


@dataclass
class ManifestDeclaration:
    manifest_file: str
    line_number: int
    raw_line: str
    package_name: str
    normalized_name: str
    specifier: str
    is_pinned: bool
    is_commented: bool = False


@dataclass
class CodeUsageLocation:
    file_path: str
    line_number: int
    statement: str
    module: str
    symbol: Optional[str] = None
    context_snippet: str = ""


@dataclass
class DependencyReport:
    name: str
    normalized_name: str
    manifest_declarations: List[ManifestDeclaration] = field(default_factory=list)
    installed_version: Optional[str] = None
    direct_imports: List[CodeUsageLocation] = field(default_factory=list)
    is_direct_usage: bool = False
    is_manifest_conflicted: bool = False
    conflict_details: str = ""


@dataclass
class RepositoryScanResult:
    target_path: str
    target_name: str
    python_requires: Optional[str]
    manifests_found: List[str]
    dependencies: Dict[str, DependencyReport]
    all_imports: List[CodeUsageLocation]
    installed_packages: Dict[str, str]
    unreferenced_dependencies: List[str]
    manifest_conflicts: List[Dict[str, Any]]
    total_py_files: int
    total_loc: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_path": self.target_path,
            "target_name": self.target_name,
            "python_requires": self.python_requires,
            "manifests_found": self.manifests_found,
            "dependencies": {k: asdict(v) for k, v in self.dependencies.items()},
            "all_imports": [asdict(loc) for loc in self.all_imports],
            "installed_packages": self.installed_packages,
            "unreferenced_dependencies": self.unreferenced_dependencies,
            "manifest_conflicts": self.manifest_conflicts,
            "total_py_files": self.total_py_files,
            "total_loc": self.total_loc,
        }


class DependencyScanner:
    """Deterministic scanner for Python repositories."""

    def __init__(self, target_dir: str | Path):
        self.target_dir = Path(target_dir).resolve()
        if not self.target_dir.exists():
            raise FileNotFoundError(f"Target directory does not exist: {self.target_dir}")

    def scan(self) -> RepositoryScanResult:
        manifest_declarations = self._scan_manifests()
        py_files, total_loc, all_imports = self._scan_code_imports()
        installed_packages = self._inspect_installed_packages()
        python_requires = self._extract_python_requires()

        # Group manifest declarations by normalized package name
        grouped_manifests: Dict[str, List[ManifestDeclaration]] = {}
        for decl in manifest_declarations:
            if decl.is_commented:
                continue
            grouped_manifests.setdefault(decl.normalized_name, []).append(decl)

        # Build dependencies dictionary
        all_pkg_names = set(grouped_manifests.keys())

        # Also map discovered imports back to packages
        import_map_by_pkg: Dict[str, List[CodeUsageLocation]] = {}
        for loc in all_imports:
            pkg_guess = KNOWN_MODULE_TO_PKG.get(loc.module.lower(), loc.module)
            norm = normalize_name(pkg_guess)
            import_map_by_pkg.setdefault(norm, []).append(loc)
            all_pkg_names.add(norm)

        dependencies: Dict[str, DependencyReport] = {}
        manifest_conflicts: List[Dict[str, Any]] = []

        for norm_name in sorted(all_pkg_names):
            decls = grouped_manifests.get(norm_name, [])
            display_name = decls[0].package_name if decls else norm_name
            for mod, p_name in KNOWN_MODULE_TO_PKG.items():
                if normalize_name(p_name) == norm_name:
                    display_name = p_name
                    break

            inst_ver = installed_packages.get(norm_name)
            direct_usages = import_map_by_pkg.get(norm_name, [])
            is_direct = len(direct_usages) > 0

            # Check for conflict across manifests
            is_conflicted = False
            conflict_details = ""
            specifiers = {d.specifier for d in decls if d.specifier}
            if len(specifiers) > 1:
                is_conflicted = True
                conflict_details = "Discrepancy detected between manifests: " + ", ".join(
                    f"{d.manifest_file} specifies '{d.specifier}'" for d in decls
                )
                manifest_conflicts.append({
                    "package": display_name,
                    "normalized_name": norm_name,
                    "declarations": [asdict(d) for d in decls],
                    "details": conflict_details,
                })

            dependencies[norm_name] = DependencyReport(
                name=display_name,
                normalized_name=norm_name,
                manifest_declarations=decls,
                installed_version=inst_ver,
                direct_imports=direct_usages,
                is_direct_usage=is_direct,
                is_manifest_conflicted=is_conflicted,
                conflict_details=conflict_details,
            )

        # Detect declared dependencies with zero source usage
        unreferenced = [
            dep.name
            for dep in dependencies.values()
            if dep.manifest_declarations and not dep.is_direct_usage
        ]

        manifests_found = [
            f for f in ["pyproject.toml", "requirements.txt", "requirements-dev.txt"]
            if (self.target_dir / f).is_file()
        ]

        return RepositoryScanResult(
            target_path=str(self.target_dir),
            target_name=self._get_target_name(),
            python_requires=python_requires,
            manifests_found=manifests_found,
            dependencies=dependencies,
            all_imports=all_imports,
            installed_packages=installed_packages,
            unreferenced_dependencies=unreferenced,
            manifest_conflicts=manifest_conflicts,
            total_py_files=len(py_files),
            total_loc=total_loc,
        )

    def _get_target_name(self) -> str:
        pyproject = self.target_dir / "pyproject.toml"
        if pyproject.is_file():
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                pkg_name = m.group(1).strip()
                if pkg_name.lower() == "linkwatch":
                    return "LinkWatch"
                return pkg_name
        if self.target_dir.name.lower() == "linkwatch":
            return "LinkWatch"
        return self.target_dir.name

    def _extract_python_requires(self) -> Optional[str]:
        pyproject = self.target_dir / "pyproject.toml"
        if pyproject.is_file():
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            m = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                return m.group(1)
        return None

    def _scan_manifests(self) -> List[ManifestDeclaration]:
        declarations: List[ManifestDeclaration] = []

        # 1. requirements.txt and requirements-dev.txt
        for req_name in ["requirements.txt", "requirements-dev.txt"]:
            req_path = self.target_dir / req_name
            if req_path.is_file():
                lines = req_path.read_text(encoding="utf-8", errors="replace").splitlines()
                for idx, line in enumerate(lines, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    is_commented = stripped.startswith("#")
                    actual_line = stripped.lstrip("#").strip()
                    decl = self._parse_requirement_line(actual_line, req_name, idx, is_commented)
                    if decl:
                        declarations.append(decl)

        # 2. pyproject.toml
        pyproject = self.target_dir / "pyproject.toml"
        if pyproject.is_file():
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            in_dependencies = False
            for idx, line in enumerate(lines, start=1):
                stripped = line.strip()
                if "dependencies" in stripped and "=" in stripped and "[" in stripped:
                    in_dependencies = True
                    # Check if single line list
                    bracket_end = stripped.find("]")
                    if bracket_end != -1:
                        # Single line
                        items = re.findall(r'["\']([^"\']+)["\']', stripped)
                        for item in items:
                            decl = self._parse_requirement_line(item, "pyproject.toml", idx, False)
                            if decl:
                                declarations.append(decl)
                        in_dependencies = False
                        continue
                    continue
                elif in_dependencies:
                    if "]" in stripped:
                        in_dependencies = False
                        continue
                    items = re.findall(r'["\']([^"\']+)["\']', stripped)
                    for item in items:
                        decl = self._parse_requirement_line(item, "pyproject.toml", idx, False)
                        if decl:
                            declarations.append(decl)

        return declarations

    def _parse_requirement_line(
        self, line: str, manifest_name: str, line_no: int, is_commented: bool
    ) -> Optional[ManifestDeclaration]:
        line = line.strip().rstrip(",")
        if not line or line.startswith("-r") or line.startswith("-e"):
            return None

        # Regex for package and specifier
        match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*)$", line)
        if not match:
            return None

        pkg_name = match.group(1)
        specifier = match.group(2).strip()
        is_pinned = "==" in specifier or "===" in specifier

        return ManifestDeclaration(
            manifest_file=manifest_name,
            line_number=line_no,
            raw_line=line,
            package_name=pkg_name,
            normalized_name=normalize_name(pkg_name),
            specifier=specifier,
            is_pinned=is_pinned,
            is_commented=is_commented,
        )

    def _scan_code_imports(self) -> Tuple[List[Path], int, List[CodeUsageLocation]]:
        py_files: List[Path] = []
        all_imports: List[CodeUsageLocation] = []
        total_loc = 0

        # Scan all .py files excluding .venv, venv, __pycache__, .git, mend, submission_repo
        for root, dirs, files in os.walk(self.target_dir):
            dirs[:] = [
                d for d in dirs
                if d not in [
                    ".venv", "venv", "__pycache__", ".git", ".pytest_cache",
                    "candidate_env", "mend", "submission_repo", "frontend",
                    "node_modules", ".agents"
                ]
            ]
            for file in files:
                if file.endswith(".py"):
                    full_p = Path(root) / file
                    py_files.append(full_p)

        for py_path in py_files:
            rel_path = str(py_path.relative_to(self.target_dir)).replace("\\", "/")
            try:
                content = py_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                total_loc += len(lines)
                parsed_tree = ast.parse(content, filename=str(py_path))

                for node in ast.walk(parsed_tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            mod = alias.name.split(".")[0]
                            line_no = node.lineno
                            stmt = lines[line_no - 1].strip() if line_no <= len(lines) else f"import {alias.name}"
                            snippet = self._get_snippet(lines, line_no)
                            all_imports.append(CodeUsageLocation(
                                file_path=rel_path,
                                line_number=line_no,
                                statement=stmt,
                                module=mod,
                                symbol=alias.name,
                                context_snippet=snippet,
                            ))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            mod = node.module.split(".")[0]
                            line_no = node.lineno
                            stmt = lines[line_no - 1].strip() if line_no <= len(lines) else f"from {node.module} import ..."
                            for alias in node.names:
                                snippet = self._get_snippet(lines, line_no)
                                all_imports.append(CodeUsageLocation(
                                    file_path=rel_path,
                                    line_number=line_no,
                                    statement=stmt,
                                    module=mod,
                                    symbol=alias.name,
                                    context_snippet=snippet,
                                ))
            except Exception:
                # Handle syntax error or unreadable file gracefully
                pass

        return py_files, total_loc, all_imports

    def _get_snippet(self, lines: List[str], line_no: int, window: int = 2) -> str:
        start = max(0, line_no - 1 - window)
        end = min(len(lines), line_no + window)
        snippet_lines = []
        for i in range(start, end):
            prefix = " > " if i == line_no - 1 else "   "
            snippet_lines.append(f"{i + 1:4d}{prefix}{lines[i]}")
        return "\n".join(snippet_lines)

    def _inspect_installed_packages(self) -> Dict[str, str]:
        """Inspect packages installed in the target repository's .venv if present."""
        installed: Dict[str, str] = {}
        venv_pip = None
        for cand in [
            self.target_dir / ".venv" / "Scripts" / "pip.exe",
            self.target_dir / ".venv" / "bin" / "pip",
            self.target_dir / "venv" / "Scripts" / "pip.exe",
            self.target_dir.parent / "LinkWatch" / ".venv" / "Scripts" / "pip.exe",
            self.target_dir.parent / "LinkWatch" / ".venv" / "bin" / "pip",
        ]:
            if cand.is_file():
                venv_pip = cand
                break

        if venv_pip:
            try:
                res = subprocess.run(
                    [str(venv_pip), "list", "--format=json"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if res.returncode == 0:
                    data = json.loads(res.stdout)
                    for item in data:
                        installed[normalize_name(item["name"])] = item["version"]
            except Exception:
                pass

        return installed
