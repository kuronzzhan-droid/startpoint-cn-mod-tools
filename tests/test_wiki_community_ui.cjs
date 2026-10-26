const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const C = require('../wiki/community-client.js');
const tick = () => new Promise((resolve) => setImmediate(resolve));
class Node {
  constructor(tag, className='', text='') {Object.assign(this,{tag,className,ownText:String(text),children:[],events:{},attributes:{},dataset:{},value:'',checked:false,disabled:false});}
  append(...nodes) {nodes.forEach((node)=>{node.parent=this;this.children.push(node);});}
  prepend(...nodes) {nodes.forEach((node)=>{node.parent=this;});this.children.unshift(...nodes);}
  replaceChildren(...nodes) {this.children.forEach((node)=>node.parent=null);this.children=[];this.ownText='';this.append(...nodes);}
  remove() {if(this.parent)this.parent.children=this.parent.children.filter((node)=>node!==this);this.parent=null;}
  set textContent(text) {this.replaceChildren();this.ownText=String(text);}
  get textContent() {return this.ownText+this.children.map((node)=>node.textContent).join('');}
  setAttribute(key,value) {this.attributes[key]=value;}
  getAttribute(key) {return this.attributes[key];}
  addEventListener(key,callback) {this.events[key]=callback;}
  focus() {this.focused=true;}
  select() {this.selected=true;}
  get isConnected() {return this.connected===true || Boolean(this.parent?.isConnected);}
  async fire(name) {return this.events[name]?.({preventDefault(){}});}
  querySelectorAll(selector) {
    const match=(node)=>selector==='input:checked' ? node.tag==='input'&&node.checked
      : selector==='[data-catalog-avatar]' ? node.dataset.catalogAvatar !== undefined
      : selector.startsWith('.') ? node.className.split(' ').includes(selector.slice(1)) : node.tag===selector;
    return this.children.flatMap((node)=>[...(match(node)?[node]:[]),...node.querySelectorAll(selector)]);
  }
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
}
const el=(tag,cls,value)=>new Node(tag,cls,value);
const data={characters:['c1','c2','c3'].map((id)=>({id,name:`角色${id}`,element:'火',icon:'test.webp',origin:id==='c1'?'新增MOD':id==='c3'?'改版官方':'原版',
  avatars:{before:`${id}-before.webp`,...(id==='c3'?{}:{after:`${id}-after.webp`})}})),
  equipment:[{id:'w1',name:'装备',soul:{available:true}}]};
const team=C.teamCopy({main:['c1','c2','c3'],weapon:['w1']});
const item={id:'t1',status:'approved',title:'推荐 <img src=x onerror=alert(1)>',author:'作者',notes:'<script>bad</script>',
  team,element:'火',damageTypes:['skill'],createdAt:'2026-09-29T01:00:00Z',likes:3};
function setup(client, writeText) {
  const location={hash:'#community'}, window={WFCommunity:{...C,client},navigator:{clipboard:{writeText}},isSecureContext:true,
    WFTeamImport:{load:(...args)=>{window.imported=args;}}};
  const storage=new Map(),context={window,location,URLSearchParams,Date,console,
    localStorage:{getItem:(key)=>storage.get(key),setItem:(key,value)=>storage.set(key,value)}};
  for (const file of ['character-badges.js','catalog-avatars.js','community-game-codes.js','community-code-search.js','community.js','community-submit.js']) vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki',file),'utf8'),context);
  const host=el('main');host.connected=true;
  const ui={el,safeUrl:(value)=>typeof value==='string'?value:'',picture:(url,alt,cls)=>{const node=el('img',cls);node.setAttribute('src',url);return node;}};
  const modals=[], challenges=[];
  window.WFCommunity.dialog=()=>{const modal={element:el('dialog'),cleanup(fn){this.clean=fn;}};modal.element.connected=true;modals.push(modal);return modal;};
  window.WFCommunity.challenge=(_host,_config,_action,_ui,onChange)=>{
    const challenge={tokens:[],resets:0,destroyed:false,take(){onChange(false);return this.tokens.shift()||'';},reset(){this.resets++;onChange(false);},destroy(){this.destroyed=true;},ready(token){this.tokens.push(token);onChange(true);}};
    challenges.push(challenge);return challenge;
  };
  return {window,context,host,ui,modals,challenges,storage,C:window.WFCommunity};
}
const config={enabled:true,elements:['火','水','universal']};
test('keyword search submits explicitly, combines filters, paginates and resets to the directory',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(p)=>{calls.push(p);return {items:[{...item}],nextCursor:'next'};}});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const input=x.host.querySelector('.community-code-search-input'),form=x.host.querySelector('.community-code-search-form');
  input.value='  玛丽娜  ';await input.fire('input');assert.equal(calls.length,1);
  await form.fire('submit');assert.equal(new URLSearchParams(calls.at(-1).split('?')[1]).get('q'),'玛丽娜');
  assert.equal(x.host.querySelector('.community-directory').hidden,false);assert.match(x.host.querySelector('.community-status').textContent,/玛丽娜/);
  const element=x.host.querySelectorAll('select').find(node=>node.getAttribute('aria-label')==='推荐队伍属性');
  element.value='火';await element.fire('change');await tick();
  let params=new URLSearchParams(calls.at(-1).split('?')[1]);assert.equal(params.get('q'),'玛丽娜');assert.equal(params.get('element'),'火');
  await x.host.querySelector('.community-more').fire('click');await tick();
  params=new URLSearchParams(calls.at(-1).split('?')[1]);assert.equal(params.get('q'),'玛丽娜');assert.equal(params.get('cursor'),'next');
  await x.host.querySelector('.community-filter-reset').fire('click');await tick();
  params=new URLSearchParams(calls.at(-1).split('?')[1]);assert.equal(params.has('q'),false);assert.equal(params.has('cursor'),false);assert.equal(input.value,'');
});

