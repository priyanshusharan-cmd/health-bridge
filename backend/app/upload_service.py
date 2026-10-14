"""Durable upload jobs, extraction provenance tracking, and reviewed record corrections."""
import asyncio
import hashlib
import json
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from fastapi import HTTPException
from . import db
from .documents import read_document_detailed, metadata, MAX_BYTES

WORKER_ID = f"worker_{secrets.token_hex(6)}"
_upload_semaphore = asyncio.Semaphore(3)
LEASE_SECONDS = 180

def get_job(job_id: str) -> Optional[dict]:
    with db.connection() as con:
        return con.one('upload_jobs', {'id': job_id})

def claim_job(con, job_id: str, worker_id: str, lease_duration: int = LEASE_SECONDS) -> bool:
    """Atomically claim a queued or expired job with worker lease."""
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    expires_iso = (now_dt + timedelta(seconds=lease_duration)).isoformat()
    
    if hasattr(con, 'raw'):
        con.raw.execute("""
            UPDATE upload_jobs
            SET state = 'failed',
                error_code = 'max_attempts_exceeded',
                error_message = 'Extraction failed after repeated attempts.',
                lease_owner = NULL,
                lease_expires_at = NULL,
                updated_at = ?
            WHERE id = ? AND attempt_count >= 3 AND state IN ('queued', 'processing')
        """, (now_iso, job_id))

        cur = con.raw.execute("""
            UPDATE upload_jobs
            SET state = 'processing',
                lease_owner = ?,
                lease_expires_at = ?,
                attempt_count = attempt_count + 1,
                progress = 20,
                updated_at = ?
            WHERE id = ?
              AND (state = 'queued' OR (state = 'processing' AND (lease_expires_at IS NULL OR lease_expires_at < ?)))
              AND attempt_count < 3
        """, (worker_id, expires_iso, now_iso, job_id, now_iso))
        return cur.rowcount > 0
    else:
        job = con.one('upload_jobs', {'id': job_id})
        if not job:
            return False
        attempts = job.get('attempt_count', 0)
        if attempts >= 3 and job.get('state') in ('queued', 'processing'):
            con.update('upload_jobs', {'id': job_id}, {
                'state': 'failed',
                'error_code': 'max_attempts_exceeded',
                'error_message': 'Extraction failed after repeated attempts.',
                'lease_owner': None,
                'lease_expires_at': None,
                'updated_at': now_iso
            })
            return False
        lease_exp = job.get('lease_expires_at')
        is_queued = job.get('state') == 'queued'
        is_expired = job.get('state') == 'processing' and (not lease_exp or lease_exp < now_iso)
        if (is_queued or is_expired) and attempts < 3:
            con.update('upload_jobs', {'id': job_id}, {
                'state': 'processing',
                'lease_owner': worker_id,
                'lease_expires_at': expires_iso,
                'attempt_count': attempts + 1,
                'progress': 20,
                'updated_at': now_iso
            })
            return True
        return False

