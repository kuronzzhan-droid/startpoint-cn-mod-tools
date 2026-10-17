const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = (name) => fs.readFileSync(path.join(__dirname, '../wiki', name), 'utf8');
function loader(split = true) {
  const scripts = [];
  const characters = [{id:'ca', name:'A'}, {id:'cb', name:'B'}];
  const data = {characters, equipment: [{id:'wa'}], bossGuide:{stages:[]}};
  if (split) data.dataManifest = {chunks: Object.fromEntries(['character:ca','character:cb','equipment','bossGuide','search']
    .map((key) => [key, {url:`data/${key.replace(':','-')}-0123.js`}]))};
  const context = {window:{WF_WIKI:data}, setTimeout, clearTimeout,
    document:{createElement:() => ({remove(){this.removed=true;}}),head:{append:(script) => scripts.push(script)}}};
  vm.runInNewContext(source('data-loader.js'), context);
  const complete = (key, value, index = scripts.length - 1) => {
    (context.window.WF_WIKI_CHUNKS ||= {})[key] = value;
    scripts[index].onload();
  };
  return {api:context.window.WFWikiData, data, scripts, complete, context};
}
test('concurrent character reads share one request and retain complete effects', async () => {
  const x=loader(), first=x.api.loadCharacter('ca'), second=x.api.loadCharacter('ca');
  assert.equal(x.scripts.length,1);
  const full={id:'ca',voices:[{text:'台词'}],skills:[{description:'完整效果'}]};
  x.complete('character:ca',full);
  assert.equal(await first,full); assert.equal(await second,full);
  assert.equal(await x.api.loadCharacter('ca'),full); assert.equal(x.scripts.length,1);
  assert.equal(x.scripts[0].removed,true);
});
test('network and invalid payload failures can retry without poisoning the cache', async () => {
  const x=loader(), first=x.api.loadCharacter('ca'); x.scripts[0].onerror(); await assert.rejects(first);
  const second=x.api.loadCharacter('ca'); x.complete('character:ca',{id:'cb'}); await assert.rejects(second);
  const third=x.api.loadCharacter('ca'); x.complete('character:ca',{id:'ca',name:'Recovered'});
  assert.equal((await third).name,'Recovered'); assert.equal(x.scripts.length,3);
});
test('missing character and unsafe manifest paths do not request scripts', async () => {
  const x=loader(); assert.equal(await x.api.loadCharacter('missing'),null);
  x.data.dataManifest.chunks['character:ca'].url='https://example.com/untrusted.js';
  await assert.rejects(x.api.loadCharacter('ca')); assert.equal(x.scripts.length,0);
});
test('equipment mutates the shared catalogue only after a successful response', async () => {
  const x=loader(), original=x.data.equipment, pending=x.api.loadEquipment();
  assert.equal(x.data.equipment,original);
  const equipment=[{id:'wb',soul:{available:true}}];
  x.complete('equipment',{equipment,equipmentMeta:{rules:{limit:2}}});
  assert.equal(await pending,equipment); assert.equal(x.data.equipment,equipment);
  assert.equal(x.data.equipmentMeta.rules.limit,2);
});
test('search normalizes full descriptions separately from lightweight character objects', async () => {
  const x=loader(), promise=x.api.loadSearchIndex();
  x.complete('search',{ca:'ＡＢＣ 技能 台词',cb:'共鸣'});
  const index=await promise;
  assert.equal(index.get('ca'),'abc 技能 台词'); assert.equal(x.api.searchIndex(),index);
  assert.equal(x.data.characters[0].name,'A'); assert.equal(await x.api.loadSearchIndex(),index);
});