test('code lookup and keyword directory stay separate and returning to list clears the search',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(p)=>{calls.push(p);return p.startsWith('/game-codes/')?{active:true,title:'查码结果',team}:{items:[{...item}]};}});
  x.window.WFWikiData={loadEquipment:async()=>data.equipment};
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const input=x.host.querySelector('.community-code-search-input'),form=x.host.querySelector('.community-code-search-form');
  input.value='玛丽娜';await form.fire('submit');
  input.value='BSFUGDCMCTD3';await input.fire('input');await form.fire('submit');
  assert.equal(calls.at(-1),'/game-codes/BSFUGDCMCTD3');assert.equal(x.host.querySelector('.community-directory').hidden,true);
  assert.match(x.host.querySelector('.community-code-search-result').textContent,/查码结果/);
  await form.querySelectorAll('button').find(button=>button.textContent==='返回列表').fire('click');await tick();
  assert.equal(x.host.querySelector('.community-directory').hidden,false);
  assert.equal(new URLSearchParams(calls.at(-1).split('?')[1]).has('q'),false);assert.equal(input.value,'');
  assert.equal(x.host.querySelector('.community-code-search-result').children.length,0);
});

test('recommendations paginate, escape text and link to compact team details',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(p)=>{calls.push(p);return calls.length===1?{items:[{...item}],nextCursor:'second'}:{items:[{...item,id:'t2'}]};}});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  assert.match(x.host.textContent,/<img src=x onerror=alert\(1\)>/);
  assert.equal(x.host.querySelectorAll('script').length,0);
  const links=x.host.querySelectorAll('a').map((link)=>link.href);
  assert.ok(links.includes('#community/t1'));assert.ok(!links.includes('#weapon/w1'));
  const more=x.host.querySelectorAll('.community-more')[0];await more.fire('click');await tick();
  assert.match(calls[1],/cursor=second/);assert.equal(x.host.querySelectorAll('.community-card').length,2);
  assert.equal(x.host.querySelectorAll('.community-board').length,2);
  assert.equal(x.host.querySelectorAll('.community-slot').length,12);
  assert.equal(x.host.querySelectorAll('.community-notes').length,0);
  assert.equal(x.host.querySelectorAll('.community-card-footer').length,0);
  assert.ok(!x.host.querySelectorAll('button').some(button=>button.textContent==='装入编成'));
  assert.equal(x.window.imported,undefined);
});
test('recommendation title and avatar open its plate and preserve the clicked character selection',async()=>{
  const x=setup({config:async()=>config,request:async()=>({team:item})});
  await x.window.renderWikiCommunity(x.host,data,x.ui,{id:item.id});await tick();
  const title=x.host.querySelectorAll('a').find((link)=>link.textContent===item.title);await title.fire('click');
  assert.equal(x.context.location.hash,'#team');assert.equal(x.window.imported[1],item.title);
  const avatar=x.host.querySelectorAll('a').find((link)=>link.attributes['aria-label']==='2号主位：角色c2');await avatar.fire('click');
  assert.equal(x.window.imported[2].group,'main');assert.equal(x.window.imported[2].index,1);
  x.window.imported[0].main[0]='changed';assert.equal(item.team.main[0],'c1');
});

