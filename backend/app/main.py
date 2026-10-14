import hashlib
import json
import os
import secrets
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from dotenv import load_dotenv

# Explicit process settings override private local configuration.
load_dotenv(Path(__file__).resolve().parents[2] / '.env')

from . import db
from .demo_config import DEMO_PASSWORD
from .ai import organize
from .languages import LANGUAGES, CODES
from .documents import MAX_BYTES, read_document, read_document_detailed, metadata
from .upload_service import (
    create_upload_job,
    get_job,
    get_record_with_provenance,
    apply_metadata_correction,
    apply_text_correction,
    recover_pending_upload_jobs,
)
from .brief_service import build_structured_brief
from .review_service import (
    create_clarification,
    add_clarification_message,
    resolve_clarification,
    get_patient_clarifications,
    append_brief_review,
    publish_patient_instruction,
    withdraw_instruction,
    acknowledge_instruction,
)

@asynccontextmanager
async def lifespan(app):
    db.initialize()
    recover_pending_upload_jobs()
    yield

app = FastAPI(title='HealthBridge', lifespan=lifespan)

from pymongo.errors import PyMongoError, OperationFailure
from fastapi.responses import JSONResponse

@app.exception_handler(PyMongoError)
async def database_error(request, exc):
    conflict = isinstance(exc, OperationFailure) and exc.has_error_label('TransientTransactionError')
    return JSONResponse(status_code=409 if conflict else 503, content={'detail':
        'Another update was saved at the same time. Please refresh and retry.' if conflict else
        'The database is temporarily unavailable. Please retry shortly.'})

origins = [value.strip().rstrip('/') for value in os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',') if value.strip()]
if os.getenv('RENDER_EXTERNAL_URL'):
    origins.append(os.environ['RENDER_EXTERNAL_URL'].rstrip('/'))
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=['GET','POST','PATCH'],allow_headers=['Content-Type'])