def create_upload_job(
    patient_id: str,
    user: dict,
    filename: str,
    data: bytes,
    idempotency_key: Optional[str] = None,
    ocr_lang: Optional[str] = None
) -> dict:
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Please choose a file smaller than 10 MB.')
    
    file_hash = hashlib.sha256(data).hexdigest()
    
    with db.connection() as con:
        if idempotency_key:
            existing = con.one('upload_jobs', {
                'patient_id': patient_id,
                'idempotency_key': idempotency_key
            })
            if existing:
                # If existing job is still queued or abandoned in processing, trigger worker
                if existing['state'] in ('queued', 'processing'):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(process_upload_job(existing['id'], existing.get('ocr_lang'), user['name']))
                    except RuntimeError:
                        pass
                return existing

        # Check for duplicate document content already uploaded for this patient
        dup_job = con.one('upload_jobs', {
            'patient_id': patient_id,
            'file_hash': file_hash,
            'state': 'completed'
        })
        duplicate_warning = None
        if dup_job:
            duplicate_warning = f"A document with identical content was already uploaded as '{dup_job.get('filename')}'."

        job_id = secrets.token_hex(12)
        now_ts = db.now()
        # Save temp file for worker processing
        temp_file_id = f"job_{job_id}"
        con.insert('files', {'id': temp_file_id, 'data': data})
        
        job_row = {
            'id': job_id,
            'patient_id': patient_id,
            'user_id': user['id'],
            'idempotency_key': idempotency_key,
            'filename': filename,
            'file_hash': file_hash,
            'ocr_lang': ocr_lang,
            'attempt_count': 0,
            'lease_owner': None,
            'lease_expires_at': None,
            'duplicate_warning': duplicate_warning,
            'state': 'queued',
            'progress': 0,
            'error_code': None,
            'error_message': None,
            'record_id': None,
            'created_at': now_ts,
            'updated_at': now_ts,
        }
        con.insert('upload_jobs', job_row)
        db.audit(con, patient_id, user['name'], 'Upload job queued', filename)

    # Trigger processing if event loop is running
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(process_upload_job(job_id, ocr_lang, user['name']))
    except RuntimeError:
        pass
    return job_row

async def process_upload_job(job_id: str, ocr_lang: Optional[str] = None, actor_name: Optional[str] = None):
    """Worker task processing the extraction and persisting the record atomically."""
    async with _upload_semaphore:
        with db.connection() as con:
            claimed = claim_job(con, job_id, WORKER_ID)
            if not claimed:
                return
            job = con.one('upload_jobs', {'id': job_id})
            if not job:
                return
            if ocr_lang is None:
                ocr_lang = job.get('ocr_lang')
            if actor_name is None:
                u = con.one('users', {'id': job.get('user_id')})
                actor_name = u['name'] if u else 'System'
            temp_file = con.one('files', {'id': f"job_{job_id}"})

        if not temp_file:
            with db.connection() as con:
                con.update('upload_jobs', {'id': job_id}, {
                    'state': 'failed',
                    'error_code': 'file_missing',
                    'error_message': 'Uploaded file payload is missing or expired.',
                    'lease_owner': None,
                    'lease_expires_at': None,
                    'updated_at': db.now()
                })
            return

        data = bytes(temp_file['data'])
        filename = job['filename'] or 'document.pdf'

        try:
            # Offload CPU-bound OCR / parsing to threadpool
            loop = asyncio.get_running_loop()
            text, media_type, meta = await loop.run_in_executor(
                None,
                read_document_detailed,
                data,
                filename,
                ocr_lang
            )
        except Exception as exc:
            with db.connection() as con:
                con.update('upload_jobs', {'id': job_id}, {
                    'state': 'failed',
                    'error_code': 'extraction_failed',
                    'error_message': str(exc),
                    'lease_owner': None,
                    'lease_expires_at': None,
                    'updated_at': db.now()
                })
                con.delete('files', {'id': f"job_{job_id}"})
            return

        if len(text.strip()) < 10:
            with db.connection() as con:
                con.update('upload_jobs', {'id': job_id}, {
                    'state': 'failed',
                    'error_code': 'no_readable_text',
                    'error_message': 'No readable text found. Try a clearer document or a text file.',
                    'lease_owner': None,
                    'lease_expires_at': None,
                    'updated_at': db.now()
                })
                con.delete('files', {'id': f"job_{job_id}"})
            return

        if len(text) > 80000:
            with db.connection() as con:
                con.update('upload_jobs', {'id': job_id}, {
                    'state': 'failed',
                    'error_code': 'text_too_large',
                    'error_message': 'Document text exceeds 80,000 characters. Split the document first.',
                    'lease_owner': None,
                    'lease_expires_at': None,
                    'updated_at': db.now()
                })
                con.delete('files', {'id': f"job_{job_id}"})
            return

        record_id = secrets.token_hex(12)
        fields = metadata(text)
        title = Path(filename).stem[:120]
        extraction_id = secrets.token_hex(12)
        now_ts = db.now()

        # Persist record, extraction provenance, and mark job completed atomically
        with db.connection() as con:
            con.insert('files', {'id': record_id, 'data': data})
            con.delete('files', {'id': f"job_{job_id}"})
            con.insert_row('records', (
                record_id,
                job['patient_id'],
                title,
                fields['kind'],
                fields['date'],
                fields['provider'],
                text,
                record_id,
                media_type,
                now_ts
            ))
            con.insert('record_extractions', {
                'id': extraction_id,
                'record_id': record_id,
                'version': 1,
                'pages_json': json.dumps(meta.get('pages', [])),
                'method': meta.get('method', 'direct_text'),
                'ocr_lang': meta.get('ocr_lang'),
                'warnings': json.dumps(meta.get('warnings', [])),
                'created_at': now_ts
            })
            con.update('upload_jobs', {'id': job_id}, {
                'state': 'completed',
                'progress': 100,
                'record_id': record_id,
                'lease_owner': None,
                'lease_expires_at': None,
                'updated_at': now_ts
            })
            con.invalidate(job['patient_id'])
            db.audit(con, job['patient_id'], actor_name, 'Record added', title)

