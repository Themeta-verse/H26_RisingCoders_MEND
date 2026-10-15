# MEND — Migration Evidence & Dependency Navigator
### Hacktoberfest 2026 — Track 1: Gemma 4 — Dependency Resilience

[![Track 1](https://img.shields.io/badge/Hacktoberfest%202026-Track%201%3A%20Gemma%204%20Dependency%20Resilience-blue?style=flat-square)](#)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-green?style=flat-square)](#)
[![Model](https://img.shields.io/badge/AI%20Model-gemma4%3Ae2b--it--q4__K__M-purple?style=flat-square)](#)
[![Local Inference](https://img.shields.io/badge/Inference-Ollama%20Local%20(100%25%20Offline)-orange?style=flat-square)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

MEND (**Migration Evidence & Dependency Navigator**) is an intelligent, evidence-grounded dependency resilience and migration engine. Rather than focusing on external CVE vulnerability alerts, MEND focuses on **Dependency Resilience**: discovering breaking transitive pairings, manifest specifier drift, dead/obsolete libraries, and unreferenced phantom dependencies, and using local **Gemma 4** (`gemma4:e2b-it-q4_K_M`) via Ollama to generate verified migration paths.

---

## Key Achievements on Target Codebase (`LinkWatch`)

When evaluating the real, unmodified `LinkWatch` target repository, MEND discovered:
1. **Critical Incompatible Transitive Pairing**: `Jinja2==2.11.3` pinned in `requirements.txt:4` imports `soft_unicode` from MarkupSafe. MarkupSafe 3.0.4 removed `soft_unicode`, causing `tests/test_report.py` to immediately crash with `ImportError: cannot import name 'soft_unicode' from 'markupsafe'` (**Baseline: 9 Passed, 1 Failed**).
2. **Manifest Specification Conflict**: `pydantic` is declared with `==1.10.13` in `requirements.txt:5` but `>=2` in `pyproject.toml:17`.
3. **Pydantic V1/V2 Migration Risk**: `linkwatch/config.py` uses deprecated v1 patterns (`@validator`, `class Config: anystr_strip_whitespace = True`), which fail under Pydantic v2.
4. **Abandoned Upstream Library**: `appdirs==1.4.4` (discontinued since 2017) used in `linkwatch/cache.py:4`; standard community replacement is `platformdirs`.
5. **Deprecated Runtime API**: `linkwatch/resources.py:1` imports `pkg_resources`, generating setuptools deprecation warnings.
6. **Obsolete Dev Framework**: `nose==1.3.7` declared in `requirements-dev.txt:2` relies on `imp` (removed in Python 3.12); test suite actually uses `pytest`.
7. **Unused / Zombie Dependency**: `six` declared in manifests but 0 imports exist in source code.
8. **Empirically Verified Sandbox Fix**: Upgrading `Jinja2` to `>=3.1.4` was verified in an isolated sandbox without altering `LinkWatch`, turning the failing test into **10 Passed, 0 Failed**.

---

## Non-Negotiable Operational Principles

1. **Strict Epistemic Separation**:
   - **Observed Facts**: Exact file paths, line numbers, installed versions, test runner exit codes, and raw tracebacks.
   - **Rule-Engine Findings**: Deterministic static analysis detections with confidence, rationale, and documented severities.
   - **AI Recommendations**: Structured guidance generated strictly by Gemma 4 via local Ollama. Always labeled as non-authoritative recommendations.
   - **Verification Results**: Real pytest subprocess execution outputs from isolated sandboxes.
2. **Zero Target Repository Modification**: The target `LinkWatch/` is preserved as pristine baseline evidence. Experiments execute in temporary sandbox environments using PYTHONPATH overrides.
3. **100% Zero-Cost Local Inference**: Powered entirely by `gemma4:e2b-it-q4_K_M` via local Ollama. No cloud dependencies, paid tokens, or API keys required.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MEND Dashboard (Vite + React + TS)          │
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

## AI Model & Runtime Specifications

| Attribute | Specification |
|---|---|
| **Model Tag** | `gemma4:e2b-it-q4_K_M` |
| **Model Family** | Gemma 4 (4.6B parameters, Q4_K_M quantization) |
| **Runtime Provider** | Ollama Local Daemon (`http://localhost:11434`) |
| **Inference Endpoint** | `POST http://localhost:11434/api/chat` |
| **Context Strategy** | Bounded context (manifest declarations, AST import locations, rule findings, and observed baseline failures) |
| **Output Format** | Validated JSON strictly adhering to `MigrationRecommendation` Pydantic schema |
| **License / Terms** | [Gemma Terms of Use](https://ai.google.dev/gemma/terms) (Google Open Weights) |

---

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js v18+ (tested on v24.19)
- Ollama running locally with `gemma4:e2b-it-q4_K_M` downloaded:
  ```bash
  ollama pull gemma4:e2b-it-q4_K_M
  ```

### Installation

1. Activate or create the virtual environment for MEND:
   ```powershell
   cd mend
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Build or start the frontend:
   ```powershell
   cd frontend
   npm install
   npm run build
   ```

### Running MEND

You can run MEND using a single command:
```powershell
# From mend/ directory with virtualenv active:
uvicorn mend.api.main:app --host 127.0.0.1 --port 8000
```
Open your browser at **`http://127.0.0.1:8000`**. The FastAPI server automatically serves the built React frontend at `/` and the REST API at `/api/*`.

Alternatively, for frontend hot-reloading:
```powershell
# Terminal 1: Backend
uvicorn mend.api.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Frontend
cd mend/frontend
npm run dev
# Open http://localhost:5173
```

---

## Running the Automated Test Suite

Run the full MEND unit and integration test suite:
```powershell
pytest mend/tests -v
```

All 13 test suites execute and pass deterministically:
- `test_scanner.py`: AST parsing, manifest conflict detection, name normalization.
- `test_rules.py`: Incompatible transitive pairing rule, manifest conflict rule, deprecation rules.
- `test_model_client.py`: Structured JSON parsing, markdown stripping, schema validation errors.
- `test_capsule.py`: Versioned JSON capsule generation and HTML report rendering.
- `test_api.py`: FastAPI endpoints, status checks, downloads, and report generation.

---

## The Dependency Exit Capsule

MEND generates an auditable, versioned (`$schema_version: "1.0.0"`) **Dependency Exit Capsule**.

### Contained Artifacts:
- **Target Metadata**: Repository path, Python requires specifier, detected manifest files, LOC.
- **Observed Facts**: Manifest declarations, installed packages, AST usage locations.
- **Rule Engine Findings**: Every resilience risk with severity, category, rationale, and exact code snippet.
- **Gemma 4 Migration Guidance**: Exact proposed packages, migration steps, test commands, and unresolved risks.
- **Verification Evidence**: Complete baseline test run logs and isolated candidate sandbox execution logs.
- **Downloads**:
  - `dependency_exit_capsule_linkwatch.json` (Machine-readable)
  - `dependency_exit_capsule_linkwatch.html` (Standalone, zero-dependency executive report)

---

## Project Structure

```
MEND-Hackathon/
├── LinkWatch/                  # Target repository under analysis (PRISTINE / UNTOUCHED)
│   ├── linkwatch/              # Application source code
│   ├── tests/                  # Test suite (9 passing, 1 failing baseline)
│   ├── pyproject.toml          # Declares pydantic>=2
│   └── requirements.txt        # Pins pydantic==1.10.13, Jinja2==2.11.3
├── mend/                       # Our application
│   ├── core/
│   │   ├── scanner.py          # Deterministic AST & Manifest scanner
│   │   ├── rules.py            # 8 Resilience rules (conflicts, incompatibilities, deprecations)
│   │   ├── model_client.py     # Local Gemma 4 client via Ollama
│   │   ├── candidate_runner.py # Isolated sandbox candidate runner (pytest)
│   │   └── capsule.py          # Dependency Exit Capsule JSON & HTML generator
│   ├── api/
│   │   └── main.py             # FastAPI REST application
│   ├── frontend/               # React + TypeScript + Vite dashboard
│   ├── tests/                  # Pytest test suite (13 passing tests)
│   └── LICENSE                 # MIT License
├── MEND_PROJECT_RULES.md       # Root operational rules
└── README.md                   # This documentation
```

---

## Troubleshooting

- **Ollama connection refused (`http://localhost:11434`)**:
  Start Ollama in your terminal: `ollama serve`. Verify with `Invoke-RestMethod http://localhost:11434/api/tags`.
- **Model `gemma4:e2b-it-q4_K_M` not found**:
  Pull the model: `ollama pull gemma4:e2b-it-q4_K_M`.
- **Port 8000 already in use**:
  Run uvicorn on an alternative port: `uvicorn mend.api.main:app --port 8080`.
