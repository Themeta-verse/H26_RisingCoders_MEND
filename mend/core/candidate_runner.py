"""Candidate Verification Runner for MEND.

Executes baseline tests in the target repository (read-only) and runs
candidate migration experiments in strictly isolated sandbox environments.
Captures exit codes, stdout, stderr, test counts, and side-by-side comparisons.
Never alters the original target codebase or its baseline virtual environment.
"""

from __future__ import annotations

import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TestFailureDetail:
    test_name: str
    file_path: str
    failure_message: str
    traceback_snippet: str


@dataclass
class TestExecutionResult:
    environment_type: str  # "baseline" or "candidate"
    command_executed: str
    cwd: str
    exit_code: int
    duration_seconds: float
    timestamp: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_count: int
    raw_stdout: str
    raw_stderr: str
    failures: List[TestFailureDetail] = field(default_factory=list)
    success: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MigrationVerificationComparison:
    candidate_id: str
    package_name: str
    proposed_change: str
    baseline_result: TestExecutionResult
    candidate_result: TestExecutionResult
    status: str  # "VERIFIED_FIX", "REGRESSION", "STILL_FAILING", "ERROR"
    verdict_summary: str
    unresolved_gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


SANDBOX_SAFETY_SPECIFICATION: Dict[str, Any] = {
    "isolation_mechanism": "Filesystem sandbox clone with prioritized PYTHONPATH override",
    "target_repository_mutation": "strictly_prevented (read-only execution)",
    "process_execution": "Direct argument list invocation (subprocess.run without shell=True)",
    "command_allowlist": ["pytest", "pip install --target"],
    "input_allowlist_regex": r"^[a-zA-Z0-9_\-\.\[\]><=~! ]+$",
    "resource_bounds": {
        "pytest_timeout_seconds": 60,
        "pip_timeout_seconds": 90,
        "max_output_size_bytes": 250000,
        "sandbox_retention_limit": 5,
    },
    "sandbox_boundaries_disclaimer": (
        "The MEND sandbox isolates target file modifications and candidate dependencies via workspace "
        "directory clones and localized PYTHONPATH overrides. It executes under current host user privileges "
        "and does not constitute kernel-level containerization or hypervisor virtualization."
    ),
}


