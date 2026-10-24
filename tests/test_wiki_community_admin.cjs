const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const community = require('../wiki/community-client.js');
const teamState = require('../wiki/team-state.js');
const source = fs.readFileSync(path.join(__dirname,'../wiki/community-admin.js'),'utf8');
class Node {
  constructor(tag, className = '', value = '') {
    Object.assign(this,{tag,className,text:String(value || ''),children:[],attributes:{},dataset:{},events:{},value:'',hidden:false,disabled:false});
  }
  append(...nodes) {for (const node of nodes) {node.parent = this; this.children.push(node);}}
  replaceChildren(...nodes) {this.children.forEach((node)=>{node.parent=null;}); this.children=[]; this.append(...nodes);}
  setAttribute(key,value) {this.attributes[key]=value;}
  getAttribute(key) {return this.attributes[key];}
  addEventListener(key,fn) {this.events[key]=fn;}
  querySelectorAll(selector) {return this.all(node=>selector.startsWith('.') ? node.className.split(' ').includes(selector.slice(1)) : node.tag===selector);}
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
  async click() {if (!this.disabled) await this.events.click?.();}
  get isConnected() {return Boolean(this.root || this.parent?.isConnected);}
  get childElementCount() {return this.children.length;}
  get textContent() {return this.text+this.children.map((node)=>node.textContent).join('');}
  set textContent(value) {this.text=String(value); this.children=[];}
  all(predicate) {return this.children.flatMap((node)=>[...(predicate(node)?[node]:[]),...node.all(predicate)]);}
}
const el=(tag,cls,text)=>new Node(tag,cls,text);
const one=(node,cls)=>node.all((n)=>n.className.split(' ').includes(cls))[0];
const visible=node=>!node.hidden&&(!node.parent||visible(node.parent));
const control=(node,label)=>node.all(n=>visible(n)&&n.attributes['aria-label']===label)[0];
const button=(node,label)=>node.all((n)=>n.tag==='button'&&n.textContent===label)[0];
const select=(node,label)=>node.all((n)=>n.tag==='select'&&n.attributes['aria-label']===label)[0];
const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
function fixture() {
  const characters=Array.from({length:85},(_,i)=>({id:`c${i+1}`,name:`角色${i+1}`,element:'火',rarity:5,aliases:[]}));
  const equipment=[{id:'w1',name:'武器1',soul:{available:true}},{id:'w2',name:'武器2'}];
  const item={id:'team1',title:'测试盘',notes:'原备注',author:'投稿者',element:'火',damageTypes:['skill'],revision:4,status:'approved',visibility:'public',createdBy:'trusted',
    team:{main:['c1','c2','c3'],unison:['','',''],weapon:['w1','',''],soul:['','','']}};
  return {data:{characters,equipment},item};
}
function setup(handler,options={}) {
  const {data,item}=fixture(),calls=[],host=el('main'); host.root=true;
  const fetcher=async(url,init)=>{calls.push({url,...init}); return handler ? handler(url,init,{data,item}) :
    response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'trusted',email:'admin@example.test',role:options.role||'editor'}:{items:[item],nextCursor:''});};
  const window={WFTeamState:teamState,WFCharacterOrder:{compareTeam:(a,b)=>a.name.localeCompare(b.name)},
    WFCharacterFilters:{create:({onChange})=>{const search=el('input');search.setAttribute('aria-label','搜索角色');search.value='';search.addEventListener('input',onChange);return {element:search,matches:item=>item.name.includes(search.value)};}},
    WFCommunity:community,location:{protocol:options.protocol||'https:',hostname:options.hostname||'wiki.example'},fetch:fetcher,
    WFWikiData:{loadEquipment:async()=>data.equipment}, WFCommunityAdminConfirm:{ask:options.confirm || (()=>Promise.resolve(true))}};
  const context={window,AbortController,setTimeout,clearTimeout,URLSearchParams};
  for (const file of ['equipment-order.js','team-equipment-filters.js','team-candidates.js','community-team-picker.js','community-game-codes.js','community-admin-cards.js','community-admin-editor.js']) vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki',file),'utf8'),context);
  vm.runInNewContext(source,context);
  return {host,window,data,item,calls,start:()=>window.renderWikiCommunityAdmin(host,data,{el})};
}
test('offline and unconfigured sites never claim successful administrator authentication',async()=>{
  const offline=setup(null,{protocol:'file:'}); await offline.start();
  assert.equal(offline.calls.length,0); assert.match(offline.host.textContent,/离线版不能登录/);
  const disabled=setup(()=>response({enabled:false})); await disabled.start();
  assert.equal(disabled.calls.length,1); assert.match(disabled.host.textContent,/暂未启用社区/);
  assert.equal(disabled.host.all((n)=>n.tag==='form').length,0);
  assert.equal(one(disabled.host,'admin-controls').hidden,false);
});
test('authentication-required state links to server login and cannot accept a supplied email',async()=>{
  const x=setup((url)=>response(url.endsWith('/config')?{enabled:true,development:true}:
    {error:'admin_auth_required',message:'login'},url.endsWith('/config')?200:401));
  await x.start();
  assert.equal(x.host.all((n)=>n.tag==='a'&&n.textContent==='登录管理员')[0].href,'/api/community/admin/login');
  assert.equal(one(x.host,'admin-controls').hidden,false);
  assert.equal(x.host.all((n)=>n.tag==='input').length,0);
  assert.equal(button(x.host,'本机测试：登录测试管理员'),undefined);
});
test('local development login requires an actual cookie endpoint response before showing verified identity',async()=>{
  let logged=false;
  const x=setup((url,init,{item})=>{
    if(url.endsWith('/config')) return response({enabled:true,development:true});
    if(url.endsWith('/development-admin-login')) {assert.equal(init.method,'POST');logged=true;return response({ok:true});}
    if(url.endsWith('/me')) return logged?response({id:'dev',email:'dev-admin@example.test'}):response({error:'admin_auth_required'},401);
    return response({items:[item],nextCursor:''});
  },{protocol:'http:',hostname:'127.0.0.1'});
  await x.start(); assert.doesNotMatch(x.host.textContent,/dev-admin@example.test/);
  await button(x.host,'本机测试：登录测试管理员').click();
  assert.match(x.host.textContent,/本机测试身份 · dev-admin@example.test/);
});
test('editing uses searchable portrait candidates and preserves original data until saving',async()=>{
  const x=setup();await x.start();const before=JSON.stringify(x.data);
  await button(x.host,'编辑队伍').click();const form=one(x.host,'admin-edit-form');
  assert.equal(form.all(n=>n.className==='community-picker-slot').length,12);
  assert.equal(form.querySelectorAll('.team-candidate').length,0);
  await control(form,'调整1号主位：角色1').click();
  const search=control(form,'搜索角色');search.value='角色85';search.events.input();
  assert.equal(form.querySelectorAll('.team-candidate').length,1);await control(form,'选择角色85').click();
  assert.ok(control(form,'调整1号主位：角色85'));assert.equal(JSON.stringify(x.data),before);
  await control(form,'调整1号魂珠：空位').click();assert.equal(control(form,'选择武器2魂珠').disabled,true);
});

