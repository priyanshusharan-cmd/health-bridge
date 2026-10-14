"""Private hospital workspaces and email-bound patient invitations."""
import hashlib
import re
import secrets
import sqlite3
import time
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from pymongo.errors import DuplicateKeyError
from . import db
from .main import current_user, public, clinician, issue_session, attempts
router = APIRouter()

class Email(BaseModel):
    email: str = Field(max_length=200)

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        value=value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):
            raise ValueError('Enter a valid email address.')
        return value

class Registration(Email):
    name: str = Field(min_length=2,max_length=100)
    password: str = Field(min_length=8,max_length=200)
    account_type: Literal['patient','hospital']
    hospital_name: str = Field(default='',max_length=160)
    language: Literal['en','hi','kn'] = 'en'
    invitation: str = Field(default='',max_length=200)

    @field_validator('name')
    @classmethod
    def valid_name(cls,value):
        if len(value.strip())<2: raise ValueError('Enter your full name.')
        return value.strip()

class InvitationCode(BaseModel):
    invitation: str = Field(min_length=20,max_length=200)

def accept(con, token, email, patient_id):
    token=token.strip()
    invitation=con.one('invitations',{'token':hashlib.sha256(token.encode()).hexdigest()})
    if not invitation or invitation['expires'] <= time.time() or invitation['accepted_by'] or invitation['email'] != email:
        raise HTTPException(422,'This invitation is invalid, expired, already used, or belongs to another email address.')
    if con.one('memberships',{'user_id':patient_id}):
        raise HTTPException(409,'This account already belongs to a hospital workspace.')
    con.insert('memberships',dict(id=secrets.token_hex(12),user_id=patient_id,organization_id=invitation['organization_id']))
    con.insert('assignments',dict(clinician_id=invitation['clinician_id'],patient_id=patient_id))
    con.update('invitations',{'id':invitation['id']},{'accepted_by':patient_id})
    db.audit(con,patient_id,'HealthBridge','Hospital joined','Patient accepted an invitation to their care workspace.')

@router.post('/api/auth/register')
def register(body: Registration, request: Request, response: Response):
    address='register:'+(request.client.host if request.client else 'unknown')
    attempts[address]=[stamp for stamp in attempts[address] if stamp > time.time()-60]
    if len(attempts[address])>=8: raise HTTPException(429,'Too many attempts. Try again in a minute.')
    attempts[address].append(time.time())
    if body.account_type=='hospital' and len(body.hospital_name.strip())<2:
        raise HTTPException(422,'Enter your hospital or clinic name.')
    if body.account_type=='hospital' and body.invitation:
        raise HTTPException(422,'Patient invitations cannot create hospital accounts.')
    uid=secrets.token_hex(12)
    try:
        with db.connection() as con:
            if con.one('users',{'email':body.email}): raise HTTPException(409,'An account with this email already exists. Please sign in.')
            con.insert('users',dict(id=uid,name=body.name,email=body.email,password=db.password_hash(body.password),role='clinician' if body.account_type=='hospital' else 'patient',language=body.language,age=None,initials=''.join(word[0] for word in body.name.split()[:2]).upper()))
            if body.account_type=='hospital':
                oid=secrets.token_hex(12)
                con.insert('organizations',dict(id=oid,name=body.hospital_name.strip(),created_at=db.now()))
                con.insert('memberships',dict(id=secrets.token_hex(12),user_id=uid,organization_id=oid))
            elif body.invitation:
                accept(con,body.invitation,body.email,uid)
            issue_session(con,uid,request,response)
            created=con.one('users',{'id':uid})
    except (DuplicateKeyError,sqlite3.IntegrityError):
        raise HTTPException(409,'An account with this email already exists. Please sign in.') from None
    return public(created)

@router.post('/api/hospital/invitations')
def invite(body:Email,user=Depends(current_user)):
    clinician(user)
    token=secrets.token_urlsafe(32)
    with db.connection() as con:
        membership=con.one('memberships',{'user_id':user['id']})
        if not membership: raise HTTPException(403,'Create a hospital account to invite patients.')
        if con.count('invitations',{'clinician_id':user['id'],'expires':{'$gt':time.time()},'accepted_by':None})>=30:
            raise HTTPException(429,'Invitation limit reached. Please use your existing invitations.')
        existing=con.one('users',{'email':body.email})
        if existing and (existing['role']!='patient' or con.one('memberships',{'user_id':existing['id']})):
            raise HTTPException(409,'This email cannot accept a patient invitation. Use an unassigned patient account.')
        expires=time.time()+86400
        con.insert('invitations',dict(id=secrets.token_hex(12),token=hashlib.sha256(token.encode()).hexdigest(),organization_id=membership['organization_id'],clinician_id=user['id'],email=body.email,expires=expires,accepted_by=None))
    return {'invitation':token,'email':body.email,'expires':expires}

@router.post('/api/hospital/join')
def join(body:InvitationCode,user=Depends(current_user)):
    if user['role']!='patient': raise HTTPException(403,'Only patient accounts can accept patient invitations.')
    with db.connection() as con: accept(con,body.invitation,user['email'],user['id'])
    return public(user)

@router.get('/api/hospital/invitations')
def list_invitations(user=Depends(current_user)):
    clinician(user)
    with db.connection() as con:
        rows = con.find('invitations', {'clinician_id': user['id']}, sort=[('expires', -1)])
        return [{
            'id': r['id'],
            'email': r['email'],
            'expires': r['expires'],
            'accepted_by': r['accepted_by'],
            'status': 'accepted' if r['accepted_by'] else ('expired' if r['expires'] <= time.time() else 'active')
        } for r in rows]

@router.delete('/api/hospital/invitations/{invitation_id}')
def revoke_invitation(invitation_id: str, user=Depends(current_user)):
    clinician(user)
    with db.connection() as con:
        inv = con.one('invitations', {'id': invitation_id, 'clinician_id': user['id']})
        if not inv:
            raise HTTPException(404, 'Invitation not found.')
        if inv['accepted_by']:
            raise HTTPException(400, 'Cannot revoke an already accepted invitation.')
        con.delete('invitations', {'id': invitation_id})
        return {'ok': True, 'revoked': True}

@router.post('/api/hospital/assignments/{patient_id}/unlink')
def unlink_assignment(patient_id: str, user=Depends(current_user)):
    with db.connection() as con:
        if user['role'] == 'clinician':
            clinician_id = user['id']
            assign = con.one('assignments', {'clinician_id': clinician_id, 'patient_id': patient_id})
        else:
            if user['id'] != patient_id:
                raise HTTPException(403, 'You can only manage your own care assignments.')
            assign = con.one('assignments', {'patient_id': patient_id})
            clinician_id = assign['clinician_id'] if assign else None

        if not assign:
            raise HTTPException(404, 'Assignment not found.')

        con.delete('assignments', {'clinician_id': clinician_id, 'patient_id': patient_id})
        # If no active assignments remain for the patient, clear hospital membership to allow transfer/reassignment
        remaining = con.find('assignments', {'patient_id': patient_id})
        if not remaining:
            con.delete('memberships', {'user_id': patient_id})
        db.audit(con, patient_id, user['name'], 'Assignment unlinked', f'Clinician {clinician_id} unlinked from patient {patient_id}.')
        return {'ok': True, 'unlinked': True}
