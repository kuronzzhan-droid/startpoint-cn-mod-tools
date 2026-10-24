const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
class Node {
  constructor(tag){Object.assign(this,{tag,children:[],attributes:{},dataset:{},events:{},ownText:''});}
  append(...nodes){nodes.forEach(n=>{n.parent=this;this.children.push(n);});}
  replaceChildren(...nodes){this.children.forEach(n=>n.parent=null);this.children=[];this.ownText='';this.append(...nodes);}
  setAttribute(key,value){this.attributes[key]=value;}
  getAttribute(key){return this.attributes[key];}
  get textContent(){return this.ownText+this.children.map(n=>n.textContent).join('');}
  set textContent(text){this.replaceChildren();this.ownText=text;}
  get isConnected(){return this.tag==='body'||Boolean(this.parent?.isConnected);}
  addEventListener(key,callback){(this.events[key]??=new Set()).add(callback);}
  fire(key){[...(this.events[key]||[])].forEach(fn=>fn());}
  all(match){return this.children.flatMap(n=>[...(match(n)?[n]:[]),...n.all(match)]);}
  querySelectorAll(query){return this.all(n=>query==='[data-catalog-avatar]'?n.dataset.catalogAvatar!=null:n.tag===query);}
  querySelector(query){return this.querySelectorAll(query)[0]||null;}
}
const code=name=>fs.readFileSync(path.join(__dirname,'../wiki',name),'utf8');
function setup(saved='before'){
  const body=new Node('body'),top=new Node('button');top.id='back-to-top';body.append(top);
  const window=Object.assign(new Node('window'),{location:{hash:'#'},scrollY:0});
  const document={body,createElement:tag=>new Node(tag),getElementById:id=>body.all(n=>n.id===id)[0]||null};
  const storage=new Map([['wf-wiki-catalog-avatar',saved]]),context={window,document,
    localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)}};
  ['catalog-avatars.js','avatar-shortcut.js'].forEach(file=>vm.runInNewContext(code(file),context));
  const button=document.getElementById('avatar-shortcut');
  const navigate=(hash,y=400)=>{window.location.hash=hash;window.scrollY=y;window.fire('hashchange');};
  const scroll=y=>{window.scrollY=y;window.fire('scroll');};
  function view(){
    const host=new Node('div'),catalog=new Node('main');body.append(host,catalog);
    const characters=[{id:'a',icon:'before.webp',avatars:{before:'before.webp',after:'after.webp'}}];
    const ui={el:(tag,cls,text)=>{const n=new Node(tag);n.className=cls;n.textContent=text||'';return n;},safeUrl:x=>x||'',
      picture:url=>{const n=new Node('img');n.setAttribute('src',url);return n;}};
    const controller=window.WFCatalogAvatars.create({host,catalog,characters,ui});catalog.append(controller.picture(characters[0]));
    return {host,catalog,controller};
  }
  return {window,document,body,button,storage,context,navigate,scroll,view};
}
test('shortcut follows scroll threshold and only useful routes, including public single-team pages',()=>{
  const x=setup();assert.equal(x.button.hidden,true);x.scroll(319);assert.equal(x.button.hidden,true);
  x.scroll(320);assert.equal(x.button.hidden,false);
  for(const hash of ['','#','#main-content','#team','#community','#community/t1']){x.navigate(hash);assert.equal(x.button.hidden,false,hash);}
  for(const hash of ['#weapons','#weapon/w1','#five-boss','#character/a','#character/a/details/profile','#community/admin']){
    x.navigate(hash);assert.equal(x.button.hidden,true,hash);
  }
  x.navigate('#team',0);assert.equal(x.button.hidden,true);
});
test('floating and existing controls synchronize both ways using the original preference key',()=>{
  const x=setup('after'),view=x.view();x.navigate('#team');
  assert.match(x.button.textContent,/觉醒后/);assert.equal(x.button.attributes['aria-pressed'],'true');assert.match(x.button.title,/点击切换为觉醒前/);
  x.button.fire('click');assert.equal(view.catalog.querySelector('img').getAttribute('src'),'before.webp');
  assert.equal(view.host.querySelectorAll('button')[0].attributes['aria-pressed'],'true');
  assert.equal(x.storage.get('wf-wiki-catalog-avatar'),'before');
  view.host.querySelectorAll('button')[1].fire('click');assert.match(x.button.textContent,/觉醒后/);
  assert.equal(x.button.attributes['aria-pressed'],'true');assert.match(x.button.attributes['aria-label'],/觉醒后头像/);
});
test('route replacement removes stale view consumers and shortcut initialization is idempotent',()=>{
  const x=setup(),old=x.view(),oldImage=old.catalog.querySelector('img');
  x.navigate('#weapons');old.host.replaceChildren();old.catalog.replaceChildren();
  const next=x.view();x.navigate('#community');x.button.fire('click');
  assert.equal(oldImage.getAttribute('src'),'before.webp');assert.equal(next.catalog.querySelector('img').getAttribute('src'),'after.webp');
  vm.runInNewContext(code('avatar-shortcut.js'),x.context);
  assert.equal(x.body.all(n=>n.id==='avatar-shortcut').length,1);assert.equal(x.window.events.scroll.size,1);
});