test('real character filters find skill-only text through search chunks when bootstrap has no effects', async () => {
  const {Node}=require('./wiki_equipment_fixture.cjs'),x=loader();
  vm.runInNewContext(source('character-filters.js'),x.context);
  const ui={el:(...args)=>new Node(...args),nativeIcon:()=>new Node('span')};
  let done;const changed=new Promise(resolve=>{done=resolve;});
  const filters=x.context.window.WFCharacterFilters.create({characters:x.data.characters,ui,idPrefix:'test-slim',
    onChange:()=>done(x.data.characters.filter(filters.matches).map(c=>c.id))});
  const mounted=new Node('document');mounted.append(filters.element);
  assert.equal(x.data.characters[0].leader,undefined);assert.equal(x.data.characters[0].abilities,undefined);
  filters.search.value='技能发动';filters.search.fire('input');
  await new Promise(resolve=>setTimeout(resolve,95));
  assert.equal(x.scripts.length,1);assert.match(x.scripts[0].src,/search/);
  x.complete('search',{ca:'角色A 每次技能发动时攻击+50%',cb:'角色B 主位强化弹射'});
  assert.deepEqual(Array.from(await changed),['ca']);
  assert.equal(x.data.characters[0].abilities,undefined);
});
test('rapid search-panel disclosure does not render results or fetch search or character chunks', () => {
  const {Node}=require('./wiki_equipment_fixture.cjs'),x=loader();
  vm.runInNewContext(source('character-filters.js'),x.context);
  let changed=0;
  const filters=x.context.window.WFCharacterFilters.create({characters:x.data.characters,idPrefix:'catalog-check',initiallyOpen:false,
    ui:{el:(...args)=>new Node(...args),nativeIcon:()=>new Node('span')},onChange:()=>changed++});
  const mounted=new Node('document');mounted.append(filters.element);
  for(let index=0;index<40;index++){filters.element.open=!filters.element.open;filters.element.fire('toggle');}
  assert.equal(filters.element.open,false);assert.equal(changed,0);assert.equal(x.scripts.length,0);
});
test('legacy unsplit exports remain readable without any requests', async () => {
  const x=loader(false);
  assert.equal((await x.api.loadCharacter('ca')).name,'A');
  assert.equal((await x.api.loadEquipment())[0].id,'wa');
  assert.equal(await x.api.loadSearchIndex(),null);
  assert.equal(x.scripts.length,0);
});

function router() {
  const nodes={};
  const el=(tag, cls, value) => ({tag,cls,textContent:value,children:[],hidden:false,
    append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;},
    setAttribute(){},addEventListener(event,fn){this[event]=fn;}});
  ['catalog-view','detail-view','extra-view','character-grid'].forEach((id) => nodes[id]=el('div'));
  const requests={},rendered=[],data={};
  const wait=(key) => new Promise((resolve,reject) => {requests[key]={resolve,reject};});
  const context={window:{scrollTo(){},WFWikiData:{loadCharacter:(id)=>wait(id),loadEquipment:()=>wait('equipment'),loadBossGuide:()=>wait('boss'),
    loadRewards:()=>wait('rewards'),
    loadDungeons:()=>wait('dungeons').then(value=>{data.dungeons=value;return value;})}},
    location:{hash:''},document:{getElementById:(id)=>nodes[id],querySelectorAll:()=>[]}};
  context.window.renderWikiCharacterSummary=(_host,c)=>rendered.push(c.id);
  context.window.renderWikiCharacter=(_host,c,_m,_u,o)=>rendered.push(`${c.id}/${o.initialTab}`);
  context.window.renderWikiPage=(page)=>{rendered.push(page);return true;};
  vm.runInNewContext(source('router.js'),context);
  const route=context.window.createWikiRouter({data,meta:{},ui:{el,text:(value)=>value},renderCatalog:()=>rendered.push('catalog')});
  return {nodes,requests,rendered,context,route,go(hash){context.location.hash=hash;return route();}};
}
test('late character responses cannot overwrite a later navigation', async () => {
  const x=router(), first=x.go('#character/ca'), second=x.go('#character/cb');
  x.requests.cb.resolve({id:'cb'}); await second;
  x.requests.ca.resolve({id:'ca'}); await first;
  assert.deepEqual(x.rendered,['cb']);
});
test('cancelled asynchronous navigation leaves the mounted editor and downloads unchanged', async () => {
  const x=router(), draft={textContent:'unsaved draft'};x.nodes['extra-view'].replaceChildren(draft);
  let resolve;x.context.window.WFNavigationGuard={allow:()=>new Promise(done=>resolve=done)};
  const pending=x.go('#weapons');assert.equal(x.nodes['extra-view'].children[0],draft);
  assert.deepEqual(Object.keys(x.requests),[]);resolve(false);await pending;
  assert.equal(x.nodes['extra-view'].children[0],draft);assert.deepEqual(x.rendered,[]);
});
test('accepted navigation only mounts the still-current destination', async () => {
  const x=router();let resolve;
  x.context.window.WFNavigationGuard={allow:()=>new Promise(done=>resolve=done)};
  const pending=x.go('#weapons');x.context.location.hash='#community';resolve(true);await pending;
  assert.deepEqual(Object.keys(x.requests),[]);assert.deepEqual(x.rendered,[]);
});
test('team rendering waits for equipment, and superseded team loads stay inactive', async () => {
  const x=router(), team=x.go('#team'); assert.deepEqual(x.rendered,[]);
  await x.go('#'); x.requests.equipment.resolve([]); await team;
  assert.deepEqual(x.rendered,['catalog']);
  const next=x.go('#team'); x.requests.equipment.resolve([]); await next;
  assert.deepEqual(x.rendered,['catalog','team']);
});