test('gallery avatar toggle preserves compact cards and filters while paginated cards follow its preference',async()=>{
  let requests=0;const x=setup({config:async()=>config,request:async()=>{requests++;return {items:[{...item,id:`t${requests}`}],nextCursor:requests===1?'second':''};}});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const cards=x.host.querySelectorAll('.community-card'),first=cards[0],portraits=first.querySelectorAll('[data-catalog-avatar]');
  const after=x.host.querySelectorAll('button').find((button)=>button.textContent==='觉醒后');
  await after.fire('click');
  assert.equal(portraits[0].querySelector('img').getAttribute('src'),'c1-after.webp');
  assert.equal(portraits[2].querySelector('img').getAttribute('src'),'test.webp');
  assert.match(portraits[2].title,/未收录/);assert.equal(x.host.querySelectorAll('.community-card')[0],first);
  assert.equal(requests,1);assert.equal(x.storage.get('wf-wiki-catalog-avatar'),'after');
  assert.equal(first.querySelector('.community-card-preview').href,'#community/t1');
  await x.host.querySelectorAll('.community-more')[0].fire('click');await tick();
  assert.equal(x.host.querySelectorAll('.community-card')[1].querySelector('img').getAttribute('src'),'c1-after.webp');
  assert.equal(first.querySelectorAll('.community-slot').length,6);
  assert.equal(x.window.imported,undefined);
});

