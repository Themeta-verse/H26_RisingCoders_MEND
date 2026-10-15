# MEND Project Rules — Hacktoberfest 2026 Track 1: Gemma 4 — Dependency Resilience

## Purpose
MEND (Migration Evidence & Dependency Navigator) is an intelligent, evidence-grounded dependency resilience and migration engine. It enables development teams to inspect real codebases, identify dependency friction, obtain structured migration guidance from a local Gemma 4 model via Ollama, verify candidate fixes in isolated environments, and export reproducible Dependency Exit Capsules.

## Non-Negotiable Operational Rules

1. **Preserve Target Repository Integrity**:
   - The target under analysis (`LinkWatch/`) must remain pristine.
   - Never edit files or alter the baseline virtual environment in `LinkWatch/`.
   - All migration candidate experiments must execute in dedicated temporary candidate environments or sandbox copies.

2. **Strict Epistemic Separation**:
   - **Observed Facts**: Exact manifest declarations, file paths, line numbers, installed versions, test runner exit codes, and raw tracebacks.
   - **Rule-Engine Findings**: Deterministic static analysis detections (e.g., manifest version conflicts, deprecated libraries, unused dependencies, deprecated APIs).
   - **AI Recommendations**: Structured migration guidance generated strictly by Gemma 4 (`gemma4:e2b-it-q4_K_M`) via local Ollama inference. Must always be marked as AI-generated recommendations.
   - **Verification Results**: Real test suite execution outputs from isolated candidate runs.

3. **Gemma 4 Local Inference**:
   - Model tag: `gemma4:e2b-it-q4_K_M` via Ollama at `http://localhost:11434`.
   - Never claim a fallback or dummy heuristic is Gemma 4. If Ollama or the model is offline, clearly report the offline state and preserve deterministic scanner capabilities.
   - Do not substitute cloud APIs or external commercial models. Core workflow is 100% local and zero-cost.

4. **No Fabricated Evidence**:
   - No mock test successes, no simulated benchmark outputs, no fake diffs.
   - If candidate testing is not executed or fails, report the exact status and tracebacks honestly.

5. **Dependency Exit Capsule**:
   - Provide a versioned, portable JSON artifact capturing full provenance: target metadata, detected manifests, code usage evidence, deterministic risk findings, Gemma 4 migration advice, candidate test verification runs, and unresolved compatibility gaps.
