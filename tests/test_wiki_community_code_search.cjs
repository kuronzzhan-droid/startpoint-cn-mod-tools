const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const community = require('../wiki/community-client.js');
class Node {
  constructor(tag, className='', text='') {Object.assign(this,{tag,className,text:String(text),children:[],events:{},attributes:{},value:'',disabled:false});}
  append(...nodes) {nodes.forEach(node=>{node.parent=this;this.children.push(node);});}
  replaceChildren(...nodes) {this.children.forEach(node=>node.parent=null);this.children=[];this.text='';this.append(...nodes);}
  get textContent() {return this.text+this.children.map(node=>node.textContent).join('');}
  set textContent(value) {this.replaceChildren();this.text=String(value);}
  set innerHTML(_value) {throw new Error('Untrusted search content must not use HTML insertion');}
  setAttribute(key,value) {this.attributes[key]=value;}
  addEventListener(name,callback) {this.events[name]=callback;}
  get isConnected() {return this.connected===true || Boolean(this.parent?.isConnected);}
  focus() {this.focused=true;}
  select() {this.selected=true;}
  async fire(name) {if(name==='click'&&this.disabled)return;return this.events[name]?.({preventDefault(){},stopPropagation(){}});}
  all(selector) {
    const match=node=>selector.startsWith('.') ? node.className.split(' ').includes(selector.slice(1)) : node.tag===selector;
    return this.children.flatMap(node=>[...(match(node)?[node]:[]),...node.all(selector)]);
  }
}
const el=(...args)=>new Node(...args), tick=()=>new Promise(resolve=>setImmediate(resolve));
const code='H4QUDN7W5R22', secondCode='BSFUGDCMCTD3';
const plain=value=>JSON.parse(JSON.stringify(value));
const team=community.teamCopy({main:['c1','c2','c3'],unison:['c4'],weapon:['w1'],soul:['w1']});
const found=(overrides={})=>({title:'公开码阵容',active:true,team:plain(team),...overrides});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
function setup({request=async()=>found(),equipment=async()=>{},load,keyword,previewOnly=false}={}) {
  const calls=[],activity=[],imports=[],location={hash:previewOnly?'#team':'#community'},data={
    characters:['c1','c2','c3','c4'].map(id=>({id,name:`角色 ${id}`,icon:`${id}.webp`})),
    equipment:[{id:'w1',name:'武器一',icon:'w1.webp',soul:{available:true}}],
  };
  const window={WFCommunity:{...community,client:{request:(...args)=>{calls.push(args);return request(...args);}}},
    WFWikiData:{loadEquipment:equipment},WFTeamImport:{load:(...args)=>{imports.push(args);return load?.(...args);}},
    navigator:{clipboard:{writeText:async()=>{}}},isSecureContext:true};
  const ui={el,picture:(src,alt,cls)=>{const node=el('img',cls);node.setAttribute('src',src);node.setAttribute('alt',alt);return node;}};
  const context={window,location,URLSearchParams,Date};
  for(const file of ['community-game-codes.js','community-code-search.js','community.js']) {
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki',file),'utf8'),context);
  }
  const box=window.WFCommunity.codeSearch({data,ui,onActiveChange:value=>activity.push(value),onKeywordSearch:keyword,previewOnly});box.connected=true;
  const input=box.all('.community-code-search-input')[0],form=box.all('form')[0],status=box.all('.community-code-search-status')[0];
  const search=box.all('button').find(node=>node.type==='submit'),clear=box.all('button').find(node=>node.textContent===(previewOnly?'清除':'返回列表'));
  const result=box.all('.community-code-search-result')[0];
  return {box,input,status,search,clear,result,calls,activity,imports,window,location,data,
    submit:async(value=code)=>{input.value=value;return form.fire('submit');},
    edit:async(value)=>{input.value=value;await input.fire('input');}};
}
const useButton=x=>x.box.all('button').find(node=>node.textContent==='装入 Wiki 编队');

