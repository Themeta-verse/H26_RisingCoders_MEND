"""Unit tests for MEND Ecosystem Adapters and Capability Boundaries."""

import json
from pathlib import Path
import tempfile
import pytest

from mend.core.adapters import (
    BaseEcosystemAdapter,
    EcosystemDetectionResult,
    EcosystemType,
    SupportLevel,
    PythonEcosystemAdapter,
    JavaScriptEcosystemAdapter,
    detect_ecosystem,
)


def test_python_adapter_linkwatch_detection():
    # LinkWatch has pyproject.toml
    adapter = PythonEcosystemAdapter()
    detection = adapter.detect(Path(__file__).resolve().parent.parent.parent.parent / "LinkWatch")
    assert detection is not None
    assert detection.ecosystem == EcosystemType.PYTHON
    assert detection.support_level == SupportLevel.FULL
    assert detection.capabilities.candidate_sandbox_verification is True
    assert "pyproject.toml" in detection.detected_manifests


def test_javascript_adapter_detection_and_rules():
    adapter = JavaScriptEcosystemAdapter()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create sample package.json with unpinned range and deprecated package
        pkg_json = {
            "name": "sample-node-app",
            "version": "1.0.0",
            "dependencies": {
                "request": "^2.88.2",  # Deprecated + unpinned
                "lodash": "4.17.21",   # Pinned
                "express": "*",        # Wildcard unpinned
            },
            "devDependencies": {
                "mocha": "^10.0.0"     # Unreferenced zombie
            }
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg_json, indent=2), encoding="utf-8")

        # Create sample index.js using request and lodash
        sample_js = """
        const request = require('request');
        import _ from 'lodash';

        console.log("Running app");
        """
        (tmp_path / "index.js").write_text(sample_js, encoding="utf-8")

        # 1. Detection
        detection = adapter.detect(tmp_path)
        assert detection is not None
        assert detection.ecosystem == EcosystemType.JAVASCRIPT
        assert detection.support_level == SupportLevel.PARTIAL
        assert detection.capabilities.candidate_sandbox_verification is False
        assert "Candidate sandbox" in detection.limitations[1]
        assert "UNSUPPORTED" in detection.limitations[1]

        # 2. Scan
        scan_res = adapter.scan(tmp_path)
        assert scan_res.target_name == "sample-node-app"
        assert len(scan_res.dependencies) == 4
        assert "request" in scan_res.dependencies
        assert scan_res.dependencies["request"].is_direct_usage is True
        assert scan_res.dependencies["mocha"].is_direct_usage is False
        assert "mocha" in scan_res.unreferenced_dependencies

        # 3. Rule evaluation
        findings = adapter.evaluate_rules(scan_res)
        rule_ids = [f.rule_id for f in findings]
        assert "RULE-JS-001" in rule_ids  # Deprecated 'request'
        assert "RULE-JS-002" in rule_ids  # Unpinned '^2.88.2' or '*'
        assert "RULE-JS-003" in rule_ids  # Unreferenced zombie 'mocha'


def test_unsupported_ecosystem_detection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / "data.txt").write_text("plain text file", encoding="utf-8")

        adapter, detection = detect_ecosystem(tmp_path)
        assert detection.ecosystem == EcosystemType.UNSUPPORTED
        assert detection.support_level == SupportLevel.UNSUPPORTED
        assert "Unsupported" in detection.display_name
