"""Clarification workflows, brief review auditing, and instruction lifecycle management."""
import json
import secrets
from fastapi import HTTPException

from . import db

def create_clarification(patient_id: str, brief_id: str | None, question: str, originating_uncertainty_id: str | None, user: dict) -> dict:
    q = question.strip()
    if len(q) < 3:
        raise HTTPException(422, "Clarification question must be at least 3 characters.")
    cid = secrets.token_hex(12)
    mid = secrets.token_hex(12)
    now_ts = db.now()

    with db.connection() as con:
        intake = con.one("intakes", {"patient_id": patient_id}, sort=[("created_at", -1)])
        con.insert("clarifications", {
            "id": cid,
            "patient_id": patient_id,
            "intake_id": intake["id"] if intake else None,
            "brief_id": brief_id,
            "question": q,
            "originating_uncertainty_id": originating_uncertainty_id,
            "creator_id": user["id"],
            "creator_name": user["name"],
            "assigned_owner": "clinician" if user["role"] == "patient" else "patient",
            "status": "open",
            "resolution_reason": None,
            "created_at": now_ts,
            "resolved_at": None,
            "resolved_by": None,
        })
        con.insert("clarification_messages", {
            "id": mid,
            "clarification_id": cid,
            "author_id": user["id"],
            "author_name": user["name"],
            "role": user["role"],
            "text": q,
            "created_at": now_ts,
        })
        db.audit(con, patient_id, user["name"], "Clarification requested", q[:100])

    return {"id": cid, "status": "open", "question": q, "created_at": now_ts}


def add_clarification_message(clarification_id: str, text: str, user: dict) -> dict:
    msg_text = text.strip()
    if len(msg_text) < 1:
        raise HTTPException(422, "Message cannot be empty.")
    mid = secrets.token_hex(12)
    now_ts = db.now()

    with db.connection() as con:
        clar = con.one("clarifications", {"id": clarification_id})
        if not clar:
            raise HTTPException(404, "Clarification not found.")
        if clar['status'] == 'resolved':
            raise HTTPException(409, 'This conversation is resolved. Start a new question.')
        con.insert("clarification_messages", {
            "id": mid,
            "clarification_id": clarification_id,
            "author_id": user["id"],
            "author_name": user["name"],
            "role": user["role"],
            "text": msg_text,
            "created_at": now_ts,
        })
        db.audit(con, clar["patient_id"], user["name"], "Clarification response", msg_text[:100])

    return {"id": mid, "clarification_id": clarification_id, "text": msg_text, "created_at": now_ts}


def resolve_clarification(clarification_id: str, reason: str, user: dict) -> dict:
    if user["role"] != "clinician":
        raise HTTPException(403, "Only clinicians can resolve clarifications.")
    res_reason = reason.strip()
    if len(res_reason) < 3:
        raise HTTPException(422, "Please provide a meaningful resolution reason.")
    now_ts = db.now()

    with db.connection() as con:
        clar = con.one("clarifications", {"id": clarification_id})
        if not clar:
            raise HTTPException(404, "Clarification not found.")
        con.update("clarifications", {"id": clarification_id}, {
            "status": "resolved",
            "resolution_reason": res_reason,
            "resolved_at": now_ts,
            "resolved_by": user["name"],
        })
        db.audit(con, clar["patient_id"], user["name"], "Clarification resolved", res_reason[:100])

    return {"ok": True, "id": clarification_id, "status": "resolved", "resolved_at": now_ts}


def get_patient_clarifications(patient_id: str, intake_id: str | None = None) -> list[dict]:
    with db.connection() as con:
        rows = con.find("clarifications", {"patient_id": patient_id}, sort=[("created_at", -1)])
        intake = con.one("intakes", {"patient_id": patient_id}, sort=[("created_at", -1)])
        current_id = intake_id if intake_id is not None else (intake["id"] if intake else None)
        result = []
        for r in rows:
            if r.get("intake_id") != current_id:
                continue
            msgs = con.find("clarification_messages", {"clarification_id": r["id"]}, sort=[("created_at", 1)])
            result.append({**dict(r), "messages": [dict(m) for m in msgs]})
        return result