class CandidateRunner:
    """Manages baseline and isolated candidate test executions."""

    def __init__(self, target_dir: str | Path, scratch_dir: Optional[str | Path] = None):
        self.target_dir = Path(target_dir).resolve()
        if scratch_dir:
            self.scratch_dir = Path(scratch_dir).resolve()
        else:
            self.scratch_dir = self.target_dir.parent / "mend" / "sandbox_runs"
        self.scratch_dir.mkdir(parents=True, exist_ok=True)

    def _prune_old_sandboxes(self, max_keep: int = 5) -> None:
        """Prune old sandbox run directories to bound temporary resource consumption."""
        try:
            cand_dirs = sorted(
                [d for d in self.scratch_dir.iterdir() if d.is_dir() and d.name.startswith("cand_")],
                key=lambda p: p.stat().st_mtime,
            )
            while len(cand_dirs) > max_keep:
                oldest = cand_dirs.pop(0)
                shutil.rmtree(oldest, ignore_errors=True)
        except Exception:
            pass

    def _find_target_python(self) -> Tuple[Path, str]:
        for cand in [
            self.target_dir / ".venv" / "Scripts" / "python.exe",
            self.target_dir / ".venv" / "bin" / "python",
            self.target_dir / "venv" / "Scripts" / "python.exe",
            self.target_dir.parent / "LinkWatch" / ".venv" / "Scripts" / "python.exe",
            self.target_dir.parent / "LinkWatch" / ".venv" / "bin" / "python",
        ]:
            if cand.is_file():
                return cand, "target_venv"
        return Path(sys.executable), "host_python"

    def run_baseline_tests(self) -> TestExecutionResult:
        """Run pytest on the target repository strictly in read-only mode."""
        py_exe, env_type = self._find_target_python()
        cmd = [str(py_exe), "-m", "pytest", "-v"]

        start_time = time.monotonic()
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.target_dir),
                capture_output=True,
                text=True,
                timeout=60,
                env=os.environ.copy(),
            )
            duration = round(time.monotonic() - start_time, 2)
            res = self._parse_pytest_output(
                env_type="baseline",
                cmd=" ".join(cmd),
                cwd=str(self.target_dir),
                exit_code=proc.returncode,
                duration=duration,
                timestamp=timestamp,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
            return res
        except subprocess.TimeoutExpired:
            return TestExecutionResult(
                environment_type="baseline",
                command_executed=" ".join(cmd),
                cwd=str(self.target_dir),
                exit_code=-1,
                duration=60.0,
                timestamp=timestamp,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                error_count=1,
                raw_stdout="",
                raw_stderr="Pytest execution timed out after 60s.",
                success=False,
                notes="Execution timed out",
            )
        except Exception as exc:
            return TestExecutionResult(
                environment_type="baseline",
                command_executed=" ".join(cmd),
                cwd=str(self.target_dir),
                exit_code=-1,
                duration=round(time.monotonic() - start_time, 2),
                timestamp=timestamp,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                error_count=1,
                raw_stdout="",
                raw_stderr=str(exc),
                success=False,
                notes=f"Failed to launch test runner: {str(exc)}",
            )

    def run_candidate_experiment(
        self,
        candidate_id: str,
        package_name: str,
        package_install_spec: str,
        code_modifications: Optional[List[Dict[str, str]]] = None,
        baseline_result: Optional[TestExecutionResult] = None,
    ) -> MigrationVerificationComparison:
        """Create an isolated sandbox copy, apply candidate modifications, and verify with pytest."""
        # Validate candidate installation specification to prevent shell/command injection
        clean_spec = package_install_spec.strip()
        if not re.match(r"^[a-zA-Z0-9_\-\.\[\]><=~! ]+$", clean_spec):
            raise ValueError(
                f"Candidate install specification '{clean_spec}' rejected by allowlist. "
                "Only alphanumeric package names and PEP 440/508 version specifiers are permitted."
            )

        # Prune old sandbox runs to conserve disk resources
        self._prune_old_sandboxes(max_keep=5)

        if baseline_result is None:
            baseline_result = self.run_baseline_tests()

        run_dir = self.scratch_dir / f"cand_{candidate_id}_{int(time.time())}"
        run_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Copy repo files into sandbox (excluding .venv and caches)
            for item in self.target_dir.iterdir():
                if item.name in [".venv", "venv", ".pytest_cache", "__pycache__", ".git"]:
                    continue
                dst = run_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)

            # 2. Apply code modifications in the sandbox if provided
            if code_modifications:
                for mod in code_modifications:
                    rel_p = mod.get("file_path", "")
                    target_file = run_dir / rel_p
                    if target_file.is_file():
                        orig = mod.get("original_snippet", "")
                        repl = mod.get("replacement_snippet", "")
                        content = target_file.read_text(encoding="utf-8", errors="replace")
                        if orig and orig in content:
                            content = content.replace(orig, repl)
                            target_file.write_text(content, encoding="utf-8")

            # 3. Install candidate package into an isolated override directory inside sandbox
            override_dir = run_dir / "candidate_packages"
            override_dir.mkdir(parents=True, exist_ok=True)

            pip_exe = Path(sys.executable).parent / "pip.exe"
            if not pip_exe.is_file():
                # fallback to base python pip
                base_py, _ = self._find_target_python()
                pip_cmd = [str(base_py), "-m", "pip", "install", "--target", str(override_dir), package_install_spec]
            else:
                pip_cmd = [str(pip_exe), "install", "--target", str(override_dir), package_install_spec]

            install_proc = subprocess.run(
                pip_cmd,
                cwd=str(run_dir),
                capture_output=True,
                text=True,
                timeout=90,
            )

            # 4. Run pytest in the sandbox using LinkWatch's python with PYTHONPATH priority
            base_py, _ = self._find_target_python()
            test_cmd = [str(base_py), "-m", "pytest", "-v"]

            # Construct PYTHONPATH with sandbox packages first, then sandbox root
            current_env = os.environ.copy()
            sep = ";" if os.name == "nt" else ":"
            current_env["PYTHONPATH"] = f"{str(override_dir)}{sep}{str(run_dir)}"

            start_time = time.monotonic()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            test_proc = subprocess.run(
                test_cmd,
                cwd=str(run_dir),
                capture_output=True,
                text=True,
                timeout=60,
                env=current_env,
            )
            duration = round(time.monotonic() - start_time, 2)

            cand_result = self._parse_pytest_output(
                env_type="candidate",
                cmd=" ".join(test_cmd),
                cwd=str(run_dir),
                exit_code=test_proc.returncode,
                duration=duration,
                timestamp=timestamp,
                stdout=test_proc.stdout,
                stderr=test_proc.stderr,
            )

            # Compare baseline vs candidate
            unresolved = []
            if cand_result.success and not baseline_result.success:
                status = "VERIFIED_FIX"
                summary = (
                    f"Candidate verified successfully! Resolved baseline failure "
                    f"({baseline_result.failed_tests} failure -> {cand_result.passed_tests} passing, 0 failing)."
                )
            elif cand_result.success and baseline_result.success:
                status = "VERIFIED_MAINTAINED"
                summary = f"All {cand_result.passed_tests} tests continue to pass without regression."
            elif cand_result.failed_tests > baseline_result.failed_tests:
                status = "REGRESSION"
                summary = (
                    f"Regression observed: failures increased from {baseline_result.failed_tests} "
                    f"to {cand_result.failed_tests}."
                )
                unresolved.append("Candidate introduces new test failures.")
            elif cand_result.failed_tests > 0:
                status = "STILL_FAILING"
                summary = f"Tests still failing ({cand_result.failed_tests} failed)."
                unresolved.append(f"Residual failures in: {[f.test_name for f in cand_result.failures]}")
            else:
                status = "ERROR"
                summary = f"Execution exited with code {cand_result.exit_code}."
                unresolved.append("Test runner exited abnormally.")

            return MigrationVerificationComparison(
                candidate_id=candidate_id,
                package_name=package_name,
                proposed_change=package_install_spec,
                baseline_result=baseline_result,
                candidate_result=cand_result,
                status=status,
                verdict_summary=summary,
                unresolved_gaps=unresolved,
            )
        finally:
            # Leave the sandbox dir or clean up if needed
            pass

    def _parse_pytest_output(
        self,
        env_type: str,
        cmd: str,
        cwd: str,
        exit_code: int,
        duration: float,
        timestamp: str,
        stdout: str,
        stderr: str,
    ) -> TestExecutionResult:
        max_chars = 250000
        if len(stdout) > max_chars:
            stdout = stdout[:max_chars] + "\n\n[MEND Output Truncated at 250KB limit]"
        if len(stderr) > max_chars:
            stderr = stderr[:max_chars] + "\n\n[MEND Output Truncated at 250KB limit]"

        total = 0
        passed = 0
        failed = 0
        skipped = 0
        errors = 0

        # Pattern: "1 failed, 9 passed, 1 warning in 8.62s"
        summary_match = re.search(r"(=+ short test summary info =+.*?|)([\d\w\s,]+) in [\d.]+s", stdout, re.DOTALL)
        last_line = stdout.strip().splitlines()[-1] if stdout.strip() else ""

        p_match = re.search(r"(\d+)\s+passed", stdout)
        if p_match:
            passed = int(p_match.group(1))

        f_match = re.search(r"(\d+)\s+failed", stdout)
        if f_match:
            failed = int(f_match.group(1))

        s_match = re.search(r"(\d+)\s+skipped", stdout)
        if s_match:
            skipped = int(s_match.group(1))

        e_match = re.search(r"(\d+)\s+error", stdout)
        if e_match:
            errors = int(e_match.group(1))

        total = passed + failed + skipped + errors

        # Extract failure details
        failures: List[TestFailureDetail] = []
        if failed > 0 or errors > 0:
            failure_blocks = re.split(r"_{10,}\s+([^_]+)\s+_{10,}", stdout)
            # failure_blocks comes in pairs: [header, test_name, block_content, ...]
            if len(failure_blocks) > 2:
                for i in range(1, len(failure_blocks), 2):
                    t_name = failure_blocks[i].strip()
                    content = failure_blocks[i + 1] if i + 1 < len(failure_blocks) else ""
                    lines = content.strip().splitlines()
                    last_few = "\n".join(lines[-10:])
                    err_msg = lines[-1] if lines else "Test failed"
                    failures.append(TestFailureDetail(
                        test_name=t_name,
                        file_path="tests",
                        failure_message=err_msg,
                        traceback_snippet=last_few,
                    ))
            elif "FAILED" in stdout:
                for line in stdout.splitlines():
                    if line.startswith("FAILED "):
                        failures.append(TestFailureDetail(
                            test_name=line.replace("FAILED ", "").strip(),
                            file_path="tests",
                            failure_message=line.strip(),
                            traceback_snippet=line.strip(),
                        ))

        success = (exit_code == 0)

        return TestExecutionResult(
            environment_type=env_type,
            command_executed=cmd,
            cwd=cwd,
            exit_code=exit_code,
            duration_seconds=duration,
            timestamp=timestamp,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            skipped_tests=skipped,
            error_count=errors,
            raw_stdout=stdout,
            raw_stderr=stderr,
            failures=failures,
            success=success,
            notes=f"Pytest exited with code {exit_code}",
        )