test('tier board needs no detail downloads and supersedes a pending team page', async () => {
  const x=router(); await x.go('#tier-list');
  assert.deepEqual(Object.keys(x.requests), []);
  assert.equal(x.nodes['catalog-view'].hidden, true);
  assert.equal(x.nodes['extra-view'].hidden, false);
  assert.deepEqual(x.rendered, ['tier-list']);
  const pending=x.go('#team'); await x.go('#tier-list');
  x.requests.equipment.resolve([]); await pending;
  assert.deepEqual(x.rendered, ['tier-list', 'tier-list']);
});

test('community list renders without downloading equipment', async () => {
  const x=router();await x.go('#community');
  assert.equal(x.requests.equipment,undefined);assert.deepEqual(x.rendered,['community']);
  assert.equal(x.nodes['extra-view'].hidden,false);
});

test('community details, admin and individual weapon routes load equipment and stay outside the catalogue', async () => {
  for (const hash of ['#community/t1', '#community/admin', '#weapon/w1']) {
    const x=router(), pending=x.go(hash);
    assert.equal(x.nodes['catalog-view'].hidden, true);
    assert.equal(x.nodes['extra-view'].hidden, false);
    x.requests.equipment.resolve([]); await pending;
    assert.deepEqual(x.rendered, [hash.slice(1)]);
  }
});

test('dungeon directory avoids equipment downloads and obsolete directory loads do not render', async () => {
  const x=router(), pending=x.go('#dungeons');
  assert.equal(x.nodes['catalog-view'].hidden,true);assert.equal(x.requests.equipment,undefined);
  x.requests.dungeons.resolve({items:[]});await pending;assert.deepEqual(x.rendered,['dungeons']);
  const old=x.go('#dungeons');await x.go('#');x.requests.dungeons.resolve({items:[]});await old;
  assert.deepEqual(x.rendered,['dungeons','catalog']);assert.equal(x.requests.equipment,undefined);
});

test('new five-boss detail and old link both load the complete boss guide and team equipment', async () => {
  for(const hash of ['#dungeons/boss-1-99','#five-boss']) {
    const x=router(),pending=x.go(hash);
    x.requests.dungeons.resolve({items:[{id:'boss-1-99',legacyGuide:'five-boss'}]});
    await new Promise(resolve=>setImmediate(resolve));
    assert.ok(x.requests.equipment);assert.ok(x.requests.boss);assert.deepEqual(x.rendered,[]);
    x.requests.equipment.resolve([]);x.requests.rewards.resolve({});x.requests.boss.resolve({stages:[]});await pending;
    assert.deepEqual(x.rendered,[hash.slice(1)]);
  }
});

test('series details load team equipment without requesting the unrelated five-boss guide', async () => {
  const x=router(), pending=x.go('#dungeons/series-machina');
  x.requests.dungeons.resolve({items:[{id:'boss-1-60',seriesId:'series-machina'}]});
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(x.requests.equipment);assert.equal(x.requests.boss,undefined);assert.deepEqual(x.rendered,[]);
  x.requests.equipment.resolve([]);x.requests.rewards.resolve({});await pending;
  assert.deepEqual(x.rendered,['dungeons/series-machina']);
});

test('leaving a pending dungeon catalogue never starts its later equipment or boss reads', async () => {
  const x=router(),pending=x.go('#five-boss');await x.go('#');
  x.requests.dungeons.resolve({items:[{id:'boss-1-99',legacyGuide:'five-boss'}]});await pending;
  assert.equal(x.requests.equipment,undefined);assert.equal(x.requests.boss,undefined);
  assert.deepEqual(x.rendered,['catalog']);
});

test('legacy five-boss route retains its guide if a snapshot has no corresponding directory item', async () => {
  const x=router(),pending=x.go('#five-boss');x.requests.dungeons.resolve({items:[]});
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(x.requests.equipment);assert.ok(x.requests.boss);
  x.requests.equipment.resolve([]);x.requests.rewards.resolve({});x.requests.boss.resolve({stages:[]});await pending;
  assert.deepEqual(x.rendered,['five-boss']);
});

