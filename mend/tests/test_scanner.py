"""Unit tests for MEND DependencyScanner."""

from pathlib import Path
import pytest
from mend.core.scanner import DependencyScanner, normalize_name


def test_normalize_name():
    assert normalize_name("Jinja2") == "jinja2"
    assert normalize_name("python_dateutil") == "python-dateutil"
    assert normalize_name("PyYAML") == "pyyaml"
    assert normalize_name("pkg.resources") == "pkg-resources"


def _get_target() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    if (root / "LinkWatch" / "pyproject.toml").is_file():
        return root / "LinkWatch"
    if (root / "pyproject.toml").is_file():
        return root
    return root / "LinkWatch"


def test_scan_linkwatch_manifests():
    target = _get_target()
    scanner = DependencyScanner(target)
    scan = scanner.scan()

    assert "pyproject.toml" in scan.manifests_found
    assert "requirements.txt" in scan.manifests_found
    assert "requirements-dev.txt" in scan.manifests_found
    assert len(scan.dependencies) >= 10

    # Pydantic should be conflicted
    pydantic_dep = scan.dependencies.get("pydantic")
    assert pydantic_dep is not None
    assert pydantic_dep.is_manifest_conflicted is True
    assert len(scan.manifest_conflicts) >= 1

    # Six should be unreferenced
    assert "six" in [d.lower() for d in scan.unreferenced_dependencies]

    # Jinja2 should have code usages
    jinja = scan.dependencies.get("jinja2")
    assert jinja is not None
    assert jinja.is_direct_usage is True
    assert len(jinja.direct_imports) >= 1
    assert any("report.py" in loc.file_path for loc in jinja.direct_imports)
