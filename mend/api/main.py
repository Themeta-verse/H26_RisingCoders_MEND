"""FastAPI Server for MEND (Migration Evidence & Dependency Navigator).

Provides REST APIs for:
- Reusable repository management (LinkWatch default + public GitHub repositories)
- Modular ecosystem adapters (Python Full Support, JavaScript/Node.js Partial Support)
- System and Gemma 4 health checking
- Deterministic repository scanning and AST source usage analysis
- Rule engine resilience evaluation
- Real Gemma 4 migration recommendation generation via local Ollama
- Baseline test suite execution (read-only)
- Isolated candidate experiment verification in sandboxed clones
- Auditable Dependency Exit Capsule generation, JSON download, and HTML report export
"""

from __future__ import annotations

import datetime
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mend.core.adapters import (
    BaseEcosystemAdapter,
    EcosystemDetectionResult,
    EcosystemType,
    JavaScriptEcosystemAdapter,
    PythonEcosystemAdapter,
    SupportLevel,
)
from mend.core.candidate_runner import (
    SANDBOX_SAFETY_SPECIFICATION,
    CandidateRunner,
    MigrationVerificationComparison,
    TestExecutionResult,
)
from mend.core.capsule import DependencyCapsuleGenerator
from mend.core.ledger import MigrationIntegrityLedger
from mend.core.model_client import GemmaModelClient, MigrationRecommendation
from mend.core.repository_manager import RepositoryManager, RepositorySession
from mend.core.rules import RuleEngine, RuleFinding
from mend.core.scanner import DependencyScanner, RepositoryScanResult, diff_scans
from mend.core.version_service import DependencyIntelligenceService

