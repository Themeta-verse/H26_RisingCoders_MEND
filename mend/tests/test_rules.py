"""Unit tests for MEND RuleEngine."""

from pathlib import Path
from mend.core.scanner import DependencyScanner
from mend.core.rules import RuleEngine, Severity, Category


def _get_target() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    if (root / "LinkWatch" / "pyproject.toml").is_file():
        return root / "LinkWatch"
    if (root / "pyproject.toml").is_file():
        return root
    return root / "LinkWatch"


def test_rule_engine_findings_on_linkwatch():
    target = _get_target()
    scanner = DependencyScanner(target)
    scan = scanner.scan()

    engine = RuleEngine()
    findings = engine.evaluate(scan)

    assert len(findings) >= 5

    rule_ids = {f.rule_id for f in findings}
    assert "RULE-CONF-001" in rule_ids   # Pydantic manifest conflict
    assert "RULE-COMPAT-001" in rule_ids # Jinja2 / MarkupSafe incompatibility
    assert "RULE-BREAK-001" in rule_ids  # Pydantic v1 vs v2
    assert "RULE-DEPR-001" in rule_ids   # appdirs
    assert "RULE-DEPR-002" in rule_ids   # pkg_resources
    assert "RULE-OBSOLETE-001" in rule_ids # nose
    assert "RULE-ZOMBIE-001" in rule_ids # six

    # Verify every finding has documented evidence, reason, and severity
    for f in findings:
        assert f.severity in list(Severity)
        assert f.category in list(Category)
        assert len(f.rationale) > 10
        assert len(f.evidence_locations) >= 1
