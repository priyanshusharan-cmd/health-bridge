import os
import secrets
import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from app import db
from app.main import app, attempts
from app.ai import organize

@pytest.fixture
def client(tmp_path,monkeypatch):
    attempts.clear()
    remote = os.getenv('HEALTHBRIDGE_TEST_MONGO') == '1'
    test_database = 'healthbridge_test_' + secrets.token_hex(8)
    if remote:
        monkeypatch.setenv('MONGODB_DATABASE', test_database)
    else:
        monkeypatch.setenv('MONGODB_URI','')
    monkeypatch.setattr(db,'DATA',tmp_path)
    monkeypatch.setenv('DEMO_ENABLED','true')
    monkeypatch.setenv('AI_BACKEND','extractive')
    try:
        with TestClient(app) as c:
            yield c
    finally:
        if remote:
            from app.store import mongo_client
            mongo_client().drop_database(test_database)

def login(c,role='patient'):
    email='patient@healthbridge.demo' if role=='patient' else 'doctor@healthbridge.demo'
    response=c.post('/api/auth/login',json={'email':email,'password':'BridgeDemo2026!'})
    assert response.status_code==200
    return response

def test_complete_handoff_persists_and_enforces_roles(client):
    c=client
    assert c.get('/api/patients/patient-asha/workspace').status_code==401
    login(c)
    assert c.get('/api/patients/patient-kabir/workspace').status_code==403
    assert c.get('/api/patients').status_code==403
    body={'reason':'I want to discuss my old report.','duration':'Two weeks','questions':'What should I bring?','language':'en'}
    assert c.post('/api/patients/patient-asha/intake',json=body).status_code==200
    uploaded=c.post('/api/patients/patient-asha/records',files={'file':('demo.txt',b'SYNTHETIC DEMO DATA\nDate: 2026-10-01\nProvider: Test Clinic\nVisit note\nPlease bring earlier records.','text/plain')})
    assert uploaded.status_code==200
    rid=uploaded.json()['id']
    assert 'Test Clinic' in c.get(f'/api/records/{rid}').json()['text']
    assert c.get(f'/api/records/{rid}/file').status_code==200
    bid=c.post('/api/patients/patient-asha/brief').json()['id']
    assert c.post(f'/api/briefs/{bid}/review',json={'status':'approved','note':'Checked sources.'}).status_code==403
    assert c.post('/api/patients/patient-asha/instructions',json={'original':'Bring your records.','plain':'Bring your records.','language':'en','confirmed':True}).status_code==403
    c.post('/api/auth/logout')
    assert c.get('/api/me').status_code==401
    login(c,'clinician')
    assert c.post(f'/api/briefs/{bid}/review',json={'status':'approved','note':'Reviewed all cited records; confirm allergies at visit.'}).status_code==200
    instructions={'original':'Bring your previous reports on 15 October 2026.','plain':'Bring your earlier reports on 15 October 2026.','language':'en','confirmed':True}
    assert c.post('/api/patients/patient-asha/instructions',json=instructions).status_code==200
    login(c)
    state=c.get('/api/patients/patient-asha/workspace').json()
    assert state['brief']['status']=='approved'
    assert state['instructions'][0]['plain']==instructions['plain']
    assert any(a['action']=='Brief approved' for a in state['activity'])
    assert c.post('/api/patients/patient-asha/intake',json={**body,'reason':'Updated concerns for my appointment.'}).status_code==200
    assert c.get('/api/patients/patient-asha/workspace').json()['brief']['status']=='outdated'
    login(c,'clinician')
    assert c.post(f'/api/briefs/{bid}/review',json={'status':'approved','note':'Approve old version.'}).status_code==409

def test_file_validation_and_csrf(client):
    login(client)
    assert client.post('/api/patients/patient-asha/records',files={'file':('x.html',b'<script>bad</script>')}).status_code==422
    assert client.post('/api/patients/patient-asha/records',files={'file':('x.pdf',b'not actually a pdf')}).status_code==422
    assert client.post('/api/patients/patient-asha/records',files={'file':('x.txt',b'x'*(10*1024*1024+1))}).status_code==413
    assert client.post('/api/patients/patient-asha/intake',headers={'Origin':'https://malicious.example'},json={'reason':'some reason'}).status_code==403
    assert client.post('/api/patients/patient-asha/intake',json={'reason':'     '}).status_code==422
    assert client.get('/api/records/absent').status_code==404

