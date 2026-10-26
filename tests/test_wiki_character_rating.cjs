const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const tick = () => new Promise(setImmediate);
const source = fs.readFileSync(path.join(__dirname,'../wiki/character-rating.js'),'utf8');
class Node {
  constructor(tag,className='',text='') {Object.assign(this,{tag,className,ownText:String(text),children:[],events:{},attributes:{},disabled:false,hidden:false});}
  append(...nodes) {nodes.forEach((node)=>{node.parent=this;this.children.push(node);});}
  replaceChildren(...nodes) {this.children.forEach((node)=>{node.parent=null;});this.children=[];this.ownText='';this.append(...nodes);}
  get textContent() {return this.ownText+this.children.map((node)=>node.textContent).join('');}
  set textContent(value) {this.replaceChildren();this.ownText=String(value);}
  setAttribute(name,value) {this.attributes[name]=value;}
  addEventListener(name,action) {this.events[name]=action;}
  get isConnected() {return Boolean(this.connected||this.parent?.isConnected);}
  all(match) {return this.children.flatMap((node)=>[...(match(node)?[node]:[]),...node.all(match)]);}
  async fire(name='click') {if(!this.disabled)return this.events[name]?.();}
}
const el=(...args)=>new Node(...args);
const cls=(root,name)=>root.all((node)=>node.className.split(' ').includes(name))[0];
const button=(root,label)=>root.all((node)=>node.tag==='button'&&node.textContent===label)[0];
const nextVoteAt=Date.parse('2026-09-30T16:00:00Z');
const unrated={average:3.25,voters:27,myScore:null,ratedToday:false,nextVoteAt};
function setup(handler=async()=>unrated,options={}) {
  const calls=[],dialogs=[],challenges=[];let configCalls=0;
  const C={client:{request:async(...args)=>{calls.push(args);return handler(...args);},config:async()=>{configCalls++;return options.config?options.config():{enabled:true,siteKey:'test'};}}};
  C.dialog=()=>{const modal={element:el('dialog'),cleanup(fn){this.clean=fn;},close(){this.clean?.();this.element.connected=false;}};modal.element.connected=true;dialogs.push(modal);return modal;};
  C.challenge=(_host,_config,action,_ui,onChange)=>{
    const challenge={action,resets:0,destroyed:false,token:'',ready(value='one-use'){this.token=value;onChange(true);},take(){const value=this.token;this.token='';onChange(false);return value;},reset(){this.resets++;this.token='';onChange(false);},destroy(){this.destroyed=true;}};
    challenges.push(challenge);return challenge;
  };
  const events={},documentEvents={},listeners=[],document={hidden:false,addEventListener(name,action){listeners.push(`document:${name}`);documentEvents[name]=action;}};
  const window={WFCommunity:C,document,location:{protocol:options.protocol||'https:'},addEventListener(name,action){listeners.push(`window:${name}`);events[name]=action;}};
  const clock={now:options.now??nextVoteAt-1000};
  class ClockDate extends Date {static now(){return clock.now;}}
  vm.runInNewContext(source,{window,Date:ClockDate});
  const mount=(id='c1',connected=true)=>{const host=el('section');host.connected=connected;const root=window.WFCharacterRating.mount(host,{id,name:'测试角色'}, {el});return {host,root};};
  return {window,calls,dialogs,challenges,mount,clock,events,documentEvents,listeners,configCalls:()=>configCalls};
}

test('mount shows only authoritative aggregates and 0–5 choices without starting verification',async()=>{
  let resolve;const x=setup(()=>new Promise((done)=>{resolve=done;})),{root}=x.mount();
  assert.equal(cls(root,'character-rating-average').textContent,'—');assert.equal(x.configCalls(),0);assert.equal(x.challenges.length,0);
  assert.deepEqual(root.all((node)=>node.className==='character-rating-score').map((node)=>node.textContent),['0','1','2','3','4','5']);
  resolve(unrated);await tick();assert.equal(cls(root,'character-rating-average').textContent,'3.3');assert.equal(cls(root,'character-rating-voters').textContent,'27 位玩家');
  assert.equal(button(root,'0').disabled,false);assert.equal(x.calls[0][0],'/ratings/characters/c1');
});

test('zero voters render no average rather than inventing a zero rating, even before host insertion',async()=>{
  const x=setup(async()=>({...unrated,average:null,voters:0})),view=x.mount('c-new',false);view.host.connected=true;await tick();
  assert.equal(cls(view.root,'character-rating-average').textContent,'—');assert.equal(cls(view.root,'character-rating-voters').textContent,'0 位玩家');assert.equal(button(view.root,'5').disabled,false);
});

