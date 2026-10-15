"""Real Gemma 4 Model Client for MEND.

Connects strictly to the local Ollama API at http://localhost:11434/api/chat,
using model tag 'gemma4:e2b-it-q4_K_M'.
Sends bounded code and manifest evidence, parses and validates structured JSON recommendations,
and provides transparent offline/error diagnostics without ever fabricating AI output.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("mend.model_client")

OLLAMA_DEFAULT_URL = "http://localhost:11434"
DEFAULT_GEMMA_MODEL = "gemma4:e2b-it-q4_K_M"

# Provenance documentation
GEMMA_METADATA = {
    "model_tag": DEFAULT_GEMMA_MODEL,
    "provider": "Ollama (Local Inference Runtime)",
    "runtime": "Ollama (Local Inference Runtime)",
    "family": "gemma4",
    "runtime_endpoint": OLLAMA_DEFAULT_URL,
    "license_terms": "Gemma Terms of Use (Google Open Weights)",
    "epistemic_status": "AI-Generated Recommendation (Non-Authoritative until Verified)",
}


class CodeDiffProposal(BaseModel):
    file_path: str
    original_snippet: str
    replacement_snippet: str
    explanation: str


class MigrationRecommendation(BaseModel):
    package_name: str
    target_issue: str
    recommendation_type: str = Field(
        ...,
        description="One of: 'version_bump', 'library_replacement', 'prune_dependency', 'code_migration'"
    )
    proposed_package: str
    proposed_specifier: str
    migration_steps: List[str]
    code_changes: List[CodeDiffProposal] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    suggested_tests: List[str] = Field(default_factory=list)
    unresolved_risks: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.85, ge=0.0, le=1.0)
    provenance: Dict[str, Any] = Field(default_factory=lambda: GEMMA_METADATA.copy())


@dataclass
class OllamaStatus:
    is_online: bool
    endpoint: str
    model_tag: str
    model_available: bool
    available_models: List[str]
    error_message: Optional[str] = None


class GemmaModelClient:
    """Real client for local Gemma 4 inference through Ollama."""

    def __init__(self, base_url: str = OLLAMA_DEFAULT_URL, model_name: str = DEFAULT_GEMMA_MODEL, timeout_seconds: float = 90.0):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def check_health(self) -> OllamaStatus:
        """Verify Ollama service reachability and presence of the Gemma 4 model."""
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    is_available = any(
                        self.model_name == m or self.model_name in m
                        for m in models
                    )
                    return OllamaStatus(
                        is_online=True,
                        endpoint=self.base_url,
                        model_tag=self.model_name,
                        model_available=is_available,
                        available_models=models,
                        error_message=None if is_available else f"Model '{self.model_name}' not found in Ollama tags",
                    )
                return OllamaStatus(
                    is_online=False,
                    endpoint=self.base_url,
                    model_tag=self.model_name,
                    model_available=False,
                    available_models=[],
                    error_message=f"Ollama returned HTTP status {res.status_code}",
                )
        except httpx.ConnectError:
            return OllamaStatus(
                is_online=False,
                endpoint=self.base_url,
                model_tag=self.model_name,
                model_available=False,
                available_models=[],
                error_message=f"Could not connect to Ollama at {self.base_url}. Is the service running?",
            )
        except Exception as exc:
            return OllamaStatus(
                is_online=False,
                endpoint=self.base_url,
                model_tag=self.model_name,
                model_available=False,
                available_models=[],
                error_message=f"Health check error: {str(exc)}",
            )

    def request_recommendation(
        self,
        package_name: str,
        manifest_declarations: List[Dict[str, Any]],
        code_usage_locations: List[Dict[str, Any]],
        rule_findings: List[Dict[str, Any]],
        observed_test_failure: Optional[str] = None,
        python_requires: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> MigrationRecommendation:
        """Send bounded evidence to Gemma 4 and validate structured JSON recommendation."""
        eff_timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds

        # 1. Check health quickly (3s timeout)
        health = self.check_health()
        if not health.is_online:
            raise ConnectionError(
                f"Ollama is offline or unreachable at {self.base_url}. {health.error_message}"
            )
        if not health.model_available:
            raise RuntimeError(
                f"Gemma 4 model '{self.model_name}' is not downloaded in Ollama. "
                f"Available models: {health.available_models}"
            )

        # 2. Build bounded evidence context
        system_prompt = (
            "You are MEND's Dependency Resilience AI Expert powered by Gemma 4.\n"
            "Your task is to analyze real repository evidence and recommend a concrete, safe migration plan "
            "for a specific Python package.\n"
            "CRITICAL: Output MUST be a single valid JSON object strictly adhering to the schema below. "
            "Do not output markdown code blocks (```json) or introductory chit-chat, only the raw JSON.\n\n"
            "JSON Schema:\n"
            "{\n"
            '  "package_name": "string",\n'
            '  "target_issue": "string",\n'
            '  "recommendation_type": "version_bump" | "library_replacement" | "prune_dependency" | "code_migration",\n'
            '  "proposed_package": "string",\n'
            '  "proposed_specifier": "string",\n'
            '  "migration_steps": ["step 1", "step 2", ...],\n'
            '  "code_changes": [\n'
            '    {\n'
            '      "file_path": "string",\n'
            '      "original_snippet": "string",\n'
            '      "replacement_snippet": "string",\n'
            '      "explanation": "string"\n'
            '    }\n'
            '  ],\n'
            '  "assumptions": ["string", ...],\n'
            '  "suggested_tests": ["string", ...],\n'
            '  "unresolved_risks": ["string", ...],\n'
            '  "confidence_score": float between 0.0 and 1.0\n'
            "}"
        )

        user_content = self._build_prompt_payload(
            package_name=package_name,
            manifest_declarations=manifest_declarations,
            code_usage_locations=code_usage_locations,
            rule_findings=rule_findings,
            observed_test_failure=observed_test_failure,
            python_requires=python_requires,
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic engineering precision
                "top_p": 0.9,
            },
        }

        # 3. Perform inference with explicit bounded timeout
        try:
            with httpx.Client(timeout=eff_timeout) as client:
                resp = client.post(f"{self.base_url}/api/chat", json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"Ollama inference error (HTTP {resp.status_code}): {resp.text}"
                    )
                data = resp.json()
                raw_response = data.get("message", {}).get("content", "").strip()
        except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout):
            raise TimeoutError(
                f"Gemma 4 inference timed out after {eff_timeout}s at {self.base_url}."
            )
        except Exception as exc:
            raise RuntimeError(f"Gemma 4 query failed: {str(exc)}") from exc

        # 4. Parse and validate JSON
        return self._parse_and_validate_recommendation(raw_response, package_name)

    def _build_prompt_payload(
        self,
        package_name: str,
        manifest_declarations: List[Dict[str, Any]],
        code_usage_locations: List[Dict[str, Any]],
        rule_findings: List[Dict[str, Any]],
        observed_test_failure: Optional[str],
        python_requires: Optional[str],
    ) -> str:
        sections = [
            f"# TARGET DEPENDENCY: {package_name}",
            f"Python Target Version: {python_requires or '>=3.10'}",
            "\n## MANIFEST DECLARATIONS:",
        ]
        if manifest_declarations:
            for d in manifest_declarations:
                sections.append(f"- In {d.get('manifest_file')} (line {d.get('line_number')}): `{d.get('raw_line')}`")
        else:
            sections.append("- (No explicit manifest declaration found)")

        sections.append("\n## RELEVANT CODE USAGE LOCATIONS:")
        if code_usage_locations:
            for loc in code_usage_locations[:5]:  # Bounded to top 5 locations to avoid bloating context
                sections.append(
                    f"File: {loc.get('file_path')} (line {loc.get('line_number')})\n"
                    f"Statement: `{loc.get('statement')}`\n"
                    f"Context snippet:\n{loc.get('context_snippet', '')}"
                )
        else:
            sections.append("- No direct imports found in source code (possibly zombie or transitive).")

        sections.append("\n## RULE-BASED FINDINGS:")
        if rule_findings:
            for f in rule_findings:
                sections.append(
                    f"- [{f.get('rule_id')}] ({f.get('severity')} - {f.get('category')}): {f.get('title')}\n"
                    f"  Details: {f.get('description')}\n"
                    f"  Suggested Action: {f.get('suggested_action')}"
                )
        else:
            sections.append("- No deterministic rule flags for this package.")

        if observed_test_failure:
            sections.append(f"\n## OBSERVED BASELINE TEST FAILURE:\n```\n{observed_test_failure}\n```")

        sections.append(
            "\nProvide your concrete, safe migration recommendation in JSON format as specified."
        )
        return "\n".join(sections)

    def _parse_and_validate_recommendation(self, raw_text: str, default_pkg: str) -> MigrationRecommendation:
        """Strip markdown markers if present, parse JSON, and validate against schema."""
        cleaned = raw_text.strip()
        # Remove markdown code blocks if the model wrapped it
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Find first '{' and last '}'
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start : end + 1]

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Gemma 4 returned invalid JSON: {str(exc)}\nRaw output was:\n{raw_text[:500]}"
            ) from exc

        # Ensure package_name is present
        if not parsed.get("package_name"):
            parsed["package_name"] = default_pkg

        try:
            return MigrationRecommendation.model_validate(parsed)
        except ValidationError as exc:
            raise ValueError(
                f"Gemma 4 response failed schema validation: {str(exc)}\nParsed object: {parsed}"
            ) from exc