test('lookup waits for explicit submit, normalizes pasted codes and deduplicates a busy submission',async()=>{
  const waiting=deferred(),x=setup({request:()=>waiting.promise});
  assert.equal(x.calls.length,0);await x.edit('ｈ４ｑｕｄｎ７ｗ５ｒ２２\n ');assert.equal(x.calls.length,0);
  const pending=x.submit(x.input.value);
  assert.equal(x.input.value,code);assert.deepEqual(x.calls,[[`/game-codes/${code}`]]);
  assert.equal(x.search.disabled,true);assert.equal(x.box.attributes['aria-busy'],'true');
  await x.submit(code);assert.equal(x.calls.length,1);
  waiting.resolve(found());await pending;
  assert.equal(x.search.disabled,false);assert.equal(x.box.attributes['aria-busy'],'false');
  assert.equal(x.status.textContent,'已找到队伍');assert.equal(x.result.all('article').length,1);
});

test('native ten-character and invalid codes never send API requests',async()=>{
  for(const [value,message] of [['23456789AB',/10 位游戏内队伍码/],['',/12 位/],['A'.repeat(11),/12 位/],
    ['AAAAAAAAAAA0',/12 位/],['AAAAAAAAAAAI',/12 位/],['/../teams/t1',/12 位/]]) {
    const x=setup();await x.submit(value);assert.equal(x.calls.length,0);assert.match(x.status.textContent,message);
    assert.equal(x.result.children.length,0);assert.equal(x.search.disabled,false);assert.equal(x.clear.hidden,false);
  }
});

test('a separately published code displays minimal private-team data without exposing response metadata',async()=>{
  const x=setup({request:async()=>found({id:'private-secret-id',visibility:'private',author:'秘密作者',notes:'秘密攻略',
    createdBy:'secret-account@example.com',audit:[{message:'秘密审计'}],gameCode:'DO-NOT-USE'})});
  await x.submit();assert.equal(x.calls.length,1);assert.match(x.result.textContent,/公开码阵容/);
  assert.doesNotMatch(x.result.textContent,/秘密|secret|DO-NOT-USE|private-secret-id/);
  assert.equal(x.result.all('input')[0].value,code);
  assert.ok(x.result.all('a').every(node=>!String(node.href).includes('community/')));
  assert.equal(x.result.all('.community-slot').length,18);assert.equal(x.result.all('details')[0].open,undefined);
  assert.equal(x.result.all('.community-slot-weapon').length,3);assert.equal(x.result.all('.community-slot-soul').length,3);
});

