import test from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
const bundle=buildSync({entryPoints:[new URL('../src/api.ts',import.meta.url).pathname],bundle:true,platform:'node',format:'cjs',write:false}).outputFiles[0].text;
const module={exports:{}};new Function('module','exports',bundle)(module,module.exports);
const {api}=module.exports;
test('API reports a readable connection failure', async()=>{
 const previous=globalThis.fetch;
 globalThis.fetch=async()=>{throw new TypeError('fetch failed');};
 try {await assert.rejects(()=>api('/health'),/Cannot reach the server/);}finally{globalThis.fetch=previous;}
});
test('API reports timeouts and preserves caller cancellation',async()=>{
 const previous=globalThis.fetch;
 globalThis.fetch=async()=>{throw new DOMException('deadline','TimeoutError');};
 try {
  await assert.rejects(()=>api('/health'),/request timed out/);
  const controller=new AbortController();controller.abort();
  const cancellation=new DOMException('cancelled','AbortError');
  globalThis.fetch=async()=>{throw cancellation;};
  await assert.rejects(()=>api('/health',{signal:controller.signal}),error=>error===cancellation);
 }finally{globalThis.fetch=previous;}
});
test('API keeps upload boundaries and returns server validation messages',async()=>{
 const previous=globalThis.fetch;
 globalThis.fetch=async(path,options)=>{
  assert.ok(options.body instanceof FormData);
  assert.equal(options.headers,undefined);
  assert.equal(options.credentials,'same-origin');
  return new Response(JSON.stringify({detail:'Readable document required.'}),{status:422,headers:{'Content-Type':'application/json'}});
 };
 try {await assert.rejects(()=>api('/records',{method:'POST',body:new FormData()}),/Readable document required/);}finally{globalThis.fetch=previous;}
});
test('expired PATCH /me dispatches session expiry while initial GET /me does not', async () => {
 const previous=globalThis.fetch;
 let dispatched=0;
 globalThis.window = {
  dispatchEvent: (evt) => {
   if (evt.type === 'healthbridge-session-expired') dispatched++;
  }
 };
 globalThis.Event = class { constructor(type) { this.type = type; } };
 globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Session expired' }), { status: 401, headers: { 'Content-Type': 'application/json' } });
 try {
  await assert.rejects(() => api('/me'));
  assert.equal(dispatched, 0, 'initial GET /me must not dispatch session expiry');
  await assert.rejects(() => api('/me', { method: 'PATCH', body: JSON.stringify({ language: 'hi' }) }));
  assert.equal(dispatched, 1, 'expired PATCH /me must dispatch session expiry');
 } finally {
  globalThis.fetch = previous;
  delete globalThis.window;
  delete globalThis.Event;
 }
});
