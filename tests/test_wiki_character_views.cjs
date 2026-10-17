const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {create,normalize}=require('../wiki/character-views.js');
const source=fs.readFileSync(require('node:path').join(__dirname,'../wiki/character-views.js'),'utf8');
const value=(id='c1',views=5)=>({characterId:id,views,windowSeconds:1800});
const tick=()=>new Promise(setImmediate);
test('read-only panels do not establish identity or increment views',async()=>{
 const calls=[],client={config(){throw Error('unexpected config');},async request(...args){calls.push(args);return value();}};
 assert.equal((await create(client).load('c1')).views,5);assert.deepEqual(calls,[['/characters/c1/views']]);
});
test('actual visits initialize identity before POST and coalesce concurrent recording',async()=>{
 let resolve;const calls=[],api=create({async config(){calls.push('config');},request(...args){calls.push(args);return new Promise(done=>resolve=done);}});
 const a=api.load('c1',true),b=api.load('c1',true);assert.equal(a,b);await tick();
 assert.deepEqual(calls,['config',['/characters/c1/views',{},'POST']]);resolve(value());await a;
 const c=api.load('c1',true);await tick();resolve(value('c1',6));assert.equal((await c).views,6);
});
test('expired identity recovers once; blocked cookies do not retry forever',async()=>{
 const configs=[];let calls=0;
 const client={async config(options){configs.push(options);},async request(){calls++;if(calls<2)throw Object.assign(Error(),{status:428,code:'visitor_required'});return value();}};
 assert.equal((await create(client).load('c1',true)).views,5);assert.deepEqual(configs,[undefined,{refresh:true}]);
 calls=0;client.request=async()=>{calls++;throw Object.assign(Error(),{status:428,code:'visitor_required'});};
 await assert.rejects(create(client).load('c1',true));assert.equal(calls,2);
});
test('a rate-limited visit falls back to a read-only total without retrying the POST',async()=>{
 const calls=[],client={async config(){},async request(...args){calls.push(args);if(args[2]==='POST')throw Object.assign(Error(),{status:429,code:'rate_limited'});return value('c1',7);}};
 assert.equal((await create(client).load('c1',true)).views,7);
 assert.deepEqual(calls,[['/characters/c1/views',{},'POST'],['/characters/c1/views']]);
});
test('network failure never creates a fabricated count and retry is possible',async()=>{
 let bad=true;const api=create({async request(){if(bad)throw Error('network');return value('c1',0);}});
 await assert.rejects(api.load('c1'));bad=false;assert.equal((await api.load('c1')).views,0);
});
test('reject malformed and cross-character counts',()=>{
 for(const row of [value('c2'),value('c1',-1),value('c1',1.5),value('c1','5'),{...value(),windowSeconds:1}])assert.throws(()=>normalize(row,'c1'));
});
class Node{
 constructor(tag,className='',text=''){Object.assign(this,{tag,className,own:String(text),children:[],events:{},hidden:false,attributes:{}});}
 append(...nodes){nodes.forEach(n=>{n.parent=this;this.children.push(n);});}
 get textContent(){return this.own+this.children.map(n=>n.textContent).join('');}set textContent(v){this.own=String(v);this.children=[];}
 setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,v){this.events[k]=v;}
 get isConnected(){return Boolean(this.connected||this.parent?.isConnected);}
}
function setup(handler,protocol='https:'){
 const calls=[],window={location:{protocol,hash:'#character/c1'},document:{},WFCommunity:{client:{config:async()=>({enabled:true}),request:async(...args)=>{calls.push(args);return handler(...args);}}}};
 vm.runInNewContext(source,{window});const host=new Node('section');host.connected=true;
 const panel=window.WFCharacterViews.mount(host,{id:'c1'},{el:(...args)=>new Node(...args)},{record:true});
 return {window,host,panel,calls};
}
test('visible counter shows server totals beneath rating without a timer',async()=>{
 const x=setup(async()=>value());await tick();assert.match(x.panel.textContent,/已被查看5次/);assert.match(x.panel.title,/30 分钟/);
 assert.equal(x.calls.length,1);assert.equal(x.panel.children.at(-1).hidden,true);
});
test('offline counter is unavailable rather than zero and sends nothing',async()=>{
 const x=setup(()=>{throw Error('unexpected');},'file:');await tick();assert.match(x.panel.textContent,/离线版不统计/);assert.equal(x.calls.length,0);
});
test('late responses after character navigation cannot paint the old panel',async()=>{
 let resolve;const x=setup(()=>new Promise(done=>resolve=done));await tick();x.window.location.hash='#character/c2';resolve(value());await tick();
 assert.match(x.panel.textContent,/—/);assert.doesNotMatch(x.panel.textContent,/已被查看5次/);
});
test('failed counters expose a bounded manual retry, preserving unavailable state',async()=>{
 let bad=true;const x=setup(async()=>{if(bad)throw Error('offline');return value('c1',0);});await tick();
 const retry=x.panel.children.at(-1);assert.equal(retry.hidden,false);assert.match(x.panel.textContent,/暂不可用/);
 bad=false;await retry.events.click();assert.match(x.panel.textContent,/已被查看0次/);assert.equal(retry.hidden,true);
});