test('choosing zero needs a consumed verification token and confirmed POST before changing the aggregate',async()=>{
  let finish;const x=setup((_path,body)=>body?new Promise((done)=>{finish=done;}):Promise.resolve(unrated)),{root}=x.mount();await tick();
  const catalogUpdates=[];x.window.WFCatalogRatings={update:(id,value)=>catalogUpdates.push({id,...value})};
  await button(root,'0').fire();await tick();const dialog=x.dialogs[0].element,submit=button(dialog,'确认提交 0 分');
  assert.equal(x.challenges[0].action,'rate_character');await submit.fire();assert.equal(x.calls.length,1);
  x.challenges[0].ready('zero-token');const pending=submit.fire();assert.equal(x.calls[1][1].score,0);assert.equal(x.calls[1][1].turnstileToken,'zero-token');
  assert.equal(cls(root,'character-rating-average').textContent,'3.3');assert.equal(submit.disabled,true);
  finish({...unrated,average:3,rankScore:2.921875,myScore:0,ratedToday:true});await pending;
  assert.equal(cls(root,'character-rating-average').textContent,'3.0');assert.equal(cls(root,'character-rating-voters').textContent,'27 位玩家');
  assert.match(root.textContent,/今天已评 0 分.*北京时间/);assert.equal(button(root,'5').disabled,true);assert.equal(x.challenges[0].resets,1);
  assert.equal(catalogUpdates.length,1);assert.equal(catalogUpdates[0].id,'c1');assert.equal(catalogUpdates[0].average,3);
  assert.equal(catalogUpdates[0].rankScore,2.921875);
  await submit.fire();assert.equal(x.calls.length,2);
});

test('daily duplicate replies update from their record and do not invent a personal score for an IP claim',async()=>{
  const x=setup(async(_path,body)=>{if(body)throw Object.assign(new Error('already'),{status:409,code:'already_rated',data:{...unrated,average:4.1,myScore:null,ratedToday:true}});return unrated;});
  const {root}=x.mount();await tick();await button(root,'4').fire();await tick();x.challenges[0].ready();
  await button(x.dialogs[0].element,'确认提交 4 分').fire();assert.equal(cls(root,'character-rating-average').textContent,'4.1');assert.match(root.textContent,/今天已评分/);assert.doesNotMatch(root.textContent,/今天已评 4 分/);
  assert.equal(button(root,'0').disabled,true);assert.ok(root.all((node)=>node.className==='character-rating-score').every((node)=>node.attributes['aria-pressed']==='false'));
});

test('401 and 429 failures preserve server totals and require fresh verification for another attempt',async()=>{
  for(const status of [401,429]) {
    const x=setup(async(_path,body)=>{if(body)throw Object.assign(new Error('failed'),{status,retryAfter:17});return unrated;}),{root}=x.mount();await tick();
    await button(root,'2').fire();await tick();x.challenges[0].ready();const dialog=x.dialogs[0].element;await button(dialog,'确认提交 2 分').fire();
    assert.match(dialog.textContent,status===401?/访客身份/:/17 秒/);assert.equal(cls(root,'character-rating-average').textContent,'3.3');assert.equal(cls(root,'character-rating-voters').textContent,'27 位玩家');assert.equal(button(dialog,'确认提交 2 分').disabled,true);assert.equal(x.challenges[0].resets,1);
  }
});

test('closing during verification setup disposes nothing late, and a submitted result still updates surviving views',async()=>{
  let configResolve;const x=setup(async()=>unrated,{config:()=>new Promise((done)=>{configResolve=done;})}),view=x.mount();await tick();
  await button(view.root,'3').fire();x.dialogs[0].close();configResolve({enabled:true});await tick();assert.equal(x.challenges.length,0);assert.equal(button(view.root,'3').disabled,false);
  let finish;const y=setup((_path,body)=>body?new Promise((done)=>{finish=done;}):Promise.resolve(unrated)),other=y.mount();await tick();
  await button(other.root,'3').fire();await tick();y.challenges[0].ready();const pending=button(y.dialogs[0].element,'确认提交 3 分').fire();y.dialogs[0].close();assert.equal(y.challenges[0].destroyed,true);
  finish({...unrated,average:3.1,myScore:3,ratedToday:true});await pending;assert.equal(cls(other.root,'character-rating-average').textContent,'3.1');assert.equal(button(other.root,'3').disabled,true);
});

test('a stale GET cannot overwrite a confirmed vote and all mounted views of the character stay in sync',async()=>{
  let reads=0,oldRead;const x=setup((_path,body)=>body?Promise.resolve({...unrated,average:4,myScore:5,ratedToday:true}):++reads===1?Promise.resolve(unrated):new Promise((done)=>{oldRead=done;}));
  const first=x.mount();await tick();await button(first.root,'5').fire();await tick();x.challenges[0].ready();const second=x.mount();
  await button(x.dialogs[0].element,'确认提交 5 分').fire();oldRead(unrated);await tick();
  for(const {root} of [first,second]) {assert.equal(cls(root,'character-rating-average').textContent,'4.0');assert.equal(button(root,'5').disabled,true);assert.match(root.textContent,/今天已评 5 分/);}
});

