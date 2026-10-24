const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Node {
  constructor(tag, cls='', text='') {Object.assign(this,{tag,className:cls,text,children:[],events:{},attributes:{},disabled:false,value:''});}
  append(...nodes) {nodes.forEach(node=>{node.parent=this;this.children.push(node);});}
  replaceChildren(...nodes) {this.children.forEach(node=>node.parent=null);this.children=[];this.text='';this.append(...nodes);}
  get textContent() {return this.text+this.children.map(node=>node.textContent).join('');}
  set textContent(value) {this.replaceChildren();this.text=value;}
  setAttribute(name,value) {this.attributes[name]=value;}
  addEventListener(name,cb) {this.events[name]=cb;}
  get isConnected() {return this.root||Boolean(this.parent?.isConnected);}
  focus() {this.focused=true;}
  all(tag) {return this.children.flatMap(node=>[...(node.tag===tag?[node]:[]),...node.all(tag)]);}
}
const el=(...args)=>new Node(...args), tick=()=>new Promise(resolve=>setImmediate(resolve));
const source=fs.readFileSync(path.join(__dirname,'../wiki/wiki-aliases.js'),'utf8');
const editorSource=fs.readFileSync(path.join(__dirname,'../wiki/wiki-aliases-editor.js'),'utf8');
function setup(request) {
  const window={WFCommunity:{client:{request},message:error=>error.message}};
  vm.runInNewContext(editorSource,{window});vm.runInNewContext(source,{window});const host=el('main');host.root=true;
  return {A:window.WFWikiAliases,host,mount:(kind='character')=>window.WFWikiAliases.mount(host,kind,'c1',{el})};
}
const button=(node,text)=>node.all('button').find(b=>b.textContent===text);
const input=node=>node.all('input')[0];
const formSubmit=node=>node.all('form')[0].events.submit({preventDefault(){}});
const chips=(node,editable=false)=>node.all('span').filter(item=>item.className.split(' ').includes(editable?'wiki-alias-chip-editable':'wiki-alias-chip'));
const remove=(node,alias)=>node.all('button').find(item=>item.attributes['aria-label']===`删除黑话：${alias}`).events.click();
async function editing(aliases=[],saveHandler) {
  const calls=[];const x=setup(async(path,body,method)=>{
    calls.push({path,body,method});
    if(path==='/aliases')return {items:[{kind:'character',id:'c1',aliases,revision:4}]};
    if(path==='/admin/me')return {id:'editor',email:'test@example.invalid'};
    return body?(saveHandler?saveHandler(body):{kind:'character',id:'c1',aliases:body.aliases,revision:5}):{kind:'character',id:'c1',aliases,revision:4};
  });
  const panel=x.mount();await tick();await button(panel,'编辑黑话').events.click();return {...x,panel,calls};
}
test('anonymous detail shows empty nicknames and never offers edits; shared loads are deduplicated',async()=>{
  let reads=0;const x=setup(async path=>{if(path==='/aliases'){reads++;return {items:[]};}throw new Error('login required');});
  const panel=x.mount();x.mount('weapon');await tick();
  assert.equal(reads,1);assert.match(panel.textContent,/暂未填写/);assert.equal(button(panel,'编辑黑话').hidden,true);
  await button(panel,'编辑黑话').events.click();assert.equal(panel.all('form').length,0);
});
test('saved nicknames are separate literal tags and visitors cannot access delete controls',async()=>{
  const aliases=['光团长','<img src=x onerror=bad>'];
  const x=setup(async path=>{if(path==='/aliases')return {items:[{kind:'character',id:'c1',aliases,revision:2}]};throw new Error('login required');});
  const panel=x.mount();await tick();assert.deepEqual(chips(panel).map(item=>item.textContent),aliases);
  assert.equal(panel.all('img').length,0);assert.equal(chips(panel,true).length,0);assert.equal(button(panel,'编辑黑话').hidden,true);
});
test('administrator saves with the fetched revision and search values reflect sanitized server response without changing source aliases',async()=>{
  const calls=[];const x=setup(async(path,body,method)=>{
    calls.push({path,body,method});
    if(path==='/aliases')return {items:[]};
    if(path==='/admin/me')return {id:'editor',email:'test@example.invalid'};
    return body?{kind:'character',id:'c1',aliases:['光团长','光大叔'],revision:5}:{kind:'character',id:'c1',aliases:[],revision:4};
  });
  const panel=x.mount();await tick();await button(panel,'编辑黑话').events.click();
  input(panel).value='光团长，光大叔';await formSubmit(panel);
  const saved=calls.find(call=>call.method==='PATCH');assert.equal(saved.body.expectedRevision,4);
  assert.deepEqual(Array.from(saved.body.aliases),['光团长','光大叔']);assert.deepEqual(Array.from(x.A.values('character','c1')),['光团长','光大叔']);
  assert.match(panel.textContent,/黑话已保存/);assert.equal(panel.all('input').length,0);
  assert.deepEqual(chips(panel).map(item=>item.textContent),['光团长','光大叔']);
});
test('edit conflicts preserve input and block repeat writes until administrator reloads the editor',async()=>{
  let writes=0;const x=setup(async(path,body)=>{
    if(path==='/aliases')return {items:[]};if(path==='/admin/me')return {id:'a',email:'a@example.invalid'};
    if(body){writes++;throw Object.assign(new Error('conflict'),{status:409});}
    return {kind:'character',id:'c1',aliases:[],revision:2};
  });
  const panel=x.mount();await tick();await button(panel,'编辑黑话').events.click();
  input(panel).value='<img src=x onerror=bad>';const submit=panel.all('form')[0].events.submit;
  await submit({preventDefault(){}});await submit({preventDefault(){}});
  assert.equal(writes,1);assert.equal(button(panel,'保存黑话').disabled,true);
  assert.equal(chips(panel,true)[0].textContent,'<img src=x onerror=bad>×');assert.match(panel.textContent,/其他管理员/);
  assert.equal(input(panel).disabled,true);assert.equal(button(panel,'取消').disabled,false);
  button(panel,'取消').events.click();assert.equal(panel.all('form').length,0);assert.equal(button(panel,'编辑黑话').disabled,false);
});
test('Enter, comma and pasted lists append draft chips immediately; deleting and cancelling never save',async()=>{
  const x=await editing(['旧称']),{panel}=x;let prevented=0;
  input(panel).value='光团长';input(panel).events.keydown({key:'Enter',preventDefault(){prevented++;}});
  input(panel).value='光大叔';input(panel).events.keydown({key:',',preventDefault(){prevented++;}});
  input(panel).value='第三称，第四称';input(panel).events.input({isComposing:false});
  assert.equal(prevented,2);assert.equal(chips(panel,true).length,5);assert.equal(x.calls.filter(call=>call.method==='PATCH').length,0);
  remove(panel,'旧称');assert.equal(chips(panel,true).length,4);assert.deepEqual(Array.from(x.A.values('character','c1')),['旧称']);
  button(panel,'取消').events.click();assert.deepEqual(chips(panel).map(item=>item.textContent),['旧称']);assert.equal(x.calls.filter(call=>call.method==='PATCH').length,0);
});
test('composition Enter does not add a partial alias; adding removes case-insensitive and NFC duplicates',async()=>{
  const {panel}=await editing(['ABC','é']);
  input(panel).value='拼音中';input(panel).events.keydown({key:'Enter',isComposing:true,preventDefault(){assert.fail('composition prevented');}});
  assert.equal(chips(panel,true).length,2);assert.equal(input(panel).value,'拼音中');
  input(panel).value='abc,e\u0301,新称';button(panel,'添加').events.click();assert.equal(chips(panel,true).length,3);assert.equal(input(panel).value,'');
});
test('count and Unicode length limits reject drafts without dropping existing tags or making requests',async()=>{
  const {panel,calls}=await editing(Array.from({length:12},(_,index)=>`称呼${index}`));
  input(panel).value='第十三条';await formSubmit(panel);assert.equal(chips(panel,true).length,12);assert.equal(input(panel).value,'第十三条');assert.match(panel.textContent,/最多添加 12/);
  remove(panel,'称呼0');input(panel).value='狐'.repeat(33);await formSubmit(panel);assert.equal(chips(panel,true).length,11);assert.match(panel.textContent,/最多 32 字/);
  assert.equal(calls.filter(call=>call.method==='PATCH').length,0);
  input(panel).value='🦊'.repeat(32);button(panel,'添加').events.click();assert.equal(chips(panel,true).length,12);assert.equal(input(panel).value,'');
});
test('clearing tags saves an empty list with CAS revision and updates all mounted views',async()=>{
  const x=await editing(['甲','乙']);const other=x.mount();await tick();
  input(x.panel).value='未添加';button(x.panel,'清空标签').events.click();assert.equal(chips(x.panel,true).length,0);assert.equal(input(x.panel).value,'');
  await formSubmit(x.panel);const saved=x.calls.find(call=>call.method==='PATCH');assert.deepEqual(Array.from(saved.body.aliases),[]);assert.equal(saved.body.expectedRevision,4);
  assert.match(x.panel.textContent,/暂未填写/);assert.match(other.textContent,/暂未填写/);assert.deepEqual(Array.from(x.A.values('character','c1')),[]);
});
test('pending writes lock draft controls, failures preserve tags and a retry uses the unchanged revision',async()=>{
  let fail;let attempts=0;const x=await editing(['旧称'],body=>++attempts===1?new Promise((_resolve,reject)=>{fail=reject;}):{kind:'character',id:'c1',aliases:body.aliases,revision:5});
  input(x.panel).value='新增';const pending=formSubmit(x.panel);assert.equal(input(x.panel).disabled,true);assert.equal(button(x.panel,'取消').disabled,true);
  remove(x.panel,'旧称');assert.equal(chips(x.panel,true).length,2);
  fail(new Error('网络失败'));await pending;assert.equal(input(x.panel).disabled,false);assert.equal(button(x.panel,'保存黑话').disabled,false);assert.match(x.panel.textContent,/网络失败/);
  await formSubmit(x.panel);assert.equal(x.calls.filter(call=>call.method==='PATCH').length,2);assert.deepEqual(chips(x.panel).map(item=>item.textContent),['旧称','新增']);
});