def append_brief_review(
    brief_id: str,
    status: str,
    note: str,
    expected_source_revision: str | None,
    reviewed_uncertainties: list[str] | None,
    user: dict
) -> dict:
    now_ts = db.now()
    review_id = secrets.token_hex(12)

    with db.connection() as con:
        row = con.one("briefs", {"id": brief_id})
        if not row:
            raise HTTPException(404, "Brief not found.")
        patient_id = row["patient_id"]
        latest = con.one("briefs", {"patient_id": patient_id}, sort=[("created_at", -1)])
        if row["status"] == "outdated" or not latest or latest["id"] != brief_id:
            raise HTTPException(409, "This brief is outdated. Prepare a new one before reviewing.")

        current_rev = con.clinical_revision(patient_id)
        if expected_source_revision and expected_source_revision != current_rev:
            con.update("briefs", {"id": brief_id}, {"status": "outdated"})
            raise HTTPException(409, "The patient clinical records changed since this review was prepared. Refresh before reviewing.")

        content = json.loads(row["content"])
        content["note"] = note
        con.update("briefs", {"id": brief_id}, {
            "content": json.dumps(content),
            "status": status,
            "reviewed_by": user["name"],
            "reviewed_at": now_ts,
        })

        con.insert("brief_reviews", {
            "id": review_id,
            "brief_id": brief_id,
            "expected_source_revision": current_rev,
            "reviewer_id": user["id"],
            "reviewer_name": user["name"],
            "outcome": status,
            "note": note,
            "reviewed_uncertainties": json.dumps(reviewed_uncertainties or []),
            "created_at": now_ts,
        })
        db.audit(con, patient_id, user["name"], f"Brief {status}", note)

    return {"ok": True, "review_id": review_id, "status": status}


def publish_patient_instruction(
    patient_id: str,
    original: str,
    plain: str,
    language: str,
    translated: str = "",
    content_language: str | None = None,
    confirmed: bool = False,
    user: dict | None = None,
    override_reason: str | None = None,
    previous_version_id: str | None = None,
    status: str = "published"
) -> dict:
    if not user:
        raise HTTPException(401, "Authentication required.")
    if not confirmed:
        raise HTTPException(422, "Please confirm that you reviewed these instructions.")
    orig = original.strip()
    pl = plain.strip()
    if len(orig) < 10 or len(pl) < 10:
        raise HTTPException(422, "Instruction versions must contain meaningful text (at least 10 characters).")

    with db.connection() as con:
        version = 1
        prev_to_supersede = None
        if previous_version_id:
            prev = con.one("instructions", {"id": previous_version_id})
            if not prev:
                raise HTTPException(404, "Previous instruction version not found.")
            if prev["patient_id"] != patient_id:
                raise HTTPException(403, "Cannot supersede an instruction belonging to another patient.")
            if prev.get("status") == "superseded":
                raise HTTPException(409, "This instruction version has already been superseded by another revision. Please refresh.")
            if prev.get("status") not in ("published", "draft"):
                raise HTTPException(422, f"Cannot supersede an instruction with status '{prev.get('status')}'.")
            version = (prev.get("version") or 1) + 1
            if status == "published":
                prev_to_supersede = previous_version_id

        # Check publication policy:
        # Current brief must be approved and all open clarifications resolved, or require explicit override reason
        latest_brief = con.one("briefs", {"patient_id": patient_id}, sort=[("created_at", -1)])
        open_clarifications = con.find("clarifications", {"patient_id": patient_id, "status": "open"})

        brief_approved = latest_brief and latest_brief["status"] == "approved"
        has_open_clarifications = len(open_clarifications) > 0
        clean_override = (override_reason or "").strip()

        if latest_brief is not None:
            if (not brief_approved or has_open_clarifications) and len(clean_override) < 5:
                reason_msg = "Current visit brief must be approved and all clarifications resolved before publishing instructions."
                if not brief_approved:
                    reason_msg = f"Visit brief is {latest_brief['status']}. An approved brief is required to publish instructions."
                elif has_open_clarifications:
                    reason_msg = f"There are {len(open_clarifications)} unresolved clarification question(s)."
                raise HTTPException(422, f"{reason_msg} Otherwise, provide an explicit clinician override reason (at least 5 characters).")
        else:
            if len(clean_override) < 5:
                raise HTTPException(422, "Please provide an explicit clinician override reason (at least 5 characters) when authoring instructions without an approved visit brief.")

        if prev_to_supersede:
            con.update("instructions", {"id": prev_to_supersede}, {"status": "superseded"})

        iid = secrets.token_hex(12)
        now_ts = db.now()
        clinical_rev = con.clinical_revision(patient_id)

        con.insert("instructions", {
            "id": iid,
            "patient_id": patient_id,
            "original": orig,
            "plain": pl,
            "translated": (translated or "").strip(),
            "language": language,
            "author": user["name"],
            "created_at": now_ts,
            "brief_id": latest_brief["id"] if latest_brief else None,
            "source_revision": clinical_rev,
            "reviewer_id": user["id"],
            "reviewer_name": user["name"],
            "status": status,
            "withdrawal_reason": None,
            "version": version,
            "previous_version_id": previous_version_id,
            "content_language": content_language or language,
            "reviewed_at": now_ts,
            "acknowledged_at": None,
            "acknowledgement_status": None,
            "override_reason": clean_override if clean_override else None,
        })
        db.audit(con, patient_id, user["name"], f"Instructions {status}", f"v{version}: {pl[:100]}")

    return {
        "id": iid,
        "version": version,
        "status": status,
        "created_at": now_ts,
        "source_revision": clinical_rev
    }


