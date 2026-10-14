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
 // Asynchronous upload queue with idempotency
 const jobForm=new FormData();jobForm.append('file',new Blob(['SYNTHETIC LAB REPORT\nDate: 2026-10-04\nProvider: Lab Service\nBlood glucose 95 mg/dL.']), 'lab.txt');
 jobForm.append('ocr_lang','en');
 jobForm.append('idempotency_key','idem-integration-1');
 const queuedJob=await api(path+'/upload-jobs',{method:'POST',body:jobForm});
 assert.ok(queuedJob.id);
 const reQueuedJob=await api(path+'/upload-jobs',{method:'POST',body:jobForm});
 assert.equal(reQueuedJob.id,queuedJob.id);
 let finishedJob;
 for(let i=0;i<40;i++){
   finishedJob=await api(`/upload-jobs/${queuedJob.id}`);
   if(finishedJob.state==='completed')break;
   await new Promise(r=>setTimeout(r,150));
 }
 assert.equal(finishedJob.state,'completed');
 assert.ok(finishedJob.record_id);
 const brief=await post(path+'/brief');
 await assert.rejects(()=>post(`/briefs/${brief.id}/review`,{status:'approved',note:'Checked source'}),/Clinician/);
 await post('/auth/logout');
 await post('/auth/login',doctor);
 // Metadata and text corrections on extracted record by clinician
 const metaCorr=await api(`/records/${finishedJob.record_id}/metadata`,{
   method:'PATCH',
   body:JSON.stringify({
     kind:'Lab report',
     date:'2026-10-04',
     provider:'Corrected Lab Clinic',
     reason:'Provider typo correction',
     expected_version:1
   })
 });
 assert.equal(metaCorr.corrections.length,1);
 assert.equal(metaCorr.provider,'Corrected Lab Clinic');

 const textCorr=await post(`/records/${finishedJob.record_id}/corrections`,{
   text:(await api(`/records/${finishedJob.record_id}`)).text + '\nClinician reviewed.',
   reason:'Added reviewed note to text',
   expected_version:2
 });
 assert.equal(textCorr.corrections.length,2);

 await assert.rejects(
   ()=>post(`/briefs/${brief.id}/review`,{status:'approved',note:'Checked source'}),
   /outdated/
 );
 const currentBrief=await post(path+'/brief');
 await post(`/briefs/${currentBrief.id}/review`,{status:'approved',note:'Synthetic source checked by integration test.'});
 const inst1=await post(path+'/instructions',{original:'Please bring your previous reports to the next visit.',plain:'Bring your earlier reports to your next visit.',language:'en',confirmed:true});
 assert.equal(inst1.version,1);

 // Patient requests clarification via acknowledgment
 await post('/auth/logout');await post('/auth/login',patient);
 await post(`/instructions/${inst1.id}/acknowledge`,{status:'needs_clarification',question:'Should I bring blood reports or scan reports?'});
 const ws1=await api(path+'/workspace');
 const clarThread=ws1.clarifications.find(c=>c.question.includes('blood reports or scan reports'));
 assert.ok(clarThread,'Clarification thread should be created from patient question');
 assert.equal(clarThread.status,'open');

 // Clinician replies and resolves clarification thread
 await post('/auth/logout');await post('/auth/login',doctor);
 await post(`/clarifications/${clarThread.id}/messages`,{text:'Please bring both sets of reports.'});
 await post(`/clarifications/${clarThread.id}/resolve`,{reason:'Advised patient on report types needed.'});

 // Clinician publishes version 2 superseding version 1
 const inst2=await post(path+'/instructions',{
   original:'Please bring all blood and scan reports to the next visit.',
   plain:'Bring all your blood and scan reports to your next visit.',
   language:'en',
   previous_version_id:inst1.id,
   confirmed:true
 });
 assert.equal(inst2.version,2);

 // Foreign instruction supersession is rejected with 403 Forbidden
 await assert.rejects(
   ()=>post(`/patients/patient-kabir/instructions`,{
     original:'Foreign supersession attempt',
     plain:'Foreign supersession attempt',
     language:'en',
     previous_version_id:inst2.id,
     confirmed:true
   }),
   /belonging to another patient|403/
 );

 // Draft instruction is hidden from patient workspace and cannot be acknowledged
 const draftInst=await post(path+'/instructions',{
   original:'Draft unreviewed note.',
   plain:'Draft unreviewed note.',
   language:'en',
   status:'draft',
   confirmed:true
 });

 await post('/auth/logout');await post('/auth/login',patient);
 const workspace=await api(path+'/workspace');
 assert.equal(workspace.brief.status,'approved');
 assert.ok(!workspace.instructions.some(i=>i.id===draftInst.id),'Draft instruction must not leak to patient');
 await assert.rejects(
   ()=>post(`/instructions/${draftInst.id}/acknowledge`,{status:'acknowledged'}),
   /Only published instructions can be acknowledged|422/
 );
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
 const unlinkRes=await post(`/hospital/assignments/${fresh.id}/unlink`,{});
 assert.equal(unlinkRes.unlinked,true);
 console.log(`PASS: frontend API → Vite → FastAPI → ${mongo?'Atlas':'SQLite'}: profile, regional languages, appointments, intake, files, upload jobs, corrections, clarifications, instruction versioning, draft protection, foreign supersession prevention, brief, permissions, review, audit, private signup, hospital invitation, assignment unlinking.`);
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
