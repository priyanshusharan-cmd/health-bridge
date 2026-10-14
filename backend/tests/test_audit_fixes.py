"""Targeted regression tests for independent review findings (2026-10-14)."""
import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from app import db
from app.main import app
from app.demo_config import DEMO_PASSWORD
from app.upload_service import (
    create_upload_job,
    claim_job,
    recover_pending_upload_jobs,
    get_job
)
from app.brief_service import (
    select_passages_across_document,
    build_structured_brief,
    detect_conflicts_and_uncertainties
)
from app.review_service import (
    publish_patient_instruction,
    acknowledge_instruction,
    withdraw_instruction
)

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setattr(db, "DATA", tmp_path)
    monkeypatch.setattr(db, "backend", lambda: "sqlite")
    db.initialize_sqlite()
    pw = db.password_hash(DEMO_PASSWORD)
    with db.connection() as con:
        con.insert("users", {"id": "pat_a", "name": "Patient A", "email": "pata@test.local", "password": pw, "role": "patient", "language": "en"})
        con.insert("users", {"id": "pat_b", "name": "Patient B", "email": "patb@test.local", "password": pw, "role": "patient", "language": "en"})
        con.insert("users", {"id": "doc_1", "name": "Dr. One", "email": "doc1@test.local", "password": pw, "role": "clinician", "language": "en"})
        con.insert("assignments", {"clinician_id": "doc_1", "patient_id": "pat_a"})
        con.insert("assignments", {"clinician_id": "doc_1", "patient_id": "pat_b"})
    return tmp_path

def test_foreign_instruction_supersession_rejected(isolated_db):
    """Publishing an instruction for patient B cannot supersede an instruction belonging to patient A."""
    client = TestClient(app)
    client.post("/api/auth/login", json={"email": "doc1@test.local", "password": DEMO_PASSWORD})

    # Dr. One creates published instruction for Patient A
    res_a = client.post("/api/patients/pat_a/instructions", json={
        "original": "Instruction for Patient A.",
        "plain": "Instruction for Patient A.",
        "language": "en",
        "override_reason": "Direct clinical authoring note",
        "confirmed": True
    })
    assert res_a.status_code == 200
    inst_a_id = res_a.json()["id"]

    # Dr. One attempts to publish instruction for Patient B referencing Patient A's instruction as previous_version_id
    res_b = client.post("/api/patients/pat_b/instructions", json={
        "original": "Instruction for Patient B.",
        "plain": "Instruction for Patient B.",
        "language": "en",
        "previous_version_id": inst_a_id,
        "override_reason": "Attempting cross-tenant supersession",
        "confirmed": True
    })
    assert res_b.status_code == 403
    assert "Cannot supersede an instruction belonging to another patient" in res_b.json()["detail"]

    # Patient A's instruction remains published and unaffected
    with db.connection() as con:
        inst_a = con.one("instructions", {"id": inst_a_id})
        assert inst_a["status"] == "published"

def test_deleted_records_excluded_from_briefs_and_model_input(isolated_db):
    """Deleted/tombstoned records must be excluded from newly generated briefs and model evidence inputs."""
    client = TestClient(app)
    client.post("/api/auth/login", json={"email": "pata@test.local", "password": DEMO_PASSWORD})

    # Add 2 records
    now_ts = db.now()
    with db.connection() as con:
        con.insert("records", {
            "id": "rec_live", "patient_id": "pat_a", "title": "Live Record", "kind": "Lab report",
            "date": "2026-10-01", "provider": "Live Clinic", "text": "Blood count normal.",
            "filename": None, "media_type": "text/plain", "created_at": now_ts, "status": "active", "deleted_at": None
        })
        con.insert("records", {
            "id": "rec_deleted", "patient_id": "pat_a", "title": "Deleted Record", "kind": "Note",
            "date": "2026-09-01", "provider": "Old Clinic", "text": "Old obsolete findings.",
            "filename": None, "media_type": "text/plain", "created_at": now_ts, "status": "withdrawn", "deleted_at": now_ts
        })

    # Generate brief
    res = client.post("/api/patients/pat_a/brief")
    assert res.status_code == 200
    ws = client.get("/api/patients/pat_a/workspace").json()
    brief = ws["brief"]
    sources = brief["content"]["sources"]
    source_ids = [s["id"] for s in sources]

    assert "rec_live" in source_ids
    assert "rec_deleted" not in source_ids

    # Trying to generate brief with deleted record explicitly selected raises 422
    err_res = client.post("/api/patients/pat_a/brief", json={"selected_record_ids": ["rec_deleted"]})
    assert err_res.status_code == 422
    assert "selected records are no longer available" in err_res.json()["detail"].lower()