test('revision conflicts preserve entered values and lock repeated saves until explicit reload',async()=>{
  const x=setup((url,init,{item})=>init.method==='PATCH'?response({error:'edit_conflict'},409):
    response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'a',email:'a@b.test'}:{items:[item],nextCursor:''}));
  await x.start(); await button(x.host,'编辑队伍').click(); const form=one(x.host,'admin-edit-form');
  const notes=form.all((n)=>n.tag==='textarea')[0]; notes.value='保留我的输入';
  await form.events.submit({preventDefault(){}});
  assert.match(one(form,'admin-edit-status').textContent,/已被其他管理员修改/);
  assert.equal(notes.value,'保留我的输入'); assert.equal(button(form,'保存修改').disabled,true);
  await form.events.submit({preventDefault(){}});
  assert.equal(x.calls.filter((call)=>call.method==='PATCH').length,1);
  assert.equal(button(form,'重新加载列表').hidden,false);
  await button(form,'重新加载列表').click(); assert.equal(form.isConnected,false);
});
test('saving edited slots and hidden state sends the original revision with same-origin credentials',async()=>{
  let saved;
  const x=setup((url,init,{item})=>{
    if(init.method==='PATCH') {saved=JSON.parse(init.body); return response({team:{...item,...saved,revision:5}});}
    return response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'a',email:'a@b.test'}:{items:[item],nextCursor:''});
  });
  await x.start(); await button(x.host,'编辑队伍').click(); const form=one(x.host,'admin-edit-form');
  await control(form,'调整1号主位：角色1').click();await control(form,'选择角色4').click();
  const meta=one(form,'admin-edit-meta'); meta.all((n)=>n.tag==='select')[1].value='hidden';
  select(form,'配队分类').value='原版毕业队';
  select(form,'玩法分区').value='five-boss';
  await form.events.submit({preventDefault(){}});
  assert.equal(saved.expectedRevision,4); assert.equal(saved.team.main[0],'c4'); assert.equal(saved.status,'hidden');
  assert.equal(saved.damageTypes[0],'skill'); assert.equal(x.calls.find((call)=>call.method==='PATCH').credentials,'same-origin');
  assert.equal(saved.category,'原版毕业队');
  assert.equal(saved.section,'five-boss');
  assert.match(one(x.host,'admin-notice').textContent,/已保存.*当前版本 5/);
});
test('invalid duplicate characters and missing damage selections never reach the write endpoint',async()=>{
  const x=setup();x.item.team.main[0]='c2';await x.start();await button(x.host,'编辑队伍').click();const form=one(x.host,'admin-edit-form');
  await form.events.submit({preventDefault(){}}); assert.match(one(form,'admin-edit-status').textContent,/重复/);
  form.all((n)=>n.type==='checkbox').forEach((node)=>{node.checked=false;});
  await form.events.submit({preventDefault(){}}); assert.match(one(form,'admin-edit-status').textContent,/至少选择/);
  assert.equal(x.calls.filter((call)=>call.method==='PATCH').length,0);
});
test('late authentication cannot overwrite a different route in the same reused host',async()=>{
  let answer;
  const x=setup((url)=>url.endsWith('/config')?response({enabled:true}):new Promise((resolve)=>{answer=resolve;}));
  const pending=x.start(); await new Promise(setImmediate);
  x.host.replaceChildren(el('section','','另一页面'));
  answer(response({id:'a',email:'a@b.test'})); await pending;
  assert.equal(x.host.textContent,'另一页面'); assert.equal(x.calls.length,2);
});