test('single recommendation retains its avatar switch when list filters are hidden',async()=>{
  const x=setup({config:async()=>config,request:async()=>({team:item})});
  await x.window.renderWikiCommunity(x.host,data,x.ui,{id:item.id});await tick();
  assert.equal(x.host.querySelectorAll('.community-toolbar')[0].hidden,true);
  const group=x.host.querySelectorAll('.catalog-avatar-controls')[0];assert.ok(group);assert.notEqual(group.parent.hidden,true);
  await group.querySelectorAll('button')[1].fire('click');
  assert.equal(x.host.querySelectorAll('.community-board')[0].querySelector('img').getAttribute('src'),'c1-after.webp');
});
test('all gallery cards link to saved details without nesting portrait links or importing a team',async()=>{
  const x=setup({config:async()=>config,request:async()=>({items:[{...item,id:'team / one',category:'萌新启航'}]})});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const preview=x.host.querySelector('.community-card-preview');
  assert.equal(preview.tag,'a');assert.equal(preview.href,'#community/team%20%2F%20one');
  assert.equal(preview.attributes['aria-label'],`查看队伍：${item.title}`);
  assert.match(preview.textContent,/萌新启航/);assert.equal(preview.querySelectorAll('.community-slot').length,6);
  assert.equal(preview.querySelector('.community-slot-leader').getAttribute('aria-label'),'队长');
  assert.equal(preview.querySelector('.community-slot-leader').textContent,'');
  assert.equal(preview.querySelector('.character-label-mod').textContent,'MOD');
  assert.equal(preview.querySelectorAll('.character-label-mod').length,1);assert.equal(preview.querySelectorAll('.character-label-modified').length,1);
  assert.equal(preview.querySelectorAll('.character-label-limited').length,0);
  assert.equal(preview.querySelectorAll('a').length,0);assert.equal(preview.querySelectorAll('.community-slot-weapon').length,0);
  assert.equal(x.window.imported,undefined);
  await x.host.querySelectorAll('button').find(node=>node.textContent==='觉醒后').fire('click');
  assert.equal(preview.querySelector('img').getAttribute('src'),'c1-after.webp');
});
test('team details name all slots and retain the load action and weapon links',async()=>{
  const x=setup({config:async()=>config,request:async()=>({team:item})});
  await x.window.renderWikiCommunity(x.host,data,x.ui,{id:item.id});await tick();
  assert.equal(x.host.querySelector('.community-card-preview'),null);
  const names=x.host.querySelectorAll('.community-slot-name').map(node=>node.textContent);
  assert.equal(names.length,12);assert.ok(names.includes('角色c1'));assert.ok(names.includes('装备'));assert.ok(names.includes('空位'));
  assert.ok(x.host.querySelectorAll('a').some(node=>node.href==='#weapon/w1'));
  await x.host.querySelectorAll('button').find(node=>node.textContent==='装入编成').fire('click');
  assert.equal(x.window.imported[1],item.title);assert.deepEqual(JSON.parse(JSON.stringify(x.window.imported[0])),team);
});
test('old page cannot populate a newly mounted page even when both have the same route',async()=>{
  let resolve;const x=setup({config:async()=>config,request:()=>new Promise((done)=>{resolve=done;})});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const oldCards=x.host.querySelectorAll('.community-grid')[0];x.host.replaceChildren(el('p','','new page'));
  resolve({items:[item]});await tick();assert.equal(oldCards.children.length,0);assert.equal(x.host.textContent,'new page');
});
test('filter races cannot restore old results and non-public rows are not displayed',async()=>{
  const requests=[];const x=setup({config:async()=>config,request:(url)=>new Promise((resolve)=>requests.push({url,resolve}))});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const select=x.host.querySelectorAll('select').find((node)=>node.attributes['aria-label']==='推荐队伍属性');select.value='水';select.fire('change');
  requests[1].resolve({items:[{...item,id:'water',title:'水队'}, {...item,id:'hidden',status:'hidden',title:'不公开'}]});await tick();
  requests[0].resolve({items:[item]});await tick();
  assert.match(x.host.textContent,/水队/);assert.doesNotMatch(x.host.textContent,/不公开|推荐 <img/);
});
test('late configuration fills attribute choices without resetting an already selected section or reloading teams',async()=>{
  let finishConfig;const calls=[],x=setup({config:()=>new Promise(resolve=>{finishConfig=resolve;}),request:async(url)=>{calls.push(url);return {items:[item]};}});
  const mounted=x.window.renderWikiCommunity(x.host,data,x.ui);
  const section=x.host.querySelectorAll('button').find(node=>node.textContent==='深渊');await section.fire('click');await tick();
  const card=x.host.querySelector('.community-card');finishConfig(config);await mounted;await tick();
  const select=x.host.querySelectorAll('select').find(node=>node.attributes['aria-label']==='推荐队伍属性');
  assert.deepEqual(select.children.map(node=>node.value),['','火','水','universal']);
  assert.equal(calls.length,1);assert.match(calls[0],/section=abyss/);assert.equal(x.host.querySelector('.community-card'),card);
  assert.equal(section.attributes['aria-pressed'],'true');
  select.value='水';await select.fire('change');await tick();assert.match(calls[1],/section=abyss/);assert.match(calls[1],/element=%E6%B0%B4/);
});
test('configuration returning after navigation or replacement cannot mutate the old page or start a request',async()=>{
  for(const leave of ['route','replace']) {
    let finishConfig;const calls=[],x=setup({config:()=>new Promise(resolve=>{finishConfig=resolve;}),request:async(url)=>{calls.push(url);return {items:[]};}});
    const mounted=x.window.renderWikiCommunity(x.host,data,x.ui),select=x.host.querySelectorAll('select').find(node=>node.attributes['aria-label']==='推荐队伍属性');
    if(leave==='route')x.context.location.hash='#weapons';else x.host.replaceChildren(el('p','','new page'));
    finishConfig(config);await mounted;await tick();assert.equal(select.children.length,1);assert.equal(calls.length,0);
  }
});
test('failed community config keeps the source link and a retry action visible',async()=>{
  const x=setup({config:async()=>{throw new Error('此站暂未启用配队社区');}});
  await x.window.renderWikiCommunity(x.host,data,x.ui);
  assert.match(x.host.textContent,/暂未启用/);assert.ok(x.host.querySelectorAll('a').some((node)=>node.href===C.sourceUrl));
  assert.equal(x.host.querySelectorAll('button').find((node)=>node.textContent==='重试连接').hidden,false);
});
test('administrator collection checks the session and preserves input after request failure',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(path,body)=>{
    if(path==='/admin/me')return {id:'admin'};
    assert.equal(path,'/admin/teams');calls.push(body);if(calls.length===1)throw new Error('网络失败');return {team:{id:'new',status:'approved',revision:1,visibility:body.visibility}};
  }});
  await x.C.openSubmit({team,title:'我的盘',data,ui:x.ui});await tick();
  const dialog=x.modals[0].element,inputs=dialog.querySelectorAll('input'),form=dialog.querySelectorAll('form')[0];
  inputs[1].value='投稿人';inputs.find((input)=>input.value==='skill').checked=true;
  dialog.querySelectorAll('select').find((node)=>node.attributes['aria-label']==='配队分类').value='萌新启航';
  await form.fire('submit');
  assert.equal(inputs[0].value,'我的盘');assert.equal(inputs[1].value,'投稿人');assert.match(dialog.textContent,/网络失败/);
  await form.fire('submit');assert.equal(calls.length,2);assert.equal(calls[1].turnstileToken,undefined);assert.equal(calls[1].visibility,'private');assert.match(dialog.textContent,/已保存到我的空间/);
  assert.ok(dialog.querySelectorAll('a').some((node)=>node.href==='#community/admin'));
  assert.equal(inputs[0].disabled,true);await form.fire('submit');assert.equal(calls.length,2);
  assert.equal(x.challenges.length,0);
});
test('duplicate hidden submissions do not expose a team detail link',async()=>{
  const x=setup({config:async()=>config,request:async(path)=>{if(path==='/admin/me')return {id:'admin'};const error=new Error('duplicate');Object.assign(error,{code:'duplicate',data:{existingId:'secret',status:'hidden'}});throw error;}});
  await x.C.openSubmit({team,title:'我的盘',data,ui:x.ui});await tick();
  const dialog=x.modals[0].element,inputs=dialog.querySelectorAll('input');inputs[1].value='作者';inputs.find((input)=>input.value==='skill').checked=true;
  dialog.querySelectorAll('select').find((node)=>node.attributes['aria-label']==='配队分类').value='玩具盘';
  await dialog.querySelectorAll('form')[0].fire('submit');
  assert.match(dialog.textContent,/暂不公开/);assert.equal(dialog.querySelectorAll('a').filter((node)=>node.href==='#community/secret').length,0);
});
test('a visitor cannot reach administrator creation controls',async()=>{
  const calls=[];const x=setup({request:async(path)=>{calls.push(path);const error=new Error('需要管理员登录');error.status=401;throw error;}});
  await x.C.openSubmit({team,title:'我的盘',data,ui:x.ui});await tick();
  const dialog=x.modals[0].element;assert.deepEqual(calls,['/admin/me']);assert.equal(dialog.querySelectorAll('form').length,0);
  assert.ok(dialog.querySelectorAll('a').some((node)=>node.href==='#community/admin'));
});