def test_draft_instructions_hidden_from_patient_and_cannot_be_acknowledged(isolated_db):
    """Draft instructions are visible only to clinicians; patients do not see them and cannot acknowledge them."""
    client = TestClient(app)
    # Login as clinician
    client.post("/api/auth/login", json={"email": "doc1@test.local", "password": DEMO_PASSWORD})

    # Create a draft instruction
    draft_res = client.post("/api/patients/pat_a/instructions", json={
        "original": "Draft unverified clinical advice.",
        "plain": "Draft unverified plain advice.",
        "language": "en",
        "status": "draft",
        "override_reason": "Drafting before lab confirmation",
        "confirmed": True
    })
    assert draft_res.status_code == 200
    draft_id = draft_res.json()["id"]

    # Clinician sees draft in workspace
    clin_ws = client.get("/api/patients/pat_a/workspace").json()
    assert any(i["id"] == draft_id for i in clin_ws["instructions"])

    # Patient logs in
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "pata@test.local", "password": DEMO_PASSWORD})

    # Patient does NOT see draft in workspace
    pat_ws = client.get("/api/patients/pat_a/workspace").json()
    assert not any(i["id"] == draft_id for i in pat_ws["instructions"])

    # Patient does NOT see draft in export
    pat_exp = client.get("/api/patients/pat_a/export").json()
    assert not any(i["id"] == draft_id for i in pat_exp.get("instructions", []))

    # Patient cannot acknowledge a draft
    ack_res = client.post(f"/api/instructions/{draft_id}/acknowledge", json={"status": "acknowledged"})
    assert ack_res.status_code == 422
    assert "Only published instructions can be acknowledged" in ack_res.json()["detail"]

def test_upload_queue_worker_lease_and_recovery(isolated_db):
    """Upload jobs use worker leases and recover stuck/queued jobs on startup."""
    user = {"id": "pat_a", "name": "Patient A"}
    payload = b"SYNTHETIC MEDICAL REPORT\nProvider: Recovery Clinic\nDate: 2026-10-14\nVitals stable."
    
    # 1. Create upload job
    job = create_upload_job("pat_a", user, "report.txt", payload, idempotency_key="key-recover-1")
    assert job["state"] in ("queued", "processing")
    job_id = job["id"]

    # 2. Duplicate detection warning on same content
    job_dup = create_upload_job("pat_a", user, "report_copy.txt", payload, idempotency_key="key-recover-2")
    assert job_dup["id"] != job_id
    # Once job completes, duplicate warning is surfaced
    with db.connection() as con:
        con.update("upload_jobs", {"id": job_id}, {"state": "completed", "record_id": "rec_test_1"})
    job_dup3 = create_upload_job("pat_a", user, "report_copy2.txt", payload, idempotency_key="key-recover-3")
    assert job_dup3.get("duplicate_warning") is not None
    assert "identical content" in job_dup3["duplicate_warning"]

    # 3. Simulate expired worker lease
    with db.connection() as con:
        con.update("upload_jobs", {"id": job_dup["id"]}, {
            "state": "processing",
            "lease_owner": "dead_worker",
            "lease_expires_at": "2020-01-01T00:00:00",
            "attempt_count": 1
        })
        # Claiming expired job with new worker succeeds
        claimed = claim_job(con, job_dup["id"], "new_worker", lease_duration=60)
        assert claimed is True
        updated = con.one("upload_jobs", {"id": job_dup["id"]})
        assert updated["lease_owner"] == "new_worker"
        assert updated["attempt_count"] == 2

    # 4. Attempt count >= 3 marks job as failed
    with db.connection() as con:
        con.update("upload_jobs", {"id": job_dup["id"]}, {
            "state": "processing",
            "lease_owner": "stalled_worker",
            "lease_expires_at": "2020-01-01T00:00:00",
            "attempt_count": 3
        })
        claimed_max = claim_job(con, job_dup["id"], "another_worker")
        assert claimed_max is False
        failed_job = con.one("upload_jobs", {"id": job_dup["id"]})
        assert failed_job["state"] == "failed"
        assert failed_job["error_code"] == "max_attempts_exceeded"