test('administrators can filter categories and preserve the empty legacy category while editing',async()=>{
  const x=setup();await x.start();
  const category=select(x.host,'查看配队分类');assert.equal(category.children.length,7);category.value='uncategorized';category.events.change();await new Promise(setImmediate);
  assert.equal(new URL(x.calls.at(-1).url,'https://wiki.example').searchParams.get('category'),'uncategorized');
  await button(x.host,'编辑队伍').click();assert.equal(select(x.host,'配队分类').value,'');
  assert.equal(select(x.host,'配队分类').children[0].textContent,'未分类（历史队伍）');
  assert.equal(select(x.host,'玩法分区').value,'');assert.equal(select(x.host,'玩法分区').children.find(node=>node.value==='').textContent,'其他');
});

test('administrators filter gameplay independently and reject invalid section edits before a request',async()=>{
  const x=setup();await x.start();
  const section=select(x.host,'查看玩法分区');section.value='general';section.events.change();await new Promise(setImmediate);
  const category=select(x.host,'查看配队分类');category.value='玩具盘';category.events.change();await new Promise(setImmediate);
  const params=new URL(x.calls.at(-1).url,'https://wiki.example').searchParams;
  assert.equal(params.get('section'),'general');assert.equal(params.get('category'),'玩具盘');
  await button(x.host,'编辑队伍').click();select(x.host,'玩法分区').value='not-a-section';
  await one(x.host,'admin-edit-form').events.submit({preventDefault(){}});
  assert.match(one(x.host,'admin-edit-status').textContent,/有效的玩法分区/);assert.equal(x.calls.filter((call)=>call.method==='PATCH').length,0);
});

test('space and code filters combine, and only station managers can select all private teams',async()=>{
  for(const role of ['editor','owner','deputy']) {
    const x=setup(null,{role});await x.start();const scope=select(x.host,'查看空间'),code=select(x.host,'队伍码状态');
    assert.equal(scope.children.some((node)=>node.value==='private'),role!=='editor');
    scope.value='mine';scope.events.change();await new Promise(setImmediate);code.value='none';code.events.change();await new Promise(setImmediate);
    const params=new URL(x.calls.at(-1).url,'https://wiki.example').searchParams;assert.equal(params.get('scope'),'mine');assert.equal(params.get('code'),'none');
    await button(x.host,'编辑队伍').click();assert.ok(select(x.host,'保存位置').children.some((node)=>node.value==='private'));
  }
});

