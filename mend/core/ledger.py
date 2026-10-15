"""Migration Integrity Ledger for MEND.

Maintains an auditable, evidence-backed lifecycle for every dependency:
OBSERVED -> RECOMMENDED -> EXECUTED -> VERIFIED / FAILED / INCONCLUSIVE

Never labels a recommendation as verified before actual isolated execution.
Connects real manifest declarations, AST code usages, deterministic rule findings,
Gemma 4 model provenance, sandbox pytest comparisons, and artifact integrity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .candidate_runner import MigrationVerificationComparison
from .model_client import GEMMA_METADATA, MigrationRecommendation
from .rules import RuleFinding
from .scanner import RepositoryScanResult


@dataclass
class LedgerEntry:
    package_name: str
    normalized_name: str
    stage: str  # "OBSERVED", "RECOMMENDED", "EXECUTED", "VERIFIED", "FAILED", "INCONCLUSIVE"
    observed_facts: Dict[str, Any]
    recommendation_provenance: Optional[Dict[str, Any]] = None
    candidate_execution: Optional[Dict[str, Any]] = None
    capsule_exported: bool = False
    integrity_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MigrationIntegrityLedger:
    """Builds and serializes the end-to-end evidence lifecycle ledger."""

    def __init__(
        self,
        scan_result: RepositoryScanResult,
        rule_findings: List[RuleFinding],
        recommendations: Optional[Dict[str, MigrationRecommendation]] = None,
        candidate_verifications: Optional[List[MigrationVerificationComparison]] = None,
    ):
        self.scan_result = scan_result
        self.rule_findings = rule_findings
        self.recommendations = recommendations or {}
        self.candidate_verifications = candidate_verifications or []

    def build_ledger(self) -> Dict[str, Any]:
        """Construct entries for every scanned dependency in deterministic order."""
        verif_map: Dict[str, MigrationVerificationComparison] = {}
        for comp in self.candidate_verifications:
            verif_map[comp.package_name.lower().replace("_", "-")] = comp

        entries: List[Dict[str, Any]] = []
        stage_counts = {
            "OBSERVED": 0,
            "RECOMMENDED": 0,
            "EXECUTED": 0,
            "VERIFIED": 0,
            "FAILED": 0,
            "INCONCLUSIVE": 0,
        }

        for norm_name, dep in sorted(self.scan_result.dependencies.items()):
            # 1. Observed Facts
            rel_findings = [
                f.to_dict()
                for f in self.rule_findings
                if f.package.lower().replace("_", "-") == norm_name
            ]
            obs = {
                "installed_version": dep.installed_version,
                "is_direct_usage": dep.is_direct_usage,
                "is_manifest_conflicted": dep.is_manifest_conflicted,
                "conflict_details": dep.conflict_details,
                "manifest_declarations": [asdict(d) for d in dep.manifest_declarations],
                "code_usage_count": len(dep.direct_imports),
                "code_usage_locations": [asdict(loc) for loc in dep.direct_imports],
                "rule_findings": rel_findings,
            }

            # 2. Recommendation Provenance
            rec = None
            for p, r in self.recommendations.items():
                if p.lower().replace("_", "-") == norm_name:
                    rec = r
                    break

            rec_data = None
            if rec:
                rec_dict = rec.model_dump() if hasattr(rec, "model_dump") else rec.dict()
                rec_data = {
                    "model_tag": GEMMA_METADATA["model_tag"],
                    "runtime": GEMMA_METADATA["runtime"],
                    "strategy": rec_dict.get("recommendation_type"),
                    "proposed_package": rec_dict.get("proposed_package"),
                    "proposed_specifier": rec_dict.get("proposed_specifier"),
                    "confidence_score": rec_dict.get("confidence_score"),
                    "target_issue": rec_dict.get("target_issue"),
                    "migration_steps": rec_dict.get("migration_steps", []),
                    "unresolved_risks": rec_dict.get("unresolved_risks", []),
                    "assumptions": rec_dict.get("assumptions", []),
                }

            # 3. Candidate Execution Record
            comp = verif_map.get(norm_name)
            cand_data = None
            stage = "OBSERVED"

            if comp:
                cand_data = {
                    "candidate_id": comp.candidate_id,
                    "proposed_change": comp.proposed_change,
                    "status": comp.status,
                    "verdict_summary": comp.verdict_summary,
                    "unresolved_gaps": comp.unresolved_gaps,
                    "baseline_result": {
                        "command": comp.baseline_result.command_executed,
                        "exit_code": comp.baseline_result.exit_code,
                        "passed": comp.baseline_result.passed_tests,
                        "failed": comp.baseline_result.failed_tests,
                        "duration_s": comp.baseline_result.duration_seconds,
                    },
                    "candidate_result": {
                        "command": comp.candidate_result.command_executed,
                        "exit_code": comp.candidate_result.exit_code,
                        "passed": comp.candidate_result.passed_tests,
                        "failed": comp.candidate_result.failed_tests,
                        "duration_s": comp.candidate_result.duration_seconds,
                    },
                }
                if comp.status in ("VERIFIED_FIX", "VERIFIED_MAINTAINED"):
                    stage = "VERIFIED"
                elif comp.status in ("REGRESSION", "STILL_FAILING"):
                    stage = "FAILED"
                else:
                    stage = "INCONCLUSIVE"
            elif rec:
                stage = "RECOMMENDED"
            else:
                stage = "OBSERVED"

            stage_counts[stage] = stage_counts.get(stage, 0) + 1

            # Compute tamper-evident entry digest
            canonical_repr = json.dumps(
                {"pkg": dep.name, "obs": obs, "rec": rec_data, "cand": cand_data, "stage": stage},
                sort_keys=True,
            )
            entry_hash = hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

            entries.append(
                LedgerEntry(
                    package_name=dep.name,
                    normalized_name=norm_name,
                    stage=stage,
                    observed_facts=obs,
                    recommendation_provenance=rec_data,
                    candidate_execution=cand_data,
                    capsule_exported=True,
                    integrity_hash=entry_hash,
                ).to_dict()
            )

        # Ledger-level hash
        ledger_canonical = json.dumps([e["integrity_hash"] for e in entries], sort_keys=True)
        ledger_hash = hashlib.sha256(ledger_canonical.encode("utf-8")).hexdigest()

        return {
            "target_repository": self.scan_result.target_name,
            "total_dependencies": len(entries),
            "stage_distribution": stage_counts,
            "ledger_sha256": ledger_hash,
            "source_snapshot_sha256": getattr(self.scan_result, "sha256_source_digest", ""),
            "lifecycle_rule": "OBSERVED -> RECOMMENDED -> EXECUTED -> VERIFIED / FAILED / INCONCLUSIVE",
            "entries": entries,
        }