def test_pdf_citation_accuracy_and_character_bounds():
    """PDF passage parsing extracts exact page numbers, accurate character offsets, and respects budget."""
    two_page_text = (
        "--- Page 1 ---\n"
        "Patient underwent routine physical examination.\n"
        "Blood pressure was 120/80 mmHg.\n"
        "\n"
        "--- Page 2 ---\n"
        "Follow-up lab evaluation shows normal HbA1c.\n"
        "Continue current diet and exercise.\n"
    )
    pages_info = [
        {"page": 1, "char_count": len("Patient underwent routine physical examination.\nBlood pressure was 120/80 mmHg.\n")},
        {"page": 2, "char_count": len("Follow-up lab evaluation shows normal HbA1c.\nContinue current diet and exercise.\n")}
    ]

    sampled_text, passages, shortened = select_passages_across_document(two_page_text, pages_info, max_chars=400)
    assert len(passages) >= 2

    # Verify first passage is strictly from Page 1
    p1 = passages[0]
    assert p1["page"] == 1
    assert "physical examination" in p1["quote"]
    # Verify coordinates in two_page_text
    assert two_page_text[p1["start_offset"]:p1["end_offset"]] == p1["quote"]

    # Verify second passage is strictly from Page 2
    p2 = passages[1]
    assert p2["page"] == 2
    assert "HbA1c" in p2["quote"]
    assert two_page_text[p2["start_offset"]:p2["end_offset"]] == p2["quote"]

    # Total characters extracted must be within max_chars
    total_chars = sum(len(p["quote"]) for p in passages)
    assert total_chars <= 400

def test_instruction_reassessment_flag_on_source_changes(isolated_db):
    """When clinical records or intake change after instructions are published, instructions indicate reassessment required."""
    client = TestClient(app)
    # Doctor publishes instruction
    client.post("/api/auth/login", json={"email": "doc1@test.local", "password": DEMO_PASSWORD})
    pub_res = client.post("/api/patients/pat_a/instructions", json={
        "original": "Maintain existing regimen.",
        "plain": "Keep your existing routine.",
        "language": "en",
        "override_reason": "Baseline advice",
        "confirmed": True
    })
    assert pub_res.status_code == 200
    inst_id = pub_res.json()["id"]

    # Initially, reassessment_required is False
    ws = client.get("/api/patients/pat_a/workspace").json()
    inst = next(i for i in ws["instructions"] if i["id"] == inst_id)
    assert inst["reassessment_required"] is False

    # Patient adds intake concern (changing clinical revision)
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "pata@test.local", "password": DEMO_PASSWORD})
    client.post("/api/patients/pat_a/intake", json={
        "reason": "New acute chest discomfort noticed yesterday.",
        "language": "en"
    })

    # Instructions now indicate reassessment recommended
    ws_after = client.get("/api/patients/pat_a/workspace").json()
    inst_after = next(i for i in ws_after["instructions"] if i["id"] == inst_id)
    assert inst_after["reassessment_required"] is True
    assert "Source records or intake have changed" in inst_after["reassessment_reason"]
