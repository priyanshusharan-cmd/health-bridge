import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {buildSync} from 'esbuild';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const bundle=buildSync({stdin:{contents:`export {Login} from './src/App';export {PasswordField} from './src/PasswordField';export {date} from './src/ui';export {ActivityLog} from './src/pages';export {Account,Privacy} from './src/Account';export {LocaleContext,translate} from './src/locale';`,resolveDir:new URL('..',import.meta.url).pathname,loader:'tsx'},bundle:true,platform:'node',format:'cjs',write:false,jsx:'automatic',packages:'external'}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',bundle)(require,module,module.exports);
const {ActivityLog,Account,Privacy,LocaleContext,translate}=module.exports;
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const render=(language,Component,props)=>renderToStaticMarkup(React.createElement(LocaleContext.Provider,{value:language},React.createElement(Component,props)));
for(const language of ['hi','kn']) {
 test(`${language}: activity heading, event label and dates are localized`,()=>{
  const html=render(language,ActivityLog,{w:{activity:[{id:1,action:'Brief prepared',detail:'Source excerpts · no model used',actor:'Synthetic Person',created_at:'2026-10-03T09:00:00Z'}]}});
  assert.ok(!html.includes('A transparent trail of care.'));
  assert.ok(!html.includes('Brief prepared'));
  assert.ok(html.includes(translate('Brief prepared',language)));
  assert.ok(html.includes('Synthetic Person'));
 });
 test(`${language}: profile and privacy are localized without changing account data`,()=>{
  const html=render(language,Account,{user:{name:'Synthetic Person',initials:'SP',age:30,email:'synthetic@example.test',role:'patient',language},onSaved:async()=>{}});
  assert.ok(html.includes(translate('Save profile',language)));
  assert.ok(html.includes('synthetic@example.test'));
  assert.ok(render(language,Privacy,{}).includes(translate('What is stored',language)));
 });
}
test('unknown clinical source text is preserved exactly',()=>{const source='Patient reports tiredness for two weeks.';assert.equal(translate(source,'hi'),source);assert.equal(translate(source,'kn'),source);});
test('all explicit UI translation keys have both languages',()=>{
 const catalog=JSON.parse(fs.readFileSync(new URL('../src/locales/ui.json',import.meta.url)));
 for(const file of ['App','Account','ThemeToggle','forms','pages','ui','LanguageSelect','AppointmentForm','Onboarding','PasswordField','AccountSecurity']){
  const source=fs.readFileSync(new URL(`../src/${file}.tsx`,import.meta.url),'utf8');
  for(const [,key] of source.matchAll(/tr\("([^"\n]+)"\)/g)){
   assert.ok(catalog[key]?.hi&&catalog[key]?.kn,`${file}: missing ${key}`);
  }
 }
});

test('document calendar dates do not shift in western timezones',()=>{
 const previous=process.env.TZ;
 process.env.TZ='America/Los_Angeles';
 try {
   assert.equal(module.exports.date('2026-10-06',{day:'numeric'},'en'),'6');
 } finally {
   if(previous === undefined) delete process.env.TZ; else process.env.TZ=previous;
 }
});

test('login headings retain spaces when responsive line breaks disappear',()=>{
 globalThis.window={location:{hash:'',search:''}};
 globalThis.document={documentElement:{dataset:{theme:'light'}}};
 try {
  const html=render('en',module.exports.Login,{connected:true,onLogin:()=>{},onRetry:async()=>{}});
  const text=html.replace(/<[^>]*>/g,'');
  assert.ok(text.includes('to better care.'));
  assert.ok(text.includes('Good care starts with understanding.'));
 } finally {delete globalThis.window;delete globalThis.document;}
});
test('password controls start masked with an accessible reveal action',()=>{
 const html=render('en',module.exports.PasswordField,{name:'password',label:'Password'});
 assert.ok(html.includes('type="password"'));
 assert.ok(html.includes('aria-label="Show password"'));
 assert.ok(/autocomplete="current-password"/i.test(html));
});
