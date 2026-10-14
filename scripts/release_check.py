"""Conservative submission preflight.

Evaluates evidence-backed gates and reports status as passed, failed,
missing, or requires_human_evidence.
"""
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]

gates = {}

# Local repository files and configurations
def check_file(rel_path: str, key: str):
    p = root / rel_path
    gates[key] = "passed" if p.is_file() else "missing"

check_file("submission/PROJECT_DESCRIPTION.md", "submission_description")
check_file("submission/PITCH_SCRIPT.md", "pitch_script")
check_file("LICENSE", "license")
check_file(".github/workflows/ci.yml", "continuous_integration")

# Model benchmark evidence
evidence_file = root / "submission/model-evidence.json"
if evidence_file.is_file():
    gates["model_benchmark_recorded"] = "passed"
else:
    gates["model_benchmark_recorded"] = "requires_human_evidence"

# Docker engine availability
try:
    result = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        timeout=5,
        cwd=root,
    )
    gates["docker_engine_available"] = "passed" if result.returncode == 0 else "requires_human_evidence"
except (FileNotFoundError, subprocess.TimeoutExpired):
    gates["docker_engine_available"] = "requires_human_evidence"

# External human-in-the-loop verification gates
external_gates = {
    "amd_hosted_inference_logs": "requires_human_evidence",
    "organizer_approval_and_cutoff": "requires_human_evidence",
    "published_repo_and_demo_url": "requires_human_evidence",
    "final_pitch_deck_and_recording": "requires_human_evidence",
}

# Core local readiness requires all local files to be present
local_required = [
    "submission_description",
    "pitch_script",
    "license",
    "continuous_integration",
]
local_ready = all(gates.get(k) == "passed" for k in local_required)

report = {
    "local_gates": gates,
    "external_gates": external_gates,
    "local_ready": local_ready,
    "submission_ready": local_ready and all(v == "passed" for v in gates.values()) and all(v == "passed" for v in external_gates.values()),
    "summary": "Local submission files ready. External evidence and recordings require human execution.",
}

print(json.dumps(report, indent=2))
sys.exit(0 if local_ready else 1)