def recover_pending_upload_jobs():
    """Startup recovery scan to resume queued jobs or expired worker leases."""
    now_iso = db.now()
    with db.connection() as con:
        raw_con = getattr(con, 'raw', None)
        if raw_con is not None:
            # Mark max attempts exceeded if attempt_count >= 3
            raw_con.execute("""
                UPDATE upload_jobs
                SET state = 'failed',
                    error_code = 'max_attempts_exceeded',
                    error_message = 'Extraction failed after repeated attempts.',
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE state IN ('queued', 'processing') AND attempt_count >= 3
            """, (now_iso,))
            # Find queued or expired jobs
            cursor = raw_con.execute("""
                SELECT id, ocr_lang FROM upload_jobs
                WHERE (state = 'queued' OR (state = 'processing' AND (lease_expires_at IS NULL OR lease_expires_at < ?)))
                  AND attempt_count < 3
            """, (now_iso,))
            rows = [dict(r) for r in cursor.fetchall()]
        else:
            all_pending = con.find('upload_jobs', {'state': {'$in': ['queued', 'processing']}})
            rows = []
            for job in all_pending:
                attempts = job.get('attempt_count', 0)
                if attempts >= 3:
                    con.update('upload_jobs', {'id': job['id']}, {
                        'state': 'failed',
                        'error_code': 'max_attempts_exceeded',
                        'error_message': 'Extraction failed after repeated attempts.',
                        'lease_owner': None,
                        'lease_expires_at': None,
                        'updated_at': now_iso
                    })
                    continue
                lease_exp = job.get('lease_expires_at')
                if job['state'] == 'queued' or not lease_exp or lease_exp < now_iso:
                    rows.append(job)

    try:
        loop = asyncio.get_running_loop()
        for row in rows:
            loop.create_task(process_upload_job(row['id'], row.get('ocr_lang'), "system_recovery"))
    except RuntimeError:
        pass

def get_record_with_provenance(record_id: str, con) -> Optional[dict]:
    row = con.one('records', {'id': record_id})
    if not row or row.get('status') == 'withdrawn' or row.get('deleted_at'):
        return None
    res = dict(row)
    
    # Load extraction provenance
    extraction = con.one('record_extractions', {'record_id': record_id}, sort=[('version', -1)])
    if extraction:
        try:
            pages = json.loads(extraction['pages_json'])
        except Exception:
            pages = []
        try:
            warnings = json.loads(extraction['warnings']) if extraction.get('warnings') else []
        except Exception:
            warnings = []
        res['extraction'] = {
            'version': extraction['version'],
            'method': extraction['method'],
            'ocr_lang': extraction['ocr_lang'],
            'pages': pages,
            'warnings': warnings,
            'created_at': extraction['created_at']
        }
    else:
        res['extraction'] = {
            'version': 1,
            'method': 'legacy',
            'ocr_lang': None,
            'pages': [],
            'warnings': [],
            'notice': 'Extraction details unavailable for legacy records.'
        }

    # Load reviewed corrections history
    corrections = con.find('record_corrections', {'record_id': record_id}, sort=[('version', 1)])
    res['corrections'] = corrections
    return res