def test_unassigned_clinician_and_other_patient_files(client):
    with db.connection() as con:
        con.delete('assignments', {'patient_id':'patient-asha'})
    login(client,'clinician')
    assert client.get('/api/patients/patient-asha/workspace').status_code==403
    assert client.get('/api/records/rec-1/file').status_code==403

def test_instruction_review_required(client):
    login(client,'clinician')
    content={'original':'Bring earlier records.','plain':'Bring earlier records.','confirmed':False}
    assert client.post('/api/patients/patient-asha/instructions',json=content).status_code==422
    assert client.post('/api/patients/patient-asha/instructions',json={**content,'confirmed':True,'language':'hi'}).status_code==422

def test_extractive_is_honest_and_verbatim(monkeypatch):
    monkeypatch.setenv('AI_BACKEND','extractive')
    sources=[{'id':'a','text':'Patient says: tired for two weeks.'}]
    evidence,engine,latency=asyncio.run(organize(sources))
    assert evidence==[{'source_id':'a','quote':sources[0]['text']}]
    assert 'no model' in engine and latency==0

def test_model_rejects_unsupported_output(monkeypatch):
    import app.ai as module
    monkeypatch.setenv('AI_BACKEND','rocm')
    calls=[]
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'message':{'content':json.dumps({'evidence':[{'source_id':'a','quote':'Start a new medication.'}]})}}]}
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):calls.append(kwargs);return Response()
    monkeypatch.setattr(module.httpx,'AsyncClient',Client)
    with pytest.raises(ValueError,match='Unable to verify'):
        asyncio.run(organize([{'id':'a','text':'Patient reported tiredness.'}]))
    assert len(calls)==2

def test_model_rejects_whitespace_and_duplicate_evidence(monkeypatch):
    import app.ai as module
    monkeypatch.setenv('AI_BACKEND','rocm')
    class WhitespaceResponse:
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'message':{'content':json.dumps({'evidence':[{'source_id':'a','quote':'   '}]})}}]}
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,*args,**kwargs): return WhitespaceResponse()
    monkeypatch.setattr(module.httpx,'AsyncClient',Client)
    with pytest.raises(ValueError,match='Unable to verify'):
        asyncio.run(organize([{'id':'a','text':'Patient reported tiredness.'}]))

    class DuplicateResponse:
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'message':{'content':json.dumps({'evidence':[
            {'source_id':'a','quote':'Patient reported tiredness.'},
            {'source_id':'a','quote':'Patient reported tiredness.'}
        ]})}}]}
    class DupClient:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,*args,**kwargs): return DuplicateResponse()
    monkeypatch.setattr(module.httpx,'AsyncClient',DupClient)
    with pytest.raises(ValueError,match='Unable to verify'):
        asyncio.run(organize([{'id':'a','text':'Patient reported tiredness.'}]))

def test_model_envelope_validation_and_retry(monkeypatch):
    import app.ai as module
    monkeypatch.setenv('AI_BACKEND','rocm')
    calls = []
    class Resp0:
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'invalid': 123}]}
    class Resp1:
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'message':{'content':json.dumps({'evidence':[{'source_id':'a','quote':'tiredness'}]})}}]}
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,*args,**kwargs):
            calls.append(kwargs)
            return Resp0() if len(calls) == 1 else Resp1()
    monkeypatch.setattr(module.httpx,'AsyncClient',Client)
    evidence, engine, latency = asyncio.run(organize([{'id':'a','text':'Patient reported tiredness.'}]))
    assert len(calls) == 2
    assert evidence[0]['quote'] == 'tiredness'

def test_model_preserves_negation_context(monkeypatch):
    import app.ai as module
    monkeypatch.setenv('AI_BACKEND','rocm')
    class NegationResponse:
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'message':{'content':json.dumps({'evidence':[{'source_id':'a','quote':'administer amoxicillin'}]})}}]}
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,*args,**kwargs): return NegationResponse()
    monkeypatch.setattr(module.httpx,'AsyncClient',Client)
    source_text = 'Patient has penicillin allergy. Do not administer amoxicillin or related penicillins. Continue observation.'
    evidence, engine, latency = asyncio.run(organize([{'id':'a','text':source_text}]))
    assert evidence[0]['quote'] == 'Do not administer amoxicillin or related penicillins.'

def test_brief_processing_metadata(client):
    login(client)
    client.post('/api/patients/patient-asha/brief')
    state = client.get('/api/patients/patient-asha/workspace').json()
    brief = state['brief']
    assert 'processing' in brief['content']
    proc = brief['content']['processing']
    assert proc['mode'] == 'extractive'
    assert proc['policy_version'] == '1.0'
    assert 'api_key' not in str(brief['content'])
    assert '11434' not in str(brief['content'])

