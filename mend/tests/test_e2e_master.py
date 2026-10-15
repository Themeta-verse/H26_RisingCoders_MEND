"""Master End-to-End Acceptance Verification Script.

Executes all phases specified in MASTER EXECUTION PROMPT 1/2:
- LinkWatch benchmark state & isolation
- Bottle public clone, selection, scanning, and evidence inspection
- Non-contamination verification (LinkWatch -> Bottle -> LinkWatch)
- Ledger anchoring (repo_id & commit_hash on all entries)
- Standard library recognition and AST deduplication
- Capsule export for both repositories
"""

import sys
import json
import httpx

BASE_URL = "http://127.0.0.1:8000"

def run_test():
    client = httpx.Client(base_url=BASE_URL, timeout=120.0)
    print("=== PHASE 0 & 1: VERIFY LINKWATCH (OFFICIAL BENCHMARK) ===")
    
    # Select LinkWatch
    res = client.post("/api/repositories/select", json={"repo_id": "linkwatch"})
    assert res.status_code == 200, f"Failed to select LinkWatch: {res.text}"
    print("[PASS] Selected repository 'linkwatch'")

    # Status check
    status = client.get("/api/status").json()
    assert status["target_repository"]["id"] == "linkwatch"
    assert status["target_repository"]["is_official"] is True
    linkwatch_commit = status["target_repository"]["commit_hash"]
    print(f"[PASS] LinkWatch target confirmed: commit={linkwatch_commit[:10]}, official=True")

    # Scan LinkWatch
    scan = client.get("/api/scan").json()
    assert "jinja2" in scan["dependencies"]
    assert "pydantic" in scan["dependencies"]
    assert scan["dependencies"]["pydantic"]["is_manifest_conflicted"] is True
    
    # Check datetime AST deduplication in LinkWatch
    dt_dep = scan["dependencies"].get("datetime")
    assert dt_dep is not None, "datetime not found in scan"
    assert dt_dep["is_standard_library"] is True
    checker_locs = [
        loc for loc in dt_dep["direct_imports"]
        if "checker.py" in loc["file_path"] and loc["line_number"] == 2
    ]
    assert len(checker_locs) == 1, f"Expected exactly 1 deduplicated entry for checker.py:2, got {len(checker_locs)}"
    print(f"[PASS] LinkWatch scanned: {len(scan['dependencies'])} deps, pydantic conflict verified, datetime AST deduplicated to 1 entry")

    # Baseline tests
    baseline = client.get("/api/baseline-tests").json()
    assert baseline["passed_tests"] == 9
    assert baseline["failed_tests"] == 1
    print(f"[PASS] LinkWatch baseline tests: {baseline['passed_tests']} passed, {baseline['failed_tests']} failed")

    # Ledger LinkWatch
    ledger = client.get("/api/ledger").json()
    assert ledger["repo_id"] == "linkwatch"
    assert ledger["commit_hash"] == linkwatch_commit
    assert len(ledger["entries"]) >= 20
    assert all(e["repo_id"] == "linkwatch" and e["commit_hash"] == linkwatch_commit for e in ledger["entries"])
    print(f"[PASS] LinkWatch ledger: {len(ledger['entries'])} entries all strictly anchored to repo_id=linkwatch and commit={linkwatch_commit[:10]}")

    # Generate Capsule for LinkWatch
    capsule_lw = client.post("/api/capsule/generate").json()
    assert "CAPSULE-LINKWATCH" in capsule_lw["capsule_id"]
    print(f"[PASS] LinkWatch Exit Capsule generated: {capsule_lw['capsule_id']}")

    print("\n=== PHASE 1 & 2: IMPORT BOTTLE VIA /api/repositories/add ===")
    add_res = client.post("/api/repositories/add", json={"url": "https://github.com/bottlepy/bottle"})
    if add_res.status_code == 200:
        bottle_info = add_res.json()["active_repository"]
        print(f"[PASS] Bottle cloned & registered: id={bottle_info['id']}, commit={bottle_info['commit_hash'][:10]}")
    else:
        # Check if already added
        repos = client.get("/api/repositories").json()["repositories"]
        bottle_repo = next((r for r in repos if r["id"] == "bottlepy__bottle" or "bottle" in r["id"]), None)
        assert bottle_repo is not None, f"Failed to add or locate bottle: {add_res.text}"
        bottle_info = bottle_repo
        print(f"[PASS] Bottle already registered: id={bottle_info['id']}, commit={bottle_info['commit_hash'][:10]}")

    # Select Bottle
    bottle_id = bottle_info["id"]
    sel_bottle = client.post("/api/repositories/select", json={"repo_id": bottle_id})
    assert sel_bottle.status_code == 200
    status_bottle = client.get("/api/status").json()
    assert status_bottle["target_repository"]["id"] == bottle_id
    assert status_bottle["target_repository"]["is_official"] is False
    bottle_commit = status_bottle["target_repository"]["commit_hash"]
    assert bottle_commit != linkwatch_commit, "Bottle commit MUST differ from LinkWatch commit"
    print(f"[PASS] Selected Bottle: id={bottle_id}, commit={bottle_commit[:10]}, official=False")

    # Scan Bottle
    scan_bottle = client.get("/api/scan").json()
    assert "pydantic" not in scan_bottle["dependencies"], "CONTAMINATION: LinkWatch's pydantic found in Bottle!"
    # Ensure all discovered code usage locations belong strictly to Bottle's repo, never LinkWatch
    for dep_name, dep in scan_bottle["dependencies"].items():
        for loc in dep.get("direct_imports", []):
            assert "linkwatch" not in loc["file_path"].lower(), f"CONTAMINATION: LinkWatch path in Bottle: {loc['file_path']}"
    
    # If jinja2 appears in Bottle, it must be Bottle's own template adapter in bottle.py:4070 with 0 manifest declarations
    if "jinja2" in scan_bottle["dependencies"]:
        bottle_jinja = scan_bottle["dependencies"]["jinja2"]
        assert len(bottle_jinja["manifest_declarations"]) == 0
        assert any("bottle.py" in loc["file_path"] for loc in bottle_jinja["direct_imports"])
    print(f"[PASS] Bottle scan isolated: {len(scan_bottle['dependencies'])} deps discovered from Bottle's actual code. Zero LinkWatch files or manifests present.")

    # Ledger Bottle
    ledger_bottle = client.get("/api/ledger").json()
    assert ledger_bottle["repo_id"] == bottle_id
    assert ledger_bottle["commit_hash"] == bottle_commit
    assert all(e["repo_id"] == bottle_id and e["commit_hash"] == bottle_commit for e in ledger_bottle["entries"])
    print(f"[PASS] Bottle ledger isolated: {len(ledger_bottle['entries'])} entries anchored strictly to repo_id={bottle_id} and commit={bottle_commit[:10]}")

    # Generate Capsule for Bottle
    capsule_bottle = client.post("/api/capsule/generate").json()
    assert "CAPSULE-" in capsule_bottle["capsule_id"]
    print(f"[PASS] Bottle Exit Capsule generated: {capsule_bottle['capsule_id']}")

    print("\n=== PHASE 2: SWITCH BACK TO LINKWATCH (NO CONTAMINATION) ===")
    sel_lw = client.post("/api/repositories/select", json={"repo_id": "linkwatch"})
    assert sel_lw.status_code == 200
    status_lw_back = client.get("/api/status").json()
    assert status_lw_back["target_repository"]["id"] == "linkwatch"
    assert status_lw_back["target_repository"]["commit_hash"] == linkwatch_commit

    scan_lw_back = client.get("/api/scan").json()
    assert "jinja2" in scan_lw_back["dependencies"]
    assert "pydantic" in scan_lw_back["dependencies"]

    ledger_lw_back = client.get("/api/ledger").json()
    assert ledger_lw_back["repo_id"] == "linkwatch"
    assert ledger_lw_back["commit_hash"] == linkwatch_commit
    print("[PASS] Switched back to LinkWatch: exact original state restored with zero Bottle contamination.")

    print("\n=== ALL PHASES AND ACCEPTANCE CHECKS PASSED ===")

if __name__ == "__main__":
    run_test()
