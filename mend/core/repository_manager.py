"""Repository Manager for MEND (Migration Evidence & Dependency Navigator).

Manages multi-repository workflows:
- Maintains LinkWatch as the official challenge default target
- Clones and registers public GitHub repositories in isolated workspaces
- Detects exact commit hashes / revisions via git rev-parse
- Isolates scans, findings, recommendations, verifications, and capsules per repository
- Enforces security: never executes arbitrary repository code during discovery or inspection
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mend.core.adapters import (
    BaseEcosystemAdapter,
    EcosystemDetectionResult,
    detect_ecosystem,
    get_adapter_for_path,
)
from mend.core.candidate_runner import MigrationVerificationComparison, TestExecutionResult
from mend.core.model_client import MigrationRecommendation
from mend.core.rules import RuleFinding
from mend.core.scanner import RepositoryScanResult

GITHUB_URL_REGEX = re.compile(r"^https?://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+?)(?:\.git)?/?$")


@dataclass
class RepositoryMetadata:
    id: str
    name: str
    path: str
    commit_hash: str
    short_commit: str
    clone_url: Optional[str]
    is_official: bool
    ecosystem: str
    support_level: str
    detected_manifests: List[str]
    limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RepositorySession:
    """Encapsulates isolated state for a single repository and revision."""

    def __init__(
        self,
        repo_id: str,
        name: str,
        path: Path,
        clone_url: Optional[str] = None,
        is_official: bool = False,
    ):
        self.repo_id = repo_id
        self.name = name
        self.path = Path(path).resolve()
        self.clone_url = clone_url
        self.is_official = is_official

        self.commit_hash: str = self._resolve_commit_hash()
        self.adapter, self.detection = detect_ecosystem(self.path)

        # Isolated data caches
        self.cached_scan: Optional[RepositoryScanResult] = None
        self.previous_scan: Optional[RepositoryScanResult] = None
        self.cached_findings: Optional[List[RuleFinding]] = None
        self.cached_recommendations: Dict[str, MigrationRecommendation] = {}
        self.cached_baseline_tests: Optional[TestExecutionResult] = None
        self.cached_candidate_verifications: List[MigrationVerificationComparison] = []
        self.cached_capsule_payload: Optional[Dict[str, Any]] = None
        self.exported_capsule_json: Optional[str] = None
        self.exported_capsule_html: Optional[str] = None

    def _resolve_commit_hash(self) -> str:
        """Resolve git commit hash without executing repo code."""
        if (self.path / ".git").exists():
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(self.path),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass
        return "local-snapshot"

    def refresh_commit(self) -> str:
        self.commit_hash = self._resolve_commit_hash()
        return self.commit_hash

    def get_metadata(self) -> RepositoryMetadata:
        short_hash = self.commit_hash[:10] if len(self.commit_hash) >= 10 else self.commit_hash
        return RepositoryMetadata(
            id=self.repo_id,
            name=self.name,
            path=str(self.path),
            commit_hash=self.commit_hash,
            short_commit=short_hash,
            clone_url=self.clone_url,
            is_official=self.is_official,
            ecosystem=self.detection.display_name,
            support_level=self.detection.support_level.value,
            detected_manifests=self.detection.detected_manifests,
            limitations=self.detection.limitations,
        )

    def reset_caches(self) -> None:
        """Reset all in-memory caches to force clean re-scan."""
        self.cached_scan = None
        self.cached_findings = None
        self.cached_recommendations = {}
        self.cached_baseline_tests = None
        self.cached_candidate_verifications = []
        self.cached_capsule_payload = None
        self.exported_capsule_json = None
        self.exported_capsule_html = None


class RepositoryManager:
    """Manages workspace repositories and the currently active target."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()
        self.workspaces_dir = self.workspace_root / "mend" / "workspaces"
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

        self.repositories: Dict[str, RepositorySession] = {}
        self.active_repo_id: str = "linkwatch"

        # Register default official challenge target: LinkWatch
        self._register_default_linkwatch()

    def _register_default_linkwatch(self) -> None:
        """Register the official LinkWatch starter target."""
        linkwatch_path = self.workspace_root.parent / "LinkWatch"
        if not linkwatch_path.exists():
            # Check alternative locations
            if (self.workspace_root / "LinkWatch").exists():
                linkwatch_path = self.workspace_root / "LinkWatch"
            else:
                linkwatch_path = self.workspace_root

        linkwatch_session = RepositorySession(
            repo_id="linkwatch",
            name="LinkWatch",
            path=linkwatch_path,
            clone_url="https://github.com/rishrek/LinkWatch",
            is_official=True,
        )
        self.repositories["linkwatch"] = linkwatch_session

    def get_active_session(self) -> RepositorySession:
        if self.active_repo_id not in self.repositories:
            self.active_repo_id = "linkwatch"
        return self.repositories[self.active_repo_id]

    def list_repositories(self) -> List[Dict[str, Any]]:
        result = []
        for repo_id, session in self.repositories.items():
            meta = session.get_metadata().to_dict()
            meta["is_active"] = (repo_id == self.active_repo_id)
            result.append(meta)
        return result

    def select_repository(self, repo_id: str) -> RepositorySession:
        if repo_id not in self.repositories:
            raise KeyError(f"Repository with id '{repo_id}' is not registered.")
        self.active_repo_id = repo_id
        return self.repositories[repo_id]

    def add_github_repository(self, github_url: str, ref: Optional[str] = None) -> RepositorySession:
        """Clone or update a public GitHub repository without executing any of its code."""
        url_clean = github_url.strip()
        m = GITHUB_URL_REGEX.match(url_clean)
        if not m:
            raise ValueError(
                f"Invalid GitHub URL format '{github_url}'. Must match 'https://github.com/<owner>/<repo>'."
            )

        owner, repo_name = m.group(1), m.group(2)
        repo_id = f"{owner}__{repo_name}".lower()
        target_dir = self.workspaces_dir / repo_id

        # Non-interactive git environment (no credentials prompt)
        git_env = os.environ.copy()
        git_env["GIT_TERMINAL_PROMPT"] = "0"
        git_env["GIT_ASKPASS"] = "echo"

        if target_dir.exists() and (target_dir / ".git").exists():
            # Fetch updates
            fetch_cmd = ["git", "fetch", "--depth", "1", "origin"]
            if ref:
                fetch_cmd.append(ref)
            try:
                subprocess.run(
                    fetch_cmd,
                    cwd=str(target_dir),
                    env=git_env,
                    capture_output=True,
                    text=True,
                    timeout=45,
                    check=True,
                )
                if ref:
                    subprocess.run(
                        ["git", "checkout", ref],
                        cwd=str(target_dir),
                        env=git_env,
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=True,
                    )
                else:
                    subprocess.run(
                        ["git", "reset", "--hard", "origin/HEAD"],
                        cwd=str(target_dir),
                        env=git_env,
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"Timed out while fetching repository from {url_clean}")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Git fetch error on {url_clean}: {e.stderr.strip() or e.stdout.strip()}")
        else:
            # Fresh clone
            clone_cmd = ["git", "clone", "--depth", "1"]
            if ref:
                clone_cmd.extend(["--branch", ref])
            clone_cmd.extend([url_clean, str(target_dir)])

            try:
                proc = subprocess.run(
                    clone_cmd,
                    env=git_env,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                if proc.returncode != 0:
                    err_msg = proc.stderr.strip() or proc.stdout.strip()
                    raise RuntimeError(f"Failed to clone public repository: {err_msg}")
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"Timed out while cloning repository from {url_clean}")

        session = RepositorySession(
            repo_id=repo_id,
            name=f"{owner}/{repo_name}",
            path=target_dir,
            clone_url=url_clean,
            is_official=False,
        )
        self.repositories[repo_id] = session
        self.active_repo_id = repo_id
        return session