def test_model_timeout_does_not_silently_fallback(client, monkeypatch):
    import app.ai as module
    monkeypatch.setenv('AI_BACKEND', 'rocm')
    class TimeoutClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            raise module.httpx.ConnectError('Connection refused to model endpoint')
    monkeypatch.setattr(module.httpx, 'AsyncClient', TimeoutClient)
    login(client)
    res = client.post('/api/patients/patient-asha/brief')
    assert res.status_code == 503
    assert 'The model is unavailable' in res.json()['detail']
    state = client.get('/api/patients/patient-asha/workspace').json()
    assert state['brief'] is None or state['brief']['status'] != 'pending'

def test_whitespace_model_output_fails_and_saves_no_brief(client, monkeypatch):
    import app.ai as module
    monkeypatch.setenv('AI_BACKEND', 'rocm')
    class WhitespaceResponse:
        def raise_for_status(self): pass
        def json(self):
            return {'choices': [{'message': {'content': json.dumps({'evidence': [{'source_id': 'intake-asha', 'quote': '    '}]})}}]}
    class WSClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return WhitespaceResponse()
    monkeypatch.setattr(module.httpx, 'AsyncClient', WSClient)
    login(client)
    res = client.post('/api/patients/patient-asha/brief')
    assert res.status_code == 503
    state = client.get('/api/patients/patient-asha/workspace').json()
    assert state['brief'] is None or state['brief']['status'] != 'pending'

def test_password_hashes_are_salted():
    one=db.password_hash('example');two=db.password_hash('example')
    assert one!=two
    assert db.verify_password('example',one)
    assert not db.verify_password('wrong',one)

def test_regeneration_supersedes_previous_brief(client):
    login(client)
    first=client.post('/api/patients/patient-asha/brief').json()['id']
    second=client.post('/api/patients/patient-asha/brief').json()['id']
    with db.connection() as con:
        assert con.one('briefs', {'id':first})['status']=='outdated'
    login(client,'clinician')
    assert client.post(f'/api/briefs/{second}/review',json={'status':'approved','note':'   '}).status_code==422
    assert client.get('/api/patients').json()[0]['pending']==1

def test_metadata_invalid_date_is_unknown():
    from app.documents import metadata
    assert metadata('Date: 2026-99-99\nProvider: Synthetic Clinic')['date'] is None
    assert metadata('Date: 2026-10-03')['date']=='2026-10-03'

def test_profile_preference_persists(client):
    login(client)
    assert client.patch('/api/me',json={'language':'kn'}).status_code==200
    assert client.get('/api/me').json()['language']=='kn'
    assert client.patch('/api/me',json={'language':'invalid'}).status_code==422

def test_flagged_brief_also_becomes_stale(client):
    login(client)
    bid=client.post('/api/patients/patient-asha/brief').json()['id']
    login(client,'clinician')
    assert client.post(f'/api/briefs/{bid}/review',json={'status':'flagged','note':'Please clarify the intake.'}).status_code==200
    login(client)
    assert client.post('/api/patients/patient-asha/intake',json={'reason':'Newly clarified patient concerns.'}).status_code==200
    login(client,'clinician')
    assert client.post(f'/api/briefs/{bid}/review',json={'status':'approved','note':'Cannot approve old content.'}).status_code==409

def test_real_image_ocr():
    import io
    import shutil
    from PIL import Image,ImageDraw,ImageFont
    from app.documents import read_document
    if not shutil.which('tesseract'):
        pytest.skip('Tesseract not installed')
    image=Image.new('RGB',(1200,200),'white')
    ImageDraw.Draw(image).text((30,40),'SYNTHETIC DEMO RECORD',fill='black',font=ImageFont.load_default(size=45))
    data=io.BytesIO();image.save(data,format='PNG')
    text,media=read_document(data.getvalue(),'fixture.png')
    assert 'SYNTHETIC' in text and media=='image/png'

def test_text_pdf_extraction():
    from app.documents import read_document
    stream=b'BT /F1 18 Tf 30 700 Td (SYNTHETIC DEMO REPORT) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    pdf=b'%PDF-1.4\n';offsets=[0]
    for index,obj in enumerate(objects,1):
        offsets.append(len(pdf));pdf+=f'{index} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(pdf);pdf+=b'xref\n0 6\n0000000000 65535 f \n'
    for offset in offsets[1:]:pdf+=f'{offset:010d} 00000 n \n'.encode()
    pdf+=f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode()
    text,media=read_document(pdf,'fixture.pdf')
    assert 'SYNTHETIC DEMO REPORT' in text and media=='application/pdf'

