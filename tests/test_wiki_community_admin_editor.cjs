const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const community = require('../wiki/community-client.js');
const teamState = require('../wiki/team-state.js');
const source = fs.readFileSync(path.join(__dirname,'../wiki/community-admin-editor.js'),'utf8');
class Node {
  constructor(tag,className='',text='') {Object.assign(this,{tag,className,text,children:[],attributes:{},dataset:{},events:{},value:'',disabled:false});}
  append(...nodes) {for (const node of nodes) {node.parent=this;this.children.push(node);}}
  replaceChildren(...nodes) {this.children=[];this.append(...nodes);}
  setAttribute(key,value) {this.attributes[key]=value;}
  addEventListener(key,fn) {this.events[key]=fn;}
  getAttribute(key) {return this.attributes[key];}
  querySelectorAll(selector) {return this.all(node=>selector.startsWith('.') ? node.className.split(' ').includes(selector.slice(1)) : node.tag===selector);}
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
  get isConnected() {return Boolean(this.root||this.parent?.isConnected);}
  get textContent() {return this.text+this.children.map((node)=>node.textContent).join('');}
  set textContent(value) {this.text=String(value);this.children=[];}
  all(predicate) {return this.children.flatMap((node)=>[...(predicate(node)?[node]:[]),...node.all(predicate)]);}
}
const el=(tag,cls,text)=>new Node(tag,cls,text);
const one=(node,cls)=>node.all((n)=>n.className.split(' ').includes(cls))[0];
const visible=node=>!node.hidden&&(!node.parent||visible(node.parent));
const control=(node,label)=>node.all((n)=>visible(n)&&n.attributes['aria-label']===label)[0];
const button=(node,label)=>node.all((n)=>visible(n)&&n.tag==='button'&&n.textContent===label)[0];
function setup({confirm,request,board,pictures=true,prepare=()=>{}}={}) {
  const data={characters:[1,2,3,4,5,6,7].map((id)=>({id:`c${id}`,name:`角色${id}`,icon:`c${id}.png`,avatars:{after:`c${id}-after.png`}})),
    equipment:[{id:'w1',name:'武器一',icon:'w1.png',soul:{available:true}},{id:'w2',name:'武器二',icon:'w2.png',soul:{available:true}},{id:'w3',name:'无魂珠',soul:{available:false}}]};
  const item={id:'plate',title:'原标题',author:'作者',notes:'说明',revision:4,category:'玩具盘',section:'',visibility:'public',status:'approved',createdBy:'owner',
    element:'火',damageTypes:['skill'],team:{main:['c1','c2','c3'],unison:['c4','c5','c6'],weapon:['w1','',''],soul:['w1','','']}};
  prepare(item);
  const images=[],frames=[],saved=[],window={WFTeamState:teamState,WFCharacterOrder:{compareTeam:(a,b)=>a.name.localeCompare(b.name)},
    WFCharacterFilters:{create:({onChange})=>{const search=el('input');search.setAttribute('aria-label','搜索角色');search.value='';search.addEventListener('input',onChange);return {element:search,matches:item=>item.name.includes(search.value)};}},
    WFCommunity:{...community,...(board?{board}: {})},...(confirm?{WFCommunityAdminConfirm:{ask:confirm}}:{}),
    WFCatalogAvatars:{getForm:()=> 'after'},WFCharacterFrame:{apply:(node,entry)=>{frames.push(entry.id);node.setAttribute('data-frame',entry.id);}}};
  const ui={el,...(pictures?{picture:(url,alt,cls)=>{images.push({url,alt});const node=el('img',cls);node.src=url;node.alt=alt;return node;}}:{})};
  for (const name of ['equipment-order.js','team-equipment-filters.js','team-candidates.js','community-team-picker.js']) vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki',name),'utf8'),{window});
  vm.runInNewContext(source,{window});let closed=0;
  const form=window.WFCommunityAdminEditor.create({item,identity:{id:'owner',role:'owner'},config:{},data,ui,
    request:request||(async()=>({team:{...item,revision:5}})),onSaved:(team)=>saved.push(team),onClose:()=>{closed++;},onReload:()=>{}});
  form.root=true;
  return {form,item,data,images,frames,saved,closed:()=>closed};
}

test('editor shows twelve selectable portrait slots and constructs candidates only after a slot is chosen',()=>{
  const x=setup(),board=one(x.form,'community-picker-board'),picker=one(x.form,'community-picker-library');
  assert.equal(board.children.length,3);assert.equal(board.all(n=>n.className==='community-picker-slot').length,12);
  assert.equal(picker.hidden,true);assert.equal(x.form.querySelectorAll('.team-candidate').length,0);
  assert.equal(board.all(n=>n.tag==='img').filter(n=>n.src.includes('-after')).length,6);
  assert.equal(x.form.querySelectorAll('select').length,5);assert.equal(control(x.form,'队伍说明').rows,2);
  const selected=control(x.form,'调整1号主位：角色1');selected.events.click();assert.equal(picker.hidden,false);
  assert.equal(control(x.form,'调整1号主位：角色1'),selected);
  assert.equal(x.form.querySelectorAll('.team-candidate').length,7);assert.ok(control(x.form,'选择角色7'));
});

