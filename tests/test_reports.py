import os
import re
import json
import math
from pathlib import Path
import pytest
import yaml
from fastapi.testclient import TestClient

from api.main import app
from api.database import init_db

REPO_ROOT = Path(__file__).resolve().parent.parent
SANDBOX_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()

@pytest.fixture
def client():
    return TestClient(app)

# 1. Docker Compose & Dockerfile Verification
def test_docker_compose_and_dockerfile():
    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist at repo root"
    
    with open(compose_path, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)
        
    services = compose.get("services", {})
    assert "api" in services, "api service must be defined in docker-compose.yml"
    assert "ledger" in services, "ledger service must be defined in docker-compose.yml"
    
    # Check healthchecks
    for svc_name in ["api", "ledger"]:
        svc = services[svc_name]
        assert "healthcheck" in svc, f"{svc_name} must have a healthcheck"
        hc = svc["healthcheck"]
        for key in ["interval", "timeout", "retries", "start_period"]:
            assert key in hc, f"{svc_name} healthcheck missing {key}"
            
    # Ledger mounts seeds
    ledger_volumes = services["ledger"].get("volumes", [])
    has_seeds = any("./seeds" in str(v) for v in ledger_volumes)
    assert has_seeds, "ledger must mount ./seeds or equivalent init path"
    
    # Root Dockerfile
    dockerfile_path = REPO_ROOT / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile must exist at repo root"

# 2. Environment Variables Verification
def test_env_example_and_no_live_env():
    env_example = REPO_ROOT / ".env.example"
    assert env_example.exists(), ".env.example must exist at repo root"
    
    content = env_example.read_text(encoding="utf-8")
    required_keys = [
        "CELESTO_PROVIDER",
        "CELESTO_API_KEY",
        "LLM_API_KEY",
        "LLM_MODEL",
        "DATABASE_URL",
        "API_PORT"
    ]
    for key in required_keys:
        assert f"{key}=" in content, f".env.example must define {key}"
        
    # Live .env must NOT exist in the submission
    live_env = REPO_ROOT / ".env"
    assert not live_env.exists(), ".env must not be present at the root of the submission"

