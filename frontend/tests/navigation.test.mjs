import test from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
const code=buildSync({entryPoints:[new URL('../src/useHistoryNavigation.ts',import.meta.url).pathname],bundle:true,platform:'node',format:'cjs',write:false,packages:'external'}).outputFiles[0].text;
test('trackpad navigation preserves vertical scroll, pinch, forms and horizontal tabs',()=>{
 const keys=['window','document','HTMLElement','getComputedStyle'];
 const previous=Object.fromEntries(keys.map(key=>[key,globalThis[key]]));
 const listeners=new Map(),calls=[];let cleanup;
 class Element{constructor(input=false,scroll=false){this.input=input;this.scrollWidth=scroll?200:100;this.clientWidth=100;this.parentElement=null;}matches(){return this.input;}}
 const body=new Element();
 globalThis.HTMLElement=Element;globalThis.document={body};globalThis.getComputedStyle=()=>({overflowX:'auto'});
 const history={state:null,replaceState(state){this.state=state;},go(direction){calls.push(direction);},back(){},forward(){}};
 globalThis.window={history,location:{hash:'#overview'},addEventListener(type,fn){listeners.set(type,fn);},removeEventListener(type){listeners.delete(type);}};
 const module={exports:{}};
 const require=()=>({useEffect(fn){cleanup=fn();},useState(value){return[value,()=>{}];}});
 try{
  new Function('require','module','exports',code)(require,module,module.exports);
  module.exports.useHistoryNavigation();
  window.location.hash='#records';history.state=null;listeners.get('hashchange')();
  const wheel=overrides=>listeners.get('wheel')({deltaX:-100,deltaY:0,deltaMode:0,ctrlKey:false,target:body,preventDefault(){},...overrides});
  wheel({deltaY:200});wheel({ctrlKey:true});wheel({target:new Element(true)});wheel({target:new Element(false,true)});
  assert.deepEqual(calls,[]);
  wheel({});wheel({});assert.deepEqual(calls,[-1],'One swipe momentum should navigate only once');
  cleanup();assert.equal(listeners.size,0);
 }finally{for(const key of keys){if(previous[key]===undefined)delete globalThis[key];else globalThis[key]=previous[key];}}
});
