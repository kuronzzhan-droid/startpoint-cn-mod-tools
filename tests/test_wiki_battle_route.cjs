const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {Node} = require('./wiki_equipment_fixture.cjs');
const source = name => fs.readFileSync(path.join(__dirname, '../wiki', name), 'utf8');
const modules = ['targets','effects','waves','model','storage','media','clock','render','input','selection','page'];
const globalFor = name => name === 'page' ? 'renderWikiBattle' : `WFBattle${name[0].toUpperCase()}${name.slice(1)}`;
const content = () => ({schema:1,characters:{c1:{id:'c1'}},media:{c1:{}},stages:[{id:'fire'}],coffin:{url:'media/coffin.webp'}});
const turn = () => new Promise(resolve => setImmediate(resolve));

function loader(version = 'abc12345') {
  const requests=[], timers=new Map(); let serial=0;
  const head = new Node('head'), original=head.append.bind(head);
  head.append=(node)=>{requests.push(node);original(node);};
  const document={head,currentScript:{dataset:{battleVersion:version}},createElement:tag=>new Node(tag)};
  const window={},context={window,document,setTimeout:fn=>{const id=++serial;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id)};
  vm.runInNewContext(source('battle-loader.js'),context);
  function complete(node) {
    const url=(node.src||node.href).split('?')[0];
    if(url==='data/battle-content.js')window.WF_BATTLE_CONTENT=content();
    const name=/^battle-(.+)\.js$/.exec(url)?.[1];
    if(name)window[globalFor(name)]=name==='page'?()=>{}:{};
    node.onload();
  }
  async function all() {
    for(let round=0;round<20;round++) {
      requests.filter(node=>!node.completed).forEach(node=>{node.completed=true;complete(node);});
      await turn();
    }
  }
  return {window,document,requests,timers,complete,all,api:window.WFBattleLoader};
}

test('loader is inert until requested; concurrent loads share fixed versioned dependencies', async()=>{
  const x=loader();assert.equal(x.requests.length,0);
  const first=x.api.load(),second=x.api.load();assert.equal(first,second);
  await x.all();assert.equal(await first,x.window.WF_BATTLE_CONTENT);
  assert.equal(x.requests.length,13); // One stylesheet, content and eleven modules.
  const scripts=x.requests.filter(n=>n.tag==='script').map(n=>n.src);
  assert.deepEqual(scripts.filter(url=>!url.startsWith('data/')).map(url=>url.split('?')[0]),modules.map(n=>`battle-${n}.js`));
  assert.ok(x.requests.every(n=>(n.src||n.href).endsWith('?v=abc12345')));
  assert.equal(x.document.head.children.length,1);assert.equal(x.document.head.children[0].tag,'link');
  assert.equal(x.timers.size,0);await x.api.load();assert.equal(x.requests.length,13);
});

test('loader captures its own version once and ignores later currentScript values', async()=>{
  const x=loader('build-one');x.document.currentScript={dataset:{battleVersion:'evil"&url=https://bad.example/'}};
  const pending=x.api.load();await x.all();await pending;
  assert.ok(x.requests.every(n=>(n.src||n.href).endsWith('?v=build-one')));
});

test('failed script can retry while successful modules and CSS are reused', async()=>{
  const x=loader(),first=x.api.load();
  x.requests[0].onerror();await assert.rejects(first,/加载|载入/);
  await x.all(); // Other already-started resources may finish after the first failure.
  const before=x.requests.length,second=x.api.load();await x.all();await second;
  assert.equal(x.requests.length,before+1);assert.equal(x.timers.size,0);
});

test('missing module registration fails visibly and can be retried', async()=>{
  const x=loader(),first=x.api.load();
  x.requests.find(n=>n.src?.startsWith('battle-targets')).onload();
  await assert.rejects(first,/不完整/);await x.all();
  const retry=x.api.load();await x.all();await retry;
  assert.equal(x.requests.filter(n=>n.src?.startsWith('battle-targets')).length,2);
});