# 3. Problem Statement Verification
def test_problem_json():
    problem_path = REPO_ROOT / "reports" / "problem.json"
    assert problem_path.exists(), "reports/problem.json must exist"
    
    with open(problem_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for k in ["who", "agent_work", "proof_output", "idea_source"]:
        assert k in data, f"reports/problem.json missing key '{k}'"
        
    assert data["idea_source"] in ["idea_bank", "original"], "idea_source must be 'idea_bank' or 'original'"
    assert len(data["who"]) >= 40, "who must be at least 40 characters"
    assert len(data["agent_work"]) >= 40, "agent_work must be at least 40 characters"
    assert len(data["proof_output"]) >= 20, "proof_output must be at least 20 characters"

# 4. Command Audit Log Verification
def test_commands_jsonl():
    log_path = REPO_ROOT / "logs" / "commands.jsonl"
    assert log_path.exists(), "logs/commands.jsonl must exist"
    
    lines = [line.strip() for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1, "logs/commands.jsonl must contain at least one JSON line"
    
    for line in lines:
        entry = json.loads(line)
        assert "ts" in entry and entry["ts"], "Log entry missing ts"
        assert "sandbox_name" in entry, "Log entry missing sandbox_name"
        assert SANDBOX_REGEX.match(entry["sandbox_name"]), f"Invalid sandbox_name: {entry['sandbox_name']}"
        assert "command" in entry and entry["command"].strip(), "Command must be non-empty"
        assert entry.get("decision") in ["allow", "block"], f"Invalid decision: {entry.get('decision')}"
        assert entry.get("execution_target") == "celesto_sandbox", "execution_target must be exactly 'celesto_sandbox'"

# 5. Capabilities Verification
def test_capabilities_json():
    cap_path = REPO_ROOT / "reports" / "capabilities.json"
    assert cap_path.exists(), "reports/capabilities.json must exist"
    
    with open(cap_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    capabilities = data.get("capabilities", [])
    assert len(capabilities) >= 2, "capabilities must have at least two objects"
    
    allowed_ids = {
        "persistence", "snapshots", "celestofs", "browser", "published_ports",
        "network_policy", "safety_hooks", "host_mounts", "coding_agent_preset", "agentor_durable"
    }
    
    seen_ids = set()
    for cap in capabilities:
        cap_id = cap.get("id")
        assert cap_id in allowed_ids, f"Invalid capability id '{cap_id}'"
        assert cap_id not in seen_ids, f"Duplicate capability id '{cap_id}'"
        seen_ids.add(cap_id)
        
        why = cap.get("why", "")
        assert len(why) >= 80, f"Capability '{cap_id}' why must be at least 80 characters"
        
        evidence_path = REPO_ROOT / cap.get("evidence_path", "")
        assert evidence_path.exists(), f"evidence_path does not exist: {cap.get('evidence_path')}"

# 6. Lifecycle Verification
def test_lifecycle_json():
    lf_path = REPO_ROOT / "reports" / "lifecycle.json"
    assert lf_path.exists(), "reports/lifecycle.json must exist"
    
    with open(lf_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data.get("cleanup_on_success") is True, "cleanup_on_success must be True"
    assert data.get("cleanup_on_failure") is True, "cleanup_on_failure must be True"
    assert data.get("cleanup_on_interrupt") is True, "cleanup_on_interrupt must be True"
    
    sandbox_names = data.get("sandbox_names", [])
    assert len(sandbox_names) > 0, "sandbox_names must be non-empty"
    assert len(sandbox_names) == len(set(sandbox_names)), "sandbox_names must be unique"
    
    # Check names regex
    for name in sandbox_names:
        assert SANDBOX_REGEX.match(name), f"Invalid sandbox name format: {name}"
        
    # Check that each name appears in logs/commands.jsonl or in reports/reliability.json
    commands_text = (REPO_ROOT / "logs" / "commands.jsonl").read_text(encoding="utf-8")
    reliability_text = (REPO_ROOT / "reports" / "reliability.json").read_text(encoding="utf-8")
    for name in sandbox_names:
        assert (name in commands_text) or (name in reliability_text), f"Sandbox {name} not found in logs or reliability"

# 7. Reliability and Post-Mortem Verification
def test_reliability_json_and_postmortem():
    rel_path = REPO_ROOT / "reports" / "reliability.json"
    assert rel_path.exists(), "reports/reliability.json must exist"
    
    with open(rel_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    runs = data.get("runs", [])
    run_count = data.get("run_count")
    assert run_count == len(runs), "run_count must equal len(runs)"
    assert run_count >= 20, "run_count must be at least 20"
    
    seen_sbx = set()
    success_count = 0
    wall_clocks = []
    boot_times = []
    costs = []
    
    for r in runs:
        sbx = r.get("sandbox_name")
        assert SANDBOX_REGEX.match(sbx), f"Invalid sandbox_name: {sbx}"
        assert sbx not in seen_sbx, f"Duplicate sandbox_name: {sbx}"
        seen_sbx.add(sbx)
        
        assert r.get("fresh") is True, "fresh must be True"
        if r.get("success") is True:
            success_count += 1
            
        wc = r.get("wall_clock_s")
        assert wc is not None and wc >= 0
        wall_clocks.append(wc)
        
        bt = r.get("boot_to_ready_s")
        assert bt is not None and bt >= 0
        boot_times.append(bt)
        
        c = r.get("cost_usd")
        assert c is not None and c >= 0
        costs.append(c)
        
    # Arithmetic checks
    expected_sr = success_count / run_count
    assert abs(data.get("success_rate", 0) - expected_sr) <= 0.001
    
    # Median wall clock
    sorted_wc = sorted(wall_clocks)
    n = len(sorted_wc)
    expected_med_wc = (sorted_wc[n // 2 - 1] + sorted_wc[n // 2]) / 2.0
    assert abs(data.get("median_wall_clock_s", 0) - expected_med_wc) <= 0.001
    
    # p90 wall clock
    p90_rank = math.ceil(0.90 * n)
    expected_p90 = sorted_wc[p90_rank - 1]
    assert abs(data.get("p90_wall_clock_s", 0) - expected_p90) <= 0.001
    
    # Median boot to ready
    sorted_bt = sorted(boot_times)
    expected_med_bt = (sorted_bt[n // 2 - 1] + sorted_bt[n // 2]) / 2.0
    assert abs(data.get("median_boot_to_ready_s", 0) - expected_med_bt) <= 0.001
    
    # Total cost
    expected_cost = sum(costs)
    assert abs(data.get("total_cost_usd", 0) - expected_cost) <= 0.01
    
    # Postmortem path
    pm_path = REPO_ROOT / data.get("postmortem_path", "")
    assert pm_path.exists(), "reports/postmortem.md must exist"
    assert len(pm_path.read_text(encoding="utf-8")) >= 200, "postmortem.md must be at least 200 characters"

# 8. Containment Verification
def test_containment_json():
    cont_path = REPO_ROOT / "reports" / "containment.json"
    assert cont_path.exists(), "reports/containment.json must exist"
    
    with open(cont_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data.get("attack") in ["prompt_injection_exfil", "destructive_command", "suspicious_package"]
    assert data.get("blocked") is True
    assert data.get("host_untouched") is True
    
    ev_paths = data.get("evidence_paths", [])
    assert len(ev_paths) >= 1
    for p in ev_paths:
        full_p = REPO_ROOT / p
        assert full_p.exists(), f"Evidence path does not exist: {p}"

# 9. Failure Policy Verification
def test_failure_policy_and_trace():
    fp_path = REPO_ROOT / "reports" / "failure_policy.json"
    assert fp_path.exists(), "reports/failure_policy.json must exist"
    
    with open(fp_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data.get("failed_step") == 7
    assert data.get("total_steps") == 10
    policy = data.get("policy")
    assert policy in ["resume", "rollback", "fresh"]
    assert len(data.get("rationale", "")) >= 200
    
    trace_path = REPO_ROOT / data.get("trace_path", "")
    assert trace_path.exists(), "Trace path does not exist"
    
    trace_lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    has_policy_applied = any(t.get("event") == "policy_applied" and t.get("policy") == policy for t in trace_lines)
    assert has_policy_applied, f"Trace does not contain policy_applied event with policy '{policy}'"

# 10. Concurrency Verification
def test_concurrency_json():
    conc_path = REPO_ROOT / "reports" / "concurrency.json"
    assert conc_path.exists(), "reports/concurrency.json must exist"
    
    with open(conc_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    jobs = data.get("jobs", [])
    assert len(jobs) >= 5, "concurrency.json must have at least 5 jobs"
    
    seen_names = set()
    for job in jobs:
        sbx = job.get("sandbox_name")
        assert SANDBOX_REGEX.match(sbx), f"Invalid sandbox_name: {sbx}"
        assert sbx not in seen_names, f"Duplicate job sandbox_name: {sbx}"
        seen_names.add(sbx)
        assert job.get("started_at"), "started_at must be non-empty"
        
    assert len(data.get("breakage_notes", "")) >= 40, "breakage_notes must be at least 40 characters"

# 11. Run Ledger API Verification
def test_api_endpoints(client):
    # GET /health
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    
    # GET /api/runs (includes sbx-seeddemo1)
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert any(r.get("sandbox_name") == "sbx-seeddemo1" for r in runs), "Expected sbx-seeddemo1 in runs"
    
    # POST /api/runs valid
    valid_payload = {
        "run_id": "run-test-099",
        "sandbox_name": "sbx-apitest001",
        "problem_id": "issue-123",
        "state": "running",
        "execution_target": "celesto_sandbox"
    }
    resp = client.post("/api/runs", json=valid_payload)
    assert resp.status_code == 201
    stored = resp.json()
    assert stored["sandbox_name"] == "sbx-apitest001"
    
    # POST /api/runs invalid execution_target -> 400
    bad_target = {
        "run_id": "run-test-bad-target",
        "sandbox_name": "sbx-badtarget01",
        "problem_id": "issue-123",
        "state": "running",
        "execution_target": "host"
    }
    resp = client.post("/api/runs", json=bad_target)
    assert resp.status_code == 400, f"Expected 400 for bad execution_target, got {resp.status_code}"
    
    # POST /api/runs invalid state -> 400
    bad_state = {
        "run_id": "run-test-bad-state",
        "sandbox_name": "sbx-badstate01",
        "problem_id": "issue-123",
        "state": "unknown_state",
        "execution_target": "celesto_sandbox"
    }
    resp = client.post("/api/runs", json=bad_state)
    assert resp.status_code == 400, f"Expected 400 for bad state, got {resp.status_code}"
    
    # POST /api/runs invalid sandbox_name -> 400
    bad_sbx = {
        "run_id": "run-test-bad-sbx",
        "sandbox_name": "invalid_name",
        "problem_id": "issue-123",
        "state": "running",
        "execution_target": "celesto_sandbox"
    }
    resp = client.post("/api/runs", json=bad_sbx)
    assert resp.status_code == 400, f"Expected 400 for bad sandbox_name, got {resp.status_code}"

# 12. README Required Phrases Verification
def test_readme_phrases():
    readme_path = REPO_ROOT / "README.md"
    assert readme_path.exists(), "README.md must exist at repo root"
    
    text = readme_path.read_text(encoding="utf-8")
    required_phrases = [
        "Problem statement",
        "How I used Celesto",
        "Eval report",
        "Containment test",
        "State and failure design",
        "Setup"
    ]
    for phrase in required_phrases:
        assert phrase in text, f"README.md missing required phrase: '{phrase}'"

# 13. Walkthrough Video & Seed SQL Verification
def test_artifacts_exist():
    video_path = REPO_ROOT / "demo" / "walkthrough.mp4"
    assert video_path.exists(), "demo/walkthrough.mp4 must exist"
    assert video_path.stat().st_size > 1000, "walkthrough.mp4 must not be empty"
    
    seed_sql = REPO_ROOT / "seeds" / "01_runs.sql"
    assert seed_sql.exists(), "seeds/01_runs.sql must exist"
    sql_text = seed_sql.read_text(encoding="utf-8")
    assert "sbx-seeddemo1" in sql_text
    assert "deleted" in sql_text
    assert "celesto_sandbox" in sql_text
