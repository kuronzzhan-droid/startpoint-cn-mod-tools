const test = require('node:test');
const assert = require('node:assert/strict');
const {environment} = require('./wiki_equipment_fixture.cjs');
const find = (root,key,value) => root.all(n=>n.attributes[key]===value)[0];
const cls = (root,value) => root.all(n=>n.className===value)[0];
const weapon = {id:'forms',name:'原始武器',icon:'base.webp',category:'悖论武器',element:'火',rarity:5,
  stats:{base:{hp:1,atk:2},awakened:{hp:100,atk:20}},baseEffects:['初始10%'],awakenedEffects:['满级50%'],
  soul:{available:true,effects:['魂珠5%']},enhancement:{maxLevel:200,forms:[
    {level:200,name:'蓝金形态',icon:'blue.webp',frame:'blue-frame.webp',label:'蓝金 Lv200',stats:{total:{hp:500,atk:80}},finalEffects:['最终100%'],initialFinalEffects:['初始合计60%']},
    {level:'invalid',name:'无效形态',icon:'invalid.webp'},
    {level:120,name:'终式',icon:'final.webp',label:'终式 Lv120',stats:{total:{hp:300,atk:50}},finalEffects:['最终70%'],initialFinalEffects:['初始合计30%']},
  ]}};
function cardFixture(entry=weapon,options) {
  const x=environment(),card=x.window.WFEquipmentCard.create(entry,x.ui,options);x.host.append(card);return {...x,card};
}
const open = card => {card.open=true;card.fire('toggle');};
const click = (root,key,value) => find(root,key,value).fire('click');
const cards = host => host.all(n=>n.tag==='details'&&n.className.startsWith('equipment-card '));
function catalogue() {
  const x=environment();x.window.renderWikiWeaponPage(x.host,{equipment:[weapon]},x.ui);return x;
}

test('weapons start at the highest valid enhancement with its matching icon/frame and max effects',()=>{
  const {card}=cardFixture();
  assert.equal(card.attributes['data-enhancement-level'],'200');
  assert.equal(cls(card,'equipment-icon').attributes.src,'blue.webp');
  assert.equal(cls(card,'equipment-frame-image').attributes.src,'blue-frame.webp');
  assert.match(card.children[0].attributes['aria-label'],/蓝金形态，蓝金 Lv200/);
  assert.match(cls(card,'equipment-final-stats').textContent,/HP 500 \/ 攻击力 80/);
  open(card);assert.equal(find(card,'data-effect-level','max').attributes['aria-pressed'],'true');
  assert.match(cls(card,'equipment-state').textContent,/最终100%/);
  click(card,'data-level','120');assert.equal(cls(card,'equipment-icon').attributes.src,'final.webp');
  assert.equal(cls(card,'equipment-frame-image'),undefined);
  assert.match(cls(card,'equipment-state').textContent,/最终70%/);
});

test('single-stage and ordinary weapons use max defaults while explicit unenhanced selections survive recreation',()=>{
  const single={...weapon,enhancement:{maxLevel:120,icon:'enhanced.webp',stats:{total:{hp:250,atk:40}},finalEffects:['单档满级']}};
  const x=cardFixture(single);assert.equal(x.card.attributes['data-enhancement-level'],'120');
  assert.equal(cls(x.card,'equipment-icon').attributes.src,'enhanced.webp');
  const enhancedStates=new Map([['forms',0]]),saved=cardFixture(weapon,{enhancedStates}).card;
  assert.equal(saved.attributes['data-enhancement-level'],'0');assert.equal(cls(saved,'equipment-icon').attributes.src,'base.webp');
  click(saved,'data-level','120');assert.equal(enhancedStates.get('forms'),120);
  assert.equal(cardFixture(weapon,{enhancedStates}).card.attributes['data-enhancement-level'],'120');
  const ordinary=cardFixture({...weapon,enhancement:null}).card;open(ordinary);
  assert.equal(ordinary.attributes['data-enhancement-level'],'0');
  assert.equal(cls(ordinary,'equipment-icon').attributes.src,'base.webp');
  assert.match(cls(ordinary,'equipment-final-stats').textContent,/HP 100 \/ 攻击力 20/);
  assert.match(cls(ordinary,'equipment-state').textContent,/满级50%/);
});

test('density switches preserve card choices and group state without eagerly mounting collapsed categories',()=>{
  const x=catalogue(),{host,storage}=x,groups=cls(host,'equipment-groups'),category=cls(host,'equipment-group');
  assert.equal(groups.attributes['data-layout'],'dense');assert.equal(category.open,false);assert.equal(cards(host).length,0);
  click(host,'aria-label','武器致密排列');assert.equal(groups.attributes['data-layout'],'dense');
  assert.equal(find(host,'aria-label','武器致密排列').attributes['aria-pressed'],'true');
  assert.equal(category.open,false);assert.equal(cards(host).length,0);
  open(category);const card=cards(host)[0];open(card);
  click(card,'data-level','120');click(card,'data-effect-level','initial');click(card,'role','switch');
  assert.match(cls(card,'equipment-state').textContent,/魂珠5%/);
  click(host,'aria-label','武器标准排列');assert.equal(cards(host)[0],card);assert.equal(card.open,true);
  click(host,'aria-label','武器致密排列');assert.equal(card.open,false);assert.equal(category.open,true);
  assert.equal(card.attributes['data-equipment-mode'],'soul');assert.equal(card.attributes['data-enhancement-level'],'120');
  open(card);click(card,'role','switch');assert.match(cls(card,'equipment-state').textContent,/初始合计30%/);
  click(card,'data-level','0');
  const search=find(host,'aria-label','搜索武器');search.value='没有';search.fire('input');assert.equal(cards(host).length,0);
  search.value='';search.fire('input');assert.equal(cards(host)[0],card);assert.equal(card.attributes['data-enhancement-level'],'0');
  assert.equal(storage.get('wf-wiki-equipment-layout-v2'),'dense');
  x.window.renderWikiWeaponPage(host,{equipment:[weapon]},x.ui);
  assert.equal(cls(host,'equipment-groups').attributes['data-layout'],'dense');assert.equal(cards(host).length,0);
});

test('compact header keeps optional help and advanced filters closed and exposes active criteria',()=>{
  const {host}=catalogue();assert.equal(cls(host,'equipment-help').open,false);
  const advanced=cls(host,'equipment-advanced-filters');assert.equal(advanced.open,false);
  assert.equal(find(host,'aria-label','搜索武器').parent.className,'equipment-search-row');
  for(const [label,value] of [['武器分类','悖论武器'],['武器星级','5'],['武器强化筛选','yes']]) {
    const field=find(host,'aria-label',label);assert.equal(field.parent.className,'equipment-filter-fields');
    field.value=value;field.fire('change');
  }
  assert.equal(advanced.children[0].textContent,'更多筛选 · 悖论武器 · 5★ · 可强化');
  assert.match(host.textContent,/共 1 件武器/);
});

test('direct weapon details ignore catalogue density and open the highest form immediately',()=>{
  const x=environment();x.storage.set('wf-wiki-equipment-layout-v2','dense');
  x.window.renderWikiWeaponPage(x.host,{equipment:[weapon]},x.ui,'forms');
  assert.equal(cls(x.host,'equipment-layout-controls'),undefined);assert.equal(cls(x.host,'equipment-groups'),undefined);
  const card=cards(x.host)[0];assert.equal(card.open,true);assert.equal(card.attributes['data-enhancement-level'],'200');
  card.fire('toggle');assert.match(cls(card,'equipment-state').textContent,/最终100%/);
});