@app.middleware('http')
async def protect(request: Request, call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin = request.headers.get('origin')
        if origin and origin not in origins and origin != str(request.base_url).rstrip('/'):
            return Response('Origin not allowed',status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if os.getenv('STATIC_DIR'):
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response

attempts: dict[str,list[float]] = defaultdict(list)

class Login(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(min_length=1,max_length=200)

class CheckEmail(BaseModel):
    email: str = Field(min_length=3, max_length=200)

class CareLanguage(BaseModel):
    language: str = 'en'

    @field_validator('language')
    @classmethod
    def supported_language(cls, value):
        if value not in CODES:
            raise ValueError('Choose a supported care language.')
        return value

class Intake(CareLanguage):
    reason: str = Field(min_length=5,max_length=3000)
    duration: str = Field(max_length=200,default='')
    medications: str = Field(max_length=1000,default='')
    allergies: str = Field(max_length=1000,default='')
    questions: str = Field(max_length=2000,default='')

class Review(BaseModel):
    status: Literal['approved','flagged']
    note: str = Field(min_length=3,max_length=4000)
    expected_source_revision: str | None = None
    reviewed_uncertainties: list[str] | None = None

class Instruction(CareLanguage):
    original: str = Field(min_length=10,max_length=6000)
    plain: str = Field(min_length=10,max_length=6000)
    translated: str = Field(max_length=6000,default='')
    confirmed: bool
    override_reason: str | None = None
    previous_version_id: str | None = None
    content_language: str | None = None
    status: Literal['published','draft'] = 'published'

class ClarificationCreate(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    brief_id: str | None = None
    originating_uncertainty_id: str | None = None

class ClarificationMessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

class ClarificationResolve(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

class InstructionWithdraw(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

class InstructionAcknowledge(BaseModel):
    status: Literal['acknowledged', 'needs_clarification']
    question: str | None = Field(default=None, max_length=2000)

class Profile(BaseModel):
    language: Literal['en','hi','kn']
    name: str | None = Field(default=None,min_length=2,max_length=100)
    age: int | None = Field(default=None,ge=0,le=130)

def public(user):
    result = {key:user[key] for key in ('id','name','email','role','language','age','initials')}
    result['is_demo'] = user['id'] in ('patient-asha','patient-kabir','doctor-meera')
    with db.connection() as con:
        membership = con.one('memberships', {'user_id': user['id']})
        result['organization'] = con.one('organizations', {'id': membership['organization_id']}) if membership else None
    return result

def current_user(request: Request):
    raw = request.cookies.get('hb_session','')
    with db.connection() as con:
        session = con.one('sessions', {'token': hashlib.sha256(raw.encode()).hexdigest(), 'expires': {'$gt': time.time()}})
        row = con.one('users', {'id': session['user_id']}) if session else None
    if not row:
        raise HTTPException(401,'Please sign in to continue.')
    return dict(row)

def patient_access(patient_id, user):
    if user['role'] == 'patient' and user['id'] == patient_id:
        return
    with db.connection() as con:
        if user['role'] == 'clinician' and con.one('assignments', {'clinician_id': user['id'], 'patient_id': patient_id}):
            return
    raise HTTPException(403,'This patient is not assigned to your account.')

def clinician(user):
    if user['role'] != 'clinician':
        raise HTTPException(403,'Clinician access required.')

@app.get('/api/health')
def health():
    with db.connection() as con:
        con.one('users')
    return {'status':'ok','database':db.backend(),'ai_backend':os.getenv('AI_BACKEND','extractive'),'model':os.getenv('AI_MODEL') if os.getenv('AI_BACKEND','extractive') != 'extractive' else None,'amd_verified':False,'demo':os.getenv('DEMO_ENABLED','true').lower() == 'true'}

@app.get('/api/languages')
def languages():
    return LANGUAGES

@app.get('/api/demo-accounts')
def demo_accounts():
    if os.getenv('DEMO_ENABLED','true').lower() != 'true':
        return []
    with db.connection() as con:
        users = con.find('users', {'id': {'$in': ['patient-asha','doctor-meera']}})
    return [{key:user[key] for key in ('email','name','role')} | {'password': DEMO_PASSWORD} for user in users]

def issue_session(con, user_id, request, response):
    # Replace this browser's old session when switching or creating accounts.
    old = request.cookies.get('hb_session', '')
    if old:
        con.delete('sessions', {'token': hashlib.sha256(old.encode()).hexdigest()})
    token = secrets.token_urlsafe(32)
    con.delete('sessions', {'expires': {'$lt': time.time()}})
    con.insert_row('sessions', (hashlib.sha256(token.encode()).hexdigest(), user_id, time.time()+28800))
    response.set_cookie('hb_session', token, httponly=True, secure=os.getenv('COOKIE_SECURE','false').lower()=='true', samesite='lax', max_age=28800, path='/')

@app.post('/api/auth/check-email')
def check_email(body: CheckEmail):
    clean_email = body.email.strip().lower()
    if '@' not in clean_email or '.' not in clean_email.split('@')[-1] or len(clean_email.split('.')[-1]) < 2:
        raise HTTPException(422, "Please enter a valid email address.")
    with db.connection() as con:
        user = con.one('users', {'email': clean_email})
    return {
        'registered': bool(user),
        'email': clean_email,
        'name': user['name'] if user else None,
        'role': user['role'] if user else None
    }

@app.post('/api/auth/login')
def login(body: Login, request: Request, response: Response):
    address = request.client.host if request.client else 'unknown'
    attempts[address] = [stamp for stamp in attempts[address] if stamp > time.time()-60]
    if len(attempts[address]) >= 12:
        raise HTTPException(429,'Too many attempts. Try again in a minute.')
    with db.connection() as con:
        user = con.one('users', {'email': body.email.strip().lower()})
        if not user or not db.verify_password(body.password,user['password']):
            attempts[address].append(time.time())
            raise HTTPException(401,'Email or password is incorrect.')
        issue_session(con,user['id'],request,response)
    return public(user)

@app.post('/api/auth/logout')
def logout(request: Request, response: Response):
    with db.connection() as con:
        con.delete('sessions', {'token': hashlib.sha256(request.cookies.get('hb_session','').encode()).hexdigest()})
    response.delete_cookie('hb_session')
    return {'ok':True}

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1,max_length=200)
    new_password: str = Field(min_length=8,max_length=200)

@app.post('/api/auth/password')
def change_password(body: PasswordChange, request: Request, response: Response, user=Depends(current_user)):
    if user['id'] in ('patient-asha','patient-kabir','doctor-meera'):
        raise HTTPException(403,'Shared demo passwords cannot be changed. Create your own account.')
    key='password:'+user['id']
    attempts[key]=[stamp for stamp in attempts[key] if stamp > time.time()-900]
    if len(attempts[key])>=6: raise HTTPException(429,'Too many attempts. Try again later.')
    attempts[key].append(time.time())
    with db.connection() as con:
        current=con.one('users',{'id':user['id']})
        if not current or not db.verify_password(body.current_password,current['password']):
            raise HTTPException(400,'Current password is incorrect.')
        if body.new_password == body.current_password:
            raise HTTPException(422,'Choose a different new password.')
        con.update('users',{'id':user['id']},{'password':db.password_hash(body.new_password)})
        con.delete('sessions',{'user_id':user['id']})
        issue_session(con,user['id'],request,response)
    attempts.pop(key,None)
    return {'ok':True}

@app.post('/api/auth/logout-all')
def logout_all(response: Response,user=Depends(current_user)):
    with db.connection() as con: con.delete('sessions',{'user_id':user['id']})
    response.delete_cookie('hb_session',path='/')
    return {'ok':True}

@app.get('/api/me')
def me(user=Depends(current_user)):
    return public(user)

@app.patch('/api/me')
def profile(body: Profile,user=Depends(current_user)):
    name = body.name.strip() if body.name is not None else user['name']
    if len(name)<2:
        raise HTTPException(422,'Please enter a name of at least two characters.')
    age = body.age if 'age' in body.model_fields_set else user['age']
    initials = ''.join(part[0] for part in name.split()[:2]).upper()
    with db.connection() as con:
        con.update('users', {'id': user['id']}, dict(language=body.language, name=name, age=age, initials=initials))
    return {**public(user),'language':body.language,'name':name,'age':age,'initials':initials}

@app.get('/api/patients')
def patients(user=Depends(current_user)):
    clinician(user)
    with db.connection() as con:
        assigned = con.find('assignments', {'clinician_id': user['id']})
        rows = con.find('users', {'id': {'$in': [a['patient_id'] for a in assigned]}})
        return [{**public(row),'records':con.count('records', {'patient_id': row['id']}), 'pending':con.count('briefs', {'patient_id': row['id'], 'status': 'pending'})} for row in rows]

@app.get('/api/patients/{patient_id}/workspace')
def workspace(patient_id: str,user=Depends(current_user)):
    patient_access(patient_id,user)
    with db.connection() as con:
        patient = public(con.one('users', {'id': patient_id}))
        records = [{k:r[k] for k in ('id','title','kind','date','provider','created_at')} for r in con.find('records', {'patient_id': patient_id}) if r.get('status') != 'withdrawn' and not r.get('deleted_at')]
        records.sort(key=lambda r: r['date'] or r['created_at'], reverse=True)
        intake = con.one('intakes', {'patient_id': patient_id}, sort=[('created_at', -1)])
        brief = con.one('briefs', {'patient_id': patient_id}, sort=[('created_at', -1)])
        brief = dict(brief) if brief else None
        if brief:
            brief['content'] = json.loads(brief['content'])
        raw_instructions = con.find('instructions', {'patient_id': patient_id}, sort=[('created_at', -1)], limit=None)
        current_rev = con.clinical_revision(patient_id)
        visible_instructions = []
        for inst in raw_instructions:
            if user['role'] == 'patient' and inst.get('status') == 'draft':
                continue
            inst_dict = dict(inst)
            if inst_dict.get('status') == 'published' and inst_dict.get('source_revision') and inst_dict.get('source_revision') != current_rev:
                inst_dict['reassessment_required'] = True
                inst_dict['reassessment_reason'] = 'Source records or intake have changed since these instructions were published. Clinician review recommended.'
            else:
                inst_dict['reassessment_required'] = False
            visible_instructions.append(inst_dict)

        upload_jobs = con.find('upload_jobs', {'patient_id': patient_id}, sort=[('created_at', -1)], limit=10)
        return {'patient':patient,'records':records,'intake':dict(intake) if intake else None,'brief':brief,
                'appointments':sorted(con.find('appointments', {'patient_id': patient_id}), key=lambda a: datetime.fromisoformat(a['starts_at'])),
                'instructions':visible_instructions,
                'clarifications': get_patient_clarifications(patient_id),
                'upload_jobs': upload_jobs,
                'activity':con.find('audit', {'patient_id': patient_id}, sort=[('id', -1)], limit=30)}

@app.post('/api/patients/{patient_id}/intake')
def intake(patient_id: str, body: Intake,user=Depends(current_user)):
    patient_access(patient_id,user)
    if not body.reason.strip() or len(body.reason.strip()) < 5:
        raise HTTPException(422,'Please describe your reason for the visit.')
    with db.connection() as con:
        con.insert_row('intakes',(secrets.token_hex(12),patient_id,body.reason.strip(),body.duration,body.medications,body.allergies,body.questions,body.language,db.now()))
        con.invalidate(patient_id)
        db.audit(con,patient_id,user['name'],'Intake saved','Patient-provided information; review required.')
    return {'ok':True}

class MetadataCorrectionRequest(BaseModel):
    kind: str = Field(min_length=2, max_length=120)
    date: str | None = None
    provider: str = Field(min_length=2, max_length=160)
    reason: str = Field(min_length=3, max_length=500)
    expected_version: int = 1

class TextCorrectionRequest(BaseModel):
    text: str = Field(min_length=10, max_length=80000)
    reason: str = Field(min_length=3, max_length=500)
    expected_version: int = 1

@app.post('/api/patients/{patient_id}/upload-jobs', status_code=202)
async def create_upload(
    patient_id: str,
    file: UploadFile,
    ocr_lang: str | None = Form(None),
    idempotency_key: str | None = Form(None),
    user=Depends(current_user)
):
    patient_access(patient_id, user)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Maximum file size is 10 MB.')
    job = create_upload_job(
        patient_id=patient_id,
        user=user,
        filename=file.filename or 'document',
        data=data,
        idempotency_key=idempotency_key,
        ocr_lang=ocr_lang
    )
    return job

@app.get('/api/upload-jobs/{job_id}')
def read_upload_job(job_id: str, user=Depends(current_user)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, 'Upload job not found.')
    patient_access(job['patient_id'], user)
    return {
        'id': job['id'],
        'patient_id': job['patient_id'],
        'state': job['state'],
        'progress': job['progress'],
        'record_id': job['record_id'],
        'error_code': job['error_code'],
        'error_message': job['error_message'],
        'duplicate_warning': job.get('duplicate_warning'),
        'attempt_count': job.get('attempt_count', 0),
        'created_at': job['created_at'],
        'updated_at': job['updated_at']
    }

@app.post('/api/patients/{patient_id}/records')
async def upload(patient_id: str,file: UploadFile,user=Depends(current_user)):
    patient_access(patient_id,user)
    data = await file.read(MAX_BYTES+1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413,'Maximum file size is 10 MB.')
    try:
        text, media, meta = await run_in_threadpool(read_document_detailed, data, file.filename or '')
    except Exception as exc:
        raise HTTPException(422,'Unable to read this file. Use a readable PDF (up to 20 pages), PNG, JPG or UTF-8 TXT. Scans require Tesseract.') from exc
    if len(text.strip()) < 10:
        raise HTTPException(422,'No readable text found. Try a clearer document or a text file.')
    if len(text)>80000:
        raise HTTPException(422,'Document text exceeds 80,000 characters. Split the document first.')
    rid = secrets.token_hex(12)
    fields = metadata(text)
    title = Path(file.filename or 'Uploaded record').stem[:120]
    now_ts = db.now()
    with db.connection() as con:
        con.insert('files', {'id': rid, 'data': data})
        con.insert_row('records',(rid,patient_id,title,fields['kind'],fields['date'],fields['provider'],text,rid,media,now_ts))
        con.insert('record_extractions', {
            'id': secrets.token_hex(12),
            'record_id': rid,
            'version': 1,
            'pages_json': json.dumps(meta.get('pages', [])),
            'method': meta.get('method', 'direct_text'),
            'ocr_lang': meta.get('ocr_lang'),
            'warnings': json.dumps(meta.get('warnings', [])),
            'created_at': now_ts
        })
        con.invalidate(patient_id)
        db.audit(con,patient_id,user['name'],'Record added',title)
    return {'id':rid}

@app.get('/api/records/{record_id}')
def record(record_id: str,user=Depends(current_user)):
    with db.connection() as con:
        row = get_record_with_provenance(record_id, con)
    if not row:
        raise HTTPException(404,'Record not found.')
    patient_access(row['patient_id'],user)
    return row

@app.patch('/api/records/{record_id}/metadata')
def correct_metadata(record_id: str, body: MetadataCorrectionRequest, user=Depends(current_user)):
    clinician(user)
    with db.connection() as con:
        row = con.one('records', {'id': record_id})
    if not row:
        raise HTTPException(404, 'Record not found.')
    patient_access(row['patient_id'], user)
    return apply_metadata_correction(
        record_id=record_id,
        patient_id=row['patient_id'],
        user=user,
        kind=body.kind,
        date=body.date,
        provider=body.provider,
        reason=body.reason,
        expected_version=body.expected_version
    )

@app.post('/api/records/{record_id}/corrections')
def correct_text(record_id: str, body: TextCorrectionRequest, user=Depends(current_user)):
    clinician(user)
    with db.connection() as con:
        row = con.one('records', {'id': record_id})
    if not row:
        raise HTTPException(404, 'Record not found.')
    patient_access(row['patient_id'], user)
    return apply_text_correction(
        record_id=record_id,
        patient_id=row['patient_id'],
        user=user,
        text=body.text,
        reason=body.reason,
        expected_version=body.expected_version
    )

@app.get('/api/records/{record_id}/file')
def original(record_id: str,user=Depends(current_user)):
    row = record(record_id,user)
    if row['filename']:
        with db.connection() as con:
            stored = con.one('files', {'id': row['filename']})
        if stored:
            return Response(bytes(stored['data']), media_type=row['media_type'],
                            headers={'Content-Disposition': 'attachment; filename="record' + {'application/pdf':'.pdf','image/png':'.png','image/jpeg':'.jpg'}.get(row['media_type'],'.txt') + '"'})
        # Backward compatibility for uploads saved before database-backed files.
        path = db.DATA/'uploads'/row['filename']
        if db.backend() == 'sqlite' and path.is_file():
            return FileResponse(path,media_type=row['media_type'],filename=row['title'])
        raise HTTPException(404, 'Original file is unavailable.')
    return Response(row['text'],media_type='text/plain',headers={'Content-Disposition':'attachment; filename="synthetic-record.txt"'})

@app.delete('/api/records/{record_id}')
def delete_record(record_id: str, user=Depends(current_user)):
    with db.connection() as con:
        row = con.one('records', {'id': record_id})
        if not row or row.get('status') == 'withdrawn' or row.get('deleted_at'):
            raise HTTPException(404, 'Record not found.')
        patient_access(row['patient_id'], user)
        con.update('records', {'id': record_id}, {'status': 'withdrawn', 'deleted_at': db.now()})
        con.invalidate(row['patient_id'])
        db.audit(con, row['patient_id'], user['name'], 'Record removed', f"{row['title']} ({record_id})")
    return {'ok': True, 'id': record_id, 'status': 'withdrawn'}

@app.get('/api/patients/{patient_id}/export')
def export_patient(patient_id: str, user=Depends(current_user)):
    patient_access(patient_id, user)
    with db.connection() as con:
        patient = public(con.one('users', {'id': patient_id}))
        if not patient:
            raise HTTPException(404, 'Patient not found.')
        records = [
            get_record_with_provenance(r['id'], con)
            for r in con.find('records', {'patient_id': patient_id})
            if r.get('status') != 'withdrawn' and not r.get('deleted_at')
        ]
        intake = con.one('intakes', {'patient_id': patient_id}, sort=[('created_at', -1)])
        brief = con.one('briefs', {'patient_id': patient_id}, sort=[('created_at', -1)])
        brief_data = dict(brief) if brief else None
        if brief_data:
            brief_data['content'] = json.loads(brief_data['content'])
        raw_instructions = con.find('instructions', {'patient_id': patient_id}, sort=[('created_at', -1)], limit=None)
        instructions = [dict(i) for i in raw_instructions if user['role'] == 'clinician' or i.get('status') != 'draft']
        clarifications = get_patient_clarifications(patient_id)
        appointments = con.find('appointments', {'patient_id': patient_id})

        return {
            'exported_at': db.now(),
            'provenance_notice': 'HealthBridge synthetic demonstration record export. Patient-reported intake, uploaded document extractions, and clinician-reviewed instructions are included with attribution. Not an official medical record.',
            'patient': patient,
            'intake': dict(intake) if intake else None,
            'records': [r for r in records if r is not None],
            'brief': brief_data,
            'instructions': instructions,
            'clarifications': clarifications,
            'appointments': appointments,
        }

class BriefGenerateRequest(BaseModel):
    selected_record_ids: list[str] | None = None

@app.post('/api/patients/{patient_id}/brief')
async def generate_brief(patient_id: str, body: BriefGenerateRequest | None = None, user=Depends(current_user)):
    patient_access(patient_id, user)
    with db.connection() as con:
        intake_row = con.one('intakes', {'patient_id': patient_id}, sort=[('created_at', -1)])
        intake = dict(intake_row) if intake_row else None
        # Exclude withdrawn and tombstoned records
        all_records = con.find('records', {'patient_id': patient_id}, sort=[('created_at', -1)])
        available_records = [
            dict(r) for r in all_records
            if r.get('status') != 'withdrawn' and not r.get('deleted_at')
        ]
        if not intake and not available_records:
            raise HTTPException(422, 'Add your concerns or a record first.')

        active_ids = {r['id'] for r in available_records}
        selected_ids = None
        if body and body.selected_record_ids is not None:
            selected_ids = [rid for rid in body.selected_record_ids if rid in active_ids]
            if body.selected_record_ids and not selected_ids:
                raise HTTPException(422, 'The selected records are no longer available.')

        clinical_rev = con.clinical_revision(patient_id)
        extractions_by_record = {}
        for r in available_records:
            ext = con.one('record_extractions', {'record_id': r['id']}, sort=[('version', -1)])
            if ext:
                extractions_by_record[r['id']] = dict(ext)

    ai_mode = os.getenv('AI_BACKEND', 'extractive')
    model_name = os.getenv('AI_MODEL', 'none') if ai_mode != 'extractive' else 'none'
    latency = 0
    engine = f"{ai_mode} · {model_name}" if ai_mode != 'extractive' else 'Source excerpts · no model used'
    model_evidence = None

    if ai_mode != 'extractive':
        sources = []
        if intake:
            sources.append({
                'id': intake['id'],
                'title': 'Patient intake',
                'text': '\n'.join(f'{k.title()}: {intake[k] or "Not provided"}' for k in ('reason','duration','medications','allergies','questions'))
            })
        records_for_model = [r for r in available_records if r['id'] in selected_ids] if selected_ids is not None else available_records[:12]
        for r in records_for_model:
            sources.append({'id': r['id'], 'title': r['title'], 'text': r['text']})
        try:
            model_evidence, engine, latency = await organize(sources)
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(503, 'The model is unavailable or its output could not be verified. Your records are safe. Check the model connection and retry.') from exc

    content = build_structured_brief(
        patient_id=patient_id,
        intake=intake,
        available_records=available_records,
        extractions_by_record=extractions_by_record,
        selected_record_ids=selected_ids,
        ai_mode=ai_mode,
        model_name=model_name,
        clinical_rev=clinical_rev,
        latency_ms=latency,
        model_evidence=model_evidence
    )

    bid = secrets.token_hex(12)
    with db.connection() as con:
        latest = con.clinical_revision(patient_id)
        if latest != clinical_rev:
            raise HTTPException(409, 'The patient record changed while preparing the brief. Please generate it again.')
        con.invalidate(patient_id)
        con.insert_row('briefs', (bid, patient_id, json.dumps(content), 'pending', engine, db.now(), None, None))
        db.audit(con, patient_id, user['name'], 'Brief prepared', engine)
    return {'id': bid}

@app.post('/api/briefs/{brief_id}/review')
def review(brief_id: str, body: Review, user=Depends(current_user)):
    clinician(user)
    if len(body.note.strip()) < 3:
        raise HTTPException(422, 'Add a meaningful review note.')
    with db.connection() as con:
        row = con.one('briefs', {'id': brief_id})
        if not row:
            raise HTTPException(404, 'Brief not found.')
        patient_access(row['patient_id'], user)
    return append_brief_review(
        brief_id=brief_id,
        status=body.status,
        note=body.note.strip(),
        expected_source_revision=body.expected_source_revision,
        reviewed_uncertainties=body.reviewed_uncertainties,
        user=user
    )

@app.get('/api/patients/{patient_id}/clarifications')
def list_clarifications(patient_id: str, user=Depends(current_user)):
    patient_access(patient_id, user)
    return get_patient_clarifications(patient_id)

@app.post('/api/patients/{patient_id}/clarifications')
def create_new_clarification(patient_id: str, body: ClarificationCreate, user=Depends(current_user)):
    clinician(user)
    patient_access(patient_id, user)
    return create_clarification(patient_id, body.brief_id, body.question, body.originating_uncertainty_id, user)

@app.post('/api/clarifications/{clarification_id}/messages')
def post_clarification_message(clarification_id: str, body: ClarificationMessageCreate, user=Depends(current_user)):
    with db.connection() as con:
        clar = con.one('clarifications', {'id': clarification_id})
        if not clar:
            raise HTTPException(404, 'Clarification not found.')
        patient_access(clar['patient_id'], user)
    return add_clarification_message(clarification_id, body.text, user)

@app.post('/api/clarifications/{clarification_id}/resolve')
def resolve_patient_clarification(clarification_id: str, body: ClarificationResolve, user=Depends(current_user)):
    clinician(user)
    with db.connection() as con:
        clar = con.one('clarifications', {'id': clarification_id})
        if not clar:
            raise HTTPException(404, 'Clarification not found.')
        patient_access(clar['patient_id'], user)
    return resolve_clarification(clarification_id, body.reason, user)

@app.post('/api/patients/{patient_id}/instructions')
def instructions(patient_id: str, body: Instruction, user=Depends(current_user)):
    clinician(user)
    patient_access(patient_id, user)
    if body.language != 'en' and not body.translated.strip():
        raise HTTPException(422, 'Add the reviewed translation or choose English.')
    res = publish_patient_instruction(
        patient_id=patient_id,
        original=body.original,
        plain=body.plain,
        language=body.language,
        translated=body.translated,
        content_language=body.content_language,
        confirmed=body.confirmed,
        user=user,
        override_reason=body.override_reason,
        previous_version_id=body.previous_version_id,
        status=body.status
    )
    return {'ok': True, **res}

@app.post('/api/instructions/{instruction_id}/withdraw')
def withdraw_patient_instruction(instruction_id: str, body: InstructionWithdraw, user=Depends(current_user)):
    clinician(user)
    with db.connection() as con:
        inst = con.one('instructions', {'id': instruction_id})
        if not inst:
            raise HTTPException(404, 'Instruction not found.')
        patient_access(inst['patient_id'], user)
    return withdraw_instruction(instruction_id, body.reason, user)

@app.post('/api/instructions/{instruction_id}/acknowledge')
def acknowledge_patient_instruction(instruction_id: str, body: InstructionAcknowledge, user=Depends(current_user)):
    with db.connection() as con:
        inst = con.one('instructions', {'id': instruction_id})
        if not inst:
            raise HTTPException(404, 'Instruction not found.')
        patient_access(inst['patient_id'], user)
    return acknowledge_instruction(instruction_id, body.status, user, question=body.question)

class Appointment(BaseModel):
    id: str | None = Field(default=None, max_length=100)
    clinician: str = Field(min_length=2, max_length=120)
    specialty: str = Field(min_length=2, max_length=120)
    location: str = Field(min_length=2, max_length=250)
    starts_at: datetime

    @field_validator('clinician', 'specialty', 'location')
    @classmethod
    def meaningful(cls, value):
        if len(value.strip()) < 2:
            raise ValueError('Enter at least two non-space characters.')
        return value.strip()

    @field_validator('starts_at')
    @classmethod
    def future_time(cls, value):
        from datetime import timezone
        if value.tzinfo is None or value <= datetime.now(timezone.utc):
            raise ValueError('Choose a future appointment time with a timezone.')
        return value

@app.post('/api/patients/{patient_id}/appointments')
def save_appointment(patient_id: str, body: Appointment, user=Depends(current_user)):
    patient_access(patient_id, user)
    values = body.model_dump(exclude={'id'})
    values['starts_at'] = body.starts_at.isoformat()
    with db.connection() as con:
        if body.id:
            if not con.one('appointments', {'id': body.id, 'patient_id': patient_id}):
                raise HTTPException(404, 'Appointment not found.')
            con.update('appointments', {'id': body.id, 'patient_id': patient_id}, values)
            aid = body.id
        else:
            aid = secrets.token_hex(12)
            con.insert('appointments', {'id': aid, 'patient_id': patient_id, **values})
        con.invalidate(patient_id)
        db.audit(con, patient_id, user['name'], 'Appointment saved', 'Personal appointment details; confirm the booking with your clinic.')
    return {'id': aid}

from .onboarding import router as onboarding_router
app.include_router(onboarding_router)

# One origin for the production UI and API: no cross-site cookies or proxy URLs.
if os.getenv('STATIC_DIR'):
    from fastapi.staticfiles import StaticFiles
    app.mount('/', StaticFiles(directory=os.environ['STATIC_DIR'], html=True), name='frontend')
