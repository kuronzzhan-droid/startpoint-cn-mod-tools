const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function setup(nativeNavigation = false) {
  const listeners = {}, clicks = [], history = [];
  const entries = ['#', '#weapons', '#community/admin'].map((hash,index)=>({hash,state:{existing:'retained',__wfWikiNavigationIndex:index}}));
  let index=2;
  const location = {get hash(){return entries[index].hash;},set hash(hash){entries.splice(++index);entries.push({hash,state:null});},
    href:'https://wiki.test/#community/admin', origin:'https://wiki.test', pathname:'/', search:''};
  const window = {history:{get state(){return entries[index].state;}, replaceState(state, _title, hash) {history.push({state,hash});entries[index]={state,hash};},
    pushState(state,_title,hash){entries.splice(++index);entries.push({state,hash});},
    go(delta){index+=delta;queueMicrotask(()=>window.WFNavigationGuard.allow(location.hash.slice(1)));}},
    Event:class {constructor(type){this.type=type;}},dispatchEvent(){window.WFNavigationGuard.allow(location.hash.slice(1));},
    ...(nativeNavigation?{navigation:{get currentEntry(){return {index};}}}:{}),addEventListener(type, fn) {listeners[type] = fn;}};
  const main = {focus(){this.focused=true;},scrollIntoView(){this.scrolled=true;}};
  const document = {getElementById:()=>main,addEventListener(type, fn) {if(type === 'click') clicks.push(fn);}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/navigation-guard.js'), 'utf8'), {window, document, location, URL,setTimeout,clearTimeout});
  const guard = {isActive:()=>true, needsProtection:()=>true, canLeave:async()=>false};
  window.WFNavigationGuard.register(guard);
  return {api:window.WFNavigationGuard, location, history, guard, listeners, entries, main, get index(){return index;},back(){index--;},
    click(href, extra = {}) {
      const link = {href,target:'',dataset:{},hasAttribute:()=>false,...extra.link};
      const event = {button:0,target:{closest:()=>link},preventDefault(){this.defaultPrevented=true;},stopImmediatePropagation(){this.stopped=true;},...extra};
      clicks.forEach(fn=>fn(event)); return event;
    }};
}
test('top navigation cancellation keeps editor URL and does not execute new-team preparation', async () => {
  const x=setup(); let prepared=0;
  assert.equal(await x.api.navigate('#team',()=>prepared++),false);
  assert.equal(x.location.hash,'#community/admin'); assert.equal(prepared,0);
  const event=x.click('https://wiki.test/#weapons'); await new Promise(setImmediate);
  assert.equal(event.defaultPrevented,true);assert.equal(event.stopped,true);assert.equal(x.location.hash,'#community/admin');
});
test('accepted links ask once, prepare only after approval and permit one router transition', async () => {
  const x=setup(); let asked=0, prepared=0;x.guard.canLeave=async()=>{asked++;return true;};
  assert.equal(await x.api.navigate('#team',()=>prepared++),true);
  assert.equal(x.location.hash,'#team');assert.equal(x.api.allow('team'),true);
  assert.equal(asked,1);assert.equal(prepared,1);
  await x.api.allow('weapons');assert.equal(asked,2);
});
test('browser back cancellation restores the original history position without overwriting previous entries', async () => {
  const x=setup();let resolve;x.guard.canLeave=()=>new Promise(done=>resolve=done);
  x.back();const pending=x.api.allow('weapons');
  assert.equal(x.location.hash,'#weapons');assert.equal(x.index,1);
  resolve(false);assert.equal(await pending,false);assert.equal(x.location.hash,'#community/admin');
  assert.equal(x.index,2);assert.deepEqual(x.entries.map(entry=>entry.hash),['#','#weapons','#community/admin']);
  assert.equal(x.history[0].state.existing,'retained');
});
test('accepted browser history navigation restores the destination without extra hash changes', async () => {
  const x=setup();x.guard.canLeave=async()=>true;x.location.hash='#weapons';
  assert.equal(await x.api.allow('weapons'),true);assert.equal(x.location.hash,'#weapons');
});
test('repeated clicks and direct hash changes cannot stack prompts or replace the pending destination', async () => {
  const x=setup();let resolve, asked=0;x.guard.canLeave=()=>{asked++;return new Promise(done=>resolve=done);};
  const first=x.api.navigate('#weapons');assert.equal(await x.api.navigate('#team'),false);
  x.location.hash='#tier-list';assert.equal(x.api.allow('tier-list'),false);assert.equal(x.location.hash,'#tier-list');
  resolve(true);assert.equal(await first,false);assert.equal(x.location.hash,'#community/admin');assert.equal(asked,1);
});
test('multiple Back operations during a confirmation recover the unchanged original history entry', async () => {
  const x=setup();let resolve;x.guard.canLeave=()=>new Promise(done=>resolve=done);
  x.back();const pending=x.api.allow('weapons');x.back();assert.equal(x.api.allow(''),false);
  resolve(false);assert.equal(await pending,false);assert.equal(x.index,2);assert.equal(x.location.hash,'#community/admin');
  assert.deepEqual(x.entries.map(entry=>entry.hash),['#','#weapons','#community/admin']);
});
test('cancelling a link confirmation after browser Back restores the original editor entry', async () => {
  const x=setup();let resolve;x.guard.canLeave=()=>new Promise(done=>resolve=done);
  const pending=x.api.navigate('#team');x.back();assert.equal(x.api.allow('weapons'),false);
  resolve(false);assert.equal(await pending,false);assert.equal(x.index,2);assert.equal(x.location.hash,'#community/admin');
});
test('native entry indexes restore unmarked old entries and rapid consecutive hash changes exactly', async () => {
  for(const mode of ['old','rapid']) {
    const x=setup(true);
    if(mode==='old'){x.entries[1].state=null;x.back();}
    else {x.location.hash='#weapons';x.location.hash='#tier-list';}
    assert.equal(await x.api.allow(x.location.hash.slice(1)),false);
    assert.equal(x.index,2);assert.equal(x.location.hash,'#community/admin');
    x.guard.needsProtection=()=>false;assert.equal(await x.api.navigate('#team'),true);
  }
});
test('legacy browsers recover an unknown history distance without losing the old entry or locking navigation', async () => {
  for(const mode of ['old','rapid']) {
    const x=setup();
    if(mode==='old'){x.entries[1].state=null;x.back();}
    else {x.location.hash='#weapons';x.location.hash='#tier-list';}
    assert.equal(await x.api.allow(x.location.hash.slice(1)),false);
    assert.equal(x.location.hash,'#community/admin');assert.ok(x.entries.some(entry=>entry.hash==='#weapons'));
    x.guard.needsProtection=()=>false;assert.equal(await x.api.navigate('#team'),true);
  }
});
test('a detached or replaced editor cannot authorize navigation for the next editor', async () => {
  const x=setup();let resolve;x.guard.canLeave=()=>new Promise(done=>resolve=done);
  const first=x.api.navigate('#weapons');x.api.register({...x.guard});resolve(true);
  assert.equal(await first,false);assert.equal(x.location.hash,'#community/admin');
});
test('clean or detached pages navigate without prompts; stale unregister leaves a newer guard intact', async () => {
  const x=setup();let asked=0;x.guard.canLeave=async()=>{asked++;return false;};
  const unregister=x.api.register(x.guard);x.api.register({...x.guard});unregister();
  assert.equal(await x.api.navigate('#weapons'),false);assert.equal(asked,1);
  x.api.register({...x.guard,needsProtection:()=>false});assert.equal(await x.api.navigate('#weapons'),true);
  assert.equal(x.api.allow('weapons'),true);assert.equal(asked,1);
});
test('same-page links, external links, modified clicks and custom New Team handlers keep expected behavior', async () => {
  const x=setup();let asked=0;x.guard.canLeave=async()=>{asked++;return false;};
  assert.equal(await x.api.navigate('#community/admin'),false);assert.equal(asked,0);
  for(const [href,extra] of [['https://other.test/#weapons',{}],['https://wiki.test/other#weapons',{}],
    ['https://wiki.test/?x=1#weapons',{}],['https://wiki.test/#weapons',{ctrlKey:true}],
    ['https://wiki.test/#weapons',{link:{target:'_blank'}}]]) assert.equal(x.click(href,extra).defaultPrevented,undefined);
  const custom=x.click('https://wiki.test/#team',{link:{dataset:{navigationGuard:'custom'}}});
  assert.equal(custom.defaultPrevented,true);assert.equal(custom.stopped,undefined);assert.equal(asked,0);
});
test('browser refresh and close only warn while connected work needs protection', () => {
  const x=setup();const e={preventDefault(){this.prevented=true;}};x.listeners.beforeunload(e);assert.equal(e.prevented,true);
  x.guard.needsProtection=()=>false;const clean={preventDefault(){this.prevented=true;}};x.listeners.beforeunload(clean);assert.equal(clean.prevented,undefined);
});
test('skip-to-content focuses the page without changing its route or discarding an editor', () => {
  const x=setup();const event=x.click('https://wiki.test/#main-content');
  assert.equal(event.defaultPrevented,true);assert.equal(x.main.focused,true);assert.equal(x.main.scrolled,true);
  assert.equal(x.location.hash,'#community/admin');
});
test('a failed confirmation preserves the editor without an unhandled rejection', async () => {
  const x=setup();x.guard.canLeave=async()=>{throw new Error('dialog unavailable');};
  assert.equal(await x.api.navigate('#weapons'),false);assert.equal(x.location.hash,'#community/admin');
});