def test_profile_edits_are_persistent_and_initials_derived(client):
    login(client)
    response=client.patch('/api/me',json={'name':'Demo Person','age':29,'language':'hi'})
    assert response.status_code==200
    assert response.json()['initials']=='DP'
    assert client.get('/api/me').json()['name']=='Demo Person'
    assert client.get('/api/patients/patient-asha/workspace').json()['patient']['age']==29
    assert client.patch('/api/me',json={'name':'  ','language':'en'}).status_code==422
    assert client.patch('/api/me',json={'age':999,'language':'en'}).status_code==422
    assert client.patch('/api/me',json={'language':'kn'}).json()['age']==29

def test_regional_languages_and_reviewed_translation(client):
    languages = client.get('/api/languages').json()
    assert len(languages) == 28
    assert {item['code'] for item in languages if item['interface']} == {'en', 'hi', 'kn'}
    assert next(item for item in languages if item['code'] == 'ar')['direction'] == 'rtl'
    login(client)
    assert client.post('/api/patients/patient-asha/intake',json={'reason':'Synthetic intake for a Tamil-speaking patient.', 'language':'ta'}).status_code == 200
    assert client.get('/api/patients/patient-asha/workspace').json()['intake']['language'] == 'ta'
    login(client,'clinician')
    body={'original':'Bring earlier records to the appointment.','plain':'Bring your earlier records.','language':'ta','translated':'முந்தைய பதிவுகளை கொண்டு வாருங்கள்.','confirmed':True,'override_reason':'Direct translation for patient appointment'}
    assert client.post('/api/patients/patient-asha/instructions',json=body).status_code == 200
    assert client.get('/api/patients/patient-asha/workspace').json()['instructions'][0]['translated'] == body['translated']
    assert client.post('/api/patients/patient-asha/instructions',json={**body,'language':'invalid'}).status_code == 422

def test_appointment_changes_persist_and_check_ownership(client):
    from datetime import datetime, timedelta, timezone
    login(client)
    body={'clinician':'Synthetic Clinician','specialty':'General medicine','location':'Demo Clinic','starts_at':(datetime.now(timezone.utc)+timedelta(days=10)).isoformat()}
    created=client.post('/api/patients/patient-asha/appointments',json=body)
    assert created.status_code == 200
    aid=created.json()['id']
    assert client.post('/api/patients/patient-asha/appointments',json={**body,'id':aid,'location':'Updated Demo Clinic'}).status_code == 200
    appointments=client.get('/api/patients/patient-asha/workspace').json()['appointments']
    assert next(a for a in appointments if a['id']==aid)['location']=='Updated Demo Clinic'
    assert client.post('/api/patients/patient-kabir/appointments',json=body).status_code == 403
    assert client.post('/api/patients/patient-asha/appointments',json={**body,'id':'appt-kabir'}).status_code == 404
    assert client.post('/api/patients/patient-asha/appointments',json={**body,'starts_at':'2020-01-01T00:00:00Z'}).status_code == 422

def test_upload_bytes_are_in_database_and_transaction_rolls_back(client):
    login(client)
    content=b'SYNTHETIC DEMO document for persistence verification.'
    rid=client.post('/api/patients/patient-asha/records',files={'file':('test.txt',content,'text/plain')}).json()['id']
    with db.connection() as con:
        assert bytes(con.one('files',{'id':rid})['data']) == content
    assert client.get(f'/api/records/{rid}/file').content == content
    with pytest.raises(RuntimeError):
        with db.connection() as con:
            con.insert('files',{'id':'rollback-test','data':b'not committed'})
            raise RuntimeError('Abort transaction')
    with db.connection() as con:
        assert con.one('files',{'id':'rollback-test'}) is None

