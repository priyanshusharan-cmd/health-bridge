// Real HTTP test of the frontend API client through Vite to an isolated FastAPI DB.
import { spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import assert from 'node:assert/strict';
const root=resolve(import.meta.dirname,'../..');
const data=await mkdtemp(join(tmpdir(),'healthbridge-integration-'));
const origin='http://127.0.0.1:15173';
let logs='';
const start=(bin,args,env)=>{const proc=spawn(bin,args,{cwd:root,env:{...process.env,...env},stdio:['ignore','pipe','pipe']});proc.stdout.on('data',d=>logs+=d);proc.stderr.on('data',d=>logs+=d);return proc;};
const mongo=process.env.HEALTHBRIDGE_TEST_MONGO==='1';
const database='healthbridge_e2e_'+Date.now();
const backend=start(join(root,'.venv/bin/uvicorn'),['app.main:app','--app-dir','backend','--host','127.0.0.1','--port','18000'],{...(mongo?{}:{MONGODB_URI:''}),MONGODB_DATABASE:database,DATA_DIR:data,AI_BACKEND:'extractive',DEMO_ENABLED:'true',CORS_ORIGINS:origin});
const frontend=start(process.execPath,['frontend/node_modules/vite/bin/vite.js','frontend','--host','127.0.0.1','--port','15173','--strictPort'],{API_PROXY_TARGET:'http://127.0.0.1:18000'});
const nativeFetch=globalThis.fetch;
try {
 let ready=false;
 for(let i=0;i<60;i++){try{const r=await nativeFetch(origin+'/api/health');if(r.ok){ready=true;break;}}catch{} await new Promise(r=>setTimeout(r,150));}
 assert.ok(ready,'Local servers did not start: '+logs);
 let cookie='';
 globalThis.fetch=async(path,options={})=>{
   const response=await nativeFetch(origin+path,{...options,headers:{...options.headers,Origin:origin,...(cookie?{Cookie:cookie}:{})}});
   const value=response.headers.get('set-cookie');if(value)cookie=value.split(';')[0];
   return response;
 };
 const {api,post}=await import('../src/api.ts');
 assert.equal((await api('/health')).database,mongo?'mongodb':'sqlite');
 assert.equal((await api('/languages')).length,28);
 const accounts=await api('/demo-accounts');
 const patient=accounts.find(a=>a.role==='patient'),doctor=accounts.find(a=>a.role==='clinician');
 const user=await post('/auth/login',patient);
 const path=`/patients/${user.id}`;
 await api('/me',{method:'PATCH',body:JSON.stringify({language:'hi'})});
 assert.equal((await api('/me')).language,'hi');
 const profile=await api('/me',{method:'PATCH',body:JSON.stringify({name:'Demo Tester',age:31,language:'kn'})});
 assert.equal(profile.initials,'DT');
 assert.equal((await api(path+'/workspace')).patient.name,'Demo Tester');
 assert.equal((await api('/me')).language,'kn');
 await post(path+'/intake',{reason:'Synthetic integration concern from frontend client',questions:'Which records should I bring?',language:'hi'});
 const appointment=await post(path+'/appointments',{clinician:'Synthetic E2E Clinician',specialty:'General medicine',location:'Synthetic Clinic',starts_at:new Date(Date.now()+86400000).toISOString()});
 assert.ok((await api(path+'/workspace')).appointments.some(a=>a.id===appointment.id));
 const file=new FormData();file.append('file',new Blob(['SYNTHETIC DEMO DATA\nDate: 2026-10-03\nProvider: Integration Clinic\nVisit note\nBring earlier records.']), 'integration.txt');
 const record=await api(path+'/records',{method:'POST',body:file});
 assert.ok((await api(`/records/${record.id}`)).text.includes('Integration Clinic'));
 const brief=await post(path+'/brief');
 await assert.rejects(()=>post(`/briefs/${brief.id}/review`,{status:'approved',note:'Checked source'}),/Clinician/);
 await post('/auth/logout');
 await post('/auth/login',doctor);
 await post(`/briefs/${brief.id}/review`,{status:'approved',note:'Synthetic source checked by integration test.'});
 await post(path+'/instructions',{original:'Please bring your previous reports to the next visit.',plain:'Bring your earlier reports to your next visit.',language:'en',confirmed:true});
 await post('/auth/logout');await post('/auth/login',patient);
 const workspace=await api(path+'/workspace');
 assert.equal(workspace.brief.status,'approved');
 assert.equal(workspace.instructions[0].plain,'Bring your earlier reports to your next visit.');
 assert.ok(workspace.activity.some(a=>a.action==='Brief approved'));
 const raw=await nativeFetch(origin+`/api/records/${record.id}/file`,{headers:{Cookie:cookie}});
 assert.ok((await raw.text()).includes('Integration Clinic'));
 const hospital=await post('/auth/register',{name:'Synthetic Clinic Owner',email:'owner@integration.test',password:'SyntheticPassword123!',account_type:'hospital',hospital_name:'Integration Hospital'});
 assert.equal(hospital.role,'clinician');
 assert.equal((await api('/patients')).length,0);
 const invite=await post('/hospital/invitations',{email:'newpatient@integration.test'});
 const fresh=await post('/auth/register',{name:'Synthetic New Patient',email:'newpatient@integration.test',password:'Abcd1234',account_type:'patient',invitation:invite.invitation});
 assert.equal(fresh.organization.id,hospital.organization.id);
 await post('/auth/password',{current_password:'Abcd1234',new_password:'Efgh5678'});
 await post('/auth/logout');
 await post('/auth/login',{email:'newpatient@integration.test',password:'Efgh5678'});
 assert.equal((await api('/me')).id,fresh.id);
 assert.equal((await api(`/patients/${fresh.id}/workspace`)).records.length,0);
 await assert.rejects(()=>api(path+'/workspace'),/not assigned/);
 await post('/auth/login',{email:'owner@integration.test',password:'SyntheticPassword123!'});
 assert.ok((await api('/patients')).some(p=>p.id===fresh.id));
 console.log(`PASS: frontend API → Vite → FastAPI → ${mongo?'Atlas':'SQLite'}: profile, regional languages, appointments, intake, files, brief, permissions, review, instructions, audit, private signup, hospital invitation.`);
} finally {
 globalThis.fetch=nativeFetch;
 for(const child of [frontend,backend])child.kill('SIGTERM');
 await Promise.all([frontend,backend].map(child=>child.exitCode!==null?Promise.resolve():new Promise(r=>child.once('exit',r))));
 if(mongo) {
  const cleanup=start(join(root,'.venv/bin/python'),['scripts/cleanup_test_database.py',database],{});
  const code=await new Promise(r=>cleanup.once('exit',r));
  assert.equal(code,0,'Temporary Atlas database cleanup failed');
 }
 await rm(data,{recursive:true,force:true});
}