app = FastAPI(
    title="MEND API",
    description="Migration Evidence & Dependency Navigator API powered by Gemma 4",
    version="1.1.0",
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Workspace root is submission_repo
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

# Central multi-repository manager
repo_manager = RepositoryManager(WORKSPACE_ROOT)


class SelectRepoRequest(BaseModel):
    repo_id: str


class AddRepoRequest(BaseModel):
    url: str
    ref: Optional[str] = None


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


# ---------------------------------------------------------------------------
# Repository Selection & Management Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/repositories")
def list_repositories():
    """List all registered repositories with identity, commit hash, and ecosystem support level."""
    return {
        "active_repo_id": repo_manager.active_repo_id,
        "repositories": repo_manager.list_repositories(),
    }


@app.post("/api/repositories/select")
def select_repository(req: SelectRepoRequest):
    """Switch active target repository."""
    try:
        session = repo_manager.select_repository(req.repo_id)
        return {
            "status": "success",
            "active_repository": session.get_metadata().to_dict(),
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/repositories/add")
def add_github_repository(req: AddRepoRequest):
    """Clone and register a public GitHub repository without executing its code."""
    try:
        session = repo_manager.add_github_repository(req.url, req.ref)
        return {
            "status": "success",
            "message": f"Successfully cloned repository {session.name} at commit {session.commit_hash[:10]}",
            "active_repository": session.get_metadata().to_dict(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to register repository: {str(exc)}")


@app.post("/api/repositories/refresh")
def refresh_active_repository():
    """Re-read local git revision and clear in-memory caches for a clean re-scan (local files only)."""
    session = repo_manager.get_active_session()
    new_commit = session.refresh_commit()
    session.reset_caches()
    return {
        "status": "refreshed",
        "repo_id": session.repo_id,
        "commit_hash": new_commit,
        "short_commit": new_commit[:10] if len(new_commit) >= 10 else new_commit,
    }


@app.post("/api/repositories/sync")
def sync_repository_from_github():
    """Explicitly fetch latest revision from GitHub for the active cloned repository.

    Safety Guarantee: Never mutates or overwrites the official LinkWatch directory.
    """
    session = repo_manager.get_active_session()
    try:
        res = session.sync_with_remote()
        return {
            "status": res["status"],
            "message": res["message"],
            "repo_id": session.repo_id,
            "old_commit": res["old_commit"],
            "new_commit": res["new_commit"],
            "short_commit": res["new_commit"][:10],
            "is_changed": res["is_changed"],
            "active_repository": session.get_metadata().to_dict(),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch updates from GitHub: {str(exc)}")



# ---------------------------------------------------------------------------
# System Status & Health
# ---------------------------------------------------------------------------

@app.get("/api/status")
def get_system_status(target_path: Optional[str] = None):
    """Check health of local Ollama, Gemma 4 model, and active target repository."""
    session = repo_manager.get_active_session()
    client = GemmaModelClient()
    ollama_health = client.check_health()
    meta = session.get_metadata().to_dict()

    return {
        "status": "online",
        "target_repository": {
            "id": session.repo_id,
            "name": session.name,
            "path": str(session.path),
            "commit_hash": session.commit_hash,
            "short_commit": meta["short_commit"],
            "clone_url": session.clone_url,
            "is_official": session.is_official,
            "ecosystem": session.detection.display_name,
            "support_level": session.detection.support_level.value,
            "detected_manifests": session.detection.detected_manifests,
            "limitations": session.detection.limitations,
            "exists": session.path.exists(),
            "has_pyproject": (session.path / "pyproject.toml").is_file(),
            "has_requirements": (session.path / "requirements.txt").is_file(),
            "has_venv": (session.path / ".venv").is_dir(),
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


# ---------------------------------------------------------------------------
# Deterministic Scanning & Drift
# ---------------------------------------------------------------------------

@app.get("/api/scan")
def scan_repository(target_path: Optional[str] = None, refresh: bool = False):
    """Execute deterministic static analysis using the appropriate ecosystem adapter."""
    session = repo_manager.get_active_session()
    if not session.path.exists():
        raise HTTPException(status_code=404, detail=f"Target directory {session.path} not found")

    if session.cached_scan is None or refresh:
        if session.cached_scan is not None and refresh:
            session.previous_scan = session.cached_scan

        if isinstance(session.adapter, JavaScriptEcosystemAdapter):
            session.cached_scan = session.adapter.scan(session.path)
        else:
            scanner = DependencyScanner(session.path)
            session.cached_scan = scanner.scan()

        if session.previous_scan is None:
            session.previous_scan = session.cached_scan

    return session.cached_scan.to_dict()


@app.get("/api/scan/diff")
def get_scan_diff(target_path: Optional[str] = None, refresh: bool = False):
    """Compare previous and current scan snapshots to detect drift on demand."""
    session = repo_manager.get_active_session()
    if not session.path.exists():
        raise HTTPException(status_code=404, detail=f"Target directory {session.path} not found")

    if session.cached_scan is None:
        scan_repository(refresh=False)

    if refresh:
        session.previous_scan = session.cached_scan
        if isinstance(session.adapter, JavaScriptEcosystemAdapter):
            session.cached_scan = session.adapter.scan(session.path)
        else:
            scanner = DependencyScanner(session.path)
            session.cached_scan = scanner.scan()

    old_scan = session.previous_scan if session.previous_scan is not None else session.cached_scan
    return diff_scans(old_scan, session.cached_scan)


# ---------------------------------------------------------------------------
# Dependency Intelligence & Version Comparison
# ---------------------------------------------------------------------------

@app.get("/api/dependency-intelligence")
def get_dependency_intelligence(refresh: bool = False):
    """Retrieve side-by-side version comparison against official package registries
    with clickable official links, compatibility severity, and verification status."""
    session = repo_manager.get_active_session()
    if session.cached_scan is None or refresh:
        scan_repository(refresh=refresh)

    if session.cached_intelligence is None or refresh:
        svc = DependencyIntelligenceService()
        rep = svc.analyze_repository(
            dependencies=session.cached_scan.dependencies,
            candidate_verifications=session.cached_candidate_verifications,
            ecosystem=session.detection.display_name,
        )
        session.cached_intelligence = list(rep["items"].values())

    return session.cached_intelligence


# ---------------------------------------------------------------------------
# Deterministic Rule Engine
# ---------------------------------------------------------------------------

@app.get("/api/rules")
def evaluate_rules(target_path: Optional[str] = None, refresh: bool = False):
    """Run deterministic rule engine against scanned repository evidence."""
    session = repo_manager.get_active_session()
    if session.cached_scan is None or refresh:
        scan_repository(refresh=refresh)

    if session.cached_findings is None or refresh:
        if isinstance(session.adapter, JavaScriptEcosystemAdapter):
            session.cached_findings = session.adapter.evaluate_rules(session.cached_scan)
        else:
            engine = RuleEngine()
            session.cached_findings = engine.evaluate(session.cached_scan)

    return [f.to_dict() for f in session.cached_findings]


# ---------------------------------------------------------------------------
# Gemma 4 Migration Recommendations (Local Ollama Inference)
# ---------------------------------------------------------------------------

@app.post("/api/recommend")
def get_recommendation(req: RecommendationRequest):
    """Invoke local Gemma 4 model via Ollama with bounded repository evidence for a specific package."""
    session = repo_manager.get_active_session()
    if session.cached_scan is None:
        scan_repository()
    if session.cached_findings is None:
        evaluate_rules()

    norm_name = req.package_name.lower().replace("_", "-")
    dep = session.cached_scan.dependencies.get(norm_name)
    if not dep:
        # Check by display name
        for d in session.cached_scan.dependencies.values():
            if d.name.lower() == req.package_name.lower():
                dep = d
                break

    if not dep:
        raise HTTPException(
            status_code=404,
            detail=f"Dependency '{req.package_name}' not found in active repository '{session.name}'",
        )

    # Bounded evidence
    from dataclasses import asdict
    decls = [asdict(d) for d in dep.manifest_declarations]
    usages = [asdict(loc) for loc in dep.direct_imports]
    rel_findings = [f.to_dict() for f in session.cached_findings if f.package.lower() == dep.name.lower()]

    # Check observed test failures
    observed_err = None
    pkg_terms = {dep.name.lower(), norm_name}
    for imp in dep.direct_imports:
        pkg_terms.add(imp.module.lower())

    if session.cached_baseline_tests and not session.cached_baseline_tests.success:
        for fail in session.cached_baseline_tests.failures:
            text = f"{fail.test_name} {fail.failure_message} {fail.traceback_snippet}".lower()
            if any(term in text for term in pkg_terms):
                observed_err = f"{fail.test_name}: {fail.failure_message}\n{fail.traceback_snippet}"
                break
    elif session.is_official and dep.name.lower() in ["jinja2", "markupsafe"]:
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
            python_requires=session.cached_scan.python_requires,
            timeout_seconds=timeout,
        )
        session.cached_recommendations[dep.name] = rec
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


@app.get("/api/recommendations")
def list_recommendations():
    """List all cached Gemma 4 migration recommendations for the active repository."""
    session = repo_manager.get_active_session()
    return {
        pkg: (rec.model_dump() if hasattr(rec, "model_dump") else rec.dict())
        for pkg, rec in session.cached_recommendations.items()
    }


# ---------------------------------------------------------------------------
# Candidate Verification (Isolated Sandbox Execution)
# ---------------------------------------------------------------------------

@app.get("/api/baseline-tests")
def run_baseline_tests(target_path: Optional[str] = None, refresh: bool = False):
    """Run baseline tests on target repository in read-only mode."""
    session = repo_manager.get_active_session()

    # Honest support disclosure for non-Python ecosystems
    if session.detection.ecosystem != EcosystemType.PYTHON:
        return {
            "environment_type": "baseline",
            "command_executed": "npm test (unsupported in Track 1)",
            "cwd": str(session.path),
            "exit_code": -1,
            "duration_seconds": 0.0,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "error_count": 0,
            "raw_stdout": "",
            "raw_stderr": "Sandbox candidate testing is only supported for Python repositories in this Track 1 release.",
            "failures": [],
            "success": False,
            "notes": f"Ecosystem is {session.detection.display_name} ({session.detection.support_level.value} support). Sandbox pytest verification is not supported.",
        }

    if session.cached_baseline_tests is None or refresh:
        runner = CandidateRunner(session.path)
        session.cached_baseline_tests = runner.run_baseline_tests()

    return session.cached_baseline_tests.to_dict()


@app.post("/api/verify-candidate")
def verify_candidate_experiment(req: VerifyCandidateRequest):
    """Create isolated sandbox copy, apply candidate modifications, and verify with pytest."""
    session = repo_manager.get_active_session()

    if session.detection.ecosystem != EcosystemType.PYTHON:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Candidate sandbox verification is not supported for {session.detection.display_name}. "
                "Only Python repositories have isolated candidate runner support in this Track 1 release."
            ),
        )

    if session.cached_baseline_tests is None:
        run_baseline_tests()

    runner = CandidateRunner(session.path)
    comp = runner.run_candidate_experiment(
        candidate_id=req.candidate_id,
        package_name=req.package_name,
        package_install_spec=req.package_install_spec,
        code_modifications=req.code_modifications,
        baseline_result=session.cached_baseline_tests,
    )

    # Add or replace in session cached verifications
    session.cached_candidate_verifications = [
        c for c in session.cached_candidate_verifications if c.candidate_id != req.candidate_id
    ]
    session.cached_candidate_verifications.append(comp)

    return comp.to_dict()


@app.get("/api/candidates")
def list_candidates():
    """List all verified candidate experiments for the active repository."""
    session = repo_manager.get_active_session()
    return [c.to_dict() for c in session.cached_candidate_verifications]


# ---------------------------------------------------------------------------
# Migration Integrity Ledger & Safety Artifacts
# ---------------------------------------------------------------------------

@app.get("/api/ledger")
def get_migration_ledger(target_path: Optional[str] = None):
    """Retrieve the end-to-end Migration Integrity Lifecycle Ledger for the active repository."""
    session = repo_manager.get_active_session()
    if session.cached_scan is None:
        scan_repository()
    if session.cached_findings is None:
        evaluate_rules()

    ledger = MigrationIntegrityLedger(
        scan_result=session.cached_scan,
        rule_findings=session.cached_findings,
        recommendations=session.cached_recommendations,
        candidate_verifications=session.cached_candidate_verifications,
        target_metadata=session.get_metadata().to_dict(),
    )
    return ledger.build_ledger()



@app.get("/api/integrity")
def get_artifact_integrity(target_path: Optional[str] = None):
    """Retrieve SHA-256 integrity digests, export hashes, and runner safety boundaries for active repository."""
    session = repo_manager.get_active_session()
    if session.cached_scan is None:
        scan_repository()

    exports_dir = WORKSPACE_ROOT / "mend" / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    capsule_json_path = exports_dir / f"dependency_exit_capsule_{session.repo_id}.json"
    capsule_html_path = exports_dir / f"dependency_exit_capsule_{session.repo_id}.html"

    json_sha256 = ""
    if capsule_json_path.is_file():
        json_sha256 = hashlib.sha256(capsule_json_path.read_bytes()).hexdigest()

    html_sha256 = ""
    if capsule_html_path.is_file():
        html_sha256 = hashlib.sha256(capsule_html_path.read_bytes()).hexdigest()

    return {
        "target_name": session.cached_scan.target_name,
        "repo_id": session.repo_id,
        "commit_hash": session.commit_hash,
        "short_commit": session.commit_hash[:10] if len(session.commit_hash) >= 10 else session.commit_hash,
        "clone_url": session.clone_url,
        "ecosystem": session.detection.display_name,
        "support_level": session.detection.support_level.value,
        "source_snapshot_sha256": session.cached_scan.sha256_source_digest,
        "scanned_at": session.cached_scan.scanned_at,
        "exported_capsules": {
            "json_filename": capsule_json_path.name if capsule_json_path.is_file() else None,
            "json_sha256": json_sha256 if json_sha256 else None,
            "html_filename": capsule_html_path.name if capsule_html_path.is_file() else None,
            "html_sha256": html_sha256 if html_sha256 else None,
        },
        "candidate_runner_safety": SANDBOX_SAFETY_SPECIFICATION,
        "disclaimer": (
            "SHA-256 hashes provide tamper-evident verification for pipeline audit trails. "
            "A hash is not proof of truth, authorship, external package trustworthiness, or complete security."
        ),
    }


# ---------------------------------------------------------------------------
# Dependency Exit Capsule Export
# ---------------------------------------------------------------------------

@app.post("/api/capsule/generate")
def generate_capsule(target_path: Optional[str] = None):
    """Generate Dependency Exit Capsule payload for the active repository."""
    session = repo_manager.get_active_session()
    if session.cached_scan is None:
        scan_repository()
    if session.cached_findings is None:
        evaluate_rules()
    if session.cached_baseline_tests is None and session.detection.ecosystem == EcosystemType.PYTHON:
        run_baseline_tests()

    generator = DependencyCapsuleGenerator(
        scan_result=session.cached_scan,
        rule_findings=session.cached_findings,
        recommendations=session.cached_recommendations,
        baseline_test_result=session.cached_baseline_tests,
        candidate_verifications=session.cached_candidate_verifications,
        target_metadata=session.get_metadata().to_dict(),
        limitations=session.detection.limitations,
    )
    return generator.build_capsule_data()


@app.get("/api/capsule/download")
def download_capsule_json(target_path: Optional[str] = None):
    """Download capsule as JSON file isolated by repository identity."""
    session = repo_manager.get_active_session()
    if session.cached_scan is None:
        scan_repository()
    if session.cached_findings is None:
        evaluate_rules()
    if session.cached_baseline_tests is None and session.detection.ecosystem == EcosystemType.PYTHON:
        run_baseline_tests()

    generator = DependencyCapsuleGenerator(
        scan_result=session.cached_scan,
        rule_findings=session.cached_findings,
        recommendations=session.cached_recommendations,
        baseline_test_result=session.cached_baseline_tests,
        candidate_verifications=session.cached_candidate_verifications,
        target_metadata=session.get_metadata().to_dict(),
        limitations=session.detection.limitations,
    )
    out_dir = WORKSPACE_ROOT / "mend" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = generator.export_json(out_dir / f"dependency_exit_capsule_{session.repo_id}.json")

    return FileResponse(
        path=str(out_file),
        filename=f"dependency_exit_capsule_{session.repo_id}.json",
        media_type="application/json",
    )


@app.get("/api/capsule/report")
def download_capsule_report(target_path: Optional[str] = None):
    """Download capsule as standalone HTML report isolated by repository identity."""
    session = repo_manager.get_active_session()
    if session.cached_scan is None:
        scan_repository()
    if session.cached_findings is None:
        evaluate_rules()
    if session.cached_baseline_tests is None and session.detection.ecosystem == EcosystemType.PYTHON:
        run_baseline_tests()

    generator = DependencyCapsuleGenerator(
        scan_result=session.cached_scan,
        rule_findings=session.cached_findings,
        recommendations=session.cached_recommendations,
        baseline_test_result=session.cached_baseline_tests,
        candidate_verifications=session.cached_candidate_verifications,
        target_metadata=session.get_metadata().to_dict(),
        limitations=session.detection.limitations,
    )
    out_dir = WORKSPACE_ROOT / "mend" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = generator.export_html_report(out_dir / f"dependency_exit_capsule_{session.repo_id}.html")

    return HTMLResponse(content=out_file.read_text(encoding="utf-8"))


# Mount frontend dist static files if built
FRONTEND_DIST = WORKSPACE_ROOT / "mend" / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