def withdraw_instruction(instruction_id: str, reason: str, user: dict) -> dict:
    if user["role"] != "clinician":
        raise HTTPException(403, "Only clinicians can withdraw instructions.")
    clean_reason = reason.strip()
    if len(clean_reason) < 3:
        raise HTTPException(422, "Please provide a reason for withdrawal.")

    with db.connection() as con:
        inst = con.one("instructions", {"id": instruction_id})
        if not inst:
            raise HTTPException(404, "Instruction not found.")
        assigned = con.one("assignments", {"clinician_id": user["id"], "patient_id": inst["patient_id"]})
        if not assigned:
            raise HTTPException(403, "You are not assigned to this patient.")
        con.update("instructions", {"id": instruction_id}, {
            "status": "withdrawn",
            "withdrawal_reason": clean_reason,
        })
        db.audit(con, inst["patient_id"], user["name"], "Instruction withdrawn", clean_reason[:100])

    return {"ok": True, "id": instruction_id, "status": "withdrawn"}


def acknowledge_instruction(instruction_id: str, status: str, user: dict, question: str | None = None) -> dict:
    if status not in ("acknowledged", "needs_clarification"):
        raise HTTPException(422, "Status must be 'acknowledged' or 'needs_clarification'.")

    now_ts = db.now()
    with db.connection() as con:
        inst = con.one("instructions", {"id": instruction_id})
        if not inst:
            raise HTTPException(404, "Instruction not found.")
        if inst["patient_id"] != user["id"]:
            raise HTTPException(403, "You can only acknowledge your own instructions.")
        if inst.get("status") != "published":
            raise HTTPException(422, f"Cannot acknowledge instruction with status '{inst.get('status')}'. Only published instructions can be acknowledged.")

        con.update("instructions", {"id": instruction_id}, {
            "acknowledged_at": now_ts,
            "acknowledgement_status": status,
        })
        db.audit(con, inst["patient_id"], user["name"], f"Instruction {status}", f"v{inst.get('version', 1)}")

        # If patient needs clarification, create actionable clarification thread assigned to clinician
        clarification_id = None
        if status == "needs_clarification":
            clarification_id = secrets.token_hex(12)
            mid = secrets.token_hex(12)
            q_text = (question or "").strip() or f"Patient requested clarification on instructions v{inst.get('version', 1)}: {inst.get('plain', '')[:100]}"
            con.insert("clarifications", {
                "id": clarification_id,
                "patient_id": inst["patient_id"],
                "brief_id": inst.get("brief_id"),
                "question": q_text,
                "originating_uncertainty_id": f"instruction-v{inst.get('version', 1)}",
                "creator_id": user["id"],
                "creator_name": user["name"],
                "assigned_owner": "clinician",
                "status": "open",
                "resolution_reason": None,
                "created_at": now_ts,
                "resolved_at": None,
                "resolved_by": None,
            })
            con.insert("clarification_messages", {
                "id": mid,
                "clarification_id": clarification_id,
                "author_id": user["id"],
                "author_name": user["name"],
                "role": user["role"],
                "text": q_text,
                "created_at": now_ts,
            })
            db.audit(con, inst["patient_id"], user["name"], "Clarification requested", q_text[:100])

    return {"ok": True, "id": instruction_id, "status": status, "acknowledged_at": now_ts, "clarification_id": clarification_id}
