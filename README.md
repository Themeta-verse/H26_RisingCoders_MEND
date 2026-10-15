# MEND — Migration Evidence & Dependency Navigator
### Hacktoberfest 2026 — Track 1: Gemma 4 — Dependency Resilience
**Submission Repository**: [H26_RisingCoders_MEND](https://github.com/Themeta-verse/H26_RisingCoders_MEND)  
**Target Repository Under Investigation**: `LinkWatch` (CLI link/uptime checker & HTML status page)

[![Track 1](https://img.shields.io/badge/Hacktoberfest%202026-Track%201%3A%20Gemma%204%20Dependency%20Resilience-blue?style=flat-square)](#)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-green?style=flat-square)](#)
[![AI Model](https://img.shields.io/badge/AI%20Model-gemma4%3Ae2b--it--q4__K__M-purple?style=flat-square)](#)
[![Local Inference](https://img.shields.io/badge/Inference-Ollama%20Local%20(100%25%20Offline)-orange?style=flat-square)](#)
[![Tests Passing](https://img.shields.io/badge/MEND%20Tests-15%2F15%20Passed-brightgreen?style=flat-square)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

## 1. Executive Summary & Purpose

Traditional security tools focus exclusively on known CVE databases. However, real-world software breaks primarily due to **Dependency Friction & Transitive Incompatibilities**: uncoordinated minor/major bumps, manifest specification drift between `pyproject.toml` and `requirements.txt`, unmaintained upstream libraries, and breaking transitive peer dependencies.

**MEND** (**Migration Evidence & Dependency Navigator**) is an evidence-grounded dependency resilience and migration engine. It:
1. Extracts deterministic code usages via static AST parsing and manifest declarations.
2. Identifies resilience friction points across 8 deterministic rule categories.
3. Queries a local **Gemma 4** model (`gemma4:e2b-it-q4_K_M`) via Ollama with bounded evidence context (no context bloat, strict JSON schema validation).
4. Empirically verifies candidate migrations in isolated sandbox directories with real `pytest` execution without mutating the target repository.
5. Emits auditable, versioned **Dependency Exit Capsules** (JSON schema `1.0.0` and standalone zero-dependency HTML).

---

## 2. Key Findings on Target Codebase (`LinkWatch`)

When evaluating the real, unmodified `LinkWatch` target repository, MEND discovered:

1. **Critical Incompatible Transitive Pairing**:
   - `requirements.txt:4` pins `Jinja2==2.11.3`.
   - The runtime environment has `MarkupSafe 3.0.4`.
   - `Jinja2 2.11.3` imports `from markupsafe import soft_unicode`.
   - `MarkupSafe 3.0+` completely removed `soft_unicode`.
   - **Observed Test Failure**: `tests/test_report.py` crashes with `ImportError: cannot import name 'soft_unicode' from 'markupsafe'` (**Baseline: 9 Passed, 1 Failed**).
2. **Manifest Specification Conflict**:
   - `pydantic` is declared with `==1.10.13` in `requirements.txt:5` but `>=2` in `pyproject.toml:17`.
   - *Evidence Consistency*: Both the dashboard and the generated Dependency Exit Capsules reconcile to this **single true manifest conflict** (`pydantic`).
3. **Pydantic V1/V2 Code Collision**:
   - `linkwatch/config.py` uses deprecated v1 patterns (`@validator`, `class Config: anystr_strip_whitespace = True`), which fail under Pydantic v2.
4. **Abandoned Upstream Library**:
   - `appdirs==1.4.4` (discontinued since 2017) used in `linkwatch/cache.py:4`; standard community replacement is `platformdirs`.
   - *Evidence Integrity*: Evaluated purely as a deprecation rule finding (`RULE-DEPR-001`); no false failure or `ImportError` claims are attributed to `appdirs`.
5. **Deprecated Runtime API**:
   - `linkwatch/resources.py:1` imports `pkg_resources`, generating setuptools deprecation warnings.
6. **Obsolete Dev Framework**:
   - `nose==1.3.7` declared in `requirements-dev.txt:2` relies on `imp` (removed in Python 3.12); the test suite actually uses `pytest`.
7. **Unused / Phantom Dependency**:
   - `six` declared in manifests, but 0 imports exist across the codebase.
8. **Empirically Verified Sandbox Fix**:
   - Upgrading `Jinja2` to `>=3.1.4` was tested in an isolated sandbox, turning the baseline into **10 Passed, 0 Failed** (`VERIFIED_FIX`).

---

## 3. Strict Epistemic Separation

MEND enforces a clear distinction between four epistemic categories across both the UI and audit artifacts:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        EPISTEMIC TIERS IN MEND                         │
├─────────────────────────┬──────────────────────────────────────────────┤
│ Tier 1: Observed Facts  │ AST import snippets, manifest lines,         │
│                         │ installed package versions, exit codes.      │
├─────────────────────────┼──────────────────────────────────────────────┤
│ Tier 2: Static Rules    │ 8 Deterministic resilience rules             │
│                         │ (RULE-CONF, RULE-COMPAT, RULE-DEPR, etc.).   │
├─────────────────────────┼──────────────────────────────────────────────┤
│ Tier 3: AI Advisory     │ Non-authoritative guidance generated by      │
│                         │ local Gemma 4; never replaces proof.         │
├─────────────────────────┼──────────────────────────────────────────────┤
│ Tier 4: Empirical Proof │ Actual subprocess pytest exit codes from     │
│                         │ isolated sandbox candidate runs.             │
└─────────────────────────┴──────────────────────────────────────────────┘
```

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              MEND Editorial Swiss Dashboard (React + TS)        │
│   Inventory • Rule Findings • Gemma 4 Advisory • Sandboxes      │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP / JSON
┌───────────────────────────────▼─────────────────────────────────┐
│                   MEND FastAPI Backend Engine                   │
├─────────────────────┬──────────────────────┬────────────────────┤
│ Deterministic       │ Static Resilience    │ Local Gemma 4      │
│ Scanner             │ Rule Engine          │ Model Client       │
│ (AST & Manifests)   │ (8 Built-in Rules)   │ (Ollama :11434)    │
├─────────────────────┴──────────────────────┴────────────────────┤
│ Sandbox Candidate Verification Runner (pytest isolation)        │
├─────────────────────────────────────────────────────────────────┤
│ Dependency Exit Capsule Generator (Versioned JSON & HTML)       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Prerequisites

- **Python**: Version 3.12+ (tested with Python 3.12.10).
- **Node.js**: Version 18+ (tested with Node.js v24.19).
- **Ollama**: Running locally with the official Gemma 4 model:
  ```bash
  ollama pull gemma4:e2b-it-q4_K_M
  ```

---

## 6. Quick Start & Run Instructions

### Step 1: Set Up Python 3.12 Virtual Environment for MEND
```bash
# From workspace root
python -m venv mend/.venv

# Activate virtual environment
# Windows (PowerShell):
.\mend\.venv\Scripts\Activate.ps1
# Linux/macOS:
source mend/.venv/bin/activate

# Install MEND dependencies
pip install -r mend/requirements.txt
```

### Step 2: Build the Editorial Frontend
The production frontend bundle is pre-built in `mend/frontend/dist/`. To rebuild manually:
```bash
cd mend/frontend
npm install
npm run build
cd ../..
```

### Step 3: Ensure Ollama is Running
Ensure Ollama is running and has `gemma4:e2b-it-q4_K_M`:
```bash
ollama list
# Should display gemma4:e2b-it-q4_K_M
```

### Step 4: Launch MEND
Run the FastAPI backend with the pre-mounted frontend:
```bash
python -m uvicorn mend.api.main:app --host 127.0.0.1 --port 8000
```
Open your browser to: **`http://127.0.0.1:8000`**

---

## 7. Running the Automated Test Suite

Run the full MEND pytest test suite (15 unit, rule, API, and capsule tests):
```bash
# Windows PowerShell:
$env:PYTHONPATH='.'
.\mend\.venv\Scripts\python -m pytest mend/tests -v

# Linux/macOS:
PYTHONPATH=. ./mend/.venv/bin/python -m pytest mend/tests -v
```

All 15 tests execute cleanly:
- `test_api.py`: Status, scan, rules, recommendations, and capsule export routes.
- `test_capsule.py`: Schema `1.0.0` structure and export integrity.
- `test_model_client.py`: Bounded prompt construction and structured JSON parsing.
- `test_rules.py`: Incompatible transitive pairing and deprecation detections.
- `test_scanner.py`: AST parsing, manifest conflict detection, name normalization.

---

## 8. Verification & Demo Workflow

1. **Dashboard Inventory Tab**:
   - Inspect all 30 dependencies detected from `LinkWatch`'s `requirements.txt`, `requirements-dev.txt`, and `pyproject.toml`.
   - Filter by **Conflicts (1)** to view `pydantic`'s specifier discrepancy (`==1.10.13` vs `>=2`).
2. **Rule Findings Tab**:
   - Review 8 deterministic rule findings complete with severity, exact file line numbers, and code context snippets.
3. **Gemma 4 Advisory Tab**:
   - Click **Ask Gemma** for `Jinja2` or `appdirs`.
   - The UI displays an elapsed timer `(Xs elapsed)` and a cancellation button.
   - Gemma 4 returns a validated JSON migration plan citing drop-in replacements, step-by-step procedures, and residual risks.
4. **Empirical Sandbox Verification Tab**:
   - Inspect baseline test results (9 Passed, 1 Failed).
   - Click **Verify in Isolated Sandbox** to run candidate upgrades (`Jinja2>=3.1.4`) in a clean sandbox directory.
   - Observe the verified verdict: **10 Passed, 0 Failed (`VERIFIED_FIX`)**.
5. **Download Dependency Exit Capsules**:
   - Download the versioned audit capsule as JSON: [dependency_exit_capsule_linkwatch.json](mend/exports/dependency_exit_capsule_linkwatch.json)
   - View the standalone executive HTML report: [dependency_exit_capsule_linkwatch.html](mend/exports/dependency_exit_capsule_linkwatch.html)

---

## 9. Project Structure

```
.
├── linkwatch/                  # Pristine target codebase under test (read-only)
├── tests/                      # Pristine target pytest suite (baseline)
├── pyproject.toml              # Target pyproject manifest
├── requirements.txt            # Target requirements manifest
├── requirements-dev.txt        # Target development requirements manifest
├── sites.toml                  # Target site configuration
├── MEND_PROJECT_RULES.md       # Operational rules and epistemic constraints
├── PRESENTATION_SLIDES_EVIDENCE.md # 6-slide presentation evidence guide
├── README.md                   # This submission guide
└── mend/                       # MEND Application
    ├── api/
    │   ├── __init__.py
    │   └── main.py             # FastAPI REST endpoints & static file server
    ├── core/
    │   ├── __init__.py
    │   ├── candidate_runner.py # Isolated sandbox runner & test execution
    │   ├── capsule.py          # Dependency Exit Capsule generator (JSON/HTML)
    │   ├── model_client.py     # Local Gemma 4 client (Ollama HTTP / JSON)
    │   ├── rules.py            # 8 Deterministic resilience rules
    │   └── scanner.py          # Deterministic AST & manifest parser
    ├── exports/                # Generated Dependency Exit Capsules
    │   ├── dependency_exit_capsule_linkwatch.json
    │   └── dependency_exit_capsule_linkwatch.html
    ├── frontend/               # Vite + React + TypeScript Swiss Editorial UI
    │   ├── dist/               # Pre-compiled static assets
    │   ├── src/
    │   ├── package.json
    │   └── vite.config.ts
    ├── tests/                  # 15 Automated pytest verification tests
    └── requirements.txt        # Backend dependencies (fastapi, uvicorn, etc.)
```

---

## 10. License

MEND is open-source under the [MIT License](mend/LICENSE).  
Gemma 4 model weights are governed by the [Gemma Terms of Use](https://ai.google.dev/gemma/terms).
