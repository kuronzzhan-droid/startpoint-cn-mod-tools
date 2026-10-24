const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Node {
  constructor(tag, cls='', text='') {Object.assign(this,{tag,className:cls,text:String(text),children:[],events:{},attributes:{},disabled:false});}
  append(...nodes) {nodes.forEach((node)=>{node.parent=this;this.children.push(node);});}
  replaceChildren(...nodes) {this.children.forEach((node)=>node.parent=null);this.children=[];this.text='';this.append(...nodes);}
  get textContent() {return this.text+this.children.map((node)=>node.textContent).join('');}
  set textContent(value) {this.replaceChildren();this.text=String(value);}
  setAttribute(name,value) {this.attributes[name]=value;}
  addEventListener(name,callback) {this.events[name]=callback;}
  get isConnected() {return this.root||Boolean(this.parent?.isConnected);}
  focus() {this.focused=true;}
  select() {this.selected=true;}
  all(tag) {return this.children.flatMap((node)=>[...(node.tag===tag?[node]:[]),...node.all(tag)]);}
  async click() {if(!this.disabled)return this.events.click?.();}
}
const el=(...args)=>new Node(...args);
const source=fs.readFileSync(path.join(__dirname,'../wiki/community-game-codes.js'),'utf8');
const code='H4QUDN7W5R22';
const button=(node,label)=>node.all('button').find((node)=>node.textContent===label);
const tick=()=>new Promise((resolve)=>setImmediate(resolve));
function setup(writeText, isSecureContext=true) {
  const window={WFCommunity:{message:(error)=>error.message},navigator:writeText?{clipboard:{writeText}}:{},isSecureContext};
  vm.runInNewContext(source,{window});return {G:window.WFCommunityGameCodes,ui:{el}};
}
function manager(request,status='approved') {
  const x=setup(),item={id:'t1',status,revision:3};
  const section=x.G.controls(item,x.ui,request);section.root=true;
  return {...x,item,section,open:()=>{section.open=true;section.events.toggle();return tick();}};
}
test('visitors see only valid server-issued codes for public records and cannot generate them',()=>{
  const x=setup();
  assert.equal(x.G.readonly({gameCode:null,status:'approved'},x.ui),null);
  assert.equal(x.G.readonly({gameCode:code,status:'hidden'},x.ui),null);
  assert.equal(x.G.readonly({gameCode:code,status:'approved',visibility:'private'},x.ui),null);
  assert.equal(x.G.readonly({gameCode:'H4QUDN7W5R',status:'approved'},x.ui),null);
  assert.equal(x.G.readonly({gameCode:'AAAAAAAAAAA0',status:'approved'},x.ui),null);
  const view=x.G.readonly({gameCode:code,status:'approved'},x.ui);
  assert.equal(view.all('input')[0].value,code);assert.equal(view.all('input')[0].readOnly,true);
  assert.deepEqual(view.all('button').map((node)=>node.textContent),['复制游戏码']);
  assert.match(view.textContent,/仅接入本站队伍码的游戏服务器可用/);
});
test('copy uses the exact returned game code and falls back to selected text on clipboard failure',async()=>{
  const written=[],x=setup(async(value)=>written.push(value)),view=x.G.readonly({gameCode:code},x.ui);
  await button(view,'复制游戏码').click();assert.deepEqual(written,[code]);assert.match(view.textContent,/已复制/);
  const fail=setup(async()=>{throw new Error('denied');}),fallback=fail.G.readonly({gameCode:code},fail.ui);
  await button(fallback,'复制游戏码').click();
  assert.equal(fallback.all('input')[0].selected,true);assert.equal(fallback.all('input')[0].focused,true);
  assert.match(fallback.textContent,/请复制上方已选中/);assert.doesNotMatch(fallback.textContent,/已复制。/);
});