test('malformed aggregates and unavailable service never become a synthetic score and can be retried',async()=>{
  let calls=0;const x=setup(async()=>++calls===1?{...unrated,voters:-1}:unrated),{root}=x.mount();await tick();
  assert.equal(cls(root,'character-rating-average').textContent,'—');assert.equal(button(root,'0').disabled,true);assert.match(root.textContent,/评分数据暂时不可用/);
  await button(root,'刷新评分').fire();assert.equal(cls(root,'character-rating-average').textContent,'3.3');
  const offline=setup(async()=>unrated,{protocol:'file:'}),view=offline.mount();await tick();assert.equal(offline.calls.length,0);assert.match(view.root.textContent,/离线版/);assert.equal(button(view.root,'5').disabled,true);
});

test('verification connection failure provides a retry and a detached old summary is not repainted',async()=>{
  let attempts=0;const x=setup(async()=>unrated,{config:async()=>{if(++attempts===1)throw new Error('验证连接失败');return {enabled:true};}}),view=x.mount();await tick();
  await button(view.root,'1').fire();await tick();const dialog=x.dialogs[0].element;assert.match(dialog.textContent,/验证连接失败/);await button(dialog,'重新连接评分服务').fire();assert.equal(x.challenges.length,1);
  let answer;const y=setup(()=>new Promise((done)=>{answer=done;})),old=y.mount();old.host.connected=false;const before=old.root.textContent;answer(unrated);await tick();assert.equal(old.root.textContent,before);
});

test('crossing the daily boundary refreshes on focus and only the server can unlock voting',async()=>{
  let finish;const rated={...unrated,myScore:3,ratedToday:true},x=setup(()=>x.calls.length===1?Promise.resolve(rated):new Promise(resolve=>{finish=resolve;})),view=x.mount();await tick();
  assert.equal(button(view.root,'刷新评分').hidden,false);assert.equal(button(view.root,'5').disabled,true);
  x.events.focus();await tick();assert.equal(x.calls.length,1);
  x.clock.now=nextVoteAt+1;x.events.focus();x.events.focus();await tick();
  assert.equal(x.calls.length,2);assert.equal(button(view.root,'5').disabled,true);assert.equal(x.challenges.length,0);
  finish({...rated,ratedToday:false,nextVoteAt:nextVoteAt+86400000});await tick();
  assert.equal(button(view.root,'5').disabled,false);assert.match(view.root.textContent,/选择 0–5 分/);
});

test('expired ratings refresh when visible or touched while hidden and detached summaries make no requests',async()=>{
  for(const trigger of ['visible','pointerdown','focusin']) {
    const x=setup(async()=>({...unrated,myScore:2,ratedToday:true})),view=x.mount();await tick();x.clock.now=nextVoteAt+1;
    if(trigger==='visible') {
      x.window.document.hidden=true;x.documentEvents.visibilitychange();x.events.focus();await tick();assert.equal(x.calls.length,1);
      x.window.document.hidden=false;x.documentEvents.visibilitychange();
    } else await view.root.fire(trigger);
    await tick();assert.equal(x.calls.length,2);assert.equal(button(view.root,'2').disabled,true);
    x.events.focus();await view.root.fire('pointerdown');await tick();assert.equal(x.calls.length,2);
  }
  const x=setup(async()=>({...unrated,ratedToday:true})),view=x.mount();await tick();view.host.connected=false;x.clock.now=nextVoteAt+1;
  x.events.focus();x.documentEvents.visibilitychange();await tick();assert.equal(x.calls.length,1);
});

test('failed automatic daily refresh keeps voting locked and an explicit refresh can recover',async()=>{
  const x=setup(async()=>{if(x.calls.length===2)throw new Error('网络失败');return x.calls.length===1?{...unrated,ratedToday:true}: {...unrated,nextVoteAt:nextVoteAt+86400000};}),view=x.mount();await tick();
  x.clock.now=nextVoteAt+1;x.events.focus();await tick();assert.equal(button(view.root,'5').disabled,true);assert.match(view.root.textContent,/网络失败/);
  x.events.focus();x.documentEvents.visibilitychange();await tick();assert.equal(x.calls.length,2);
  await button(view.root,'刷新评分').fire();assert.equal(x.calls.length,3);assert.equal(button(view.root,'5').disabled,false);
});

test('many visited characters share one pair of resume listeners and refresh only connected summaries',async()=>{
  const x=setup(async()=>({...unrated,ratedToday:true}));let view;
  for(let index=0;index<20;index++) {if(view)view.host.connected=false;view=x.mount(`c${index}`);await tick();}
  assert.deepEqual(x.listeners,['window:focus','document:visibilitychange']);
  x.clock.now=nextVoteAt+1;x.events.focus();await tick();assert.equal(x.calls.length,21);assert.equal(x.calls.at(-1)[0],'/ratings/characters/c19');
});
