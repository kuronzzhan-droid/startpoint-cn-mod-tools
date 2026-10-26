const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const community=require('../wiki/community-client.js');
class Node {
  constructor(tag,className='',text='') {Object.assign(this,{tag,className,text:String(text),children:[],events:{},attributes:{},value:'',disabled:false,style:{setProperty(){}}});}
  append(...nodes) {nodes.forEach(node=>{node.parent=this;this.children.push(node);});}
  replaceChildren(...nodes) {this.children.forEach(node=>node.parent=null);this.children=[];this.text='';this.append(...nodes);}
  get textContent() {return this.text+this.children.map(node=>node.textContent).join('');}
  set textContent(value) {this.replaceChildren();this.text=String(value);}
  set innerHTML(_value) {throw new Error('Announcement content must remain text');}
  setAttribute(key,value) {this.attributes[key]=value;}
  getAttribute(key) {return this.attributes[key];}
  addEventListener(name,callback) {this.events[name]=callback;}
  get isConnected() {return this.connected===true||Boolean(this.parent?.isConnected);}
  async fire(name) {if(name==='click'&&this.disabled)return;return this.events[name]?.({preventDefault(){}});}
  all(selector) {const match=node=>selector.startsWith('.')?node.className.split(' ').includes(selector.slice(1)):node.tag===selector;
    return this.children.flatMap(node=>[...(match(node)?[node]:[]),...node.all(selector)]);}
}
const el=(...args)=>new Node(...args),tick=()=>new Promise(resolve=>setImmediate(resolve));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const button=(box,text)=>box.all('button').find(node=>node.textContent===text);
function setup({request=async()=>({text:'当前公告',revision:3,updatedAt:'2026-10-01T00:00:00Z'}),confirm,admin=false}={}) {
  const calls=[],location={hash:admin?'#community/admin':'#community'},window={WFCommunity:{...community},
    ...(confirm?{WFCommunityAdminConfirm:{ask:confirm}}:{})};
  const send=(route,body,method=body?'PATCH':'GET')=>{calls.push({route,body,method});return request(route,body,method);};
  window.WFCommunity.client={request:send};const context={window,location,setInterval(){throw new Error('Announcement must not poll');},setTimeout(){throw new Error('Announcement must not poll');}};
  for(const file of ['community-announcement.js','community-announcement-editor.js'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki',file),'utf8'),context);
  const box=admin?window.WFCommunity.announcementEditor({ui:{el},request:send}):window.WFCommunity.announcement({el});box.connected=true;
  return {box,calls,location,window,context,input:box.all('textarea')[0],status:box.all('.community-status')[0],
    open:async()=>{box.open=true;await box.fire('toggle');await tick();},
    submit:()=>box.all('form')[0].fire('submit')};
}

test('public announcement performs one read and treats content as text with a separate complete view',async()=>{
  const message='<img src=x onerror=alert(1)>\n<script>bad()</script>',x=setup({request:async()=>({text:message})});
  assert.equal(x.box.hidden,true);assert.equal(x.calls.length,0);await tick();
  assert.deepEqual(x.calls.map(call=>call.route),['/announcement']);assert.equal(x.box.hidden,false);
  assert.equal(x.box.all('script').length,0);assert.equal(x.box.all('img').length,0);
  const full=x.box.all('.community-announcement-full')[0],track=x.box.all('.community-announcement-track')[0];
  assert.equal(full.textContent,message);assert.equal(full.hidden,true);assert.equal(track.children[1].getAttribute('aria-hidden'),'true');
  assert.match(track.textContent,/　·　/);await tick();assert.equal(x.calls.length,1);
});

test('public announcement expands and pauses without fetching another copy',async()=>{
  const x=setup();await tick();const label=button(x.box,'公告'),pause=button(x.box,'暂停'),full=x.box.all('.community-announcement-full')[0];
  await label.fire('click');assert.equal(full.hidden,false);assert.equal(label.getAttribute('aria-expanded'),'true');
  await label.fire('click');assert.equal(full.hidden,true);await pause.fire('click');
  assert.equal(x.box.getAttribute('data-paused'),'true');assert.equal(pause.getAttribute('aria-pressed'),'true');assert.equal(pause.textContent,'播放');
  await pause.fire('click');assert.equal(x.box.getAttribute('data-paused'),'false');assert.equal(pause.textContent,'暂停');assert.equal(x.calls.length,1);
});

test('empty, malformed and failed announcements remain hidden and never block the page or poll',async()=>{
  for(const payload of [{text:''},{text:' \n '},{text:123},null,new Error('网络失败')]) {
    const x=setup({request:async()=>{if(payload instanceof Error)throw payload;return payload;}});await tick();
    assert.equal(x.box.hidden,true);assert.equal(x.calls.length,1);await tick();assert.equal(x.calls.length,1);
  }
});

test('late public responses cannot revive a removed or departed page',async()=>{
  for(const leave of ['route','unmount']) {
    const waiting=deferred(),x=setup({request:()=>waiting.promise});await tick();
    if(leave==='route')x.location.hash='#weapons';else x.box.connected=false;
    waiting.resolve({text:'过期页面公告'});await tick();assert.equal(x.box.hidden,true);assert.doesNotMatch(x.box.textContent,/过期页面公告/);
  }
});

test('administrator editor reads only after expansion and does not write on input or collapse',async()=>{
  const x=setup({admin:true});assert.equal(x.calls.length,0);assert.equal(x.input.disabled,true);assert.equal(button(x.box,'保存公告').disabled,true);
  await x.open();assert.equal(x.calls.length,1);assert.equal(x.calls[0].route,'/admin/announcement');assert.equal(x.calls[0].method,'GET');
  assert.equal(x.input.value,'当前公告');assert.equal(x.input.disabled,false);assert.equal(x.box.isDirty(),false);
  x.input.value='仅本地编辑';await x.input.fire('input');x.box.open=false;await x.box.fire('toggle');assert.equal(x.calls.length,1);
  x.box.open=true;await x.box.fire('toggle');assert.equal(x.calls.length,1);
});

test('administrator save sends normalized plain text and the loaded expected revision explicitly',async()=>{
  const x=setup({admin:true,request:async(_path,body)=>body?{text:body.text,revision:4}:({text:'旧公告',revision:3})});await x.open();
  x.input.value='  <script>文字</script>\r\n第二行  ';await x.submit();
  assert.equal(x.calls.length,2);const write=x.calls[1];assert.equal(write.method,'PATCH');assert.equal(write.route,'/admin/announcement');
  assert.equal(write.body.expectedRevision,3);assert.equal(write.body.text,'<script>文字</script>\n第二行');
  assert.equal(x.input.value,write.body.text);assert.equal(x.box.isDirty(),false);assert.match(x.status.textContent,/公告已保存/);assert.equal(x.box.all('script').length,0);
});

test('the 500-character limit counts Unicode code points and accepts an explicitly empty announcement',async()=>{
  let revision=3;const x=setup({admin:true,request:async(_path,body)=>body?{text:body.text,revision:++revision}:{text:'原公告',revision}});await x.open();
  x.input.value='😀'.repeat(501);await x.submit();assert.equal(x.calls.length,1);assert.match(x.status.textContent,/不能超过 500/);
  x.input.value='😀'.repeat(500);await x.submit();assert.equal(x.calls.length,2);assert.equal([...x.calls[1].body.text].length,500);
  x.input.value=' \n ';await x.submit();assert.equal(x.calls[2].body.text,'');assert.equal(x.calls[2].body.expectedRevision,4);
  assert.equal(x.box.isDirty(),false);assert.match(x.status.textContent,/公告已撤下/);
});

test('invalid read payloads leave editing disabled and can be explicitly retried',async()=>{
  for(const payload of [{text:5,revision:3},{text:'bad',revision:-1},{text:'bad',revision:3.5},{text:'bad',revision:'3'},null]) {
    let attempt=0;const x=setup({admin:true,request:async()=>++attempt===1?payload:{text:'修复公告',revision:4}});await x.open();
    assert.match(x.status.textContent,/返回格式异常/);assert.equal(x.input.disabled,true);assert.equal(button(x.box,'保存公告').disabled,true);
    await button(x.box,'重新读取').fire('click');assert.equal(x.input.value,'修复公告');assert.equal(x.input.disabled,false);
  }
});

test('a mismatched save acknowledgement preserves the draft and never reports success',async()=>{
  for(const receipt of [{text:'另一条',revision:4},{text:'新稿',revision:3},{text:'新稿',revision:5},null]) {
    const x=setup({admin:true,request:async(_path,body)=>body?receipt:{text:'原公告',revision:3}});await x.open();
    x.input.value='新稿';await x.submit();assert.match(x.status.textContent,/回执不一致/);assert.doesNotMatch(x.status.textContent,/公告已保存/);
    assert.equal(x.input.value,'新稿');assert.equal(x.box.isDirty(),true);
  }
});

test('409 conflicts retain the draft and lock save until a confirmed reload succeeds',async()=>{
  let reads=0,accept=false;const x=setup({admin:true,confirm:()=>accept,request:async(_path,body)=>{
    if(body)throw Object.assign(new Error('conflict'),{status:409,code:'edit_conflict'});
    return ++reads===1?{text:'原公告',revision:3}:{text:'别人更新',revision:4};}});await x.open();
  x.input.value='我的草稿';await x.submit();assert.equal(x.box.isDirty(),true);assert.equal(button(x.box,'保存公告').disabled,true);
  assert.match(x.status.textContent,/其他管理员已更新/);await x.submit();assert.equal(x.calls.length,2);
  await button(x.box,'重新读取').fire('click');assert.equal(reads,1);assert.equal(x.input.value,'我的草稿');
  accept=true;await button(x.box,'重新读取').fire('click');assert.equal(reads,2);assert.equal(x.input.value,'别人更新');
  assert.equal(button(x.box,'保存公告').disabled,false);assert.equal(x.box.isDirty(),false);
});

test('network save failure preserves the draft and permits an explicit retry',async()=>{
  let writes=0;const x=setup({admin:true,request:async(_path,body)=>{
    if(!body)return {text:'原公告',revision:3};if(++writes===1)throw new Error('保存网络失败');return {text:body.text,revision:4};}});await x.open();
  x.input.value='未丢失的稿件';await x.submit();assert.match(x.status.textContent,/保存网络失败/);assert.equal(x.input.value,'未丢失的稿件');
  assert.equal(x.box.isDirty(),true);assert.equal(button(x.box,'保存公告').disabled,false);await x.submit();assert.equal(writes,2);assert.equal(x.box.isDirty(),false);
});

test('busy saves reject duplicate submissions, reload and navigation',async()=>{
  const waiting=deferred();let confirmations=0;const x=setup({admin:true,confirm:()=>{confirmations++;return true;},
    request:async(_path,body)=>body?waiting.promise:{text:'原公告',revision:3}});await x.open();x.input.value='保存中';
  const pending=x.submit();await x.submit();await button(x.box,'重新读取').fire('click');assert.equal(await x.box.canClose(),false);
  assert.equal(x.calls.length,2);assert.equal(confirmations,0);assert.equal(x.box.isBusy(),true);assert.equal(x.input.disabled,true);
  waiting.resolve({text:'保存中',revision:4});await pending;assert.equal(x.box.isBusy(),false);assert.equal(await x.box.canClose(),true);
});

test('simultaneous initial expansion and reload still start only one read',async()=>{
  const waiting=deferred(),x=setup({admin:true,request:()=>waiting.promise});x.box.open=true;
  const opening=x.box.fire('toggle'),reloading=button(x.box,'重新读取').fire('click');await tick();
  assert.equal(x.calls.length,1);waiting.resolve({text:'一次读取',revision:3});await opening;await reloading;await tick();
});

test('navigation guard protects unsaved drafts, deduplicates confirmations and rejects changed drafts',async()=>{
  const answer=deferred();let confirmations=0;const x=setup({admin:true,confirm:()=>{confirmations++;return answer.promise;}});await x.open();
  assert.equal(await x.box.canClose(),true);assert.equal(confirmations,0);x.input.value='草稿一';
  const first=x.box.canClose(),second=x.box.canClose();assert.equal(first,second);assert.equal(confirmations,1);assert.equal(x.box.isBusy(),true);
  await x.submit();assert.equal(x.calls.length,1);x.input.value='草稿二';answer.resolve(true);assert.equal(await first,false);
  assert.equal(x.input.value,'草稿二');assert.equal(x.box.isBusy(),false);
});

test('missing or rejected confirmation never discards unsaved edits',async()=>{
  for(const confirm of [undefined,()=>false]) {
    const x=setup({admin:true,confirm});await x.open();x.input.value='保留草稿';
    assert.equal(await x.box.canClose(),false);await button(x.box,'重新读取').fire('click');
    assert.equal(x.calls.length,1);assert.equal(x.input.value,'保留草稿');
  }
});

test('detached editors ignore late read and save acknowledgements',async()=>{
  const reading=deferred(),first=setup({admin:true,request:()=>reading.promise});await first.open();first.box.connected=false;
  reading.resolve({text:'过期读取',revision:3});await tick();assert.equal(first.input.value,'');
  const writing=deferred(),second=setup({admin:true,request:async(_path,body)=>body?writing.promise:{text:'原稿',revision:3}});await second.open();
  second.input.value='编辑稿';const pending=second.submit();second.box.connected=false;writing.resolve({text:'编辑稿',revision:4});await pending;
  assert.doesNotMatch(second.status.textContent,/公告已保存/);assert.equal(second.box.isDirty(),true);
});

test('management page registers announcement drafts with its existing navigation guard',async()=>{
  let allowed=false,guard;const x=setup({admin:true,confirm:()=>allowed,request:async route=>{
    if(route==='/config')return {enabled:true};if(route==='/admin/me')return {id:'admin',email:'admin@example.test',role:'editor'};
    if(route==='/admin/announcement')return {text:'当前公告',revision:3};if(route.startsWith('/admin/teams?'))return {items:[],nextCursor:''};
    throw new Error(`Unexpected request: ${route}`);
  }});
  x.window.fetch=()=>{throw new Error('The existing client must be reused');};x.window.location={...x.location,protocol:'https:'};
  x.window.WFNavigationGuard={register:registration=>{guard=registration;}};
  Object.assign(x.context,{URLSearchParams,clearTimeout(){}});
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/community-admin.js'),'utf8'),x.context);
  const host=el('main');host.connected=true;await x.window.renderWikiCommunityAdmin(host,{characters:[],equipment:[]},{el});
  assert.ok(guard);assert.equal(guard.isActive(),true);assert.equal(guard.needsProtection(),false);
  assert.equal(x.calls.some(call=>call.route==='/admin/announcement'),false);
  const editor=host.all('.community-announcement-editor')[0];editor.open=true;await editor.fire('toggle');await tick();
  editor.all('textarea')[0].value='导航前的未保存公告';assert.equal(guard.needsProtection(),true);assert.equal(await guard.canLeave(),false);
  allowed=true;assert.equal(await guard.canLeave(),true);host.replaceChildren();assert.equal(guard.isActive(),false);assert.equal(guard.needsProtection(),false);
});

test('management mounts sponsorship only for owner/deputy and protects their unsaved drafts through navigation guard',async()=>{
  for(const role of ['owner','deputy','editor']) {
    let allowed=false,confirmations=0,guard;
    const x=setup({admin:true,confirm:()=>{confirmations++;return allowed;},request:async route=>{
      if(route==='/config')return {enabled:true};
      if(route==='/admin/me')return {id:'admin',email:'admin@example.test',role};
      if(route==='/admin/sponsorship')return {enabled:false,title:'',description:'',imageUrl:'',targetUrl:'',revision:0,updatedAt:null};
      if(route.startsWith('/admin/teams?'))return {items:[],nextCursor:''};
      throw new Error(`Unexpected request: ${route}`);
    }});
    x.window.fetch=()=>{throw new Error('The existing client must be reused');};x.window.location={...x.location,protocol:'https:'};
    x.window.WFSponsor=require('../wiki/sponsor.js');
    x.window.WFNavigationGuard={register:registration=>{guard=registration;}};
    Object.assign(x.context,{URLSearchParams,clearTimeout(){},document:{createElement:tag=>el(tag)}});
    for(const file of ['sponsor-editor.js','community-admin.js'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki',file),'utf8'),x.context);
    const host=el('main');host.connected=true;await x.window.renderWikiCommunityAdmin(host,{characters:[],equipment:[]},{el});
    const editors=host.all('.sponsor-editor');assert.equal(editors.length,role==='editor'?0:1,role);
    assert.equal(x.calls.some(call=>call.route==='/admin/sponsorship'),false);assert.equal(guard.needsProtection(),false);
    if(role==='editor')continue;
    const editor=editors[0];assert.equal(editor.open,false);editor.open=true;await editor.fire('toggle');await tick();
    const title=editor.all('input').find(node=>node.getAttribute('aria-label')==='广告标题');title.value='尚未保存的赞助草稿';
    assert.equal(guard.needsProtection(),true);assert.equal(await guard.canLeave(),false);assert.equal(confirmations,1);
    assert.equal(title.value,'尚未保存的赞助草稿');allowed=true;assert.equal(await guard.canLeave(),true);assert.equal(confirmations,2);
    assert.equal(x.calls.filter(call=>call.route==='/admin/sponsorship').length,1);
    host.replaceChildren();assert.equal(guard.isActive(),false);assert.equal(guard.needsProtection(),false);
  }
});