test('compact codes preserve copying and insecure contexts fall back without using clipboard',async()=>{
  let writes=0,stopped=false;const x=setup(async()=>{writes++;},false),view=x.G.readonly({gameCode:code},x.ui,{compact:true});
  assert.match(view.className,/community-game-code-compact/);assert.equal(view.all('input')[0].value,code);
  await button(view,'复制').events.click({stopPropagation(){stopped=true;}});
  assert.equal(writes,0);assert.equal(stopped,true);assert.equal(view.all('input')[0].selected,true);
  assert.match(view.textContent,/请复制上方已选中/);assert.doesNotMatch(view.textContent,/已复制。/);
});
test('administrator code status loads only on expansion and generation is server-confirmed',async()=>{
  const calls=[];const x=manager(async(path,body,method)=>{
    calls.push({path,body,method});return {gameCode:method==='POST'?code:null,active:method==='POST',teamRevision:3};
  });
  assert.equal(calls.length,0);assert.equal(x.section.all('input').length,0);
  await x.open();assert.equal(calls[0].path,'/admin/teams/t1/game-code');assert.equal(calls[0].method,'GET');
  await button(x.section,'公开队伍码').click();
  assert.equal(calls[1].method,'POST');assert.equal(calls[1].body.expectedRevision,3);
  assert.equal(x.section.all('input')[0].value,code);assert.equal(x.item.gameCode,code);assert.equal(x.item.revision,3);
  assert.ok(button(x.section,'复用已公开队伍码'));
});
test('failed generation never displays an invented code and can be retried',async()=>{
  let posts=0;const x=manager(async(_path,_body,method)=>{
    if(method==='GET')return {gameCode:null,active:false,teamRevision:3};
    if(++posts===1)throw new Error('网络失败');return {gameCode:code,active:true,teamRevision:3};
  });
  await x.open();await button(x.section,'公开队伍码').click();
  assert.equal(x.section.all('input').length,0);assert.match(x.section.textContent,/网络失败/);
  await button(x.section,'公开队伍码').click();assert.equal(x.section.all('input')[0].value,code);
});
test('hidden records cannot generate and successful revocation removes the displayed code',async()=>{
  const hidden=manager(async()=>({gameCode:null,active:false,teamRevision:3}),'hidden');await hidden.open();
  assert.equal(button(hidden.section,'公开队伍码').disabled,true);assert.match(hidden.section.textContent,/不能公开/);
  const calls=[],active=manager(async(path,body,method)=>{
    calls.push({path,body,method});return {gameCode:path.endsWith('/revoke')?null:code,active:!path.endsWith('/revoke'),teamRevision:3};
  });
  await active.open();await button(active.section,'停用游戏码').click();
  assert.equal(calls[1].path,'/admin/teams/t1/game-code/revoke');assert.equal(calls[1].body.expectedRevision,3);
  assert.equal(active.section.all('input').length,0);assert.equal(active.item.gameCode,null);
  assert.equal(button(active.section,'停用游戏码').disabled,true);
});
test('changed revisions require reloading the actual team rather than silently accepting its code',async()=>{
  const x=manager(async()=>({gameCode:code,active:true,teamRevision:4}));await x.open();
  assert.equal(x.item.revision,3);assert.equal(x.section.all('input').length,0);
  assert.match(x.section.textContent,/重新加载管理列表/);assert.equal(button(x.section,'公开队伍码').disabled,true);
});
test('detached management panels ignore late generation results',async()=>{
  let resolve;const x=manager((_path,_body,method)=>method==='GET'?Promise.resolve({gameCode:null,active:false,teamRevision:3}):new Promise((done)=>{resolve=done;}));
  await x.open();const pending=button(x.section,'公开队伍码').click();x.section.root=false;
  resolve({gameCode:code,active:true,teamRevision:3});await pending;
  assert.equal(x.item.gameCode,null);assert.equal(x.section.all('input').length,0);
});

test('a network failure after a revision conflict cannot re-enable stale code mutations',async()=>{
  let calls=0;const x=manager(async()=>{if(++calls===1)return {gameCode:code,active:true,teamRevision:4};throw new Error('网络失败');});
  await x.open();assert.equal(button(x.section,'公开队伍码').disabled,true);
  await button(x.section,'刷新状态').click();assert.equal(button(x.section,'公开队伍码').disabled,true);
  assert.equal(button(x.section,'停用游戏码').disabled,true);assert.equal(x.section.all('input').length,0);
});
