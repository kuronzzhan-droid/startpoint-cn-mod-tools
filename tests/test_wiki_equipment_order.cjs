const test = require('node:test');
const assert = require('node:assert/strict');
const {environment} = require('./wiki_equipment_fixture.cjs');
const order = require('../wiki/equipment-order.js');
const entries = [
  {id:'zzz',name:'早期五星',rarity:5,category:'其他武器'},
  {id:'aaa',name:'后期五星',rarity:5,category:'其他武器'},
  {id:'weak',name:'近期三星',rarity:3,category:'其他武器'},
  {id:'abyss-old',name:'深渊早期五星',rarity:5,category:'深渊武器'},
  {id:'abyss-new',name:'深渊后期五星',rarity:5,category:'深渊武器'},
  {id:'abyss-low',name:'深渊一星',rarity:1,category:'深渊武器'},
];
test('higher rarity precedes newer low rarity and same-rarity order ignores opaque ID spelling', () => {
  const before = entries.map((entry) => entry.id), compare = order.createCompare(entries);
  assert.deepEqual([...entries].sort(compare).map((entry) => entry.id),['abyss-new','abyss-old','aaa','zzz','weak','abyss-low']);
  assert.deepEqual(entries.map((entry) => entry.id),before);
  assert.deepEqual([entries[0],entries[1],entries[2]].sort(compare).map((entry) => entry.id),['aaa','zzz','weak']);
});
test('unknown positions and missing rarity sort after known entries without producing NaN', () => {
  const compare = order.createCompare(entries);
  assert.ok(compare(entries[0],{id:'not-in-catalog',rarity:5}) < 0);
  assert.ok(compare(entries[5],{id:'not-in-catalog'}) < 0);
  assert.equal(compare({id:'none',rarity:'invalid'},{id:'other'}),0);
});
test('weapon groups start unmounted and preserve category/rarity ordering when expanded and filtered', () => {
  const {host,window,ui} = environment();
  window.renderWikiWeaponPage(host,{equipment:entries},ui);
  const names = () => host.all((node) => node.tag === 'strong' && node.parent.className === 'equipment-card-title').map((node) => node.textContent);
  assert.deepEqual(names(), []);
  assert.ok(host.all((node) => node.className === 'equipment-group').every((node) => node.open === false));
  host.all((node) => node.tag === 'button' && node.textContent === '全部展开')[0].fire('click');
  assert.deepEqual(names(),['深渊后期五星','深渊早期五星','深渊一星','后期五星','早期五星','近期三星']);
  const rarity = host.all((node) => node.attributes['aria-label'] === '武器星级')[0];
  rarity.value = '5'; rarity.fire('change');
  assert.deepEqual(names(),['深渊后期五星','深渊早期五星','后期五星','早期五星']);
  const category = host.all((node) => node.attributes['aria-label'] === '武器分类')[0];
  category.value = '其他武器'; category.fire('change'); assert.deepEqual(names(),['后期五星','早期五星']);
});

test('a standalone weapon still opens its detail card immediately', () => {
  const {host,window,document,ui} = environment();
  window.renderWikiWeaponPage(host,{equipment:entries},ui,'aaa');
  const card = host.all((node) => node.className.includes('equipment-card'))[0];
  assert.equal(card.open,true); assert.match(document.title,/后期五星/);
});

function catalogue(items) {
  const {host,window,ui} = environment();
  window.renderWikiWeaponPage(host,{equipment:items},ui);
  const expand = (open = true) => host.all((node) => node.tag === 'button' && node.textContent === (open ? '全部展开' : '全部收起'))[0].fire('click');
  const select = (label,value) => {const node=host.all((n)=>n.attributes['aria-label']===label)[0];node.value=value;node.fire('change');};
  const names = (root=host) => root.all((node)=>node.tag==='strong'&&node.parent.className==='equipment-card-title').map((node)=>node.textContent);
  return {host,expand,select,names};
}
const mixed = [
  ['plain-old','普通早期五星','暗',5,false],['fire-old','火强化早期五星','火',5,true],
  ['water-new','水强化五星','水',5,true],['fire-low','火强化三星','火',3,true],
  ['fire-new','火强化后期五星','火',5,true],['plain-new','普通后期五星','火',5,false],
  ['wind','风强化','风',5,true],['thunder','雷强化','雷',5,true],['light','光强化','光',5,true],
  ['dark','暗强化','暗',5,true],['general','通用强化','通用/未分类',5,true],['plain-low','普通三星','水',3,false],
].map(([id,name,element,rarity,enhanced])=>({id,name,element,rarity,category:'领主掉落与兑换',
  ...(enhanced?{enhancement:{maxLevel:120,stats:{total:{hp:100,atk:20}}}}:{})}));

test('each category separates enhanced cards from ordinary cards with enhanced attribute/rarity/reverse-catalogue ordering',()=>{
  const before=mixed.map(e=>e.id),x=catalogue(mixed);assert.deepEqual(x.names(),[]);x.expand();
  assert.deepEqual(x.names(),['火强化后期五星','火强化早期五星','火强化三星','水强化五星','雷强化','风强化','光强化','暗强化','通用强化','普通后期五星','普通早期五星','普通三星']);
  const tiers=x.host.all(n=>n.className.startsWith('equipment-tier '));assert.equal(tiers.length,2);
  assert.match(tiers[0].className,/enhanceable/);assert.match(tiers[1].className,/regular/);
  assert.equal(tiers[0].all(n=>n.className==='equipment-grid').length,1);assert.equal(tiers[1].all(n=>n.className==='equipment-grid').length,1);
  assert.equal(x.names(tiers[0]).length,9);assert.equal(x.names(tiers[1]).length,3);assert.deepEqual(mixed.map(e=>e.id),before);
  // Formation ordering remains independent: a newer ordinary five-star still wins there.
  assert.ok(order.createCompare(mixed)(mixed[5],mixed[1])<0);
});

test('filtering hides empty tiers, keeps rarity order and preserves an enhanced card state across unmounts',()=>{
  const x=catalogue(mixed);x.expand();
  const card=x.host.all(n=>n.className.includes('equipment-card')&&n.textContent.includes('火强化后期五星'))[0];
  card.all(n=>n.tag==='button'&&n.attributes['data-level']==='120')[0].fire('click');
  assert.equal(card.attributes['data-enhancement-level'],'120');
  x.select('武器强化筛选','no');assert.deepEqual(x.names(),['普通后期五星','普通早期五星','普通三星']);
  assert.equal(x.host.all(n=>n.className.startsWith('equipment-tier ')).length,1);
  x.select('武器强化筛选','yes');x.select('武器星级','5');
  assert.deepEqual(x.names(),['火强化后期五星','火强化早期五星','水强化五星','雷强化','风强化','光强化','暗强化','通用强化']);
  assert.ok(x.host.all(n=>n===card).length);assert.equal(card.attributes['data-enhancement-level'],'120');
  x.expand(false);assert.deepEqual(x.names(),[]);x.expand();assert.equal(card.attributes['data-enhancement-level'],'120');
});

test('category priority still precedes enhancement and missing attributes fall back after dark',()=>{
  const x=catalogue([{id:'abyss',name:'深渊普通',category:'深渊武器',rarity:1},
    ...mixed.filter(e=>e.id==='dark'),{id:'unknown',name:'未知属性强化',category:'领主掉落与兑换',rarity:5,enhancement:{maxLevel:120}}]);
  x.expand();assert.deepEqual(x.names(),['深渊普通','暗强化','未知属性强化']);
});
