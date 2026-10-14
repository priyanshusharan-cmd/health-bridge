"""Persistent storage with MongoDB deployment and SQLite local development."""
import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .demo_config import DEMO_PASSWORD

DATA = Path(os.getenv('DATA_DIR', str(Path(__file__).resolve().parents[1] / 'data')))
DATA.mkdir(parents=True, exist_ok=True)

def now():
    return datetime.now(timezone.utc).isoformat()

def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'{salt}:{digest}'

def verify_password(password: str, stored: str) -> bool:
    return secrets.compare_digest(password_hash(password, stored.split(':')[0]), stored)

def backend():
    return 'mongodb' if os.getenv('MONGODB_URI') else 'sqlite'

@contextmanager
def connection():
    from .store import MongoStore, SQLiteStore, mongo_client
    if backend() == 'mongodb':
        client = mongo_client()
        with client.start_session() as session:
            with session.start_transaction():
                yield MongoStore(client[os.getenv('MONGODB_DATABASE', 'healthbridge')], session)
    else:
        con = sqlite3.connect(DATA / 'healthbridge.db', timeout=15)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            con.execute('BEGIN')
            yield SQLiteStore(con)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

def audit(con, patient_id, actor, action, detail):
    con.add_audit(dict(patient_id=patient_id, actor=actor, action=action, detail=detail, created_at=now()))

def initialize():
    if backend() == 'mongodb':
        from .store import initialize_mongo
        initialize_mongo()
    else:
        initialize_sqlite()
    with connection() as con:
        if os.getenv('DEMO_ENABLED', 'true').lower() != 'true' or con.one('users'):
            return
        pw = password_hash(DEMO_PASSWORD)
        con.insert_rows('users', [
            ('patient-asha','Asha Rao','patient@healthbridge.demo',pw,'patient','en',34,'AR'),
            ('patient-kabir','Kabir Mehta','kabir@healthbridge.demo',pw,'patient','hi',42,'KM'),
            ('doctor-meera','Dr. Meera Shah','doctor@healthbridge.demo',pw,'clinician','en',None,'MS')])
        con.insert_rows('assignments', [('doctor-meera','patient-asha'),('doctor-meera','patient-kabir')])
        con.insert_rows('appointments',[
            ('appt-asha','patient-asha','Dr. Meera Shah','General medicine','Greenleaf Clinic · Room 204','2026-10-15T10:30:00+05:30'),
            ('appt-kabir','patient-kabir','Dr. Meera Shah','General medicine','Greenleaf Clinic · Room 204','2026-10-15T11:00:00+05:30')])
        fixtures = [
            ('rec-1','Follow-up visit note','Visit note','2026-09-28','Greenleaf Clinic','SYNTHETIC DEMO DATA\nDate: 2026-09-28\nProvider: Greenleaf Clinic\nVisit note\nPatient reported feeling tired over the past two weeks. Patient will bring earlier reports to the next appointment. Follow-up appointment: 15 October 2026. Medication information was not recorded in this note.'),
            ('rec-2','Complete blood count','Lab report','2026-09-24','City Diagnostics','SYNTHETIC DEMO DATA\nDate: 2026-09-24\nProvider: City Diagnostics\nLab report: Complete blood count\nSample collected 24 September 2026. Report supplied for clinician review. This demonstration intentionally omits numerical results and medical interpretation.'),
            ('rec-3','Referral to general medicine','Referral','2026-09-18','Lakeside Health Centre','SYNTHETIC DEMO DATA\nDate: 2026-09-18\nProvider: Lakeside Health Centre\nReferral\nPlease arrange a general medicine appointment. Patient reports fatigue. Previous records should be available for the receiving clinician. No new treatment instructions are included.'),
            ('rec-4','Previous consultation','Visit note','2026-08-12','Greenleaf Clinic','SYNTHETIC DEMO DATA\nDate: 2026-08-12\nProvider: Greenleaf Clinic\nVisit note\nRoutine consultation. Patient-reported allergy information needs confirmation at the next visit. No medication list was provided.')]
        for rid,title,kind,date,provider,body in fixtures:
            con.insert_row('records',(rid,'patient-asha',title,kind,date,provider,body,None,'text/plain',now()))
        con.insert_row('intakes',('intake-asha','patient-asha','I have been feeling more tired than usual. I would like to discuss my recent blood report.','About two weeks','Not provided','Penicillin — patient reported, needs confirmation','What should I bring to my follow-up? Could you explain my recent report?','en',now()))
        con.insert_row('instructions',('instruction-asha','patient-asha','Please bring your previous reports to the follow-up appointment on 15 October 2026. Write down the questions you would like to discuss.','Bring your earlier reports on 15 October 2026. Write down your questions before the visit.','15 अक्टूबर 2026 की अगली मुलाकात में अपनी पिछली रिपोर्ट साथ लाएँ। जिन सवालों पर बात करनी है, उन्हें लिख लें।','hi','Dr. Meera Shah (synthetic fixture)',now()))
        audit(con,'patient-asha','HealthBridge','Demo created','Synthetic records loaded. No real patient data.')


