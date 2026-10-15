"""Dependency Exit Capsule Generator for MEND.

Generates versioned, self-contained, auditable JSON and HTML capsules
capturing all observed repository facts, deterministic rule findings,
Gemma 4 migration recommendations, and real baseline vs. candidate test results.
"""

from __future__ import annotations

import datetime
import hashlib
import html
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .candidate_runner import MigrationVerificationComparison, TestExecutionResult
from .model_client import GEMMA_METADATA, MigrationRecommendation
from .rules import RuleFinding
from .scanner import RepositoryScanResult

CAPSULE_SCHEMA_VERSION = "1.0.0"


class DependencyCapsuleGenerator:
    """Creates auditable Dependency Exit Capsules."""

    def __init__(
        self,
        scan_result: RepositoryScanResult,
        rule_findings: List[RuleFinding],
        recommendations: Optional[Dict[str, MigrationRecommendation]] = None,
        baseline_test_result: Optional[TestExecutionResult] = None,
        candidate_verifications: Optional[List[MigrationVerificationComparison]] = None,
        limitations: Optional[List[str]] = None,
    ):
        self.scan_result = scan_result
        self.rule_findings = rule_findings
        self.recommendations = recommendations or {}
        self.baseline_test_result = baseline_test_result
        self.candidate_verifications = candidate_verifications or []
        self.limitations = limitations or [
            "Analysis bounded to static AST parsing and declared Python package manifests.",
            "Dynamic runtime imports, exec calls, or C-extension behaviors are not analyzed.",
            "Candidate verification executed in isolated sandbox virtualenvs with system packages.",
            "AI-generated migration steps must be reviewed by engineers prior to deployment.",
        ]

    def build_capsule_data(self) -> Dict[str, Any]:
        """Build the structured capsule payload adhering to schema v1.0.0."""
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Dependencies list
        dep_list = []
        for norm_name, dep in self.scan_result.dependencies.items():
            dep_list.append({
                "package_name": dep.name,
                "normalized_name": norm_name,
                "installed_version": dep.installed_version,
                "is_direct_usage": dep.is_direct_usage,
                "is_manifest_conflicted": dep.is_manifest_conflicted,
                "conflict_details": dep.conflict_details,
                "manifest_declarations": [asdict(d) for d in dep.manifest_declarations],
                "code_usage_count": len(dep.direct_imports),
                "code_usage_locations": [asdict(loc) for loc in dep.direct_imports],
            })

        recs_data = {}
        for pkg, rec in self.recommendations.items():
            recs_data[pkg] = rec.model_dump() if hasattr(rec, "model_dump") else rec.dict()

        capsule = {
            "$schema_version": CAPSULE_SCHEMA_VERSION,
            "capsule_id": f"CAPSULE-{self.scan_result.target_name.upper()}-{int(datetime.datetime.now().timestamp())}",
            "generated_at": timestamp,
            "target": {
                "name": self.scan_result.target_name,
                "path": self.scan_result.target_path,
                "python_requires": self.scan_result.python_requires,
                "manifests_detected": self.scan_result.manifests_found,
                "total_python_files": self.scan_result.total_py_files,
                "total_loc": self.scan_result.total_loc,
            },
            "provenance": {
                "scanner": "MEND Deterministic AST & Manifest Engine v1.0.0",
                "rule_engine": "MEND Resilience Rules v1.0.0",
                "ai_model": GEMMA_METADATA,
                "verification_engine": "MEND Sandbox Candidate Runner (pytest)",
            },
            "summary_metrics": {
                "total_dependencies": len(self.scan_result.dependencies),
                "direct_used_dependencies": sum(1 for d in self.scan_result.dependencies.values() if d.is_direct_usage),
                "unreferenced_dependencies": len(self.scan_result.unreferenced_dependencies),
                "manifest_conflicts": len(self.scan_result.manifest_conflicts),
                "rule_findings_count": len(self.rule_findings),
                "critical_findings": sum(1 for f in self.rule_findings if f.severity.value == "Critical"),
                "high_findings": sum(1 for f in self.rule_findings if f.severity.value == "High"),
                "medium_findings": sum(1 for f in self.rule_findings if f.severity.value == "Medium"),
                "low_findings": sum(1 for f in self.rule_findings if f.severity.value == "Low"),
                "info_findings": sum(1 for f in self.rule_findings if f.severity.value == "Info"),
            },
            "observed_facts": {
                "dependencies": dep_list,
                "installed_environment_packages": self.scan_result.installed_packages,
                "unreferenced_packages": self.scan_result.unreferenced_dependencies,
                "manifest_conflicts": self.scan_result.manifest_conflicts,
            },
            "deterministic_rule_findings": [f.to_dict() for f in self.rule_findings],
            "ai_migration_recommendations": recs_data,
            "test_verification_evidence": {
                "baseline_test_run": self.baseline_test_result.to_dict() if self.baseline_test_result else None,
                "candidate_comparisons": [comp.to_dict() for comp in self.candidate_verifications],
            },
            "limitations_and_assumptions": self.limitations,
        }

        # Compute SHA-256 integrity hash over canonical content
        canonical_content = json.dumps({
            "target": capsule["target"],
            "observed_facts": capsule["observed_facts"],
            "deterministic_rule_findings": capsule["deterministic_rule_findings"],
            "ai_migration_recommendations": capsule["ai_migration_recommendations"],
            "test_verification_evidence": capsule["test_verification_evidence"],
        }, sort_keys=True)
        content_hash = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()

        source_hash = getattr(self.scan_result, "sha256_source_digest", "")

        capsule["artifact_integrity"] = {
            "algorithm": "SHA-256",
            "capsule_payload_sha256": content_hash,
            "source_snapshot_sha256": source_hash,
            "disclaimer": (
                "SHA-256 digest provides tamper-evident integrity of the serialized export audit record. "
                "A hash is not proof of truth, authorship, runtime correctness, or complete security."
            ),
        }

        return capsule

    def export_json(self, output_path: str | Path) -> Path:
        """Export the capsule to a pretty-printed JSON file."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        data = self.build_capsule_data()
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return out

    def export_html_report(self, output_path: str | Path) -> Path:
        """Export a clean, standalone, zero-dependency HTML executive report."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        data = self.build_capsule_data()

        target = data["target"]
        metrics = data["summary_metrics"]
        findings = data["deterministic_rule_findings"]
        recs = data["ai_migration_recommendations"]
        baseline = data["test_verification_evidence"]["baseline_test_run"]
        verifs = data["test_verification_evidence"]["candidate_comparisons"]

        findings_html = ""
        for f in findings:
            sev_class = f["severity"].lower()
            locs_html = "".join(
                f"<li><code>{html.escape(loc['file'])}:{loc.get('line', '')}</code>: <pre>{html.escape(loc.get('snippet', ''))}</pre></li>"
                for loc in f["evidence_locations"]
            )
            findings_html += f"""
            <div class="finding-card sev-{sev_class}">
                <div class="card-header">
                    <span class="badge badge-{sev_class}">{html.escape(f['severity'])}</span>
                    <span class="badge badge-cat">{html.escape(f['category'])}</span>
                    <strong>{html.escape(f['rule_id'])}</strong>: {html.escape(f['title'])}
                </div>
                <div class="card-body">
                    <p><strong>Package:</strong> <code>{html.escape(f['package'])}</code></p>
                    <p>{html.escape(f['description'])}</p>
                    <p class="rationale"><strong>Rationale:</strong> {html.escape(f['rationale'])}</p>
                    <p class="action"><strong>Action:</strong> {html.escape(f['suggested_action'])}</p>
                    <details>
                        <summary>Observed Evidence ({len(f['evidence_locations'])} locations)</summary>
                        <ul>{locs_html}</ul>
                    </details>
                </div>
            </div>
            """

        recs_html = ""
        for pkg, rec in recs.items():
            steps_html = "".join(f"<li>{html.escape(step)}</li>" for step in rec.get("migration_steps", []))
            tests_html = "".join(f"<li><code>{html.escape(t)}</code></li>" for t in rec.get("suggested_tests", []))
            risks_html = "".join(f"<li>{html.escape(r)}</li>" for r in rec.get("unresolved_risks", []))
            recs_html += f"""
            <div class="rec-card">
                <h3>Recommendation for <code>{html.escape(pkg)}</code> &rarr; <code>{html.escape(rec.get('proposed_package', ''))} {html.escape(rec.get('proposed_specifier', ''))}</code></h3>
                <p><strong>Strategy:</strong> {html.escape(rec.get('recommendation_type', ''))} | <strong>Confidence:</strong> {rec.get('confidence_score', 0.85):.0%}</p>
                <p><strong>Target Issue:</strong> {html.escape(rec.get('target_issue', ''))}</p>
                <h4>Migration Steps:</h4>
                <ol>{steps_html}</ol>
                {f'<h4>Suggested Tests:</h4><ul>{tests_html}</ul>' if tests_html else ''}
                {f'<h4>Unresolved Risks / Gaps:</h4><ul>{risks_html}</ul>' if risks_html else ''}
            </div>
            """

        verif_html = ""
        if baseline:
            base_badge = "badge-danger" if baseline["exit_code"] != 0 else "badge-success"
            verif_html += f"""
            <div class="verif-section">
                <h4>Baseline Test Results (Original Target Environment)</h4>
                <p>Command: <code>{html.escape(baseline['command_executed'])}</code> | Exit Code: <span class="badge {base_badge}">{baseline['exit_code']}</span></p>
                <p>Summary: {baseline['passed_tests']} passed, {baseline['failed_tests']} failed, {baseline['error_count']} errors in {baseline['duration_seconds']}s</p>
            </div>
            """

        for v in verifs:
            stat_class = "badge-success" if v["status"] == "VERIFIED_FIX" else "badge-warning"
            cand_res = v["candidate_result"]
            verif_html += f"""
            <div class="verif-card">
                <h4>Candidate Experiment: <code>{html.escape(v['package_name'])}</code> &rarr; <code>{html.escape(v['proposed_change'])}</code></h4>
                <p>Status: <span class="badge {stat_class}">{v['status']}</span></p>
                <p><strong>Verdict:</strong> {html.escape(v['verdict_summary'])}</p>
                <p>Candidate Pytest Run: {cand_res['passed_tests']} passed, {cand_res['failed_tests']} failed in {cand_res['duration_seconds']}s (Exit Code: {cand_res['exit_code']})</p>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MEND Dependency Exit Capsule — {html.escape(target['name'])}</title>
    <style>
        :root {{
            --bg: #ffffff;
            --card-bg: #ffffff;
            --border: #e4e4e7;
            --text: #18181b;
            --text-muted: #71717a;
            --primary: #1d4ed8;
            --crit: #991b1b;
            --high: #9a3412;
            --med: #854d0e;
            --low: #1d4ed8;
            --info: #1d4ed8;
        }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 2.5rem;
            line-height: 1.5;
        }}
        .container {{ max-width: 1040px; margin: 0 auto; }}
        header {{ border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; margin-bottom: 2rem; }}
        h1, h2, h3, h4 {{ color: #09090b; margin-top: 0; letter-spacing: -0.02em; }}
        .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 2px; font-size: 0.72rem; font-weight: 600; text-transform: uppercase; font-family: ui-monospace, monospace; }}
        .badge-critical {{ background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }}
        .badge-high {{ background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; }}
        .badge-medium {{ background: #fefce8; color: #854d0e; border: 1px solid #fef08a; }}
        .badge-low, .badge-info {{ background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }}
        .badge-cat {{ background: #f4f4f5; color: #3f3f46; margin-left: 0.4rem; border: 1px solid #e4e4e7; }}
        .badge-danger {{ background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }}
        .badge-success {{ background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }}
        .badge-warning {{ background: #fefce8; color: #854d0e; border: 1px solid #fef08a; }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .metric-card {{
            background: #ffffff;
            border: 1px solid var(--border);
            padding: 1rem;
            border-radius: 2px;
        }}
        .metric-val {{ font-size: 1.6rem; font-weight: 700; color: #09090b; }}
        .metric-label {{ font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 2px; }}
        .finding-card, .rec-card, .verif-card, .verif-section {{
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 2px;
            padding: 1.25rem;
            margin-bottom: 1rem;
        }}
        .finding-card.sev-critical {{ border-left: 3px solid #b91c1c; }}
        .finding-card.sev-high {{ border-left: 3px solid #c2410c; }}
        .finding-card.sev-medium {{ border-left: 3px solid #a16207; }}
        .finding-card.sev-low {{ border-left: 3px solid #1d4ed8; }}
        .finding-card.sev-info {{ border-left: 3px solid #1d4ed8; }}
        code {{ background: #f4f4f5; padding: 0.15rem 0.35rem; border-radius: 2px; font-family: ui-monospace, monospace; color: #09090b; border: 1px solid #e4e4e7; }}
        pre {{ background: #f8fafc; padding: 0.8rem; border-radius: 2px; overflow-x: auto; font-family: ui-monospace, monospace; font-size: 0.8rem; border: 1px solid var(--border); }}
        details {{ margin-top: 0.5rem; color: var(--text-muted); }}
        summary {{ cursor: pointer; color: var(--primary); font-weight: 500; font-size: 0.8rem; }}
        footer {{ border-top: 1px solid var(--border); padding-top: 1.5rem; margin-top: 3rem; color: var(--text-muted); font-size: 0.8rem; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h1>MEND Dependency Exit Capsule</h1>
                    <p style="color: var(--text-muted); margin: 0;">Target: <strong>{html.escape(target['name'])}</strong> | Generated: <code>{data['generated_at']}</code> | Schema: <code>{data['$schema_version']}</code></p>
                </div>
                <div>
                    <span class="badge badge-info">Track 1: Dependency Resilience</span>
                </div>
            </div>
        </header>

        <section>
            <h2>Executive Metrics</h2>
            <div class="metrics-grid">
                <div class="metric-card"><div class="metric-val">{metrics['total_dependencies']}</div><div class="metric-label">Total Dependencies</div></div>
                <div class="metric-card"><div class="metric-val">{metrics['direct_used_dependencies']}</div><div class="metric-label">Direct Code Usages</div></div>
                <div class="metric-card"><div class="metric-val" style="color: var(--crit);">{metrics['critical_findings']}</div><div class="metric-label">Critical Findings</div></div>
                <div class="metric-card"><div class="metric-val" style="color: var(--high);">{metrics['high_findings']}</div><div class="metric-label">High Risk Findings</div></div>
                <div class="metric-card"><div class="metric-val" style="color: var(--med);">{metrics['medium_findings']}</div><div class="metric-label">Medium Findings</div></div>
                <div class="metric-card"><div class="metric-val" style="color: var(--info);">{metrics['unreferenced_dependencies']}</div><div class="metric-label">Unreferenced / Zombie</div></div>
            </div>
        </section>

        <section>
            <h2>Deterministic Rule Engine Findings ({len(findings)})</h2>
            {findings_html}
        </section>

        {f'<section><h2>Gemma 4 Migration Recommendations ({len(recs)})</h2>{recs_html}</section>' if recs_html else ''}

        <section>
            <h2>Artifact Integrity & Fingerprints</h2>
            <div style="background: #f8fafc; border: 1px solid var(--border); padding: 1rem; border-radius: 4px; font-size: 0.85rem;">
                <p style="margin: 0 0 0.5rem 0;"><strong>Capsule Content SHA-256:</strong> <code>{data.get('artifact_integrity', {}).get('capsule_payload_sha256', '')}</code></p>
                <p style="margin: 0 0 0.5rem 0;"><strong>Target Source Snapshot SHA-256:</strong> <code>{data.get('artifact_integrity', {}).get('source_snapshot_sha256', 'N/A')}</code></p>
                <p style="margin: 0; color: var(--text-muted); font-size: 0.75rem;"><strong>Disclaimer:</strong> {html.escape(data.get('artifact_integrity', {}).get('disclaimer', ''))}</p>
            </div>
        </section>

        <footer>
            <p><strong>MEND Provenance:</strong> AI analysis performed by Gemma 4 (<code>{html.escape(GEMMA_METADATA['model_tag'])}</code>) via local Ollama runtime. Baseline and candidate tests executed via real pytest subprocesses in isolated sandbox environments.</p>
        </footer>
    </div>
</body>
</html>
"""
        out.write_text(html_content, encoding="utf-8")
        return out