test('dungeon loader shares requests, rejects broken metadata and retries without touching character data', async () => {
  const x=loader();vm.runInNewContext(source('dungeons-loader.js'),x.context);
  const first=x.api.loadDungeons(),second=x.api.loadDungeons();assert.equal(x.scripts.length,1);
  assert.equal(x.scripts[0].src,'dungeons-data.js');
  x.context.window.WF_WIKI_DUNGEONS={schemaVersion:1,items:[{id:'../bad',title:'坏',category:'活动'}]};
  x.scripts[0].onload();await assert.rejects(first);await assert.rejects(second);
  const retry=x.api.loadDungeons();assert.equal(x.scripts.length,2);
  const value={schemaVersion:1,items:[{id:'event-1',title:'活动',category:'活动'}]};
  x.context.window.WF_WIKI_DUNGEONS=value;x.scripts[1].onload();
  assert.equal(await retry,value);assert.equal(x.data.dungeons,value);
  assert.equal(x.data.characters[0].name,'A');assert.equal(await x.api.loadDungeons(),value);
  assert.equal(x.scripts.length,2);
});

test('optional reward failure does not hide a dungeon guide', async () => {
  const x=router(), pending=x.go('#dungeons/boss-1-60');
  x.requests.dungeons.resolve({items:[{id:'boss-1-60'}]});
  await new Promise(resolve=>setImmediate(resolve));
  x.requests.equipment.resolve([]);x.requests.rewards.reject(new Error('offline'));await pending;
  assert.deepEqual(x.rendered,['dungeons/boss-1-60']);
});

test('shops wait for linked catalogs and late shop responses cannot overwrite navigation', async () => {
  const x=router(), first=x.go('#shops');
  x.requests.dungeons.resolve({items:[]});x.requests.equipment.resolve([]);
  await new Promise(resolve=>setImmediate(resolve));assert.deepEqual(x.rendered,[]);
  x.requests.rewards.resolve({});await first;assert.deepEqual(x.rendered,['shops']);
  const old=x.go('#shops/boss-shop');await x.go('#');
  x.requests.dungeons.resolve({items:[]});x.requests.equipment.resolve([]);x.requests.rewards.resolve({});await old;
  assert.deepEqual(x.rendered,['shops','catalog']);
});
test('detailed routes select the requested tab and stale failures cannot display errors', async () => {
  const x=router(), full=x.go('#character/ca/details/voices'); x.requests.ca.resolve({id:'ca'}); await full;
  assert.deepEqual(x.rendered,['ca/voices']);
  const old=x.go('#character/cb'); await x.go('#'); x.requests.cb.reject(new Error('old')); await old;
  assert.equal(x.nodes['detail-view'].children.length,0);
});
test('active load failure exposes a working retry without resetting the route', async () => {
  const x=router(), first=x.go('#character/ca'); x.requests.ca.reject(new Error('offline')); await first;
  const retry=x.nodes['detail-view'].children[0].children[0];
  const pending=retry.click(); x.requests.ca.resolve({id:'ca'}); await pending;
  assert.deepEqual(x.rendered,['ca']);
});

test('team return context is attached only to the active detail, including retryable errors', async () => {
  const x=router(), attached=[];
  x.context.window.WFTeamInspector={attachReturn:(host,hash)=>attached.push({host,hash})};
  const old=x.go('#character/ca'), current=x.go('#character/cb/details/skills');
  x.requests.cb.resolve({id:'cb'});await current;x.requests.ca.resolve({id:'ca'});await old;
  assert.deepEqual(attached.map(entry=>entry.hash),['character/cb/details/skills']);
  assert.equal(attached[0].host,x.nodes['detail-view']);
  const weapon=x.go('#weapon/w1');x.requests.equipment.resolve([]);await weapon;
  assert.equal(attached.at(-1).host,x.nodes['extra-view']);
  const failed=x.go('#character/cc');x.requests.cc.reject(new Error('offline'));await failed;
  assert.equal(attached.at(-1).hash,'character/cc');
});
test('native order groups element, descending rarity, then official before MOD', () => {
  const context={window:{}}; vm.runInNewContext(source('character-order.js'),context);
  const rows=[{name:'water',element:'水',rarity:5,catalogOrder:1},
    {name:'mod',element:'火',rarity:5,catalogOrder:1,origin:'新增MOD'},
    {name:'four',element:'火',rarity:4,catalogOrder:1},
    {name:'later',element:'火',rarity:5,catalogOrder:9,origin:'改版官方'},
    {name:'early',element:'火',rarity:5,catalogOrder:2}];
  assert.deepEqual(rows.sort(context.window.WFCharacterOrder.compare).map(x=>x.name),['early','later','mod','four','water']);
});