def initialize_sqlite():
    with sqlite3.connect(DATA / 'healthbridge.db') as raw:
        raw.executescript('''
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'en', age INTEGER, initials TEXT);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), expires REAL);
        CREATE TABLE IF NOT EXISTS assignments(clinician_id TEXT REFERENCES users(id), patient_id TEXT REFERENCES users(id), PRIMARY KEY(clinician_id,patient_id));
        CREATE TABLE IF NOT EXISTS appointments(id TEXT PRIMARY KEY, patient_id TEXT REFERENCES users(id), clinician TEXT, specialty TEXT, location TEXT, starts_at TEXT);
        CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, patient_id TEXT REFERENCES users(id), title TEXT, kind TEXT, date TEXT, provider TEXT, text TEXT, filename TEXT, media_type TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS intakes(id TEXT PRIMARY KEY, patient_id TEXT REFERENCES users(id), reason TEXT, duration TEXT, medications TEXT, allergies TEXT, questions TEXT, language TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS briefs(id TEXT PRIMARY KEY, patient_id TEXT REFERENCES users(id), content TEXT, status TEXT, engine TEXT, created_at TEXT, reviewed_by TEXT, reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS instructions(id TEXT PRIMARY KEY, patient_id TEXT REFERENCES users(id), original TEXT, plain TEXT, translated TEXT, language TEXT, author TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT REFERENCES users(id), actor TEXT, action TEXT, detail TEXT, created_at TEXT);
        ''')
        raw.executescript('''
        CREATE TABLE IF NOT EXISTS organizations(id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memberships(id TEXT PRIMARY KEY, user_id TEXT UNIQUE REFERENCES users(id), organization_id TEXT REFERENCES organizations(id));
        CREATE TABLE IF NOT EXISTS invitations(id TEXT PRIMARY KEY, token TEXT UNIQUE NOT NULL, organization_id TEXT REFERENCES organizations(id), clinician_id TEXT REFERENCES users(id), email TEXT NOT NULL, expires REAL NOT NULL, accepted_by TEXT);
        ''')
        raw.execute('CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY, data BLOB NOT NULL)')
        raw.executescript('''
        CREATE TABLE IF NOT EXISTS upload_jobs(
            id TEXT PRIMARY KEY,
            patient_id TEXT REFERENCES users(id),
            user_id TEXT REFERENCES users(id),
            idempotency_key TEXT,
            filename TEXT,
            file_hash TEXT,
            state TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0,
            error_code TEXT,
            error_message TEXT,
            record_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS record_extractions(
            id TEXT PRIMARY KEY,
            record_id TEXT REFERENCES records(id),
            version INTEGER NOT NULL DEFAULT 1,
            pages_json TEXT NOT NULL,
            method TEXT NOT NULL,
            ocr_lang TEXT,
            warnings TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS record_corrections(
            id TEXT PRIMARY KEY,
            record_id TEXT REFERENCES records(id),
            version INTEGER NOT NULL,
            kind TEXT,
            date TEXT,
            provider TEXT,
            text TEXT,
            reason TEXT NOT NULL,
            reviewer_id TEXT REFERENCES users(id),
            reviewer_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            previous_version INTEGER
        );
        CREATE TABLE IF NOT EXISTS clarifications(
            id TEXT PRIMARY KEY,
            patient_id TEXT REFERENCES users(id),
            brief_id TEXT REFERENCES briefs(id),
            question TEXT NOT NULL,
            originating_uncertainty_id TEXT,
            creator_id TEXT REFERENCES users(id),
            creator_name TEXT NOT NULL,
            assigned_owner TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            resolution_reason TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by TEXT
        );
        CREATE TABLE IF NOT EXISTS clarification_messages(
            id TEXT PRIMARY KEY,
            clarification_id TEXT REFERENCES clarifications(id),
            author_id TEXT REFERENCES users(id),
            author_name TEXT NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS brief_reviews(
            id TEXT PRIMARY KEY,
            brief_id TEXT REFERENCES briefs(id),
            expected_source_revision TEXT,
            reviewer_id TEXT REFERENCES users(id),
            reviewer_name TEXT NOT NULL,
            outcome TEXT NOT NULL,
            note TEXT NOT NULL,
            reviewed_uncertainties TEXT,
            created_at TEXT NOT NULL
        );
        ''')
        # Additive migrations for instructions table
        for col_def in [
            'brief_id TEXT',
            'source_revision TEXT',
            'reviewer_id TEXT',
            'reviewer_name TEXT',
            "status TEXT NOT NULL DEFAULT 'published'",
            'withdrawal_reason TEXT',
            'version INTEGER NOT NULL DEFAULT 1',
            'previous_version_id TEXT',
            'content_language TEXT',
            'reviewed_at TEXT',
            'acknowledged_at TEXT',
            'acknowledgement_status TEXT',
            'override_reason TEXT'
        ]:
            try:
                raw.execute(f'ALTER TABLE instructions ADD COLUMN {col_def}')
            except sqlite3.OperationalError:
                pass

        # Additive migrations for records table
        for col_def in [
            "status TEXT NOT NULL DEFAULT 'active'",
            "deleted_at TEXT"
        ]:
            try:
                raw.execute(f'ALTER TABLE records ADD COLUMN {col_def}')
            except sqlite3.OperationalError:
                pass