def apply_metadata_correction(
    record_id: str,
    patient_id: str,
    user: dict,
    kind: str,
    date: Optional[str],
    provider: str,
    reason: str,
    expected_version: int = 1
) -> dict:
    if len(reason.strip()) < 3:
        raise HTTPException(422, 'A meaningful reason is required for metadata corrections.')
    
    with db.connection() as con:
        record = con.one('records', {'id': record_id})
        if not record:
            raise HTTPException(404, 'Record not found.')
        if record['patient_id'] != patient_id:
            raise HTTPException(403, 'Record does not belong to this patient.')
        
        latest_corr = con.one('record_corrections', {'record_id': record_id}, sort=[('version', -1)])
        current_version = latest_corr['version'] if latest_corr else 1
        if expected_version != current_version:
            raise HTTPException(409, f'Record has been modified (current version: {current_version}, expected: {expected_version}). Refresh and retry.')

        new_version = current_version + 1
        now_ts = db.now()
        corr_id = secrets.token_hex(12)
        con.insert('record_corrections', {
            'id': corr_id,
            'record_id': record_id,
            'version': new_version,
            'kind': kind,
            'date': date,
            'provider': provider,
            'text': record['text'],
            'reason': reason.strip(),
            'reviewer_id': user['id'],
            'reviewer_name': user['name'],
            'created_at': now_ts,
            'previous_version': current_version
        })
        con.update('records', {'id': record_id}, {
            'kind': kind,
            'date': date,
            'provider': provider
        })
        con.invalidate(patient_id)
        db.audit(con, patient_id, user['name'], 'Record metadata corrected', f"v{new_version}: {reason.strip()}")
        res = get_record_with_provenance(record_id, con)
        if not res:
            raise HTTPException(404, 'Record not found.')
        return res

def apply_text_correction(
    record_id: str,
    patient_id: str,
    user: dict,
    text: str,
    reason: str,
    expected_version: int = 1
) -> dict:
    if len(reason.strip()) < 3:
        raise HTTPException(422, 'A meaningful reason is required for text corrections.')
    if len(text.strip()) < 10:
        raise HTTPException(422, 'Corrected text must contain meaningful content.')
    if len(text) > 80000:
        raise HTTPException(422, 'Text exceeds 80,000 characters.')

    with db.connection() as con:
        record = con.one('records', {'id': record_id})
        if not record:
            raise HTTPException(404, 'Record not found.')
        if record['patient_id'] != patient_id:
            raise HTTPException(403, 'Record does not belong to this patient.')

        latest_corr = con.one('record_corrections', {'record_id': record_id}, sort=[('version', -1)])
        current_version = latest_corr['version'] if latest_corr else 1
        if expected_version != current_version:
            raise HTTPException(409, f'Record has been modified (current version: {current_version}, expected: {expected_version}). Refresh and retry.')

        new_version = current_version + 1
        now_ts = db.now()
        corr_id = secrets.token_hex(12)
        con.insert('record_corrections', {
            'id': corr_id,
            'record_id': record_id,
            'version': new_version,
            'kind': record['kind'],
            'date': record['date'],
            'provider': record['provider'],
            'text': record['text'],  # Keep old text for provenance
            'reason': reason.strip(),
            'reviewer_id': user['id'],
            'reviewer_name': user['name'],
            'created_at': now_ts,
            'previous_version': current_version
        })
        con.update('records', {'id': record_id}, {
            'text': text
        })
        con.invalidate(patient_id)
        db.audit(con, patient_id, user['name'], 'Record text corrected', f"v{new_version}: {reason.strip()}")
        res = get_record_with_provenance(record_id, con)
        if not res:
            raise HTTPException(404, 'Record not found.')
        return res
