import urllib.request
import json
import time

BASE = "http://127.0.0.1:8000"

def req(path, method="GET", data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode("utf-8") if data else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

print("1. Scanning LinkWatch...")
s, scan = req("/api/scan")
print(f"   Scan status {s}: {len(scan['dependencies'])} dependencies found, SHA256: {scan['sha256_source_digest'][:16]}...")

print("2. Evaluating Deterministic Rules...")
s, rules = req("/api/rules")
print(f"   Rules status {s}: {len(rules)} findings")

print("3. Querying Gemma 4 (Local Ollama) for Jinja2...")
t0 = time.time()
s, rec = req("/api/recommend", "POST", {"package_name": "Jinja2"})
t1 = time.time()
print(f"   Gemma 4 status {s} in {t1-t0:.2f}s: Proposed={rec['proposed_package']}{rec['proposed_specifier']}, Steps={len(rec['migration_steps'])}")

print("4. Running Sandbox Candidate Verification for Jinja2>=3.1.4...")
t0 = time.time()
s, cand = req("/api/verify-candidate", "POST", {
    "candidate_id": "jinja2-bump-3.1.4",
    "package_name": "Jinja2",
    "package_install_spec": "Jinja2>=3.1.4"
})

t1 = time.time()
b_pass = cand["baseline_result"]["passed_tests"]
b_tot = cand["baseline_result"]["total_tests"]
c_pass = cand["candidate_result"]["passed_tests"]
c_tot = cand["candidate_result"]["total_tests"]
print(f"   Candidate status {s} in {t1-t0:.2f}s: Status={cand['status']}, Baseline={b_pass}/{b_tot} -> Candidate={c_pass}/{c_tot}")
print(f"   Verdict: {cand['verdict_summary']}")

print("5. Generating Dependency Exit Capsule...")
s, cap = req("/api/capsule/generate", "POST")
print(f"   Capsule status {s}: Target={cap['target']['name']}, Timestamp={cap['generated_at']}")


print("6. Checking Integrity & Source Digest...")
s, integ = req("/api/integrity")
print(f"   Integrity status {s}: Digest={integ['source_snapshot_sha256'][:16]}...")

print("7. Inspecting Lifecycle Ledger...")
s, led = req("/api/ledger")
print(f"   Ledger status {s}: {len(led['entries'])} lifecycle entries recorded.")

print("\nSUCCESS: COMPLETE END-TO-END VERIFICATION EXECUTED WITHOUT ANY ERRORS!")
