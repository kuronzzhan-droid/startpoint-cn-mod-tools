const test = require('node:test');
const assert = require('node:assert/strict');
const {normalize, createCard, mount} = require('../wiki/sponsor.js');
const ad = {enabled:true,title:'示例赞助',description:'支持社区',imageUrl:'https://images.example.com/banner.webp',targetUrl:'https://sponsor.example.com/',revision:1,updatedAt:1};
class Node {
  constructor(tag) {Object.assign(this,{tag,children:[],events:{},attributes:{},hidden:false});}
  append(...nodes) {this.children.push(...nodes);}
  replaceChildren(...nodes) {this.children = nodes;}
  setAttribute(key,value) {this.attributes[key] = value;}
  addEventListener(key,fn) {this.events[key] = fn;}
  remove() {this.removed = true;}
}
const document = {createElement:tag=>new Node(tag)};
function setup({response=ad,storage,hash='',now=1000}={}) {
  const host = new Node('aside'), footer = new Node('footer'), events = {}, location = {protocol:'https:',hash};
  let observer, calls = 0, disconnected = false;
  const controller = mount({document,host,footer,location,storage,events:{addEventListener:(key,fn)=>events[key]=fn},
    request:async()=>{calls++; if(response instanceof Error) throw response; return response;}, now:()=>now,
    Observer:class {constructor(fn){observer=fn;} observe(node){assert.equal(node,footer);} disconnect(){disconnected=true;}}});
  return {host,location,controller,get calls(){return calls;},get disconnected(){return disconnected;},
    enter:()=>observer([{isIntersecting:true}]),navigate:hash=>{location.hash=hash;events.hashchange();}};
}
test('default and disabled sponsor are hidden; explicit preview can show a disabled draft',()=>{
  assert.equal(createCard(document,{}),null);
  assert.equal(createCard(document,{...ad,enabled:false}),null);
  const card=createCard(document,{...ad,enabled:false},{preview:true});
  assert.ok(card); assert.equal(card.children[1].tag,'div');
});
test('session caching does not extend an edge response beyond the next half-hour',async()=>{
  let raw;const storage={getItem:()=>raw,setItem:(_,value)=>raw=value};
  const before=setup({storage,now:1799000});await before.controller.load();assert.equal(before.calls,1);
  const after=setup({storage,now:1800000});await after.controller.load();assert.equal(after.calls,1);
});
test('reject unsafe destinations, image formats and credentials before creating DOM',()=>{
  for(const targetUrl of ['javascript:alert(1)','http://example.com','https://user:secret@example.com','https://127.1/a','https://[::1]/','https://localhost/','https://foo.local/','https://example.com:8001/'])
    assert.equal(normalize({...ad,targetUrl}),null,targetUrl);
  for(const imageUrl of ['data:image/png;base64,xxx','https://example.com/x.svg','/api/community/private-image','media/../secret.png'])
    assert.equal(normalize({...ad,imageUrl}),null,imageUrl);
  assert.ok(normalize({...ad,imageUrl:'media/'+ 'a'.repeat(64)+'.png'}));
});
test('render text literally, mark paid links, load images lazily and make preview non-clickable',()=>{
  const card=createCard(document,{...ad,title:'<img onerror=alert(1)>'});
  assert.equal(card.children[0].textContent,'广告 · 赞助');
  const link=card.children[1]; assert.equal(link.rel,'sponsored noopener noreferrer');
  assert.equal(link.target,'_blank'); assert.equal(link.children[0].children[0].loading,'lazy');
  assert.equal(link.children[0].children[0].referrerPolicy,'no-referrer');
  assert.equal(link.children[1].children[0].textContent,'<img onerror=alert(1)>');
});
test('only fetch when footer approaches; hash navigation does not refetch or display in admin',async()=>{
  const x=setup(); assert.equal(x.calls,0); assert.equal(x.host.hidden,true);
  x.enter(); await x.controller.load(); assert.equal(x.calls,1); assert.equal(x.host.hidden,false); assert.equal(x.disconnected,true);
  x.navigate('#community/admin'); assert.equal(x.host.hidden,true);
  x.navigate('#team'); assert.equal(x.host.hidden,false); await x.controller.load(); assert.equal(x.calls,1);
});
test('admin does not start ad loading; leaving it allows lazy loading once',async()=>{
  const x=setup({hash:'#community/admin'}); x.enter(); await x.controller.load(); assert.equal(x.calls,0);
  x.navigate('#team'); await Promise.resolve(); assert.equal(x.calls,1); await x.controller.load();
});
test('failure is silent, hidden and never creates a retry loop',async()=>{
  const x=setup({response:new Error('offline')}); x.enter(); await x.controller.load();
  x.navigate('#team'); await x.controller.load(); assert.equal(x.calls,1); assert.equal(x.host.hidden,true);
});
test('reuse valid public session cache and discard expired or invalid records',async()=>{
  let raw;const storage={getItem:()=>raw,setItem:(_,value)=>raw=value};
  const x=setup({storage}); await x.controller.load(); assert.equal(x.calls,1);
  const y=setup({storage}); await y.controller.load(); assert.equal(y.calls,0); assert.equal(y.host.hidden,false);
  raw=JSON.stringify({at:-1800001,value:ad}); const z=setup({storage}); await z.controller.load(); assert.equal(z.calls,1);
  raw=JSON.stringify({at:1000,value:{...ad,targetUrl:'javascript:alert(1)'}});
  const bad=setup({storage}); await bad.controller.load(); assert.equal(bad.calls,1);
});
