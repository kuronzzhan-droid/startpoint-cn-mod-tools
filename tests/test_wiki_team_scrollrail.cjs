const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {Node: BaseNode} = require('./wiki_equipment_fixture.cjs');
class Node extends BaseNode {
  constructor(...args) {super(...args);this.style={};this.clientHeight=200;this.scrollHeight=1000;this.scrollTop=0;}
  getBoundingClientRect() {return {top:10,height:this.clientHeight};}
  setPointerCapture(id) {this.captured=id;}
  hasPointerCapture(id) {return this.captured===id;}
  releasePointerCapture() {this.captured=null;}
  focus() {this.focused=true;}
}
function setup(mobile = true) {
  const window = new Node('window'), media = new Node('media'), frames = new Map(), observers = [];
  let counter=0;
  window.location={hash:'#team'};media.matches=mobile;window.matchMedia=()=>media;
  class Observer {constructor(callback){this.callback=callback;this.targets=[];observers.push(this);}observe(target){this.targets.push(target);}disconnect(){this.disconnected=true;}}
  const context={window,ResizeObserver:Observer,MutationObserver:Observer,
    requestAnimationFrame(callback){frames.set(++counter,callback);return counter;},cancelAnimationFrame(id){frames.delete(id);}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/team-scrollrail.js'),'utf8'),context);
  const ui={el:(...args)=>new Node(...args)},viewport=ui.el('div','team-candidates');
  const root=window.WFTeamScrollRail.wrap(viewport,ui,'候选列表'),rail=root.children[1],thumb=rail.children[0];
  const flush=()=>{for(const [id,callback]of [...frames]){frames.delete(id);callback();}};
  flush();
  const event=(type,target=thumb,extra={})=>{
    let prevented=false,stopped=false;
    rail.fire(type,{target,pointerId:1,button:0,isPrimary:true,clientY:10,preventDefault(){prevented=true;},stopPropagation(){stopped=true;},...extra});
    return {prevented,stopped};
  };
  return {window,media,viewport,root,rail,thumb,frames,observers,flush,event};
}
test('persistent handle mirrors native scroll position and pointer dragging reaches both ends without propagating',()=>{
  const x=setup();assert.equal(x.rail.hidden,false);assert.equal(x.rail.attributes.role,'scrollbar');
  assert.equal(x.rail.attributes['aria-controls'],x.viewport.id);assert.equal(x.thumb.style.height,'40px');
  x.viewport.scrollTop=400;x.viewport.fire('scroll');assert.equal(x.rail.attributes['aria-valuenow'],'50');
  assert.equal(x.thumb.style.transform,'translateY(80px)');
  assert.deepEqual(x.event('pointerdown',x.thumb,{clientY:95}),{prevented:true,stopped:true});
  assert.equal(x.rail.captured,1);assert.equal(x.rail.focused,true);
  x.event('pointermove',x.thumb,{clientY:175});assert.equal(x.viewport.scrollTop,800);
  x.event('pointermove',x.thumb,{clientY:-100});assert.equal(x.viewport.scrollTop,0);
  x.event('pointerup');assert.equal(x.rail.captured,null);
  x.event('pointermove',x.thumb,{clientY:175});assert.equal(x.viewport.scrollTop,0);
});
test('track taps, keyboard paging and Home/End scroll only the current pane',()=>{
  const x=setup();x.event('pointerdown',x.rail,{clientY:110});assert.equal(x.viewport.scrollTop,400);x.event('pointerup');
  assert.deepEqual(x.event('keydown',x.rail,{key:'ArrowDown'}),{prevented:true,stopped:true});assert.equal(x.viewport.scrollTop,440);
  x.event('keydown',x.rail,{key:'PageUp'});assert.equal(x.viewport.scrollTop,260);
  x.event('keydown',x.rail,{key:'End'});assert.equal(x.viewport.scrollTop,800);
  x.event('keydown',x.rail,{key:'Home'});assert.equal(x.viewport.scrollTop,0);
  assert.deepEqual(x.event('keydown',x.rail,{key:'Tab'}),{prevented:false,stopped:false});
  assert.deepEqual(x.event('touchstart'),{prevented:false,stopped:true});
  assert.deepEqual(x.event('dragstart'),{prevented:true,stopped:true});
});
test('async content and size changes refresh or hide the handle without polling',()=>{
  const x=setup();x.viewport.scrollHeight=200;x.observers.forEach(o=>o.callback());assert.equal(x.frames.size,1);x.flush();
  assert.equal(x.rail.hidden,true);assert.equal(x.rail.attributes['aria-valuenow'],'0');
  x.viewport.scrollHeight=2000;x.viewport.fire('load');x.viewport.fire('toggle');assert.equal(x.frames.size,1);x.flush();
  assert.equal(x.rail.hidden,false);assert.equal(x.thumb.style.height,'36px');
});
test('desktop has no custom rail and width changes cancel a captured touch',()=>{
  const x=setup(false);assert.equal(x.rail.hidden,true);
  assert.deepEqual(x.event('pointerdown'),{prevented:false,stopped:false});
  x.media.matches=true;x.media.fire('change');x.flush();assert.equal(x.rail.hidden,false);
  x.event('pointerdown');assert.equal(x.rail.captured,1);
  x.media.matches=false;x.media.fire('change');x.flush();assert.equal(x.rail.hidden,true);assert.equal(x.rail.captured,null);
});
test('route leaving and rerender disposal remove observers, pending frames and input listeners',()=>{
  for(const route of [false,true]){
    const x=setup();x.event('pointerdown');x.viewport.fire('toggle');assert.equal(x.frames.size,1);
    if(route){x.window.location.hash='#weapons';x.window.fire('hashchange');}else x.window.WFTeamScrollRail.reset();
    assert.equal(x.frames.size,0);assert.equal(x.rail.captured,null);assert.ok(x.observers.every(o=>o.disconnected));
    assert.ok(Object.values(x.rail.events).every(set=>set.size===0));assert.ok(Object.values(x.viewport.events).every(set=>set.size===0));
    assert.equal(x.media.events.change.size,0);x.window.WFTeamScrollRail.reset();
  }
});
