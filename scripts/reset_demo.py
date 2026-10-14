#!/usr/bin/env python3
"""Safe disposable-demo reset utility.

Refuses to run against the ordinary configured application database.
Requires an explicit disposable target path/name containing 'synthetic' or 'disposable'.
"""
import argparse
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_dir))

def reset_demo(target_dir: str | None = None, target_db: str | None = None, scenario_date: str = "2026-10-14", confirm: bool = False) -> None:
    default_dir = (backend_dir / "data").resolve()
    is_mongo = bool(os.getenv("MONGODB_URI"))

    resolved_dir: Path | None = None
    if is_mongo:
        db_name = (target_db or os.getenv("MONGODB_DATABASE", "")).strip()
        if not db_name or db_name == "healthbridge" or ("synthetic" not in db_name.lower() and "disposable" not in db_name.lower()):
            print(
                f"ERROR: Refusing reset. Target database '{db_name}' is not an allowed disposable target.\n"
                "Target must be explicitly specified and must contain 'synthetic' or 'disposable'.",
                file=sys.stderr
            )
            sys.exit(1)
        os.environ["MONGODB_DATABASE"] = db_name
        target_display = f"MongoDB database '{db_name}'"
    else:
        candidate_dir = target_dir or os.getenv("DATA_DIR", "")
        resolved_dir = Path(candidate_dir).resolve() if candidate_dir else None
        if not resolved_dir or resolved_dir == default_dir or ("synthetic" not in str(resolved_dir).lower() and "disposable" not in str(resolved_dir).lower()):
            print(
                f"ERROR: Refusing demo reset on ordinary database ({resolved_dir or default_dir}).\n"
                "Reset is strictly restricted to dedicated disposable targets containing 'synthetic' or 'disposable' in their directory path.\n"
                "Example: reset_demo.py --target-dir backend/data/synthetic-demo --confirm",
                file=sys.stderr
            )
            sys.exit(1)
        if not confirm:
            print("ERROR: Re-run with --confirm to verify wipe and re-seed of the designated disposable target.", file=sys.stderr)
            sys.exit(1)
        resolved_dir.mkdir(parents=True, exist_ok=True)
        os.environ["DATA_DIR"] = str(resolved_dir)
        target_display = f"SQLite directory '{resolved_dir}'"

    os.environ["SCENARIO_DATE"] = scenario_date
    os.environ["DEMO_ENABLED"] = "true"

    print(f"Target validated: {target_display}. Initializing...")

    from app import db
    from app.demo_config import DEMO_PASSWORD

    if not is_mongo and resolved_dir is not None:
        db.DATA = resolved_dir
    db.initialize()

    # Wipe tables in current connection
    with db.connection() as con:
        raw_con = getattr(con, "raw", None)
        if raw_con is not None:
            raw_con.execute("PRAGMA foreign_keys = OFF")
        # Delete demo data
        for table in [
            "clarification_messages",
            "clarifications",
            "brief_reviews",
            "instructions",
            "briefs",
            "intakes",
            "record_corrections",
            "record_extractions",
            "upload_jobs",
            "records",
            "appointments",
            "assignments",
            "sessions",
            "memberships",
            "invitations",
            "organizations",
            "audit",
            "files",
            "users",
        ]:
            con.delete(table, {})
        if raw_con is not None:
            raw_con.execute("PRAGMA foreign_keys = ON")

        # Re-seed synthetic demo users and fixtures
        pw = db.password_hash(DEMO_PASSWORD)
        con.insert_rows("users", [
            ("patient-asha", "Asha Rao", "patient@healthbridge.demo", pw, "patient", "en", 34, "AR"),
            ("patient-kabir", "Kabir Mehta", "kabir@healthbridge.demo", pw, "patient", "hi", 42, "KM"),
            ("doctor-meera", "Dr. Meera Shah", "doctor@healthbridge.demo", pw, "clinician", "en", None, "MS"),
        ])
        con.insert_rows("assignments", [
            ("doctor-meera", "patient-asha"),
            ("doctor-meera", "patient-kabir"),
        ])
        con.insert_rows("appointments", [
            ("appt-asha", "patient-asha", "Dr. Meera Shah", "General medicine", "Greenleaf Clinic · Room 204", f"{scenario_date}T10:30:00+05:30"),
            ("appt-kabir", "patient-kabir", "Dr. Meera Shah", "General medicine", "Greenleaf Clinic · Room 204", f"{scenario_date}T11:00:00+05:30"),
        ])
        fixtures = [
            ("rec-1", "Follow-up visit note", "Visit note", "2026-09-28", "Greenleaf Clinic",
             f"SYNTHETIC DEMO DATA\nDate: 2026-09-28\nProvider: Greenleaf Clinic\nVisit note\nPatient reported feeling tired over the past two weeks. Patient will bring earlier reports to the next appointment. Follow-up appointment: {scenario_date}. Medication information was not recorded in this note."),
            ("rec-2", "Complete blood count", "Lab report", "2026-09-24", "City Diagnostics",
             "SYNTHETIC DEMO DATA\nDate: 2026-09-24\nProvider: City Diagnostics\nLab report: Complete blood count\nSample collected 24 September 2026. Report supplied for clinician review. This demonstration intentionally omits numerical results and medical interpretation."),
            ("rec-3", "Referral to general medicine", "Referral", "2026-09-18", "Lakeside Health Centre",
             "SYNTHETIC DEMO DATA\nDate: 2026-09-18\nProvider: Lakeside Health Centre\nReferral\nPlease arrange a general medicine appointment. Patient reports fatigue. Previous records should be available for the receiving clinician. No new treatment instructions are included."),
            ("rec-4", "Previous consultation", "Visit note", "2026-08-12", "Greenleaf Clinic",
             "SYNTHETIC DEMO DATA\nDate: 2026-08-12\nProvider: Greenleaf Clinic\nVisit note\nRoutine consultation. Patient-reported allergy information needs confirmation at the next visit. No medication list was provided."),
        ]
        for rid, title, kind, dt, provider, body in fixtures:
            con.insert_row("records", (rid, "patient-asha", title, kind, dt, provider, body, None, "text/plain", db.now(), "active", None))

        con.insert_row("intakes", (
            "intake-asha", "patient-asha",
            "I have been feeling more tired than usual. I would like to discuss my recent blood report.",
            "About two weeks", "Not provided",
            "Penicillin — patient reported, needs confirmation",
            "What should I bring to my follow-up? Could you explain my recent report?",
            "en", db.now()
        ))
        con.insert_row("instructions", (
            "instruction-asha", "patient-asha",
            f"Please bring your previous reports to the follow-up appointment on {scenario_date}. Write down the questions you would like to discuss.",
            f"Bring your earlier reports on {scenario_date}. Write down your questions before the visit.",
            f"{scenario_date} की अगली मुलाकात में अपनी पिछली रिपोर्ट साथ लाएँ। जिन सवालों पर बात करनी है, उन्हें लिख लें।",
            "hi", "Dr. Meera Shah (synthetic fixture)", db.now()
        ))
        db.audit(con, "patient-asha", "HealthBridge", "Demo reset", f"Synthetic records reset for {target_display}. Scenario date: {scenario_date}.")

    print(f"SUCCESS: Reset disposable demo database at {target_display} with scenario date {scenario_date}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset disposable HealthBridge demonstration database.")
    parser.add_argument("--target-dir", default="", help="Target disposable SQLite directory (must contain 'synthetic' or 'disposable')")
    parser.add_argument("--target-db", default="", help="Target disposable MongoDB name (must contain 'synthetic' or 'disposable')")
    parser.add_argument("--confirm", action="store_true", help="Confirm execution on designated disposable target")
    parser.add_argument("--scenario-date", default="2026-10-14", help="Scenario anchor date (YYYY-MM-DD)")
    args = parser.parse_args()
    reset_demo(target_dir=args.target_dir, target_db=args.target_db, scenario_date=args.scenario_date, confirm=args.confirm)