test('timeouts detach failed resources and release inflight promises', async()=>{
  const x=loader(),first=x.api.load();
  const timeout=x.timers.values().next().value;timeout();await assert.rejects(first,/超时/);
  await x.all();const retry=x.api.load();await x.all();await retry;
  assert.equal(x.timers.size,0);
});

function router() {
  const nodes=Object.fromEntries(['catalog-view','detail-view','extra-view','character-grid'].map(id=>[id,new Node('div')]));
  const links=['','team','community','weapons','dungeons','tier-list'].map(href=>{const n=new Node('a');n.attributes.href='#'+href;n.getAttribute=k=>n.attributes[k];return n;});
  const calls=[], rendered=[],window={scrollTo(){},WFWikiData:{loadEquipment:async()=>calls.push('equipment'),
    loadDungeons:async()=>{calls.push('dungeons');return {items:[]};}},
    WFBattleLoader:{load:()=>{calls.push('battle');return new Promise((resolve,reject)=>Object.assign(wait,{resolve,reject}));}},
    renderWikiPage:name=>{rendered.push(name);return true;}};
  const wait={},location={hash:''},document={getElementById:id=>nodes[id],querySelectorAll:selector=>selector==='.app-navigation a'?links:[]};
  const context={window,location,document};vm.runInNewContext(source('router.js'),context);
  const route=window.createWikiRouter({data:{},meta:{},ui:{el:(...a)=>new Node(...a),text:v=>v},renderCatalog:()=>rendered.push('catalog')});
  return {window,nodes,links,calls,rendered,wait,go:hash=>{location.hash=hash;return route();}};
}

test('battle route waits for lazy modules without equipment/dungeons/pixel downloads and highlights 副本',async()=>{
  const x=router(),pending=x.go('#battle');assert.deepEqual(x.calls,['battle']);assert.deepEqual(x.rendered,[]);
  assert.equal(x.links[4].attributes['aria-current'],'page');x.wait.resolve(content());await pending;
  assert.deepEqual(x.rendered,['battle']);assert.equal(x.nodes['extra-view'].hidden,false);
});

test('leaving a loading battle prevents late page mount; ordinary pages do not load battle',async()=>{
  const x=router(),pending=x.go('#battle');await x.go('#');x.wait.resolve(content());await pending;
  assert.deepEqual(x.rendered,['catalog']);await x.go('#team');await x.go('#dungeons');
  assert.deepEqual(x.calls,['battle','equipment','dungeons']);
});

test('denied navigation does not destroy a mounted view or start a load',async()=>{
  const x=router(),old=new Node('p','','running');x.nodes['extra-view'].append(old);x.window.WFNavigationGuard={allow:()=>false};
  await x.go('#battle');assert.deepEqual(x.calls,[]);assert.equal(x.nodes['extra-view'].children[0],old);
});

test('lazy failures render retry and synchronous page dispatch calls battle renderer',async()=>{
  const x=router(),pending=x.go('#battle');x.wait.reject(new Error('加载失败'));await pending;
  assert.match(x.nodes['extra-view'].textContent,/加载失败.*重新加载/);
  const calls=[],window={renderWikiBattle:(...args)=>calls.push(args)};vm.runInNewContext(source('pages.js'),{window});
  const host={},data={},ui={};assert.equal(window.renderWikiPage('battle',host,data,ui),true);
  assert.equal(calls.length,1);assert.equal(calls[0][0],host);
});

test('only loader is registered on homepage and dungeon directory gets one local entry',async()=>{
  const html=source('index.html');
  assert.equal((html.match(/src="battle-[^"]+/g)||[]).length,1);assert.match(html,/src="battle-loader\.js"[^>]+data-battle-version="dev"/);
  assert.doesNotMatch(html,/href="battle\.css|src="data\/battle-content/);
  const window={location:{href:'https://example.test/',origin:'https://example.test',protocol:'https:'}};
  vm.runInNewContext(source('dungeons.js'),{window,URL});
  const host=new Node('main'),ui={el:(...args)=>new Node(...args)};await window.renderWikiDungeons(host,{dungeons:{items:[]}},ui);
  assert.equal(host.all(n=>n.href==='#battle').length,1);assert.equal(host.all(n=>n.href==='#shops').length,1);
});
