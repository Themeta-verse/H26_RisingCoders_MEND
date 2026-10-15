"""Unit tests for MEND DependencyCapsuleGenerator."""

import json
from pathlib import Path
from mend.core.scanner import DependencyScanner
from mend.core.rules import RuleEngine
from mend.core.capsule import DependencyCapsuleGenerator, CAPSULE_SCHEMA_VERSION


def _get_target() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    if (root / "LinkWatch" / "pyproject.toml").is_file():
        return root / "LinkWatch"
    if (root / "pyproject.toml").is_file():
        return root
    return root / "LinkWatch"


def test_capsule_structure_and_export(tmp_path):
    target = _get_target()
    scanner = DependencyScanner(target)
    scan = scanner.scan()

    engine = RuleEngine()
    findings = engine.evaluate(scan)

    generator = DependencyCapsuleGenerator(scan_result=scan, rule_findings=findings)
    data = generator.build_capsule_data()

    assert data["$schema_version"] == CAPSULE_SCHEMA_VERSION
    assert "CAPSULE-LINKWATCH" in data["capsule_id"]
    assert data["target"]["name"] == "LinkWatch"
    assert data["summary_metrics"]["total_dependencies"] > 0
    assert len(data["deterministic_rule_findings"]) > 0

    # Test JSON export
    json_path = tmp_path / "capsule.json"
    generator.export_json(json_path)
    assert json_path.exists()
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["capsule_id"] == data["capsule_id"]

    # Test HTML export
    html_path = tmp_path / "report.html"
    generator.export_html_report(html_path)
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")
    assert "MEND Dependency Exit Capsule" in content
    assert "LinkWatch" in content
