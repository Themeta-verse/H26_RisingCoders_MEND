"""Unit tests for MEND GemmaModelClient validation and schemas."""

import pytest
from pydantic import ValidationError
from mend.core.model_client import GemmaModelClient, MigrationRecommendation


def test_parse_valid_json():
    client = GemmaModelClient()
    sample = """
    ```json
    {
        "package_name": "Jinja2",
        "target_issue": "soft_unicode removed in MarkupSafe",
        "recommendation_type": "version_bump",
        "proposed_package": "Jinja2",
        "proposed_specifier": ">=3.1.4",
        "migration_steps": ["Bump Jinja2 in requirements.txt", "Run pytest"],
        "code_changes": [],
        "assumptions": ["MarkupSafe remains 3.x"],
        "suggested_tests": ["pytest tests/test_report.py"],
        "unresolved_risks": [],
        "confidence_score": 0.95
    }
    ```
    """
    rec = client._parse_and_validate_recommendation(sample, default_pkg="Jinja2")
    assert isinstance(rec, MigrationRecommendation)
    assert rec.package_name == "Jinja2"
    assert rec.proposed_specifier == ">=3.1.4"
    assert rec.confidence_score == 0.95
    assert len(rec.migration_steps) == 2


def test_parse_invalid_json():
    client = GemmaModelClient()
    with pytest.raises(ValueError, match="invalid JSON"):
        client._parse_and_validate_recommendation("This is plain text not json", "Jinja2")


def test_schema_missing_fields():
    client = GemmaModelClient()
    bad_json = '{"package_name": "Jinja2"}'
    with pytest.raises(ValueError, match="failed schema validation"):
        client._parse_and_validate_recommendation(bad_json, "Jinja2")
