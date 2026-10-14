import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const script=readFileSync(new URL('../public/theme.js',import.meta.url),'utf8');
for (const [saved,system,expected] of [['dark',false,'dark'],['light',true,'light'],[null,true,'dark'],['invalid',false,'light']]) {
 test(`theme saved=${saved}, system dark=${system}`,()=>{
   const document={documentElement:{dataset:{},style:{}}};
   vm.runInNewContext(script,{document,localStorage:{getItem:()=>saved},window:{matchMedia:()=>({matches:system})}});
   assert.equal(document.documentElement.dataset.theme,expected);
   assert.equal(document.documentElement.style.colorScheme,expected);
 });
}
test('blocked browser storage does not prevent rendering',()=>{
 const document={documentElement:{dataset:{},style:{}}};
 vm.runInNewContext(script,{document,localStorage:{getItem(){throw Error('blocked')}},window:{matchMedia:()=>({matches:false})}});
 assert.equal(document.documentElement.dataset.theme,'light');
});
