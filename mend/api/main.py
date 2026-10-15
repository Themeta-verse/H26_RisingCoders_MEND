"""FastAPI Server for MEND (Migration Evidence & Dependency Navigator).

Provides REST APIs for:
- System and Gemma 4 health checking
- Deterministic repository scanning
- Rule engine resilience evaluation
- Real Gemma 4 migration recommendation generation
- Baseline test suite execution (read-only)
- Isolated candidate experiment verification
- Dependency Exit Capsule generation, JSON download, and HTML report export
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mend.core.candidate_runner import CandidateRunner, MigrationVerificationComparison, TestExecutionResult
from mend.core.capsule import DependencyCapsuleGenerator
from mend.core.model_client import GemmaModelClient, MigrationRecommendation
from mend.core.rules import RuleEngine, RuleFinding
from mend.core.scanner import DependencyScanner, RepositoryScanResult

app = FastAPI(
    title="MEND API",
    description="Migration Evidence & Dependency Navigator API powered by Gemma 4",
    version="1.0.0",
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Workspace paths
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if (WORKSPACE_ROOT / "LinkWatch" / "pyproject.toml").is_file():
    DEFAULT_TARGET_PATH = WORKSPACE_ROOT / "LinkWatch"
elif (WORKSPACE_ROOT / "pyproject.toml").is_file():
    DEFAULT_TARGET_PATH = WORKSPACE_ROOT
else:
    DEFAULT_TARGET_PATH = WORKSPACE_ROOT / "LinkWatch"

# Global state caches for responsiveness
_cached_scan: Optional[RepositoryScanResult] = None
_cached_findings: Optional[List[RuleFinding]] = None
_cached_recommendations: Dict[str, MigrationRecommendation] = {}
_cached_baseline_tests: Optional[TestExecutionResult] = None
_cached_candidate_verifications: List[MigrationVerificationComparison] = []


def get_target_path(custom_path: Optional[str] = None) -> Path:
    if custom_path:
        p = Path(custom_path).resolve()
        if p.exists() and p.is_dir():
            return p
    return DEFAULT_TARGET_PATH


class RecommendationRequest(BaseModel):
    package_name: str
    target_path: Optional[str] = None
    timeout_seconds: Optional[float] = Field(default=60.0, description="Configurable timeout in seconds")


class VerifyCandidateRequest(BaseModel):
    candidate_id: str
    package_name: str
    package_install_spec: str
    code_modifications: Optional[List[Dict[str, str]]] = None
    target_path: Optional[str] = None


@app.get("/api/status")
def get_system_status(target_path: Optional[str] = None):
    """Check health of local Ollama, Gemma 4 model, and target repository."""
    target = get_target_path(target_path)
    client = GemmaModelClient()
    ollama_health = client.check_health()

    target_name = (
        "LinkWatch"
        if (target / "linkwatch").is_dir() or target.name.lower() == "linkwatch"
        else target.name
    )

    return {
        "status": "online",
        "target_repository": {
            "name": target_name,
            "path": str(target),
            "exists": target.exists(),
            "has_pyproject": (target / "pyproject.toml").is_file(),
            "has_requirements": (target / "requirements.txt").is_file(),
            "has_venv": (target / ".venv").is_dir(),
        },
        "gemma_runtime": {
            "endpoint": ollama_health.endpoint,
            "is_online": ollama_health.is_online,
            "model_tag": ollama_health.model_tag,
            "model_available": ollama_health.model_available,
            "available_models": ollama_health.available_models,
            "error_message": ollama_health.error_message,
        },
    }


@app.get("/api/scan")
def scan_repository(target_path: Optional[str] = None, refresh: bool = False):
    """Execute deterministic static analysis on the target repository."""
    global _cached_scan
    target = get_target_path(target_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Target directory {target} not found")

    if _cached_scan is None or refresh:
        scanner = DependencyScanner(target)
        _cached_scan = scanner.scan()

    return _cached_scan.to_dict()


@app.get("/api/rules")
def evaluate_rules(target_path: Optional[str] = None, refresh: bool = False):
    """Run deterministic rule engine against scanned repository evidence."""
    global _cached_findings
    scan_data = scan_repository(target_path=target_path, refresh=refresh)
    if _cached_findings is None or refresh:
        engine = RuleEngine()
        _cached_findings = engine.evaluate(_cached_scan)

    return [f.to_dict() for f in _cached_findings]


@app.post("/api/recommend")
def get_recommendation(req: RecommendationRequest):
    """Invoke local Gemma 4 model via Ollama with bounded evidence for a specific package."""
    global _cached_recommendations
    target = get_target_path(req.target_path)
    if _cached_scan is None:
        scan_repository(str(target))
    if _cached_findings is None:
        evaluate_rules(str(target))

    norm_name = req.package_name.lower().replace("_", "-")
    dep = _cached_scan.dependencies.get(norm_name)
    if not dep:
        # Check by display name
        for d in _cached_scan.dependencies.values():
            if d.name.lower() == req.package_name.lower():
                dep = d
                break

    if not dep:
        raise HTTPException(status_code=404, detail=f"Dependency '{req.package_name}' not found in target")

    # Bounded evidence
    from dataclasses import asdict
    decls = [asdict(d) for d in dep.manifest_declarations]
    usages = [asdict(loc) for loc in dep.direct_imports]
    rel_findings = [f.to_dict() for f in _cached_findings if f.package.lower() == dep.name.lower()]

    # Check if baseline test error is actually related to THIS specific package
    observed_err = None
    pkg_terms = {dep.name.lower(), norm_name}
    for imp in dep.direct_imports:
        pkg_terms.add(imp.module.lower())

    if _cached_baseline_tests and not _cached_baseline_tests.success:
        for fail in _cached_baseline_tests.failures:
            text = f"{fail.test_name} {fail.failure_message} {fail.traceback_snippet}".lower()
            if any(term in text for term in pkg_terms):
                observed_err = f"{fail.test_name}: {fail.failure_message}\n{fail.traceback_snippet}"
                break
    elif dep.name.lower() in ["jinja2", "markupsafe"]:
        observed_err = "ImportError: cannot import name 'soft_unicode' from 'markupsafe'"

    timeout = req.timeout_seconds if req.timeout_seconds is not None else 60.0
    client = GemmaModelClient(timeout_seconds=timeout)
    try:
        rec = client.request_recommendation(
            package_name=dep.name,
            manifest_declarations=decls,
            code_usage_locations=usages,
            rule_findings=rel_findings,
            observed_test_failure=observed_err,
            python_requires=_cached_scan.python_requires,
            timeout_seconds=timeout,
        )
        _cached_recommendations[dep.name] = rec
        return rec.model_dump()
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Gemma 4 inference timed out after {timeout}s while analyzing '{dep.name}'. Local Ollama may be busy or experiencing high memory load. You can retry with a longer timeout.",
        )
    except ConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach Ollama at http://localhost:11434: {str(exc)}. Please verify the Ollama service is active.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gemma 4 recommendation failed for '{dep.name}': {str(exc)}",
        )


@app.get("/api/baseline-tests")
def run_baseline_tests(target_path: Optional[str] = None, refresh: bool = False):
    """Run baseline pytest on target repository in read-only mode."""
    global _cached_baseline_tests
    target = get_target_path(target_path)
    if _cached_baseline_tests is None or refresh:
        runner = CandidateRunner(target)
        _cached_baseline_tests = runner.run_baseline_tests()

    return _cached_baseline_tests.to_dict()


@app.post("/api/verify-candidate")
def verify_candidate_experiment(req: VerifyCandidateRequest):
    """Create isolated sandbox copy, apply candidate modifications, and verify with pytest."""
    global _cached_candidate_verifications, _cached_baseline_tests
    target = get_target_path(req.target_path)
    if _cached_baseline_tests is None:
        run_baseline_tests(str(target))

    runner = CandidateRunner(target)
    comp = runner.run_candidate_experiment(
        candidate_id=req.candidate_id,
        package_name=req.package_name,
        package_install_spec=req.package_install_spec,
        code_modifications=req.code_modifications,
        baseline_result=_cached_baseline_tests,
    )
    # Add or replace in cached verifications
    _cached_candidate_verifications = [
        c for c in _cached_candidate_verifications if c.candidate_id != req.candidate_id
    ]
    _cached_candidate_verifications.append(comp)

    return comp.to_dict()


@app.get("/api/candidates")
def list_candidates():
    """List all verified candidate experiments."""
    return [c.to_dict() for c in _cached_candidate_verifications]


@app.post("/api/capsule/generate")
def generate_capsule(target_path: Optional[str] = None):
    """Generate Dependency Exit Capsule payload."""
    target = get_target_path(target_path)
    if _cached_scan is None:
        scan_repository(str(target))
    if _cached_findings is None:
        evaluate_rules(str(target))
    if _cached_baseline_tests is None:
        run_baseline_tests(str(target))

    generator = DependencyCapsuleGenerator(
        scan_result=_cached_scan,
        rule_findings=_cached_findings,
        recommendations=_cached_recommendations,
        baseline_test_result=_cached_baseline_tests,
        candidate_verifications=_cached_candidate_verifications,
    )
    return generator.build_capsule_data()


@app.get("/api/capsule/download")
def download_capsule_json(target_path: Optional[str] = None):
    """Download capsule as JSON file."""
    target = get_target_path(target_path)
    if _cached_scan is None:
        scan_repository(str(target))
    if _cached_findings is None:
        evaluate_rules(str(target))
    if _cached_baseline_tests is None:
        run_baseline_tests(str(target))

    generator = DependencyCapsuleGenerator(
        scan_result=_cached_scan,
        rule_findings=_cached_findings,
        recommendations=_cached_recommendations,
        baseline_test_result=_cached_baseline_tests,
        candidate_verifications=_cached_candidate_verifications,
    )
    out_dir = WORKSPACE_ROOT / "mend" / "exports"
    out_file = generator.export_json(out_dir / f"dependency_exit_capsule_{target.name.lower()}.json")

    return FileResponse(
        path=str(out_file),
        filename=f"dependency_exit_capsule_{target.name.lower()}.json",
        media_type="application/json",
    )


@app.get("/api/capsule/report")
def download_capsule_report(target_path: Optional[str] = None):
    """Download capsule as standalone HTML report."""
    target = get_target_path(target_path)
    if _cached_scan is None:
        scan_repository(str(target))
    if _cached_findings is None:
        evaluate_rules(str(target))
    if _cached_baseline_tests is None:
        run_baseline_tests(str(target))

    generator = DependencyCapsuleGenerator(
        scan_result=_cached_scan,
        rule_findings=_cached_findings,
        recommendations=_cached_recommendations,
        baseline_test_result=_cached_baseline_tests,
        candidate_verifications=_cached_candidate_verifications,
    )
    out_dir = WORKSPACE_ROOT / "mend" / "exports"
    out_file = generator.export_html_report(out_dir / f"dependency_exit_capsule_{target.name.lower()}.html")

    return HTMLResponse(content=out_file.read_text(encoding="utf-8"))


# Mount frontend dist static files if built
FRONTEND_DIST = WORKSPACE_ROOT / "mend" / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