test('an editor cannot move another creator or legacy public plate into private storage',async()=>{
  for(const createdBy of ['someone-else','']) {
    const x=setup((url,init,{item})=>response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'trusted',email:'admin@example.test',role:'editor'}:{items:[{...item,createdBy}]}));
    await x.start();await button(x.host,'编辑队伍').click();const form=one(x.host,'admin-edit-form'),visibility=select(form,'保存位置');
    assert.equal(visibility.children.some((node)=>node.value==='private'),false);visibility.value='private';
    await form.events.submit({preventDefault(){}});assert.match(one(form,'admin-edit-status').textContent,/创建者/);
    assert.equal(x.calls.filter((call)=>call.method==='PATCH').length,0);
  }
});

test('unsaved normalized form values block code publication for all metadata, damage and twelve slots',async()=>{
  const x=setup(null,{role:'owner'});await x.start();await button(x.host,'编辑队伍').click();
  const form=one(x.host,'admin-edit-form'),make=button(form,'公开队伍码');assert.equal(make.disabled,false);
  const values=[['队伍标题','新标题'],['投稿者署名','新作者'],['队伍说明','新备注'],['属性分类','universal'],['展示状态','hidden'],['配队分类','玩具盘'],['玩法分区','abyss'],['保存位置','private']];
  for(const [label,value] of values) {
    const control=form.all((node)=>node.attributes['aria-label']===label)[0],before=control.value;control.value=value;form.events.input();
    assert.equal(make.disabled,true,label);await make.events.click();control.value=before;form.events.input();assert.equal(make.disabled,false,label);
  }
  for(const control of form.all((node)=>node.type==='checkbox')) {const before=control.checked;control.checked=!before;form.events.change();assert.equal(make.disabled,true);control.checked=before;form.events.change();assert.equal(make.disabled,false);}
  for(const [group,label] of [['main','主位'],['unison','合击'],['weapon','装备'],['soul','魂珠']]) for(let index=1;index<=3;index++) {
    const before=x.item.team[group][index-1],character=group==='main'||group==='unison';
    const target=form.all(node=>node.attributes['aria-label']?.startsWith(`调整${index}号${label}：`))[0];await target.click();
    await control(form,character?'选择角色4':group==='soul'?'选择武器1魂珠':'选择武器2').click();
    assert.equal(make.disabled,true,`${label} ${index}`);await make.events.click();
    if (before) await control(form,character?`选择角色${before.slice(1)}`:`选择武器${before.slice(1)}${group==='soul'?'魂珠':''}`).click();
    else await button(form,'清空此位').click();
    assert.equal(make.disabled,false);
  }
  const title=form.all((node)=>node.attributes['aria-label']==='队伍标题')[0];title.value+='  ';form.events.input();assert.equal(make.disabled,false);
  assert.equal(x.calls.filter((call)=>call.method==='POST').length,0);assert.doesNotMatch(one(form,'admin-dirty-status').textContent,/未保存/);
});

test('saving establishes a new clean revision for explicit publication, while save conflicts keep it blocked',async()=>{
  let saved,posted;const x=setup((url,init,{item})=>{
    if(init.method==='PATCH') {saved=JSON.parse(init.body);return response({team:{...item,...saved,revision:5}});}
    if(url.endsWith('/game-code')) {posted=JSON.parse(init.body);return response({teamRevision:5,active:true,gameCode:'H4QUDN7W5R22'});}
    return response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'trusted',email:'admin@example.test',role:'editor'}:{items:[saved?{...item,...saved,revision:5}:item]});
  });
  await x.start();await button(x.host,'编辑队伍').click();let form=one(x.host,'admin-edit-form');
  select(form,'保存位置').value='private';form.events.change();assert.equal(button(form,'公开队伍码').disabled,true);
  await form.events.submit({preventDefault(){}});assert.equal(saved.visibility,'private');
  form=one(x.host,'admin-edit-form');assert.equal(button(form,'公开队伍码').disabled,false);await button(form,'公开队伍码').click();assert.equal(posted.expectedRevision,5);
  const conflict=setup((url,init,{item})=>init.method==='PATCH'?response({error:'edit_conflict'},409):response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'trusted',email:'admin@example.test'}:{items:[item]}));
  await conflict.start();await button(conflict.host,'编辑队伍').click();const stale=one(conflict.host,'admin-edit-form');
  await stale.events.submit({preventDefault(){}});stale.events.change();assert.equal(button(stale,'公开队伍码').disabled,true);
  await button(stale,'公开队伍码').events.click();assert.equal(conflict.calls.filter((call)=>call.method==='POST').length,0);
});

