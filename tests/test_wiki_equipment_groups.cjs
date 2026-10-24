const test=require('node:test');
const assert=require('node:assert/strict');
const {environment}=require('./wiki_equipment_fixture.cjs');
const entries=[{id:'fire',name:'火剑',element:'火',rarity:5,category:'深渊武器'},
  {id:'water',name:'水弓',element:'水',rarity:4,category:'其他武器'}];
const cls=(host,name)=>host.all(n=>n.className===name)[0];
function setup(){
  const x=environment();x.window.renderWikiWeaponPage(x.host,{equipment:entries},x.ui);
  const toggle=cls(x.host,'equipment-attribute-shortcut equipment-group-toggle');
  const groups=()=>x.host.all(n=>n.className==='equipment-group');
  const names=()=>x.host.all(n=>n.tag==='strong'&&n.parent.className==='equipment-card-title').map(n=>n.textContent);
  const filter=value=>{const select=x.host.all(n=>n.attributes['aria-label']==='武器分类')[0];select.value=value;select.fire('change');};
  return {...x,toggle,groups,names,filter};
}
test('one floating toggle alternates all current groups and unmounts cards when collapsed',()=>{
  const x=setup(),floating=cls(x.host,'equipment-attribute-floating');
  assert.equal(x.toggle.parent,floating);assert.equal(floating.children[0],x.toggle);
  assert.equal(floating.children.at(-1),cls(x.host,'equipment-attribute-shortcut'));
  assert.equal(x.host.all(n=>n.className==='team-controls equipment-group-controls').length,0);
  assert.equal(x.toggle.attributes.role,'switch');assert.equal(x.toggle.attributes['aria-label'],'展开全部武器分类');
  assert.equal(cls(x.toggle,'equipment-mode-track').attributes['aria-hidden'],'true');
  assert.equal(cls(x.toggle,'equipment-mode-thumb').textContent,'');
  assert.equal(x.toggle.attributes['aria-checked'],'false');
  assert.equal(x.toggle.textContent,'全部展开');assert.equal(x.toggle.attributes['aria-expanded'],'false');assert.deepEqual(x.names(),[]);
  x.toggle.fire('click');assert.equal(x.toggle.textContent,'全部收起');assert.equal(x.toggle.attributes['aria-expanded'],'true');
  assert.equal(x.toggle.attributes['aria-checked'],'true');assert.equal(x.toggle.attributes['aria-label'],'展开全部武器分类');
  assert.match(x.toggle.title,/全部收起/);
  assert.equal(x.groups().every(n=>n.open),true);assert.deepEqual(x.names(),['火剑','水弓']);
  const cards=x.host.all(n=>n.className.includes('equipment-card game-panel'));
  x.toggle.fire('click');assert.equal(x.toggle.textContent,'全部展开');assert.equal(x.toggle.attributes['aria-checked'],'false');assert.deepEqual(x.names(),[]);
  x.toggle.fire('click');assert.ok(cards.every(card=>x.host.all(n=>n===card).length===1));
});
test('manual mixed state always offers expand and changes to collapse only when every shown category is open',()=>{
  const x=setup(),groups=x.groups();
  groups[0].open=true;groups[0].fire('toggle');assert.equal(x.toggle.textContent,'全部展开');
  assert.equal(x.toggle.attributes['aria-checked'],'false');
  groups[1].open=true;groups[1].fire('toggle');assert.equal(x.toggle.textContent,'全部收起');
  assert.equal(x.toggle.attributes['aria-checked'],'true');
  groups[0].open=false;groups[0].fire('toggle');assert.equal(x.toggle.textContent,'全部展开');
  assert.equal(x.toggle.attributes['aria-checked'],'false');
  x.toggle.fire('click');assert.ok(groups.every(n=>n.open));assert.equal(x.toggle.textContent,'全部收起');
});
test('filtered actions do not open or close excluded categories and filter changes recompute the next action',()=>{
  const x=setup(),original=x.groups();
  x.filter('深渊武器');x.toggle.fire('click');assert.equal(original[0].open,true);assert.equal(original[1].open,false);
  x.filter('');assert.equal(x.toggle.textContent,'全部展开');x.toggle.fire('click');
  x.filter('深渊武器');assert.equal(x.toggle.textContent,'全部收起');x.toggle.fire('click');
  assert.equal(original[0].open,false);assert.equal(original[1].open,true);
  x.filter('');assert.equal(x.toggle.textContent,'全部展开');assert.deepEqual(x.names(),['水弓']);
  const search=x.host.all(n=>n.attributes['aria-label']==='搜索武器')[0];search.value='不存在';search.fire('input');
  assert.equal(x.toggle.disabled,true);assert.equal(x.toggle.attributes['aria-expanded'],'false');assert.equal(x.toggle.attributes['aria-checked'],'false');
  assert.equal(x.toggle.attributes['aria-label'],'展开全部武器分类');assert.equal(x.toggle.title,'没有符合筛选的武器');
  search.value='';search.fire('input');assert.equal(x.toggle.disabled,false);assert.equal(x.toggle.textContent,'全部展开');
});
test('toggling groups closes the attribute popover and leaving the route removes both controls',()=>{
  const x=setup(),shortcut=cls(x.host,'equipment-attribute-shortcut'),panel=cls(x.host,'equipment-attribute-popover');
  shortcut.fire('click');assert.equal(panel.hidden,false);x.toggle.fire('click');assert.equal(panel.hidden,true);
  x.window.fire('hashchange');assert.equal(x.toggle.isConnected,false);assert.equal(shortcut.isConnected,false);
});
