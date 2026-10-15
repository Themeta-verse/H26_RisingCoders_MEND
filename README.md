# MEND — Migration Evidence & Dependency Navigator
### Hacktoberfest 2026 — Track 1: Gemma 4 — Dependency Resilience
**Submission Repository**: [H26_RisingCoders_MEND](https://github.com/Themeta-verse/H26_RisingCoders_MEND)  
**Target Repository Under Investigation**: `LinkWatch` (CLI link/uptime checker & HTML status page)

[![Track 1](https://img.shields.io/badge/Hacktoberfest%202026-Track%201%3A%20Gemma%204%20Dependency%20Resilience-blue?style=flat-square)](#)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-green?style=flat-square)](#)
[![AI Model](https://img.shields.io/badge/AI%20Model-gemma4%3Ae2b--it--q4__K__M-purple?style=flat-square)](#)
[![Local Inference](https://img.shields.io/badge/Inference-Ollama%20Local%20(100%25%20Offline)-orange?style=flat-square)](#)
[![Tests Passing](https://img.shields.io/badge/MEND%20Tests-25%2F25%20Passed-brightgreen?style=flat-square)](#)
[![Multi-Repo](https://img.shields.io/badge/Multi--Repo-Supported-blue?style=flat-square)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

## 1. Executive Summary & Purpose

Traditional security tools focus exclusively on known CVE databases. However, real-world software breaks primarily due to **Dependency Friction & Transitive Incompatibilities**: uncoordinated minor/major bumps, manifest specification drift between `pyproject.toml` and `requirements.txt`, unmaintained upstream libraries, and breaking transitive peer dependencies.

**MEND** (**Migration Evidence & Dependency Navigator**) is an **evidence-first dependency migration workbench**, not just an AI scanner. It:
1. Extracts deterministic code usages via static AST parsing and manifest declarations.
2. Supports **reusable multi-repository scanning** across public GitHub repositories while maintaining `LinkWatch` as the official starter target.
3. Implements an **adapter-based architecture** with honest capability boundaries (Python: Full Support; JavaScript/Node.js: Partial Static Support).
4. Identifies resilience friction points across deterministic rule categories.
5. Queries a local **Gemma 4** model (`gemma4:e2b-it-q4_K_M`) via Ollama with bounded evidence context (no context bloat, strict JSON schema validation).
6. Empirically verifies candidate migrations in isolated sandbox directories with real `pytest` execution without mutating the target repository.
7. Emits auditable, versioned **Dependency Exit Capsules** (JSON schema `1.0.0` and standalone zero-dependency HTML) separated by repository identity and revision.
8. Maintains an auditable **Migration Integrity Ledger** tracking dependencies across strict lifecycle states: `OBSERVED → RECOMMENDED → EXECUTED → VERIFIED / FAILED / INCONCLUSIVE`.
9. Provides **On-Demand Scan Drift Comparison** to detect manifest, AST, and dependency changes between scan snapshots.


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

### 3.1 Migration Integrity Lifecycle Ledger
MEND implements an evidence-backed lifecycle state machine for every dependency:
`OBSERVED → RECOMMENDED → EXECUTED → VERIFIED / FAILED / INCONCLUSIVE`
- **OBSERVED**: Extracted from actual `pyproject.toml`, `requirements.txt`, and AST direct imports with exact line numbers.
- **RECOMMENDED**: Generated by local Gemma 4 (`gemma4:e2b-it-q4_K_M`) via Ollama with bounded JSON schema and confidence scoring.
- **EXECUTED**: Invoked in an isolated sandbox clone with controlled allowlisted commands.
- **VERIFIED / FAILED**: Determined strictly by empirical pytest exit codes and failure counts.
- **Rule**: Recommendations are *never* labeled as verified prior to real sandbox test execution.

### 3.2 Artifact Integrity & Cryptographic SHA-256 Fingerprints
- Target repository source snapshots are hashed deterministically via SHA-256 across all discovered manifests and Python files.
- Exported Dependency Exit Capsules (JSON and HTML) embed SHA-256 digests ensuring tamper-evident immutability for CI/CD compliance pipelines.
- **Integrity Limits & Disclaimer**: A SHA-256 hash guarantees export record immutability and tamper-detection. It is not cryptographic proof of external package trustworthiness, runtime safety, or code authorship.

### 3.3 On-Demand Scan Drift Comparison (`/api/scan/diff`)
- Developers and judges can trigger on-demand snapshot drift comparisons without claiming automated continuous background monitoring.
- Compares: added/removed packages, modified version specifiers, AST usage changes, manifest conflict introductions/resolutions, and source SHA-256 changes with honest timestamps.

### 3.4 Candidate Runner Safety Boundaries
- **Target Immutability**: LinkWatch source files and virtual environment are strictly read-only.
- **Filesystem & Environment Isolation**: Candidate experiments run in temporary clones with overridden `PYTHONPATH` prioritizing the candidate package override tree.
- **Command Control**: Parameters are strictly validated via regex (`^[a-zA-Z0-9_\-\.\[\]><=~! ]+$`); execution uses explicit parameter lists without `shell=True`.
- **Resource Limits**: 60s pytest timeout, 90s pip timeout, 250KB output cap, and automatic retention limit pruning to the 5 most recent sandboxes.
- **Sandbox Boundary Notice**: The sandbox isolates file modifications and environment overrides. It runs with host user permissions and is not a kernel-level container or VM.

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

## 4. Ecosystem Adapter Support Matrix & Honest Boundaries

MEND separates repository discovery, manifest parsing, source usage analysis, resilience rules, AI advisories, and candidate verification into modular ecosystem adapters without overclaiming capabilities:

| Ecosystem | Support Level | Manifest Parsing | AST Usage Analysis | Deterministic Rules | Gemma 4 Advisory | Sandbox Verification |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Python** (PEP 508 / PyPI) | **FULL** | `pyproject.toml`, `requirements*.txt`, `setup.py` | `ast.parse` (Import, ImportFrom) | MEND-001–008 | Bounded JSON Schema via Ollama | Isolated virtualenv + `pytest` |
| **JavaScript / Node.js** (npm) | **PARTIAL** | `package.json`, `package-lock.json` | Regex/AST (`import`, `require`) | Unpinned range, Deprecated pkgs, Zombies | Informational Advisory | **UNSUPPORTED** (Explicit boundary) |
| **Other / Unknown** | **UNSUPPORTED** | None | None | None | None | **UNSUPPORTED** |

> **Track 1 Compliance Disclosure**: Candidate sandbox verification (running `pytest` in isolated workspace clones) is exclusively implemented for Python repositories. For JavaScript/Node.js, static manifest and AST source analysis are supported, but sandbox execution is explicitly disclaimed to prevent fabricated evidence.

---

## 5. Reusable Multi-Repository Workflow

MEND is not hardcoded to `LinkWatch`. It includes a full multi-repository management system:

1. **Default Official Target**: `LinkWatch` remains the primary challenge target.
2. **Public GitHub Repository Input**:
   - Provide any public GitHub repository URL (e.g. `https://github.com/bottlepy/bottle`).
   - No GitHub Personal Access Token is required for public repositories.
   - Code is cloned into dedicated controlled workspaces (`mend/workspaces/<owner>__<repo>`).
   - Exact commit SHA is captured via `git rev-parse HEAD`.
   - **Zero Code Execution on Inspection**: Source files are inspected purely through AST/regex parsing without executing untrusted code.
3. **Data Isolation by Identity & Revision**:
   - Scan snapshots, rule findings, Gemma 4 recommendations, baseline tests, candidate verifications, and exported Capsules are strictly separated by repository ID and commit hash.
   - Switching back to `LinkWatch` restores LinkWatch's exact state without cross-contamination.
4. **Fresh Scan on Revision Updates**:
   - The UI and API support `POST /api/repositories/refresh` to re-fetch revisions and perform fresh scans.

---

## 6. Running the Automated Test Suite

Run the full MEND pytest test suite (25 unit, rule, adapter, multi-repo, API, ledger, and capsule tests):
```bash
# Windows PowerShell:
$env:PYTHONPATH='.'
.\mend\.venv\Scripts\python -m pytest mend/tests -v

# Linux/macOS:
PYTHONPATH=. ./mend/.venv/bin/python -m pytest mend/tests -v
```

All 25 tests execute cleanly:
- `test_adapters.py`: Python full detection, JavaScript partial detection & rules, and unsupported ecosystem fallback.
- `test_api.py`: Repository listing, selection, URL validation, status, scan, scan diff, rules, recommendations, lifecycle ledger, integrity fingerprints, and capsule export routes.
- `test_capsule.py`: Schema `1.0.0` structure, SHA-256 digest embedding, target metadata, and export integrity.
- `test_model_client.py`: Bounded prompt construction and structured JSON parsing.
- `test_rules.py`: Incompatible transitive pairing and deprecation detections.
- `test_scanner.py`: AST parsing, manifest conflict detection, name normalization, and snapshot diffs.


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

### 8.1 Repository Selector & Multi-Repository Workflow

MEND features a dedicated **Repository Selector** in the top navigation strip adjacent to `TARGET:`:
- **Active Repository Badge & Commit**: Displays the current target (e.g. `linkwatch`, `bottlepy__bottle`), its 10-character commit SHA (`f52f3930c8`), and its revision state (`Benchmark: Immutable` vs `Revision: Fetched`).
- **Repository Switching**: Instantaneously switch between registered repositories. All scan caches, findings, baseline results, and capsules remain strictly isolated per repository.
- **Add Public Repository**: Input any public GitHub repository URL (e.g., `https://github.com/bottlepy/bottle`) to clone `--depth 1` without executing code.

### 8.2 Operational Semantics: Sync vs. Re-scan vs. Drift Check

MEND provides clear semantic boundaries for repository operations:
1. **Add Repository** (`POST /api/repositories/add`):
   - Clones a public GitHub repository using `git clone --depth 1` into `mend/workspaces/<owner>__<repo>`.
   - Records the initial commit SHA and sets origin to `fetched`.
   - Strictly static: code is never executed during clone or registration.
2. **Sync with GitHub** (`POST /api/repositories/sync`):
   - **Explicit remote network operation**: Runs `git fetch --depth 1 origin` and `git reset --hard origin/HEAD` on cloned public repositories.
   - Detects whether a new revision was fetched or if the local checkout was already up to date.
   - Invalidates stale scan caches and forces clean re-analysis upon revision change.
   - **Safety Guarantee**: Explicitly protected on the official `linkwatch` benchmark directory. LinkWatch is an immutable challenge baseline and can never be overwritten or git-mutated.
3. **Re-scan** (`POST /api/repositories/refresh` / `GET /api/scan?refresh=true`):
   - **Strictly local operation**: Re-executes static AST parsing and manifest inspection against the local files currently in the workspace.
   - **Never makes remote network calls to GitHub**. Reflects local file modifications or working-copy edits.
4. **Drift Check** (`GET /api/scan/diff?refresh=true`):
   - Computes an in-memory snapshot diff comparing the previous scan with the current scan.
   - Identifies added/removed dependencies, version specifier shifts, AST import count fluctuations, manifest conflict changes, and source tree SHA-256 digest modifications.

### 8.3 Static Analysis Safety Guarantee

Repository inspection in MEND is **strictly static by default**:
- Python files are parsed using Python's native `ast` module and regex tokenizers. Code is never imported or executed during scanning.
- JavaScript / TypeScript packages are parsed via deterministic `package.json` manifest analysis.
- Dynamic execution is quarantined exclusively to the **Empirical Sandbox Candidate Verification** workflow, which operates within temporary sandbox directories under strict timeouts.

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
├── MEND_Track1_Gemma4_Dependency_Resilience.pptx # Official 6-slide presentation deck
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
    │   ├── ledger.py           # Migration Integrity Lifecycle Ledger
    │   ├── model_client.py     # Local Gemma 4 client (Ollama HTTP / JSON)
    │   ├── rules.py            # 8 Deterministic resilience rules
    │   └── scanner.py          # Deterministic AST & manifest parser (SHA-256 & diffs)
    ├── exports/                # Generated Dependency Exit Capsules
    │   ├── dependency_exit_capsule_linkwatch.json
    │   └── dependency_exit_capsule_linkwatch.html
    ├── frontend/               # Vite + React + TypeScript Swiss Editorial UI
    │   ├── dist/               # Pre-compiled static assets
    │   ├── src/
    │   ├── package.json
    │   └── vite.config.ts
    ├── tests/                  # 18 Automated pytest verification tests
    └── requirements.txt        # Backend dependencies (fastapi, uvicorn, etc.)
```

---

## 10. License

MEND is open-source under the [MIT License](mend/LICENSE).  
Gemma 4 model weights are governed by the [Gemma Terms of Use](https://ai.google.dev/gemma/terms).