test('cloud deletion is explicit, revision protected and keeps a recoverable row',async()=>{
  let record,deleted;
  const x=setup((url,init,{item})=>{
    record ||= {...item};
    if(init.method==='DELETE') {deleted=JSON.parse(init.body);record={...record,status:'hidden',gameCode:null,revision:5};return response({team:record});}
    return response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'trusted',email:'a@b.test'}:
      {items:new URL(url,'https://wiki.test').searchParams.get('status')===record.status?[record]:[]});
  });
  await x.start(); await button(x.host,'删除').click();
  assert.deepEqual(deleted,{expectedRevision:4});assert.match(one(x.host,'admin-notice').textContent,/回收站.*旧?原队伍码已停用/);
  await button(x.host,'回收站').click();assert.ok(button(x.host,'恢复队伍'));
  assert.match(x.host.textContent,/原队伍码不可用/);assert.equal(record.status,'hidden');
});

test('cancelled delete sends nothing; a restore does not publish a game code',async()=>{
  const cancelled=setup(null,{confirm:()=>false});await cancelled.start();await button(cancelled.host,'删除').click();
  assert.equal(cancelled.calls.filter(call=>call.method==='DELETE').length,0);
  let restored;
  const x=setup((url,init,{item})=>{
    if(init.method==='PATCH') {restored=JSON.parse(init.body);return response({team:{...item,status:'approved',revision:5}});}
    return response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'trusted',email:'a@b.test'}:{items:[{...item,status:'hidden'}]});
  });
  await x.start();await button(x.host,'恢复队伍').click();
  assert.deepEqual(restored,{expectedRevision:4,status:'approved'});
  assert.equal(x.calls.filter(call=>call.method==='POST').length,0);
  assert.match(one(x.host,'admin-notice').textContent,/已恢复.*重新公开/);
});

test('search is sent to the API with scope and code filters, never limited to loaded cards',async()=>{
  const x=setup();await x.start();await button(x.host,'我的空间').click();
  const input=x.host.all(n=>n.attributes['aria-label']==='搜索已保存队伍')[0];input.value=' 火队%_ ';
  select(x.host,'队伍码状态').value='none';await button(x.host,'刷新列表').click();
  const params=new URL(x.calls.at(-1).url,'https://wiki.test').searchParams;
  assert.equal(params.get('q'),'火队%_');assert.equal(params.get('scope'),'mine');assert.equal(params.get('code'),'none');
});

test('rejected dirty-editor navigation preserves the form and list version',async()=>{
  const x=setup(null,{confirm:()=>false});await x.start();await button(x.host,'编辑队伍').click();
  const form=one(x.host,'admin-edit-form'),notes=form.all(n=>n.tag==='textarea')[0];notes.value='未保存的说明';
  const calls=x.calls.length;await button(x.host,'刷新列表').click();
  assert.equal(x.calls.length,calls);assert.equal(form.isConnected,true);assert.equal(notes.value,'未保存的说明');
});

test('delete conflicts keep the card and tell the administrator to refresh',async()=>{
  const x=setup((url,init,{item})=>init.method==='DELETE'?response({error:'edit_conflict'},409):
    response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'trusted',email:'a@b.test'}:{items:[item]}));
  await x.start();await button(x.host,'删除').click();
  assert.match(one(x.host,'admin-notice').textContent,/已被其他管理员修改/);assert.ok(button(x.host,'编辑队伍'));
});

