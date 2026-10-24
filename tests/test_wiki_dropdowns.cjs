const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../wiki/dropdowns.js'),'utf8');
const tick=()=>new Promise(setImmediate);

// DOM boundary only: production keyboard, event dispatch and lifecycle code run unchanged.
function fixture() {
  const observers=[],pending=new Set(),timers=[];let doc;
  class Event {
    constructor(type,init={}){Object.assign(this,{type,bubbles:false,defaultPrevented:false},init);}
    preventDefault(){this.defaultPrevented=true;}stopPropagation(){this.stopped=true;}
  }
  function changed(target,record){
    for(const o of observers){if(!o.target||!(o.target===target||o.options.subtree&&o.target.contains(target)))continue;
      if(record.type==='attributes'&&(!o.options.attributes||o.options.attributeFilter&&!o.options.attributeFilter.includes(record.attributeName)))continue;
      if(record.type==='childList'&&!o.options.childList)continue;
      o.records.push({target,addedNodes:[],...record});pending.add(o);
    }
    queueMicrotask(()=>{for(const o of [...pending]){pending.delete(o);const records=o.records.splice(0);if(o.target)o.fn(records);}});
  }
  class Node {
    constructor(tag){Object.assign(this,{tagName:tag.toUpperCase(),children:[],attributes:{},style:{},events:{},ownText:'',nodeType:1});}
    get parentNode(){return this.parentElement;}get isConnected(){return this===doc.body||Boolean(this.parentElement?.isConnected);}
    get className(){return this.attributes.class||'';}set className(v){this.attributes.class=v;}
    get classList(){const node=this;return {add(c){node.className=[...new Set([...node.className.split(' '),c])].join(' ').trim();},remove(c){node.className=node.className.split(' ').filter(x=>x!==c).join(' ');},toggle(c,on){on?this.add(c):this.remove(c);}};}
    get id(){return this.attributes.id||'';}set id(v){this.attributes.id=v;}
    get textContent(){return this.ownText+this.children.map(n=>n.textContent).join('');}set textContent(v){this.replaceChildren();this.ownText=String(v);}
    setAttribute(k,v){this.attributes[k]=String(v);changed(this,{type:'attributes',attributeName:k});}
    getAttribute(k){return this.attributes[k]??null;}removeAttribute(k){delete this.attributes[k];changed(this,{type:'attributes',attributeName:k});}
    get disabled(){return this.getAttribute('disabled')!==null;}set disabled(v){v?this.setAttribute('disabled',''):this.removeAttribute('disabled');}
    get hidden(){return this.getAttribute('hidden')!==null;}set hidden(v){v?this.setAttribute('hidden',''):this.removeAttribute('hidden');}
    get required(){return this.getAttribute('required')!==null;}set required(v){v?this.setAttribute('required',''):this.removeAttribute('required');}
    append(...nodes){for(const node of nodes){node.remove();node.parentElement=this;this.children.push(node);}changed(this,{type:'childList',addedNodes:nodes});}
    before(node){const p=this.parentElement;if(!p)return;node.remove();node.parentElement=p;p.children.splice(p.children.indexOf(this),0,node);changed(p,{type:'childList',addedNodes:[node]});}
    remove(){const p=this.parentElement;if(p){p.children.splice(p.children.indexOf(this),1);this.parentElement=null;changed(p,{type:'childList'});}}
    replaceWith(node){this.before(node);this.remove();}
    replaceChildren(...nodes){this.children.forEach(n=>{n.parentElement=null;});this.children=[];this.ownText='';this.append(...nodes);}
    contains(node){return node===this||this.children.some(n=>n.contains(node));}
    matches(s){if(s===':disabled')return this.disabled||Boolean(this.parentElement?.matches(':disabled'));if(s==='dialog[open]')return this.tagName==='DIALOG'&&this.getAttribute('open')!==null;return s.startsWith('.')?this.className.split(' ').includes(s.slice(1)):this.tagName===s.toUpperCase();}
    querySelectorAll(s){return this.children.flatMap(n=>[...(s.split(',').some(v=>n.matches(v))?[n]:[]),...n.querySelectorAll(s)]);}
    closest(s){return this.matches(s)?this:this.parentElement?.closest(s)||null;}
    addEventListener(type,fn){(this.events[type]||=[]).push(fn);}removeEventListener(type,fn){this.events[type]=(this.events[type]||[]).filter(f=>f!==fn);}
    dispatchEvent(event){event.target||=this;for(const fn of [...this.events[event.type]||[]])fn(event);if(event.bubbles&&!event.stopped)this.parentElement?.dispatchEvent(event);return !event.defaultPrevented;}
    fire(type,init={}){const event=new Event(type,init);this.dispatchEvent(event);return event;}
    focus(){doc.activeElement=this;this.fire('focus');doc.fire('focusin',{target:this});}
    getBoundingClientRect(){return {left:20,right:200,width:180,height:30,bottom:this.bottom||70};}
    scrollIntoView(options){this.scrollCalls||=[];this.scrollCalls.push(options);if(this.className==='wf-dropdown-trigger'&&doc.body.querySelectorAll('.wf-dropdown-space').length)this.bottom=200;}
    cloneNode(deep){const node=new Node(this.tagName);node.attributes={...this.attributes};node.ownText=this.ownText;if(deep)for(const child of this.children)node.append(child.cloneNode(true));return node;}
  }
  class Option extends Node {
    constructor(label,value=label){super('option');this.ownText=label;this.value=value;}
    get label(){return this.getAttribute('label')??this.textContent;}
    get selected(){return this.closest('select')?.selectedOptions.includes(this)||false;}
  }
  class Select extends Node {
    constructor(){super('select');this.index=0;}
    get size(){return Number(this.getAttribute('size')||0);}set size(v){this.setAttribute('size',v);}
    get multiple(){return this.getAttribute('multiple')!==null;}set multiple(v){v?this.setAttribute('multiple',''):this.removeAttribute('multiple');}
    get options(){return this.querySelectorAll('option');}get selectedOptions(){return this.options[this.index]?[this.options[this.index]]:[];}
    get selectedIndex(){return this.index;}set selectedIndex(v){this.index=Number(v);}
    get value(){return this.options[this.index]?.value||'';}set value(v){this.index=this.options.findIndex(o=>o.value===String(v));}
    get labels(){return doc.body.querySelectorAll('label').filter(n=>n.getAttribute('for')===this.id||n.contains(this));}
  }
  class Observer {constructor(fn){this.fn=fn;this.records=[];observers.push(this);}observe(target,options){Object.assign(this,{target,options});}disconnect(){this.target=null;}}
  doc=new Node('document');doc.body=new Node('body');doc.children=[doc.body];doc.body.parentElement=doc;doc.readyState='complete';
  doc.createElement=tag=>tag==='select'?new Select():new Node(tag);
  const window=new Node('window');Object.assign(window,{innerHeight:600,innerWidth:480});
  const form=new Node('form'),label=new Node('label'),select=new Select(),next=new Node('button');
  select.id='s';select.name='filter';label.setAttribute('for','s');label.textContent='测试筛选';
  select.append(new Option('Alpha','a'),new Option('Blocked','b'),new Option('Charlie','c'));select.options[1].disabled=true;
  form.append(label,select,next);doc.body.append(form);
  vm.runInNewContext(source,{window,document:doc,MutationObserver:Observer,Event,getComputedStyle:n=>({overflowY:n.style.overflowY||'visible'}),setTimeout:fn=>timers.push(fn),Date});
  const button=()=>select.parentElement.children.find(n=>n.tagName==='BUTTON');
  const menu=()=>doc.body.querySelectorAll('.wf-dropdown-menu')[0];
  return {window,doc,form,select,next,Node,Select,Option,button,menu,timers,key:key=>button().fire('keydown',{key}),click:()=>button().fire('click'),flush:tick};
}