test('category filters combine with element and damage and reset pagination',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(url)=>{calls.push(url);return {items:[{...item,category:'MOD毕业队'}],nextCursor:'page2'};}});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const select=(label)=>x.host.querySelectorAll('select').find((node)=>node.attributes['aria-label']===label);
  select('推荐队伍属性').value='火';await select('推荐队伍属性').fire('change');await tick();
  const category=select('推荐队伍分类');assert.equal(category.children.length,7);category.value='MOD毕业队';await category.fire('change');await tick();
  const skill=x.host.querySelectorAll('input').find((node)=>node.value==='skill');skill.checked=true;await skill.fire('change');await tick();
  const params=new URLSearchParams(calls.at(-1).split('?')[1]);assert.equal(params.get('category'),'MOD毕业队');assert.equal(params.get('element'),'火');assert.equal(params.get('damage'),'skill');
  await x.host.querySelectorAll('.community-more')[0].fire('click');await tick();assert.match(calls.at(-1),/cursor=page2/);
  category.value='uncategorized';await category.fire('change');await tick();assert.doesNotMatch(calls.at(-1),/cursor=/);
  assert.ok(x.host.querySelectorAll('.badge').some((node)=>node.textContent==='MOD毕业队'));
});

test('new collection requires a category before submitting and sends its visible label',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(url,body)=>{if(url==='/admin/me')return {id:'admin'};calls.push(body);return {team:{id:'new',status:'approved',revision:1,visibility:body.visibility}};}});
  await x.C.openSubmit({team,title:'新盘',data,ui:x.ui});await tick();
  const dialog=x.modals[0].element,inputs=dialog.querySelectorAll('input'),form=dialog.querySelectorAll('form')[0];
  inputs[1].value='作者';inputs.find((node)=>node.value==='skill').checked=true;
  await form.fire('submit');assert.equal(calls.length,0);assert.match(dialog.textContent,/请选择配队分类/);
  const category=dialog.querySelectorAll('select').find((node)=>node.attributes['aria-label']==='配队分类');category.value='最新最潮盘';
  const section=dialog.querySelectorAll('select').find((node)=>node.attributes['aria-label']==='玩法分区');assert.equal(section.value,'');
  section.value='fantasy';await form.fire('submit');assert.equal(calls[0].category,'最新最潮盘');assert.equal(calls[0].section,'fantasy');
});

