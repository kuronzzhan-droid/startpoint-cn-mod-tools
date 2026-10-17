const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../wiki/character-variants.js'),'utf8');
class Node {
  constructor(tag,cls='',text=''){Object.assign(this,{tag,className:cls,textContent:text,children:[],attributes:{},events:{},isConnected:true});}
  append(...nodes){this.children.push(...nodes);nodes.forEach(n=>{n.parent=this;});}
  replaceChildren(...nodes){this.children=[];this.append(...nodes);}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
  setAttribute(key,value){this.attributes[key]=value;}addEventListener(type,fn){this.events[type]=fn;}
  fire(type='click',event={}){return this.events[type]?.(event);}
}
const chars=[{id:'c1',name:'特克托',title:'原型',theme:'通常版',origin:'官方原版',icon:'media/one.webp'},
  {id:'c2',name:'特克托',title:'燕尾礼服',theme:'其他变体',origin:'新增MOD',avatars:{before:'media/two.webp'}},
  {id:'c3',name:'另一个人',icon:'media/three.webp'}];
const index={schemaVersion:1,dataVersion:'0123456789abcdef',groups:{c1:['c1','c2'],c2:['c1','c2']}};
function setup(loaded=false){
  const head=new Node('head'),window={WF_WIKI:{characters:chars,meta:{characterVariants:{url:'data/character-variants.js',version:index.dataVersion}}}},timers=[];
  if(loaded)window.WF_CHARACTER_VARIANTS=index;
  vm.runInNewContext(source,{window,document:{head,createElement:tag=>new Node(tag)},setTimeout:fn=>{timers.push(fn);return timers.length;},clearTimeout(){},encodeURIComponent});
  const ui={el:(...args)=>new Node(...args),safeUrl:value=>value||'',picture:(url,alt,cls)=>Object.assign(new Node('img',cls),{src:url,alt})};
  return {window,head,timers,mount:(host,character=chars[0],options)=>window.WFCharacterVariants.mount(host,character,ui,options),
    resolve(value=index){window.WF_CHARACTER_VARIANTS=value;head.children[0].onload();}};
}
test('family index loads only on mount, coalesces requests, version-busts and renders current and linked variants',async()=>{
  const x=setup(),a=new Node('div'),b=new Node('div'),clicked=[];assert.equal(x.head.children.length,0);
  const first=x.mount(a,chars[0],{onNavigate:id=>clicked.push(id)}),second=x.mount(b,chars[1]);
  assert.equal(x.head.children.length,1);assert.equal(x.head.children[0].src,'data/character-variants.js?v=0123456789abcdef');x.resolve();await Promise.all([first,second]);
  const links=a.children[0].children[1].children;assert.equal(links.length,2);assert.equal(links[0].attributes['aria-current'],'page');
  assert.equal(links[1].href,'#character/c2');assert.equal(links[1].children[0].src,'media/two.webp');links[1].fire();assert.deepEqual(clicked,['c2']);
  links[1].fire('click',{ctrlKey:true});assert.deepEqual(clicked,['c2']);await x.mount(new Node('div'));assert.equal(x.head.children.length,0);
});
test('singleton and detached views stay empty; a remounted host cannot receive stale links',async()=>{
  const x=setup(),host=new Node('div'),detached=new Node('div');detached.isConnected=false;
  const a=x.mount(host,chars[0]),b=x.mount(host,chars[2]),c=x.mount(detached,chars[1]);x.resolve();await Promise.all([a,b,c]);
  assert.equal(host.children.length,0);assert.equal(detached.children.length,0);
});
test('invalid or stale indices cannot invent relationships; retry performs a fresh load',async()=>{
  const x=setup(),host=new Node('div');const first=x.mount(host);x.resolve({...index,groups:{c1:['c1','unknown']}});await first;
  assert.equal(host.children[0].tag,'button');const retry=host.children[0].fire();assert.equal(x.head.children.length,1);x.resolve();await retry;
  assert.equal(host.children[0].tag,'section');
});
test('failed and timed-out loads expose a retry without inserting partial family data',async()=>{
  const x=setup(),host=new Node('div');const first=x.mount(host);x.head.children[0].onerror();await first;assert.equal(host.children[0].tag,'button');
  const next=host.children[0].fire();x.timers.at(-1)();await next;assert.equal(host.children[0].tag,'button');assert.equal(x.head.children.length,0);
});