def test_production_frontend_and_api_share_origin(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    static=root/'frontend'/'dist'
    if not (static/'index.html').exists():
        pytest.skip('Build the frontend before checking production serving')
    code='''
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app, base_url="https://healthbridge.example") as c:
    assert c.get('/').status_code == 200
    assert 'HealthBridge' in c.get('/').text
    accounts=c.get('/api/demo-accounts').json()
    login=c.post('/api/auth/login',json=accounts[0],headers={'Origin':'https://healthbridge.example'})
    assert login.status_code == 200
    assert 'Secure' in login.headers['set-cookie']
    assert c.get('/api/me').status_code == 200
    assert c.post('/api/auth/logout',headers={'Origin':'https://other.example'}).status_code == 403
'''
    result=subprocess.run([sys.executable,'-c',code],cwd=root,env={**os.environ,'PYTHONPATH':str(root/'backend'),'MONGODB_URI':'','DATA_DIR':str(tmp_path),'STATIC_DIR':str(static),'RENDER_EXTERNAL_URL':'https://healthbridge.example','COOKIE_SECURE':'true','DEMO_ENABLED':'true'},capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result.stderr

def test_appointments_sort_by_instant_across_timezones(client):
    login(client)
    base={'clinician':'Synthetic clinician','specialty':'General medicine','location':'Test clinic'}
    # Lexical order is the opposite of the actual chronological order.
    early=client.post('/api/patients/patient-asha/appointments',json={**base,'starts_at':'2099-01-01T10:00:00+05:30'}).json()['id']
    late=client.post('/api/patients/patient-asha/appointments',json={**base,'starts_at':'2099-01-01T08:00:00+00:00'}).json()['id']
    rows=client.get('/api/patients/patient-asha/workspace').json()['appointments']
    ids=[a['id'] for a in rows]
    assert ids.index(early) < ids.index(late)

def register_account(client,email,account_type='patient',**extra):
    return client.post('/api/auth/register',json={'name':'Synthetic New User','email':email,'password':'SyntheticPassword123!','account_type':account_type,**extra})

def test_private_accounts_hospital_invitation_and_isolation(client):
    hospital=register_account(client,'hospital@example.test','hospital',hospital_name='Synthetic Hospital').json()
    assert hospital['role']=='clinician' and hospital['organization']['name']=='Synthetic Hospital'
    assert client.get('/api/patients').json()==[]
    invite=client.post('/api/hospital/invitations',json={'email':'newpatient@example.test'})
    assert invite.status_code==200
    token=invite.json()['invitation']
    with db.connection() as con:
        assert con.one('invitations',{'email':'newpatient@example.test'})['token'] != token
    wrong=register_account(client,'wrong@example.test',invitation=token)
    assert wrong.status_code==422
    with db.connection() as con:
        assert con.one('users',{'email':'wrong@example.test'}) is None
    patient=register_account(client,'newpatient@example.test',invitation=token).json()
    assert patient['organization']['id']==hospital['organization']['id']
    state=client.get(f"/api/patients/{patient['id']}/workspace").json()
    assert state['records']==[] and state['appointments']==[] and state['intake'] is None and state['brief'] is None
    assert client.get('/api/patients/patient-asha/workspace').status_code==403
    assert client.post('/api/hospital/join',json={'invitation':token}).status_code==422
    other=register_account(client,'otherhospital@example.test','hospital',hospital_name='Other Synthetic Hospital').json()
    assert client.get('/api/patients').json()==[]
    assert client.get(f"/api/patients/{patient['id']}/workspace").status_code==403
    assert other['organization']['id']!=hospital['organization']['id']
    assert client.post('/api/auth/login',json={'email':'hospital@example.test','password':'SyntheticPassword123!'}).status_code==200
    assert [p['id'] for p in client.get('/api/patients').json()]==[patient['id']]
    assert client.get(f"/api/patients/{patient['id']}/workspace").status_code==200

def test_registration_validation_and_expired_invitation(client):
    assert register_account(client,'invalid').status_code==422
    assert register_account(client,'a@example.test','hospital',hospital_name=' ').status_code==422
    assert register_account(client,'a@example.test',password='short').status_code==422
    assert register_account(client,'a@example.test').status_code==200
    assert register_account(client,'a@example.test').status_code==409
    assert client.post('/api/hospital/invitations',json={'email':'person@example.test'}).status_code==403
    assert register_account(client,'hospital@example.test','hospital',hospital_name='Demo Clinic').status_code==200
    token=client.post('/api/hospital/invitations',json={'email':'expired@example.test'}).json()['invitation']
    with db.connection() as con:
        con.update('invitations',{'email':'expired@example.test'},{'expires':0})
    assert register_account(client,'expired@example.test',invitation=token).status_code==422

def test_existing_patient_can_accept_email_bound_invitation(client):
    patient=register_account(client,'existing@example.test').json()
    register_account(client,'hospital@example.test','hospital',hospital_name='Example Clinic')
    token=client.post('/api/hospital/invitations',json={'email':'existing@example.test'}).json()['invitation']
    client.post('/api/auth/login',json={'email':'existing@example.test','password':'SyntheticPassword123!'})
    joined=client.post('/api/hospital/join',json={'invitation':token})
    assert joined.status_code==200 and joined.json()['organization']['name']=='Example Clinic'
    assert client.get('/api/me').json()['id']==patient['id']
    assert client.get('/api/me').json()['organization']['name']=='Example Clinic'

def test_password_change_revokes_sessions_and_logout_rejects_replay(client):
    user=register_account(client,'security@example.test').json()
    assert user['is_demo'] is False
    old=client.cookies.get('hb_session')
    client.cookies.clear()
    assert client.post('/api/auth/login',json={'email':user['email'],'password':'SyntheticPassword123!'}).status_code==200
    assert client.post('/api/auth/password',json={'current_password':'wrong','new_password':'ReplacementPassword123!'}).status_code==400
    assert client.post('/api/auth/password',json={'current_password':'SyntheticPassword123!','new_password':'short'}).status_code==422
    assert client.post('/api/auth/password',json={'current_password':'SyntheticPassword123!','new_password':'ReplacementPassword123!'}).status_code==200
    fresh=client.cookies.get('hb_session')
    assert fresh != old and client.get('/api/me').status_code==200
    client.cookies.clear();client.cookies.set('hb_session',old)
    assert client.get('/api/me').status_code==401
    client.cookies.clear()
    assert client.post('/api/auth/login',json={'email':user['email'],'password':'SyntheticPassword123!'}).status_code==401
    assert client.post('/api/auth/login',json={'email':user['email'],'password':'ReplacementPassword123!'}).status_code==200
    assert client.post('/api/auth/logout-all').status_code==200
    client.cookies.clear();client.cookies.set('hb_session',fresh)
    assert client.get('/api/me').status_code==401
    client.cookies.clear()
    login(client)
    demo=client.cookies.get('hb_session')
    assert client.post('/api/auth/password',json={'current_password':'BridgeDemo2026!','new_password':'ReplacementPassword123!'}).status_code==403
    assert client.post('/api/auth/logout').status_code==200
    client.cookies.clear();client.cookies.set('hb_session',demo)
    assert client.get('/api/me').status_code==401

def test_registration_session_is_atomic_and_successful_logins_do_not_rate_limit(client):
    import time
    attempts['testclient']=[time.time()]*12
    created=register_account(client,'atomic@example.test')
    assert created.status_code==200
    assert client.get('/api/me').json()['id']==created.json()['id']
    attempts.clear()
    for _ in range(13):
        assert client.post('/api/auth/login',json={'email':'atomic@example.test','password':'SyntheticPassword123!'}).status_code==200

def test_eight_character_password_boundary_and_invitation_validation(client):
    assert register_account(client,'short@example.test',password='Abcd123').status_code==422
    result=register_account(client,'eight@example.test',password='Abcd1234')
    assert result.status_code==200
    assert client.post('/api/auth/password',json={'current_password':'Abcd1234','new_password':'Efgh5678'}).status_code==200
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login',json={'email':'eight@example.test','password':'Efgh5678'}).status_code==200
    register_account(client,'owner@example.test','hospital',hospital_name='Synthetic Clinic')
    assert client.post('/api/hospital/invitations',json={'email':'owner@example.test'}).status_code==409
    token=client.post('/api/hospital/invitations',json={'email':'eight@example.test'}).json()['invitation']
    client.post('/api/auth/login',json={'email':'eight@example.test','password':'Efgh5678'})
    assert client.post('/api/hospital/join',json={'invitation':' '+token+' '}).status_code==200

def test_upload_job_lifecycle_and_idempotency(client):
    import time
    login(client)
    payload = b'SYNTHETIC DEMO DATA\nDate: 2026-10-04\nProvider: Job Test Clinic\nVisit note\nPatient feels better.'
    files = {'file': ('job_test.txt', payload, 'text/plain')}
    data = {'idempotency_key': 'job-key-123', 'ocr_lang': 'en'}
    
    resp = client.post('/api/patients/patient-asha/upload-jobs', files=files, data=data)
    assert resp.status_code == 202
    job_id = resp.json()['id']
    
    # Idempotent re-submission returns identical job
    resp2 = client.post('/api/patients/patient-asha/upload-jobs', files=files, data=data)
    assert resp2.status_code == 202
    assert resp2.json()['id'] == job_id

    # Wait for background job to finish
    for _ in range(20):
        check = client.get(f'/api/upload-jobs/{job_id}')
        assert check.status_code == 200
        state = check.json()['state']
        if state in ('completed', 'failed'):
            break
        time.sleep(0.05)
    
    assert check.json()['state'] == 'completed'
    record_id = check.json()['record_id']
    assert record_id is not None
    
    # Verify provenance
    rec = client.get(f'/api/records/{record_id}').json()
    assert 'extraction' in rec
    assert rec['extraction']['method'] == 'direct_text'
    assert len(rec['extraction']['pages']) == 1

def test_record_metadata_and_text_corrections(client):
    login(client)
    uploaded = client.post('/api/patients/patient-asha/records', files={'file': ('corr.txt', b'SYNTHETIC\nDate: 2026-10-01\nProvider: Unknown\nVisit note\nPatient reports rash.', 'text/plain')})
    assert uploaded.status_code == 200
    rid = uploaded.json()['id']
    
    # Patient cannot modify clinical metadata
    meta_body = {'kind': 'Referral', 'date': '2026-10-02', 'provider': 'Verified Clinic', 'reason': 'Checked letterhead', 'expected_version': 1}
    assert client.patch(f'/api/records/{rid}/metadata', json=meta_body).status_code == 403

    client.post('/api/auth/logout')
    login(client, 'clinician')
    
    # Clinician modifies metadata
    patch_resp = client.patch(f'/api/records/{rid}/metadata', json=meta_body)
    assert patch_resp.status_code == 200
    updated_rec = patch_resp.json()
    assert updated_rec['kind'] == 'Referral'
    assert updated_rec['provider'] == 'Verified Clinic'
    assert len(updated_rec['corrections']) == 1
    assert updated_rec['corrections'][0]['version'] == 2

    # Stale expected_version conflict
    assert client.patch(f'/api/records/{rid}/metadata', json=meta_body).status_code == 409

    # Clinician modifies text
    text_body = {'text': 'SYNTHETIC\nDate: 2026-10-01\nProvider: Verified Clinic\nVisit note\nPatient reports rash has cleared.', 'reason': 'Transcription update', 'expected_version': 2}
    txt_resp = client.post(f'/api/records/{rid}/corrections', json=text_body)
    assert txt_resp.status_code == 200
    updated_text_rec = txt_resp.json()
    assert 'cleared' in updated_text_rec['text']
    assert len(updated_text_rec['corrections']) == 2
    assert updated_text_rec['corrections'][1]['version'] == 3

def test_structured_brief_schema_and_coverage(client):
    login(client)
    # Add multiple dummy records to test record cap (> 12 records)
    for i in range(10):
        client.post('/api/patients/patient-asha/records', files={'file': (f'rec_{i}.txt', f'Record {i} text.'.encode('utf-8'), 'text/plain')})

    # Add a multi-paragraph long document with late facts as the latest record
    long_doc = "Initial clinical evaluation.\n\n" + ("Routine observation. " * 120) + "\n\nImportant late finding: Patient confirmed severe penicillin rash."
    uploaded = client.post('/api/patients/patient-asha/records', files={'file': ('long.txt', long_doc.encode('utf-8'), 'text/plain')})
    assert uploaded.status_code == 200

    # Prepare brief
    res = client.post('/api/patients/patient-asha/brief')
    assert res.status_code == 200
    state = client.get('/api/patients/patient-asha/workspace').json()
    brief = state['brief']
    content = brief['content']

    assert content['schema_version'] == '2.0'
    assert 'source_revision' in content
    sections = {s['key']: s for s in content['sections']}
    assert set(sections.keys()) == {'reason_questions', 'medications_allergies', 'recorded_history', 'information_to_confirm'}

    # Verify coverage reporting
    coverage = content['coverage']
    assert coverage['available_records'] >= 13
    assert coverage['included_records'] == 12
    assert len(coverage['excluded_sources']) >= 1
    assert any('Exceeds default limit' in s['reason'] for s in coverage['excluded_sources'])
    assert any(s['title'] == 'long' for s in coverage['shortened_sources'])

    # Late fact from long record must be included
    history_texts = " ".join(item['text'] for item in sections['recorded_history']['items'])
    assert 'penicillin rash' in history_texts.lower()

def test_differing_allergy_statements_surface_as_uncertainty(client):
    login(client)
    client.post('/api/patients/patient-asha/intake', json={
        'reason': 'Check allergies before appointment',
        'duration': '1 week',
        'medications': 'None',
        'allergies': 'Penicillin — patient reported, needs confirmation',
        'questions': 'Can I take alternatives?',
        'language': 'en'
    })
    res = client.post('/api/patients/patient-asha/brief')
    assert res.status_code == 200
    brief = client.get('/api/patients/patient-asha/workspace').json()['brief']
    uncertainties = brief['content']['uncertainties']
    
    # Must contain conflicting_sources uncertainty
    conflict = next((u for u in uncertainties if u['kind'] == 'conflicting_sources'), None)
    assert conflict is not None
    assert conflict['description'] == 'Statements differ; confirm with a clinician.'
    assert len(conflict['citations']) >= 2
    assert conflict['status'] == 'unresolved'

def test_clarification_lifecycle_and_unauthorized_resolution(client):
    login(client, 'clinician')
    brief_id = client.post('/api/patients/patient-asha/brief').json()['id']
    
    # Clinician asks a clarification
    create_res = client.post('/api/patients/patient-asha/clarifications', json={
        'brief_id': brief_id,
        'question': 'Did your rash occur immediately after amoxicillin or hours later?',
        'originating_uncertainty_id': 'unc-allergy-conflict'
    })
    assert create_res.status_code == 200
    cid = create_res.json()['id']

    # Patient responds
    client.post('/api/auth/logout')
    login(client)
    msg_res = client.post(f'/api/clarifications/{cid}/messages', json={'text': 'It started about two hours after taking the capsule.'})
    assert msg_res.status_code == 200

    # Patient cannot resolve clarification
    assert client.post(f'/api/clarifications/{cid}/resolve', json={'reason': 'I answered it.'}).status_code == 403

    # Clinician resolves
    client.post('/api/auth/logout')
    login(client, 'clinician')
    res_resolve = client.post(f'/api/clarifications/{cid}/resolve', json={'reason': 'Patient confirmed delayed cutaneous reaction; avoid penicillin class.'})
    assert res_resolve.status_code == 200
    assert res_resolve.json()['status'] == 'resolved'

    # Check in workspace
    state = client.get('/api/patients/patient-asha/workspace').json()
    clar = next(c for c in state['clarifications'] if c['id'] == cid)
    assert clar['status'] == 'resolved'
    assert len(clar['messages']) == 2

def test_instruction_publication_policy_and_acknowledgement(client):
    login(client, 'clinician')
    brief_id = client.post('/api/patients/patient-asha/brief').json()['id']

    # Open a clarification so there is an unresolved item
    cid = client.post('/api/patients/patient-asha/clarifications', json={
        'brief_id': brief_id,
        'question': 'Please confirm previous hospital name.'
    }).json()['id']

    inst_body = {
        'original': 'Avoid all penicillin-related antibiotics until further evaluation.',
        'plain': 'Do not take penicillin or amoxicillin. Use the prescribed alternative.',
        'language': 'en',
        'confirmed': True
    }

    # Attempt to publish without approved brief and with unresolved clarification -> 422
    assert client.post('/api/patients/patient-asha/instructions', json=inst_body).status_code == 422

    # Clinician provides explicit override -> 200
    override_body = {**inst_body, 'override_reason': 'Urgent allergy safety instruction published prior to clarification.'}
    overridden = client.post('/api/patients/patient-asha/instructions', json=override_body)
    assert overridden.status_code == 200
    inst_id_1 = overridden.json()['id']
    assert overridden.json()['version'] == 1

    # Clinician approves brief and resolves clarification
    client.post(f'/api/clarifications/{cid}/resolve', json={'reason': 'Verified with hospital records.'})
    client.post(f'/api/briefs/{brief_id}/review', json={'status': 'approved', 'note': 'All sources verified.'})

    # Now publication succeeds without override reason (creating v2 as a correction)
    v2_body = {**inst_body, 'plain': 'Do not take penicillin. Cephalosporin allergy test scheduled.', 'previous_version_id': inst_id_1}
    v2_res = client.post('/api/patients/patient-asha/instructions', json=v2_body)
    assert v2_res.status_code == 200
    assert v2_res.json()['version'] == 2
    inst_id_2 = v2_res.json()['id']

    # Patient acknowledges v2
    client.post('/api/auth/logout')
    login(client)
    ack_res = client.post(f'/api/instructions/{inst_id_2}/acknowledge', json={'status': 'acknowledged'})
    assert ack_res.status_code == 200
    assert ack_res.json()['status'] == 'acknowledged'

    # Clinician withdraws v2
    client.post('/api/auth/logout')
    login(client, 'clinician')
    w_res = client.post(f'/api/instructions/{inst_id_2}/withdraw', json={'reason': 'Superceded by specialist appointment plan.'})
    assert w_res.status_code == 200
    assert w_res.json()['status'] == 'withdrawn'