test('pending confirmation and slow deletion block editor, new-team and list switches until completion',async()=>{
  let confirmAction,completeDelete,loaded=0,imports=0;
  const x=setup((url,init,{item})=>{
    if(init.method==='DELETE') return new Promise(resolve=>{completeDelete=()=>resolve(response({team:{...item,status:'hidden',revision:5}}));});
    if(url.endsWith('/config')) return response({enabled:true});
    if(url.endsWith('/me')) return response({id:'trusted',email:'a@b.test'});
    loaded++;return response({items:[item,{...item,id:'team2',title:'另一队伍'}],nextCursor:'more'});
  });
  x.window.WFCommunityAdminConfirm={ask:()=>new Promise(resolve=>{confirmAction=resolve;})};
  x.window.WFTeamImport={load:()=>{imports++;}};
  await x.start();await button(x.host,'编辑队伍').click();
  const original=one(x.host,'admin-edit-form'),page=one(x.host,'community-admin');
  const secondEdit=x.host.all(n=>n.tag==='button'&&n.textContent==='编辑队伍')[1];
  const newTeam=x.host.all(n=>n.tag==='a'&&n.textContent==='＋ 新建队伍')[0];
  const home=x.host.all(n=>n.tag==='a'&&n.href==='#community')[0];
  const pending=button(x.host,'删除').click();
  async function assertLocked() {
    const count=x.calls.length;let prevented=0;
    await secondEdit.click();await button(x.host,'刷新列表').click();await button(x.host,'继续加载 / 重试').click();
    await button(x.host,'我的空间').click();
    await newTeam.events.click({preventDefault(){prevented++;}});await home.events.click({preventDefault(){prevented++;}});
    assert.equal(one(x.host,'admin-edit-form'),original);assert.equal(original.isConnected,true);
    assert.equal(x.calls.length,count);assert.equal(prevented,2);assert.equal(imports,0);
    assert.match(one(x.host,'admin-notice').textContent,/正在处理队伍操作/);
  }
  await assertLocked();assert.equal(x.calls.filter(call=>call.method==='DELETE').length,0);
  confirmAction(true);await new Promise(setImmediate);assert.equal(page.inert,true);
  await assertLocked();completeDelete();await pending;
  assert.equal(page.inert,false);assert.equal(page.attributes['aria-busy'],'false');assert.equal(loaded,2);
  assert.equal(original.isConnected,false);await button(x.host,'编辑队伍').click();assert.ok(one(x.host,'admin-edit-form'));
});

test('cancelling asynchronous deletion releases navigation without sending a write',async()=>{
  let confirmAction;const x=setup();
  x.window.WFCommunityAdminConfirm={ask:()=>new Promise(resolve=>{confirmAction=resolve;})};
  await x.start();const pending=button(x.host,'删除').click();
  await button(x.host,'编辑队伍').click();assert.equal(one(x.host,'admin-edit-form'),undefined);
  confirmAction(false);await pending;
  assert.equal(x.calls.filter(call=>call.method==='DELETE').length,0);
  assert.equal(one(x.host,'community-admin').attributes['aria-busy'],'false');
  await button(x.host,'编辑队伍').click();assert.ok(one(x.host,'admin-edit-form'));
});

test('returning to the community preserves dirty edits when leaving is declined',async()=>{
  let accepted=false;const x=setup(null,{confirm:()=>accepted});await x.start();await button(x.host,'编辑队伍').click();
  const form=one(x.host,'admin-edit-form'),notes=form.all(n=>n.tag==='textarea')[0];notes.value='未保存';
  const home=x.host.all(n=>n.tag==='a'&&n.href==='#community')[0];let prevented=0;
  await home.events.click({preventDefault(){prevented++;}});assert.equal(prevented,1);assert.equal(form.isConnected,true);assert.equal(notes.value,'未保存');
  assert.equal(x.window.location.hash,undefined);
  accepted=true;await home.events.click({preventDefault(){prevented++;}});assert.equal(prevented,2);assert.equal(x.window.location.hash,'#community');
});

test('authorized admin cards show valid private codes while public readonly still excludes them',async()=>{
  const code='H4QUDN7W5R22';
  const x=setup((url,init,{item})=>response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'trusted',email:'a@b.test'}:
    {items:[{...item,visibility:'private',gameCode:code},{...item,id:'deleted',visibility:'private',status:'hidden',gameCode:code},
      {...item,id:'invalid',visibility:'private',gameCode:'not-a-code'},{...item,id:'pending',status:'pending',gameCode:code}]}));
  await x.start();const cards=x.host.all(n=>n.className==='admin-team-row');
  assert.equal(one(cards[0],'community-game-code-value').value,code);assert.doesNotMatch(cards[0].textContent,/尚未公开/);
  assert.equal(one(cards[1],'community-game-code-value'),undefined);assert.match(cards[1].textContent,/原队伍码不可用/);
  assert.equal(one(cards[2],'community-game-code-value'),undefined);assert.equal(one(cards[3],'community-game-code-value'),undefined);
  const privateRecord={...x.item,visibility:'private',gameCode:code};
  assert.equal(x.window.WFCommunityGameCodes.readonly(privateRecord,{el}),null);
  assert.equal(privateRecord.visibility,'private');assert.ok(x.window.WFCommunityGameCodes.adminReadonly(privateRecord,{el}));
});