test('visual replacement preserves the source team and metadata while duplicate characters swap positions',()=>{
  const x=setup(),before=JSON.stringify(x.item);
  control(x.form,'调整1号主位：角色1').events.click();control(x.form,'选择角色7').events.click();
  assert.ok(control(x.form,'调整1号主位：角色7'));assert.equal(x.form.isDirty(),true);
  control(x.form,'调整2号主位：角色2').events.click();control(x.form,'选择角色7').events.click();
  assert.ok(control(x.form,'调整1号主位：角色2'));assert.ok(control(x.form,'调整2号主位：角色7'));
  assert.equal(control(x.form,'队伍标题').value,'原标题');assert.equal(control(x.form,'玩法分区').value,'');
  assert.equal(JSON.stringify(x.item),before);
});

test('equipment and soul targets reuse candidate nodes, and clearing a slot only changes that slot',()=>{
  const x=setup(),before=JSON.stringify(x.item);
  control(x.form,'调整1号装备：武器一').events.click();const weapon=control(x.form,'选择武器二');weapon.events.click();
  assert.ok(control(x.form,'调整1号装备：武器二'));
  control(x.form,'调整2号魂珠：空位').events.click();assert.equal(control(x.form,'选择武器二魂珠'),weapon);weapon.events.click();
  assert.ok(control(x.form,'调整2号魂珠：武器二'));assert.ok(control(x.form,'调整1号魂珠：武器一'));
  button(x.form,'清空此位').events.click();assert.ok(control(x.form,'调整2号魂珠：空位'));
  assert.ok(control(x.form,'调整1号装备：武器二'));assert.equal(JSON.stringify(x.item),before);
});

test('closing a clean editor is immediate, but dirty edits survive a cancelled confirmation',async()=>{
  let answer=false,confirmations=0;
  const x=setup({confirm:()=>{confirmations++;return answer;}});
  await button(x.form,'关闭编辑').events.click();assert.equal(x.closed(),1);assert.equal(confirmations,0);
  const title=control(x.form,'队伍标题');title.value='新标题';
  await button(x.form,'关闭编辑').events.click();assert.equal(x.closed(),1);assert.equal(title.value,'新标题');
  answer=true;await button(x.form,'关闭编辑').events.click();assert.equal(x.closed(),2);assert.equal(confirmations,2);
});

test('dirty guards use normalized saved values and never discard edits when confirmation is unavailable',async()=>{
  const x=setup({pictures:false});
  control(x.form,'队伍标题').value='  原标题  ';control(x.form,'调整1号主位：角色1').events.click();control(x.form,'搜索角色').value='别名';control(x.form,'搜索角色').events.input();
  assert.equal(x.form.isDirty(),false);assert.equal(await x.form.canClose(),true);
  control(x.form,'队伍说明').value='改动说明';assert.equal(await x.form.canClose(),false);
  assert.equal(one(x.form,'community-picker-board').all((n)=>n.tag==='img').length,0);
});

test('in-flight saves cannot close and successful saves establish a clean form snapshot',async()=>{
  let finish,confirmations=0;const x=setup({confirm:()=>{confirmations++;return true;},request:()=>new Promise((resolve)=>{finish=resolve;})});
  control(x.form,'队伍标题').value='新标题';const pending=x.form.events.submit({preventDefault(){}});
  assert.equal(await x.form.canClose(),false);assert.equal(confirmations,0);assert.equal(button(x.form,'保存修改').disabled,true);
  finish({team:{...x.item,title:'新标题',revision:5}});await pending;
  assert.equal(x.saved.length,1);assert.equal(x.form.isDirty(),false);assert.equal(await x.form.canClose(),true);
});

test('save conflicts keep typed changes and dirty close protection',async()=>{
  const x=setup({confirm:()=>false,request:async()=>{throw Object.assign(new Error('conflict'),{code:'edit_conflict'});}});
  control(x.form,'队伍说明').value='冲突时保留';await x.form.events.submit({preventDefault(){}});
  assert.equal(x.form.isDirty(),true);assert.equal(await x.form.canClose(),false);assert.equal(control(x.form,'队伍说明').value,'冲突时保留');
  assert.equal(button(x.form,'保存修改').disabled,true);assert.match(one(x.form,'admin-edit-status').textContent,/其他管理员修改/);
});