test('hostile titles stay text and never become executable DOM or an external link',async()=>{
  const title='<img src=x onerror=alert(1)><script>alert(2)</script>',x=setup({request:async()=>found({title})});
  await x.submit();assert.equal(x.result.all('h2')[0].textContent,title);
  assert.equal(x.result.all('script').length,0);assert.equal(x.result.all('img').length,10);
  assert.ok(x.result.all('a').every(node=>/^#(?:character|weapon)\//.test(node.href)));
  await useButton(x).fire('click');assert.equal(x.imports[0][1],title);
});

test('successful lookup loads a copied formation locally only after the explicit import action',async()=>{
  const payload=found(),x=setup({request:async()=>payload});await x.submit();
  assert.equal(x.imports.length,0);assert.equal(x.location.hash,'#community');assert.equal(useButton(x).disabled,false);
  await useButton(x).fire('click');assert.equal(x.location.hash,'#team');assert.equal(x.imports.length,1);
  assert.deepEqual(plain(x.imports[0][0]),team);assert.equal(x.imports[0][1],payload.title);
  x.imports[0][0].main[0]='changed';assert.equal(payload.team.main[0],'c1');
});

test('team-page lookup only previews a code and never offers to overwrite the current formation',async()=>{
  const x=setup({previewOnly:true});assert.equal(x.calls.length,0);await x.submit();
  assert.equal(x.status.textContent,'已找到队伍');assert.equal(x.result.all('article').length,1);
  assert.equal(x.result.all('.community-slot-weapon').length,3);assert.equal(x.result.all('.community-slot-soul').length,3);
  assert.equal(x.result.all('input')[0].value,code);assert.equal(useButton(x),undefined);
  assert.equal(x.imports.length,0);assert.equal(x.location.hash,'#team');assert.match(x.result.textContent,/不会改变当前编队/);
  await x.clear.fire('click');assert.equal(x.result.children.length,0);assert.equal(x.imports.length,0);assert.equal(x.location.hash,'#team');
});

test('not found and revoked codes display an actionable error and clear previous results',async()=>{
  for(const status of [404,410]) {
    let attempts=0;const x=setup({request:async()=>{if(++attempts===1)return found();throw Object.assign(new Error('private details'),{status});}});
    await x.submit();await x.submit(secondCode);
    assert.match(x.status.textContent,/不存在或已失效/);assert.doesNotMatch(x.status.textContent,/private details/);
    assert.equal(x.result.children.length,0);assert.equal(x.search.disabled,false);assert.equal(x.input.value,secondCode);
  }
});

test('inactive and malformed payloads do not display or import a formation',async()=>{
  for(const payload of [found({active:false}),null,found({title:42}),found({team:{}}),
    found({team:{...team,main:['c1','c2']}}),found({team:{...team,weapon:[null,'','']}})]) {
    let loads=0;const x=setup({request:async()=>payload,equipment:async()=>{loads++;}});await x.submit();
    assert.match(x.status.textContent,/不存在或已失效|数据不完整/);assert.equal(x.result.children.length,0);
    assert.equal(useButton(x),undefined);assert.equal(x.search.disabled,false);assert.equal(loads,0);
  }
});

test('network failures allow a deliberate retry without polling or losing the input',async()=>{
  let attempts=0;const x=setup({request:async()=>{if(++attempts===1)throw new Error('网络连接失败');return found();}});
  await x.submit();assert.equal(x.input.value,code);assert.match(x.status.textContent,/网络连接失败/);assert.equal(x.search.disabled,false);
  await tick();assert.equal(x.calls.length,1);await x.submit(x.input.value);assert.equal(x.calls.length,2);
  assert.equal(x.status.textContent,'已找到队伍');
});

test('equipment loading failure does not show a partial formation and can be retried',async()=>{
  let loads=0;const x=setup({equipment:async()=>{if(++loads===1)throw new Error('装备资源加载失败');}});
  await x.submit();assert.match(x.status.textContent,/装备资源加载失败/);assert.equal(x.result.children.length,0);
  assert.equal(x.search.disabled,false);await x.submit();assert.equal(x.result.all('article').length,1);assert.equal(loads,2);
});

test('current catalog validation disables local import for unknown or incompatible entries',async()=>{
  for(const replacement of [{main:['unknown','c2','c3']},{main:['','c2','c3']},{unison:['c1','','']},
    {weapon:['unknown','','']},{soul:['no-soul','','']}]) {
    const x=setup({request:async()=>found({team:{...team,...replacement}})});await x.submit();
    assert.equal(useButton(x).disabled,true);assert.match(x.result.textContent,/当前图鉴不匹配/);
    await useButton(x).fire('click');assert.equal(x.imports.length,0);assert.equal(x.location.hash,'#community');
  }
});

test('import errors stay visible and do not navigate away',async()=>{
  const x=setup({load:()=>{throw new Error('本地编队保存失败');}});await x.submit();await useButton(x).fire('click');
  assert.equal(x.location.hash,'#community');assert.match(x.status.textContent,/本地编队保存失败/);
});

test('clearing a pending search returns to the list and ignores its late response',async()=>{
  const waiting=deferred(),x=setup({request:()=>waiting.promise}),pending=x.submit();
  await x.clear.fire('click');assert.equal(x.input.value,'');assert.equal(x.input.focused,true);assert.equal(x.clear.hidden,true);
  assert.equal(x.activity.at(-1),false);assert.equal(x.search.disabled,false);
  waiting.resolve(found());await pending;assert.equal(x.result.children.length,0);assert.equal(x.status.textContent,'');
});

test('editing while searching invalidates the old result and the next search wins',async()=>{
  const a=deferred(),b=deferred();let count=0;const x=setup({request:()=>++count===1?a.promise:b.promise});
  const first=x.submit();await x.edit(secondCode);assert.equal(x.activity.at(-1),false);
  const second=x.submit(secondCode);a.resolve(found({title:'旧结果'}));await first;
  assert.equal(x.search.disabled,true);assert.equal(x.result.children.length,0);assert.equal(x.status.textContent,'正在查找队伍…');
  b.resolve(found({title:'新结果'}));await second;assert.match(x.result.textContent,/新结果/);assert.doesNotMatch(x.result.textContent,/旧结果/);
  assert.equal(x.search.disabled,false);
});

test('navigation or removing the search component prevents late responses from rendering or loading equipment',async()=>{
  for(const leave of ['route','unmount']) {
    const waiting=deferred();let loads=0;const x=setup({request:()=>waiting.promise,equipment:async()=>{loads++;}}),pending=x.submit();
    if(leave==='route')x.location.hash='#weapons';else x.box.connected=false;
    waiting.resolve(found());await pending;assert.equal(x.result.children.length,0);assert.equal(loads,0);assert.equal(x.imports.length,0);
  }
});

test('clear, editing or navigation during equipment loading also discard the stale formation',async()=>{
  for(const leave of ['clear','edit','route','unmount']) {
    const equipment=deferred(),x=setup({equipment:()=>equipment.promise}),pending=x.submit();await tick();
    if(leave==='clear')await x.clear.fire('click');else if(leave==='edit')await x.edit(secondCode);
    else if(leave==='route')x.location.hash='#weapons';else x.box.connected=false;
    equipment.resolve();await pending;assert.equal(x.result.children.length,0);assert.equal(x.imports.length,0);
    if(['clear','edit'].includes(leave)){assert.equal(x.status.textContent,'');assert.equal(x.search.disabled,false);}
  }
});

test('a stale rejected request cannot overwrite the latest successful search',async()=>{
  const first=deferred();let count=0;const x=setup({request:()=>++count===1?first.promise:Promise.resolve(found({title:'保留新结果'}))});
  const pending=x.submit();await x.edit(secondCode);await x.submit(secondCode);
  first.reject(new Error('旧请求失败'));await pending;
  assert.match(x.result.textContent,/保留新结果/);assert.equal(x.status.textContent,'已找到队伍');assert.equal(x.search.disabled,false);
});

test('unified search forwards explicit keywords intact while retaining the code lookup route',async()=>{
  const keywords=[],x=setup({keyword:async term=>keywords.push(term)});
  await x.edit(' 光 技能队 ');assert.equal(keywords.length,0);assert.equal(x.calls.length,0);
  await x.submit(x.input.value);assert.deepEqual(keywords,['光 技能队']);assert.equal(x.input.value,'光 技能队');
  assert.equal(x.calls.length,0);assert.equal(x.search.disabled,false);assert.equal(x.activity.at(-1),false);
  await x.submit('h4qudn7w5r22');assert.equal(x.calls.length,1);assert.equal(keywords.length,1);
  await x.submit('23456789AB');assert.equal(x.calls.length,1);assert.equal(keywords.length,1);assert.match(x.status.textContent,/10 位游戏内队伍码/);
});

test('unified clear resets the directory query and repeated keyword submits do not duplicate a pending request',async()=>{
  const waiting=deferred(),keywords=[],x=setup({keyword:term=>{keywords.push(term);return term?waiting.promise:Promise.resolve();}});
  const pending=x.submit('入门队');await x.submit('入门队');assert.deepEqual(keywords,['入门队']);
  waiting.resolve();await pending;await x.clear.fire('click');await tick();
  assert.deepEqual(keywords,['入门队','']);assert.equal(x.input.value,'');assert.equal(x.clear.hidden,true);assert.equal(x.search.disabled,false);
});

test('unified keyword callback failure remains retryable without calling the code API',async()=>{
  let attempts=0;const x=setup({keyword:async()=>{if(++attempts===1)throw new Error('关键词连接失败');}});
  await x.submit('光技伤');assert.match(x.status.textContent,/关键词连接失败/);assert.equal(x.input.value,'光技伤');
  assert.equal(x.search.disabled,false);await x.submit(x.input.value);assert.equal(attempts,2);assert.equal(x.calls.length,0);
  assert.equal(x.status.textContent,'');
});