test('gameplay sections combine with folded filters, keep active conditions visible and reset all conditions',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(url)=>{calls.push(url);return {items:[{...item,section:'abyss'}],nextCursor:'page2'};}});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const advanced=x.host.querySelector('.community-advanced-filters');assert.equal(advanced.open,false);
  const choose=(label)=>x.host.querySelectorAll('select').find((node)=>node.attributes['aria-label']===label);
  const abyss=x.host.querySelectorAll('button').find((node)=>node.attributes['aria-label']==='玩法分区：深渊');
  await abyss.fire('click');await tick();assert.equal(abyss.attributes['aria-pressed'],'true');
  choose('推荐队伍属性').value='火';await choose('推荐队伍属性').fire('change');await tick();
  choose('推荐队伍分类').value='MOD毕业队';await choose('推荐队伍分类').fire('change');await tick();
  for(const value of ['skill','direct']) {const input=advanced.querySelectorAll('input').find((node)=>node.value===value);input.checked=true;await input.fire('change');await tick();}
  choose('推荐队伍排序').value='popular';await choose('推荐队伍排序').fire('change');await tick();
  const params=new URLSearchParams(calls.at(-1).split('?')[1]);
  assert.equal(params.get('section'),'abyss');assert.equal(params.get('element'),'火');assert.equal(params.get('category'),'MOD毕业队');assert.equal(params.get('damage'),'skill,direct');
  assert.equal(advanced.open,false);assert.match(advanced.querySelector('summary').textContent,/更多筛选最多点赞 · 火 · MOD毕业队 · 技能伤害 · 直接攻击伤害/);
  assert.equal(choose('推荐队伍排序').parent.parent,advanced.querySelector('.community-advanced-body'));
  await x.host.querySelector('.community-more').fire('click');await tick();assert.match(calls.at(-1),/cursor=page2/);
  await x.host.querySelector('.community-filter-reset').fire('click');await tick();
  assert.equal(calls.at(-1),'/teams?sort=popular');assert.equal(advanced.querySelectorAll('input:checked').length,0);
  assert.equal(choose('推荐队伍分类').value,'');assert.equal(choose('推荐队伍属性').value,'');assert.equal(choose('推荐队伍排序').value,'popular');
  assert.equal(x.host.querySelector('.community-filter-reset').disabled,true);assert.equal(abyss.attributes['aria-pressed'],'false');
});

test('original and other sections are peer buttons and keep the legacy sentinel',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(url)=>{calls.push(url);return {items:[item]};}});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  assert.equal(x.host.querySelector('.community-section-badge').textContent,'其他');
  const buttons=x.host.querySelectorAll('.community-section-button');
  assert.deepEqual(buttons.map(node=>node.textContent),['全部','原版','深渊','幻想','深渊EX','五重','其他']);
  const other=buttons.find(node=>node.textContent==='其他');await other.fire('click');await tick();
  assert.equal(new URLSearchParams(calls.at(-1).split('?')[1]).get('section'),'general');
  assert.equal(other.attributes['aria-pressed'],'true');
  await buttons.find(node=>node.textContent==='原版').fire('click');await tick();
  assert.equal(new URLSearchParams(calls.at(-1).split('?')[1]).get('section'),'original');
  await buttons[0].fire('click');await tick();assert.doesNotMatch(calls.at(-1),/section=/);
});

test('compact card copies the exact server code without adding full details or opening the editor',async()=>{
  const written=[],gameCode='H4QUDN7W5R22';
  const x=setup({config:async()=>config,request:async()=>({items:[{...item,gameCode}]})},async(value)=>written.push(value));
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const card=x.host.querySelector('.community-card'),header=card.querySelector('.community-card-header'),footer=card.querySelector('.community-card-footer');
  const copy=header.querySelectorAll('button').find((node)=>node.textContent==='复制');assert.ok(copy);
  await copy.fire('click');assert.deepEqual(written,[gameCode]);assert.match(header.textContent,/已复制/);
  assert.equal(x.context.location.hash,'#community');assert.equal(x.window.imported,undefined);
  assert.equal(header.querySelector('input').value,gameCode);assert.equal(header.querySelector('input').readOnly,true);
  assert.equal(footer,null);assert.equal(header.parent,card);assert.equal(card.querySelector('.community-like').parent,card);
  assert.equal(card.querySelector('.community-notes'),null);
  assert.equal(card.querySelectorAll('.community-slot').length,6);
});