test('malformed or unrelated save receipts never clear edits or report a saved revision',async()=>{
  for (const receipt of [{id:'plate'}, {id:'plate',revision:'invalid'}, {id:'plate',revision:4.5}, {id:'other',revision:5}]) {
    const x=setup({request:async()=>({team:receipt})});control(x.form,'队伍说明').value='仍需保存';
    await x.form.events.submit({preventDefault(){}});
    assert.equal(x.saved.length,0);assert.equal(x.form.isDirty(),true);assert.equal(button(x.form,'保存修改').disabled,false);
    assert.match(one(x.form,'admin-edit-status').textContent,/未返回更新版本/);
  }
});

test('one asynchronous discard confirmation protects repeated close requests and rejects changed inputs',async()=>{
  let answer,calls=0;const x=setup({confirm:()=>{calls++;return new Promise(resolve=>{answer=resolve;});}});
  control(x.form,'队伍说明').value='请求确认的修改';
  const first=x.form.canClose(),second=x.form.canClose();assert.equal(first,second);assert.equal(calls,1);assert.equal(x.form.isBusy(),true);
  control(x.form,'队伍说明').value='确认后又出现的修改';answer(true);
  assert.equal(await first,false);assert.equal(x.form.isBusy(),false);assert.equal(x.form.isDirty(),true);
});

test('expired sessions and network failures retain editable drafts for a later retry',async()=>{
  let attempts=0;const x=setup({request:async()=>{if(++attempts===1)throw Object.assign(new Error('登录已失效'),{status:401});return {team:{...x.item,revision:5}};}});
  control(x.form,'队伍说明').value='保留我的草稿';await x.form.events.submit({preventDefault(){}});
  assert.equal(x.form.isDirty(),true);assert.equal(control(x.form,'队伍说明').value,'保留我的草稿');assert.equal(button(x.form,'保存修改').disabled,false);
  await x.form.events.submit({preventDefault(){}});assert.equal(x.saved.length,1);assert.equal(x.form.isDirty(),false);
});


test('visual edits save the existing id and revision, and in-flight requests block further slot changes',async()=>{
  let finish,call;const x=setup({request:(url,body)=>{call={url,body};return new Promise(resolve=>{finish=resolve;});}});
  control(x.form,'调整1号主位：角色1').events.click();control(x.form,'选择角色7').events.click();
  const staleCandidate=control(x.form,'选择角色1');
  const pending=x.form.events.submit({preventDefault(){}});
  assert.equal(call.url,'/admin/teams/plate');assert.equal(call.body.expectedRevision,4);
  assert.equal(call.body.team.main[0],'c7');assert.equal(call.body.title,'原标题');assert.equal(call.body.notes,'说明');
  assert.equal(one(x.form,'community-team-picker').disabled,true);staleCandidate.events.click();
  assert.ok(control(x.form,'调整1号主位：角色7'));assert.equal(call.body.team.main[0],'c7');
  finish({team:{...x.item,team:call.body.team,revision:5}});await pending;
  assert.equal(x.saved.length,1);assert.equal(x.form.isDirty(),false);assert.equal(one(x.form,'community-team-picker').disabled,false);
});


test('failed saves preserve selected slots and restore input without enabling unavailable soul candidates',async()=>{
  let fail;const x=setup({confirm:()=>false,request:()=>new Promise((_resolve,reject)=>{fail=reject;})});
  control(x.form,'调整1号主位：角色1').events.click();control(x.form,'选择角色7').events.click();
  control(x.form,'调整2号魂珠：空位').events.click();const unavailable=control(x.form,'选择无魂珠魂珠');
  assert.equal(unavailable.disabled,true);const pending=x.form.events.submit({preventDefault(){}});
  assert.equal(one(x.form,'community-team-picker').disabled,true);fail(new Error('网络故障'));await pending;
  assert.equal(one(x.form,'community-team-picker').disabled,false);assert.equal(unavailable.disabled,true);unavailable.events.click();
  assert.ok(control(x.form,'调整2号魂珠：空位'));assert.ok(control(x.form,'调整1号主位：角色7'));
  assert.equal(x.form.isDirty(),true);await button(x.form,'关闭编辑').events.click();assert.equal(x.closed(),0);
  assert.ok(control(x.form,'调整1号主位：角色7'));
});


test('opening an older team never silently removes entries missing from the current catalog',()=>{
  const x=setup({prepare:item=>{item.team.weapon[2]='legacy-unknown';}});
  assert.equal(x.form.isDirty(),false);assert.ok(control(x.form,'调整3号装备：未收录'));
  control(x.form,'调整1号主位：角色1').events.click();control(x.form,'选择角色7').events.click();
  assert.ok(control(x.form,'调整3号装备：未收录'));assert.equal(x.item.team.weapon[2],'legacy-unknown');
});
