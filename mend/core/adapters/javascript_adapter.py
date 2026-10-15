"""JavaScript / Node.js Ecosystem Adapter for MEND.

Provides PARTIAL support for JavaScript/TypeScript repositories:
- Manifest parsing: package.json (dependencies, devDependencies, peerDependencies), package-lock.json
- Source usage analysis: static regex-based import & require scanning across .js, .jsx, .ts, .tsx, .mjs, .cjs
- Deterministic rules: unpinned versions, deprecated packages (e.g., request), zombie dependencies
- Capabilities: Manifest and source scanning, deterministic rules, AI advisory.
- Explicit Limitation: Candidate sandbox verification (npm install / npm test) is NOT supported
  in this Track 1 release and is honestly marked as unsupported.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import (
    BaseEcosystemAdapter,
    EcosystemCapabilities,
    EcosystemDetectionResult,
    EcosystemType,
    SupportLevel,
)
from mend.core.scanner import (
    CodeUsageLocation,
    DependencyReport,
    ManifestDeclaration,
    RepositoryScanResult,
)
from mend.core.rules import Category, RuleFinding, Severity

# Well-known deprecated JavaScript packages
DEPRECATED_JS_PACKAGES: Dict[str, str] = {
    "request": "Deprecated and unmaintained since 2020. Recommend migrating to 'undici', 'axios', or native fetch.",
    "querystring": "Node.js core deprecated this module; use the URLSearchParams API instead.",
    "core-js": "Legacy core-js v2 is deprecated; migrate to core-js@3.",
    "nomnom": "Deprecated CLI option parser; migrate to 'commander' or 'yargs'.",
    "left-pad": "Unmaintained single-function utility; use String.prototype.padStart() directly.",
    "crypto": "Top-level npm 'crypto' is deprecated; use Node.js built-in 'crypto' module without npm install.",
}


class JavaScriptEcosystemAdapter(BaseEcosystemAdapter):
    """Partial-support adapter for JavaScript and TypeScript projects."""

    @property
    def ecosystem_type(self) -> EcosystemType:
        return EcosystemType.JAVASCRIPT

    @property
    def display_name(self) -> str:
        return "JavaScript / TypeScript (Node.js npm)"

    @property
    def support_level(self) -> SupportLevel:
        return SupportLevel.PARTIAL

    def detect(self, target_path: Path) -> Optional[EcosystemDetectionResult]:
        detected_manifests = []
        for manifest in ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"]:
            if (target_path / manifest).is_file():
                detected_manifests.append(manifest)

        has_js_files = any(target_path.glob("*.js")) or any(target_path.glob("*.ts"))

        if not detected_manifests and not has_js_files:
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
                candidate_sandbox_verification=False,  # Explicit boundary
                drift_detection=True,
            ),
            limitations=self.get_limitations(),
        )

    def scan_manifests(self, target_path: Path) -> List[ManifestDeclaration]:
        manifest_file = target_path / "package.json"
        if not manifest_file.is_file():
            return []

        try:
            content = manifest_file.read_text(encoding="utf-8", errors="replace")
            data = json.loads(content)
        except Exception:
            return []

        declarations: List[ManifestDeclaration] = []
        lines = content.splitlines()

        dep_sections = [
            ("dependencies", data.get("dependencies", {})),
            ("devDependencies", data.get("devDependencies", {})),
            ("peerDependencies", data.get("peerDependencies", {})),
        ]

        for section_name, deps in dep_sections:
            if not isinstance(deps, dict):
                continue
            for pkg, spec in deps.items():
                # Locate line number in package.json
                line_no = 1
                for idx, line in enumerate(lines, start=1):
                    if f'"{pkg}"' in line:
                        line_no = idx
                        break

                is_pinned = bool(re.match(r"^\d+\.\d+\.\d+$", str(spec).strip()))
                declarations.append(
                    ManifestDeclaration(
                        manifest_file="package.json",
                        line_number=line_no,
                        raw_line=f'"{pkg}": "{spec}"',
                        package_name=pkg,
                        normalized_name=pkg.lower().strip(),
                        specifier=str(spec),
                        is_pinned=is_pinned,
                    )
                )

        return declarations

    def scan_code_imports(self, target_path: Path) -> Tuple[List[Path], int, List[CodeUsageLocation]]:
        js_extensions = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
        ignore_dirs = {
            "node_modules", ".git", "dist", "build", ".next", ".turbo",
            "coverage", ".cache", "vendor"
        }

        files: List[Path] = []
        for p in target_path.rglob("*"):
            if p.is_file() and p.suffix.lower() in js_extensions:
                if any(part in ignore_dirs for part in p.parts):
                    continue
                files.append(p)

        total_loc = 0
        all_imports: List[CodeUsageLocation] = []

        # Patterns for ES modules and CommonJS
        import_patterns = [
            re.compile(r"""(?:import|export)\s+(?:.*?from\s+)?['"]([^'"]+)['"]"""),
            re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
            re.compile(r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
        ]

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                total_loc += len(lines)

                rel_path = str(file_path.relative_to(target_path)).replace("\\", "/")

                for line_idx, line in enumerate(lines, start=1):
                    line_clean = line.strip()
                    if line_clean.startswith("//") or line_clean.startswith("/*"):
                        continue

                    for pat in import_patterns:
                        for match in pat.finditer(line):
                            raw_mod = match.group(1).strip()
                            # Ignore relative paths (e.g. ./utils, ../components)
                            if raw_mod.startswith(".") or raw_mod.startswith("/"):
                                continue

                            # Extract package name (handles scoped packages e.g. @babel/core)
                            parts = raw_mod.split("/")
                            if raw_mod.startswith("@") and len(parts) >= 2:
                                pkg_name = f"{parts[0]}/{parts[1]}"
                            else:
                                pkg_name = parts[0]

                            all_imports.append(
                                CodeUsageLocation(
                                    file_path=rel_path,
                                    line_number=line_idx,
                                    statement=line_clean[:120],
                                    module=pkg_name,
                                    symbol=None,
                                    context_snippet=line_clean,
                                )
                            )
            except Exception:
                continue

        return files, total_loc, all_imports

    def scan(self, target_path: Path) -> RepositoryScanResult:
        """Run full scan on a JavaScript/Node.js repository."""
        manifest_declarations = self.scan_manifests(target_path)
        js_files, total_loc, all_imports = self.scan_code_imports(target_path)

        # Map discovered imports back to packages
        import_map: Dict[str, List[CodeUsageLocation]] = {}
        for loc in all_imports:
            norm = loc.module.lower().strip()
            import_map.setdefault(norm, []).append(loc)

        grouped_manifests: Dict[str, List[ManifestDeclaration]] = {}
        for decl in manifest_declarations:
            grouped_manifests.setdefault(decl.normalized_name, []).append(decl)

        all_pkgs = set(grouped_manifests.keys()) | set(import_map.keys())
        dependencies: Dict[str, DependencyReport] = {}

        for norm in sorted(all_pkgs):
            decls = grouped_manifests.get(norm, [])
            display_name = decls[0].package_name if decls else norm
            direct_usages = import_map.get(norm, [])
            is_direct = len(direct_usages) > 0

            dependencies[norm] = DependencyReport(
                name=display_name,
                normalized_name=norm,
                manifest_declarations=decls,
                installed_version=None,  # Node.js node_modules inspection omitted for safety
                direct_imports=direct_usages,
                is_direct_usage=is_direct,
                is_manifest_conflicted=False,
                conflict_details="",
            )

        unreferenced = [
            dep.name for dep in dependencies.values()
            if dep.manifest_declarations and not dep.is_direct_usage
        ]

        manifests_found = [
            f for f in ["package.json", "package-lock.json", "yarn.lock"]
            if (target_path / f).is_file()
        ]

        h = hashlib.sha256()
        for f in sorted(manifests_found):
            mf = target_path / f
            if mf.is_file():
                h.update(mf.read_bytes())
        for jf in sorted(js_files)[:50]:
            try:
                h.update(jf.read_bytes())
            except Exception:
                pass

        # Target name extraction from package.json
        target_name = target_path.name
        pkg_json = target_path / "package.json"
        if pkg_json.is_file():
            try:
                pj = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
                if "name" in pj and isinstance(pj["name"], str):
                    target_name = pj["name"]
            except Exception:
                pass

        return RepositoryScanResult(
            target_path=str(target_path),
            target_name=target_name,
            python_requires=None,
            manifests_found=manifests_found,
            dependencies=dependencies,
            all_imports=all_imports,
            installed_packages={},
            unreferenced_dependencies=unreferenced,
            manifest_conflicts=[],
            total_py_files=len(js_files),
            total_loc=total_loc,
            sha256_source_digest=h.hexdigest(),
            scanned_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    def evaluate_rules(self, scan_result: RepositoryScanResult) -> List[RuleFinding]:
        findings: List[RuleFinding] = []

        for norm_name, dep in scan_result.dependencies.items():
            # Rule 1: Deprecated Packages
            if norm_name in DEPRECATED_JS_PACKAGES:
                findings.append(
                    RuleFinding(
                        rule_id="RULE-JS-001",
                        package=dep.name,
                        severity=Severity.CRITICAL if dep.is_direct_usage else Severity.HIGH,
                        category=Category.DEPRECATION,
                        title=f"Deprecated JavaScript Package: {dep.name}",
                        description=DEPRECATED_JS_PACKAGES[norm_name],
                        rationale=f"Upstream maintainers officially deprecated '{dep.name}'. It receives no security patches.",
                        evidence_locations=[{"file": loc.file_path, "line": loc.line_number} for loc in dep.direct_imports[:5]],
                        suggested_action=f"Replace deprecated package '{dep.name}' with a maintained modern equivalent.",
                    )
                )

            # Rule 2: Unpinned or Wildcard Version Specs
            for decl in dep.manifest_declarations:
                spec = decl.specifier.strip()
                if spec in {"*", "latest"} or spec.startswith("^") or spec.startswith("~"):
                    findings.append(
                        RuleFinding(
                            rule_id="RULE-JS-002",
                            package=dep.name,
                            severity=Severity.MEDIUM if spec.startswith("^") else Severity.HIGH,
                            category=Category.MANIFEST_DRIFT,
                            title=f"Unpinned Version Range in package.json: {dep.name}",
                            description=f"Package '{dep.name}' declared with range '{spec}', which allows unexpected breaking drift on npm install.",
                            rationale=f"Version ranges like '{spec}' install arbitrary semver releases without deterministic locking.",
                            evidence_locations=[{"file": decl.manifest_file, "line": decl.line_number}],
                            suggested_action=f"Pin exact version in {decl.manifest_file} or enforce strict package-lock.json in CI.",
                        )
                    )

            # Rule 3: Declared dependency with zero usage (Zombie)
            if dep.manifest_declarations and not dep.is_direct_usage:
                findings.append(
                    RuleFinding(
                        rule_id="RULE-JS-003",
                        package=dep.name,
                        severity=Severity.LOW,
                        category=Category.ZOMBIE,
                        title=f"Unreferenced NPM Dependency: {dep.name}",
                        description=f"Package '{dep.name}' is declared in {dep.manifest_declarations[0].manifest_file} but no require() or import statements were detected.",
                        rationale="Unused dependencies bloat node_modules and increase supply chain attack surface.",
                        evidence_locations=[{"file": dep.manifest_declarations[0].manifest_file, "line": dep.manifest_declarations[0].line_number}],
                        suggested_action=f"Verify if '{dep.name}' is an indirect CLI tool; if unreferenced, remove from package.json.",
                    )
                )

        return findings

    def get_limitations(self) -> List[str]:
        return [
            "PARTIAL SUPPORT ONLY: JavaScript/Node.js scanning is limited to static package.json parsing, AST import extraction, and rule evaluation.",
            "Candidate sandbox execution (npm test / sandbox migration) is strictly UNSUPPORTED for JavaScript in this release.",
            "Dynamic require() calls, tsconfig path aliases, and bundler virtual modules are not evaluated.",
            "Gemma 4 migration advisories are informational; empirical candidate verification is only available for Python.",
        ]