test('card copy denial retains a selectable real code and never reports success',async()=>{
  const x=setup({config:async()=>config,request:async()=>({items:[{...item,gameCode:'H4QUDN7W5R22'}, {...item,id:'without',gameCode:null}]})},async()=>{throw new Error('denied');});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const cards=x.host.querySelectorAll('.community-card'),header=cards[0].querySelector('.community-card-header');
  await header.querySelector('button').fire('click');assert.equal(header.querySelector('input').selected,true);
  assert.match(header.textContent,/请复制上方已选中/);assert.doesNotMatch(header.textContent,/已复制。/);
  assert.equal(x.context.location.hash,'#community');assert.match(cards[1].querySelector('.community-card-header').textContent,/暂无队伍码/);
  assert.equal(cards[1].querySelector('.community-card-header').querySelectorAll('button').length,0);
});

test('code availability is folded, combines with section filters and clears with reset',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(url)=>{calls.push(url);return {items:[item,{...item,id:'private',visibility:'private',title:'不得公开的私盘'}]};}});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();assert.doesNotMatch(x.host.textContent,/不得公开的私盘/);
  const code=x.host.querySelectorAll('select').find((node)=>node.attributes['aria-label']==='推荐队伍码状态');code.value='none';await code.fire('change');await tick();
  const abyss=x.host.querySelectorAll('button').find((node)=>node.attributes['aria-label']==='玩法分区：深渊');await abyss.fire('click');await tick();
  const params=new URLSearchParams(calls.at(-1).split('?')[1]);assert.equal(params.get('code'),'none');assert.equal(params.get('section'),'abyss');
  assert.match(x.host.querySelector('.community-active-filters').textContent,/暂无队伍码/);
  await x.host.querySelector('.community-filter-reset').fire('click');await tick();assert.equal(code.value,'');assert.equal(calls.at(-1),'/teams?sort=popular');
});

test('a newly saved private plate locks its draft and publishes its game code only on an explicit later click',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(path,body,method)=>{
    calls.push({path,body,method});if(path==='/admin/me')return {id:'admin'};
    if(path==='/admin/teams')return {team:{...item,...body,id:'saved',revision:1,createdBy:'admin'}};
    assert.equal(path,'/admin/teams/saved/game-code');return {teamRevision:1,active:method==='POST',gameCode:method==='POST'?'H4QUDN7W5R22':null};
  }});
  await x.C.openSubmit({team,title:'私有测试',data,ui:x.ui});await tick();
  const dialog=x.modals[0].element,inputs=dialog.querySelectorAll('input'),form=dialog.querySelector('form');
  inputs[1].value='作者';inputs.find((node)=>node.value==='skill').checked=true;
  dialog.querySelectorAll('select').find((node)=>node.attributes['aria-label']==='配队分类').value='玩具盘';
  assert.equal(dialog.querySelectorAll('select').find((node)=>node.attributes['aria-label']==='保存位置').value,'private');
  assert.equal(dialog.querySelectorAll('.community-game-code-manager').length,0);await form.fire('submit');
  assert.equal(calls.find((call)=>call.path==='/admin/teams').body.visibility,'private');assert.equal(inputs[0].disabled,true);
  const manager=dialog.querySelector('.community-game-code-manager');assert.ok(manager);await manager.fire('toggle');await tick();
  assert.equal(calls.filter((call)=>call.method==='POST').length,0);
  await manager.querySelectorAll('button').find((node)=>node.textContent==='公开队伍码').fire('click');
  assert.equal(calls.at(-1).method,'POST');assert.equal(calls.at(-1).body.expectedRevision,1);
  assert.match(manager.textContent,/不进入配队大全/);assert.equal(manager.querySelector('input').value,'H4QUDN7W5R22');
  await form.fire('submit');assert.equal(calls.filter((call)=>call.path==='/admin/teams').length,1);
});