test('selection dispatches a bubbling input/change pair on the original select only when value changes',async()=>{
  const x=fixture(),events=[];for(const type of ['input','change'])x.form.addEventListener(type,e=>events.push([e.type,e.target,e.target.value]));
  x.key('ArrowDown');x.key('Enter');assert.equal(x.select.value,'c');
  assert.deepEqual(events.map(e=>[e[0],e[2]]),[['input','c'],['change','c']]);assert.ok(events.every(e=>e[1]===x.select));
  x.click();x.menu().children.find(n=>n.textContent==='Charlie').fire('click');assert.equal(events.length,2);
  assert.equal(x.button().getAttribute('aria-expanded'),'false');assert.equal(x.button().getAttribute('aria-label'),'测试筛选');await x.flush();
});
test('Escape cancels; Tab closes without preventing default; navigation and typeahead skip disabled options',()=>{
  const x=fixture();x.click();x.key('End');x.key('Escape');assert.equal(x.select.value,'a');assert.equal(x.menu(),undefined);
  x.click();x.key('c');x.key('Enter');assert.equal(x.select.value,'c');x.click();x.key('Home');x.key('Enter');assert.equal(x.select.value,'a');
  x.click();assert.equal(x.key('Tab').defaultPrevented,false);assert.equal(x.menu(),undefined);
});
test('value/index assignments, reset and replacing options update the visible label without extra events',async()=>{
  const x=fixture(),events=[];x.select.addEventListener('change',()=>events.push(1));
  x.select.value='c';assert.match(x.button().textContent,/^Charlie/);x.select.selectedIndex=0;assert.match(x.button().textContent,/^Alpha/);
  x.select.replaceChildren(new x.Option('New','x'),new x.Option('Second','y'));x.select.value='y';await x.flush();assert.match(x.button().textContent,/^Second/);
  x.doc.fire('reset');x.select.index=0;x.timers.splice(0).forEach(fn=>fn());assert.match(x.button().textContent,/^New/);assert.equal(events.length,0);
  assert.equal(Object.hasOwn(Object.getPrototypeOf(x.select),'wfDropdown'),false);
});
test('new controls, disabled fieldsets, hidden choices and optgroups stay accessible',async()=>{
  const x=fixture(),s=new x.Select(),group=new x.Node('optgroup');s.id='late';s.setAttribute('aria-label','Later');
  group.label='Group';group.disabled=true;group.append(new x.Option('Group blocked'));const hidden=new x.Option('Hidden');hidden.hidden=true;
  s.append(group,hidden,new x.Option('Enabled'));x.form.append(s);await x.flush();const b=s.parentElement.children[1];
  b.fire('click');b.fire('keydown',{key:'End'});b.fire('keydown',{key:'Enter'});assert.equal(s.value,'Enabled');
  const fieldset=new x.Node('fieldset');s.parentElement.before(fieldset);fieldset.append(s.parentElement);fieldset.disabled=true;await x.flush();assert.equal(b.disabled,true);
  fieldset.disabled=false;await x.flush();assert.equal(b.disabled,false);s.hidden=true;await x.flush();assert.equal(s.parentElement.hidden,true);
});
test('multiple selects return to native control and removed controls cannot keep an open popup',async()=>{
  const x=fixture();x.select.multiple=true;await x.flush();assert.equal(x.select.parentElement,x.form);assert.equal(x.select.getAttribute('aria-hidden'),null);
  assert.equal(Object.hasOwn(x.select,'value'),false);x.select.multiple=false;await x.flush();x.click();assert.ok(x.menu());
  x.select.parentElement.remove();await x.flush();assert.equal(x.menu(),undefined);
});
test('bottom-edge opening reserves removable space, positions before highlight and bounds popup height',()=>{
  const x=fixture();x.button().bottom=590;x.select.append(...Array.from({length:100},(_,i)=>new x.Option(`<img ${i}>`)));
  x.click();assert.ok(x.doc.body.querySelectorAll('.wf-dropdown-space').length);assert.equal(x.menu().style.top,'204px');assert.equal(x.menu().style.maxHeight,'320px');
  assert.equal(x.menu().querySelectorAll('img').length,0);assert.match(x.menu().children.at(-1).textContent,/<img 99>/);
  x.key('Escape');assert.equal(x.doc.body.querySelectorAll('.wf-dropdown-space').length,0);
});
test('required/description semantics mirror the native select, invalid redirects focus and a reset clears it',async()=>{
  const x=fixture();x.select.required=true;x.select.setAttribute('aria-describedby','help');await x.flush();
  assert.equal(x.button().getAttribute('aria-required'),'true');assert.equal(x.button().getAttribute('aria-describedby'),'help');
  const invalid=x.select.fire('invalid');assert.equal(invalid.defaultPrevented,true);assert.equal(x.doc.activeElement,x.button());
  assert.equal(x.button().getAttribute('aria-invalid'),'true');x.select.value='c';assert.equal(x.button().getAttribute('aria-invalid'),null);
});
