"""Durable upload jobs, extraction provenance tracking, and reviewed record corrections."""
import asyncio
import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional
from fastapi import HTTPException
from . import db
from .documents import read_document_detailed, metadata, MAX_BYTES

def get_job(job_id: str) -> Optional[dict]:
    with db.connection() as con:
        return con.one('upload_jobs', {'id': job_id})

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
                return existing

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

    # Trigger processing
    asyncio.create_task(process_upload_job(job_id, ocr_lang, user['name']))
    return job_row

async def process_upload_job(job_id: str, ocr_lang: Optional[str], actor_name: str):
    """Worker task processing the extraction and persisting the record atomically."""
    with db.connection() as con:
        job = con.one('upload_jobs', {'id': job_id})
        if not job or job['state'] in ('completed', 'failed'):
            return
        con.update('upload_jobs', {'id': job_id}, {
            'state': 'processing',
            'progress': 20,
            'updated_at': db.now()
        })
        temp_file = con.one('files', {'id': f"job_{job_id}"})

    if not temp_file:
        with db.connection() as con:
            con.update('upload_jobs', {'id': job_id}, {
                'state': 'failed',
                'error_code': 'file_missing',
                'error_message': 'Uploaded file payload is missing or expired.',
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
            'updated_at': now_ts
        })
        con.invalidate(job['patient_id'])
        db.audit(con, job['patient_id'], actor_name, 'Record added', title)

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
        return get_record_with_provenance(record_id, con)

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
        return get_record_with_provenance(record_id, con)