test('an administrator can explicitly choose the public directory without automatically publishing a code',async()=>{
  const calls=[];const x=setup({config:async()=>config,request:async(path,body)=>{
    if(path==='/admin/me')return {id:'admin'};calls.push({path,body});return {team:{...item,...body,id:'new-public',revision:1}};
  }});
  await x.C.openSubmit({team,title:'公开队伍',data,ui:x.ui});await tick();const dialog=x.modals[0].element;
  dialog.querySelectorAll('input')[1].value='作者';dialog.querySelectorAll('input').find((node)=>node.value==='skill').checked=true;
  dialog.querySelectorAll('select').find((node)=>node.attributes['aria-label']==='配队分类').value='原版毕业队';
  dialog.querySelectorAll('select').find((node)=>node.attributes['aria-label']==='保存位置').value='public';
  await dialog.querySelector('form').fire('submit');assert.equal(calls.length,1);assert.equal(calls[0].body.visibility,'public');
  assert.match(dialog.textContent,/收录成功，已公开/);assert.ok(dialog.querySelectorAll('a').some((node)=>node.href==='#community/new-public'));
});
test('like count changes only from a verified server response and repeated likes stay disabled',async()=>{
  const calls=[],results=[];const x=setup({config:async()=>config,request:async(_path,body)=>{calls.push(body);return {likes:4,likedToday:true};}});
  await x.C.openLike(item,x.ui,(result)=>results.push(result));await tick();
  const dialog=x.modals[0].element,button=dialog.querySelectorAll('button')[0];
  await button.fire('click');assert.equal(calls.length,0);
  x.challenges[0].ready('like-token');await button.fire('click');
  assert.equal(results[0].likes,4);assert.equal(button.disabled,true);assert.equal(x.challenges[0].resets,1);
  await button.fire('click');assert.equal(calls.length,1);
});

test('directory starts with popular ordering, preserves explicit latest through pagination and resets popular',async()=>{
  const calls=[],x=setup({config:async()=>config,request:async(url)=>{calls.push(url);return {items:[{...item}],nextCursor:'page2'};}});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const sort=x.host.querySelectorAll('select').find(node=>node.getAttribute('aria-label')==='推荐队伍排序');
  const reset=x.host.querySelector('.community-filter-reset');
  assert.equal(calls[0],'/teams?sort=popular');assert.equal(sort.value,'popular');assert.equal(reset.disabled,true);
  sort.value='latest';await sort.fire('change');await tick();assert.equal(reset.disabled,false);
  await x.host.querySelector('.community-more').fire('click');await tick();assert.equal(calls.at(-1),'/teams?sort=latest&cursor=page2');
  await reset.fire('click');await tick();assert.equal(calls.at(-1),'/teams?sort=popular');assert.equal(sort.value,'popular');
});

test('gallery thumb updates from server only, stays outside preview link and remembers success after filtering',async()=>{
  let writes=0;
  const x=setup({config:async()=>config,request:async(url)=>{
    if(url.endsWith('/like')) {writes++;return {likes:4,likedToday:true};}
    return {items:[{...item}]};
  }});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const card=x.host.querySelector('.community-card'),like=card.querySelector('.community-like');
  assert.equal(like.parent,card);assert.equal(card.querySelector('.community-card-preview').querySelectorAll('button').length,0);
  await like.fire('click');await tick();assert.equal(x.context.location.hash,'#community');assert.equal(x.window.imported,undefined);
  assert.equal(like.querySelector('.community-like-count').textContent,'3');assert.equal(writes,0);
  x.challenges[0].ready('verified');await x.modals[0].element.querySelectorAll('button')[0].fire('click');
  assert.equal(like.querySelector('.community-like-count').textContent,'4');assert.equal(like.disabled,true);assert.equal(like.getAttribute('aria-pressed'),'true');
  await like.fire('click');assert.equal(x.modals.length,1);assert.equal(writes,1);
  await x.host.querySelector('.community-filter-reset').fire('click');await tick();
  const restored=x.host.querySelector('.community-like');assert.equal(restored.disabled,true);assert.equal(restored.querySelector('.community-like-count').textContent,'4');
});

test('gallery thumb does not invent votes on failures and already-liked restores authoritative total',async()=>{
  let tries=0;const x=setup({config:async()=>config,request:async(url)=>{
    if(!url.endsWith('/like'))return {items:[{...item}]};
    tries++;if(tries===1)throw new Error('暂时失败');
    throw Object.assign(new Error('今天已赞'),{code:'already_liked',data:{likes:9,likedToday:true}});
  }});
  await x.window.renderWikiCommunity(x.host,data,x.ui);await tick();
  const like=x.host.querySelector('.community-like');await like.fire('click');await tick();
  const confirm=x.modals[0].element.querySelectorAll('button')[0];
  x.challenges[0].ready('first');await confirm.fire('click');assert.equal(like.disabled,false);assert.equal(like.querySelector('.community-like-count').textContent,'3');
  x.challenges[0].ready('retry');await confirm.fire('click');assert.equal(like.disabled,true);assert.equal(like.querySelector('.community-like-count').textContent,'9');
});