test('malformed or unrelated deletion receipts preserve the card and request verification',async()=>{
  for (const receipt of [{id:'team1'}, {id:'team1',revision:'invalid'}, {id:'team1',revision:4.5}, {id:'other',revision:5}]) {
    const x=setup((url,init,{item})=>init.method==='DELETE'?response({team:receipt}):
      response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'trusted',email:'a@b.test'}:{items:[item]}));
    await x.start();await button(x.host,'删除').click();
    assert.match(one(x.host,'admin-notice').textContent,/未返回新版本/);assert.ok(button(x.host,'编辑队伍'));
    assert.equal(x.calls.filter(call=>call.url.includes('/admin/teams?')).length,1);
    assert.equal(one(x.host,'community-admin').inert,false);
  }
});

test('registered navigation guard protects drafts and delegates new-team preparation once',async()=>{
  let guard,allowed=false,imports=0;const navigated=[],x=setup(null,{confirm:()=>allowed});
  x.window.WFNavigationGuard={register(value){guard=value;},async navigate(hash,before){if(await guard.canLeave()){before?.();navigated.push(hash);}}};
  x.window.WFTeamImport={load:()=>{imports++;}};
  await x.start();assert.equal(guard.needsProtection(),false);await button(x.host,'编辑队伍').click();
  const form=one(x.host,'admin-edit-form');form.all(n=>n.tag==='textarea')[0].value='草稿';assert.equal(guard.needsProtection(),true);
  const create=x.host.all(n=>n.tag==='a'&&n.href==='#team')[0];assert.equal(create.attributes['data-navigation-guard'],'custom');
  await create.events.click({preventDefault(){}});assert.equal(imports,0);assert.equal(form.isConnected,true);
  allowed=true;await create.events.click({preventDefault(){}});assert.equal(imports,1);assert.deepEqual(navigated,['#team']);
  x.host.replaceChildren();assert.equal(guard.isActive(),false);
});

test('game-code requests lock saving and navigation until the server response arrives',async()=>{
  let finish;const x=setup((url,init,{item})=>init.method==='POST'?new Promise(resolve=>{finish=resolve;}):
    response(url.endsWith('/config')?{enabled:true}:url.endsWith('/me')?{id:'trusted',email:'a@b.test'}:{items:[item]}));
  await x.start();await button(x.host,'编辑队伍').click();const form=one(x.host,'admin-edit-form');
  const pending=button(form,'公开队伍码').click();assert.equal(form.isBusy(),true);assert.equal(button(form,'保存修改').disabled,true);
  form.all(n=>n.tag==='textarea')[0].value='新修改';await form.events.submit({preventDefault(){}});
  assert.equal(x.calls.filter(call=>call.method==='PATCH').length,0);assert.equal(await form.canClose(),false);
  finish(response({teamRevision:4,active:true,gameCode:'H4QUDN7W5R22'}));await pending;
  assert.equal(form.isBusy(),false);assert.equal(button(form,'保存修改').disabled,false);assert.equal(form.isDirty(),true);
});

test('account controls preserve rejected drafts and lock new editors during account requests',async()=>{
  let actions,accepted=false,guard;const x=setup((url,init,{item})=>response(url.endsWith('/config')?{enabled:true,authMode:'password'}:{items:[item]}),{confirm:()=>accepted});
  x.window.WFCommunityAuth={ensure:async()=>({id:'trusted',email:'a@b.test',role:'owner'}),controls:(_host,_id,_ui,_refresh,options)=>{actions=options;}};
  x.window.WFNavigationGuard={register(value){guard=value;}};
  await x.start();await button(x.host,'编辑队伍').click();const form=one(x.host,'admin-edit-form');form.all(n=>n.tag==='textarea')[0].value='草稿';
  assert.equal(await actions.beforeAction(),false);assert.equal(form.isConnected,true);
  accepted=true;assert.equal(await actions.beforeAction(),true);assert.equal(form.isConnected,false);
  actions.onBusyChange(true);assert.equal(guard.needsProtection(),true);assert.equal(await guard.canLeave(),false);
  await button(x.host,'编辑队伍').click();assert.equal(one(x.host,'admin-edit-form'),undefined);
  actions.onBusyChange(false);await button(x.host,'编辑队伍').click();assert.ok(one(x.host,'admin-edit-form'));
});
