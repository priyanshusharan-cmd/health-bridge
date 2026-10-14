import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app import db
from app.main import app
from app.demo_config import DEMO_PASSWORD
from scripts.reset_demo import reset_demo

def test_record_deletion_and_invalidation(tmp_path, monkeypatch):
    test_db = tmp_path / "test_b4_records.db"
    monkeypatch.setattr(db, "DATA", tmp_path)
    monkeypatch.setattr(db, "backend", lambda: "sqlite")
    
    # Initialize DB
    with db.connection() as con:
        db.initialize_sqlite()
        pw = db.password_hash(DEMO_PASSWORD)
        con.insert("users", {"id": "p1", "name": "Pat", "email": "pat@test.local", "password": pw, "role": "patient", "language": "en"})
        con.insert("users", {"id": "d1", "name": "Doc", "email": "doc@test.local", "password": pw, "role": "clinician", "language": "en"})
        con.insert("assignments", {"clinician_id": "d1", "patient_id": "p1"})
        con.insert("records", {
            "id": "r1", "patient_id": "p1", "title": "Test Rec", "kind": "Note", "date": "2026-10-01",
            "provider": "Clinic", "text": "Some text", "filename": None, "media_type": "text/plain",
            "created_at": db.now(), "status": "active", "deleted_at": None
        })
        con.insert("briefs", {
            "id": "b1", "patient_id": "p1", "content": json.dumps({"note": "brief note", "evidence": []}),
            "status": "approved", "engine": "source_only", "created_at": db.now(), "reviewed_by": "Doc", "reviewed_at": db.now()
        })

    client = TestClient(app)
    # Login as patient
    client.post("/api/auth/login", json={"email": "pat@test.local", "password": DEMO_PASSWORD})
    
    # Check record is in workspace
    resp = client.get("/api/patients/p1/workspace")
    assert resp.status_code == 200
    assert any(r["id"] == "r1" for r in resp.json()["records"])
    assert resp.json()["brief"]["status"] == "approved"

    # Delete record
    del_resp = client.delete("/api/records/r1")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "withdrawn"

    # Workspace should no longer have r1, and brief should be marked outdated
    resp2 = client.get("/api/patients/p1/workspace")
    assert resp2.status_code == 200
    assert not any(r["id"] == "r1" for r in resp2.json()["records"])
    assert resp2.json()["brief"]["status"] == "outdated"

    # Direct fetch of withdrawn record returns 404
    assert client.get("/api/records/r1").status_code == 404
    assert client.get("/api/records/r1/file").status_code == 404

    # Check audit log for removal
    with db.connection() as con:
        aud = con.find("audit", {"patient_id": "p1", "action": "Record removed"})
        assert len(aud) >= 1

def test_patient_export(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA", tmp_path)
    monkeypatch.setattr(db, "backend", lambda: "sqlite")
    
    with db.connection() as con:
        db.initialize_sqlite()
        pw = db.password_hash(DEMO_PASSWORD)
        con.insert("users", {"id": "pat_exp", "name": "Export Patient", "email": "export@test.local", "password": pw, "role": "patient", "language": "en"})

    client = TestClient(app)
    client.post("/api/auth/login", json={"email": "export@test.local", "password": DEMO_PASSWORD})
    
    exp_resp = client.get("/api/patients/pat_exp/export")
    assert exp_resp.status_code == 200
    data = exp_resp.json()
    assert data["patient"]["id"] == "pat_exp"
    assert "provenance_notice" in data
    assert "records" in data
    assert "exported_at" in data

def test_invitation_revocation_and_assignment_unlink(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA", tmp_path)
    monkeypatch.setattr(db, "backend", lambda: "sqlite")
    
    with db.connection() as con:
        db.initialize_sqlite()
        pw = db.password_hash(DEMO_PASSWORD)
        con.insert("users", {"id": "doc_u", "name": "Dr. Unlink", "email": "docu@test.local", "password": pw, "role": "clinician", "language": "en"})
        con.insert("users", {"id": "pat_u", "name": "Pat Unlink", "email": "patu@test.local", "password": pw, "role": "patient", "language": "en"})
        con.insert("organizations", {"id": "org_u", "name": "Test Clinic", "created_at": db.now()})
        con.insert("memberships", {"id": "m1", "user_id": "doc_u", "organization_id": "org_u"})
        con.insert("assignments", {"clinician_id": "doc_u", "patient_id": "pat_u"})

    client = TestClient(app)
    # Login as clinician
    client.post("/api/auth/login", json={"email": "docu@test.local", "password": DEMO_PASSWORD})
    
    # Clinician creates invitation
    inv_resp = client.post("/api/hospital/invitations", json={"email": "somepatient@test.local"})
    assert inv_resp.status_code == 200
    
    # Clinician lists invitations
    list_resp = client.get("/api/hospital/invitations")
    assert list_resp.status_code == 200
    invitations = list_resp.json()
    assert len(invitations) == 1
    inv_id = invitations[0]["id"]
    
    # Clinician revokes invitation
    rev_resp = client.delete(f"/api/hospital/invitations/{inv_id}")
    assert rev_resp.status_code == 200
    assert rev_resp.json()["revoked"] is True
    
    # Listing again should be empty
    assert len(client.get("/api/hospital/invitations").json()) == 0

    # Clinician currently has access to patient
    assert client.get("/api/patients/pat_u/workspace").status_code == 200

    # Clinician unlinks patient
    unlink_resp = client.post("/api/hospital/assignments/pat_u/unlink")
    assert unlink_resp.status_code == 200
    assert unlink_resp.json()["unlinked"] is True

    # Future access by clinician is blocked with 403
    assert client.get("/api/patients/pat_u/workspace").status_code == 403

    # Patient data remains intact when patient logs in
    client.post("/api/auth/login", json={"email": "patu@test.local", "password": DEMO_PASSWORD})
    pat_ws = client.get("/api/patients/pat_u/workspace")
    assert pat_ws.status_code == 200
    assert pat_ws.json()["patient"]["id"] == "pat_u"

def test_safe_demo_reset_refuses_ordinary_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA", tmp_path)
    monkeypatch.setattr(db, "backend", lambda: "sqlite")
    
    # Calling reset_demo without target or env raises SystemExit
    with pytest.raises(SystemExit):
        reset_demo(target_name="ordinary-db")
    
    # Calling reset_demo with target="synthetic-demo" succeeds
    reset_demo(target_name="synthetic-demo", scenario_date="2026-10-14")
    
    with db.connection() as con:
        asha = con.one("users", {"id": "patient-asha"})
        assert asha is not None
        recs = con.find("records", {"patient_id": "patient-asha"})
        assert len(recs) == 4
