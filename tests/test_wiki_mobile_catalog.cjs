const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {Node: BaseNode} = require('./wiki_equipment_fixture.cjs');
const source = name => fs.readFileSync(path.join(__dirname, '../wiki', name), 'utf8');
class Node extends BaseNode {
  get lastElementChild() {return this.children.at(-1);}
  prepend(node) {node.remove(); node.parent=this; this.children.unshift(node);}
  matches(selector) {return selector[0]==='.' ? this.className.split(' ').includes(selector.slice(1)) : this.tag===selector;}
  closest(selector) {return (selector === 'details.character-filters' && this.tag === 'details' && this.className === 'character-filters') ? this : this.parent?.closest(selector) || null;}
  querySelector(selector) {return this.all(node=>node.matches(selector))[0] || null;}
  get classList() {return {toggle:(name, enabled)=>{
    const names=new Set(this.className.split(' ').filter(Boolean));
    if(enabled)names.add(name);else names.delete(name);this.className=[...names].join(' ');
  }};}
  scrollIntoView() {this.scrolls=(this.scrolls || 0)+1;}
  focus(options) {super.focus();this.lastFocusOptions=options;}
}
function environment(matches=true) {
  const document=new Node('document'), window=new Node('window'), query=new Node('media');query.matches=matches;
  const el=(...args)=>Object.assign(new Node(...args),{document});
  let subscriptions=0;
  window.matchMedia=()=>{subscriptions++;return query;};
  document.createElement=tag=>el(tag);
  const storage=new Map([['wf-wiki-sidebar-collapsed','true']]);
  const context={window,document,location:{hash:'#'},localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)},setTimeout,clearTimeout};
  return {context,document,window,query,el,storage,subscriptions:()=>subscriptions,
    resize(matches){query.matches=matches;query.fire('change');}};
}
function filters(x, idPrefix, options = {}) {
  vm.runInNewContext(source('character-filters.js'), x.context);
  const filter=x.window.WFCharacterFilters.create({characters:[{id:'a',name:'A',rarity:5,type:'剑士',origin:'MOD'}],
    idPrefix,ui:{el:x.el,nativeIcon:()=>x.el('img','native-icon')},...options});
  x.document.append(filter.element);
  const body=filter.element.querySelector('.character-filter-body');
  return {filter,body,fields:body.querySelector('.character-filter-fields'),elements:body.querySelector('.character-filter-elements')};
}
test('mobile catalogue tab order puts search and all three choices before element buttons',()=>{
  const x=environment(), {filter,body,fields,elements}=filters(x,'catalog-character',{initiallyOpen:false});
  assert.equal(filter.element.open,false);
  assert.equal(filter.element.querySelector('.character-filter-toggle-hint').textContent,'展开 ▾');
  const interactive=body.all(node=>node.tag==='input'||node.tag==='select'||node.className==='character-filter-element');
  assert.equal(interactive[0],filter.search);
  assert.deepEqual(interactive.slice(1,4).map(node=>node.id),['catalog-character-rarity','catalog-character-type','catalog-character-origin']);
  assert.equal(interactive[4],elements.children[0]);
  assert.ok(body.children.indexOf(fields)<body.children.indexOf(elements));
  assert.equal(elements.children.length,7);
  assert.equal(elements.children[0].textContent,'全部');
  ['火','水','雷','风','光','暗'].forEach((name,index)=>{
    const button=elements.children[index+1];
    assert.equal(button.textContent,'');assert.equal(button.children[0].tag,'img');
    assert.equal(button.attributes['aria-label'],`${name}属性`);assert.equal(button.title,`${name}属性`);
  });
  filter.focus();assert.equal(filter.element.open,true);assert.equal(x.document.activeElement,filter.search);
  filter.element.fire('toggle');assert.equal(filter.element.querySelector('.character-filter-toggle-hint').textContent,'收起 ▴');
});
test('resizing restores desktop order without replacing controls, values or keyboard focus',()=>{
  const x=environment(), {body,fields,elements}=filters(x,'catalog-character');
  const rarity=fields.children[0].children[1];rarity.value='5';rarity.focus();
  x.resize(false);
  assert.equal(body.lastElementChild,fields);assert.equal(x.document.activeElement,rarity);
  assert.equal(rarity.lastFocusOptions.preventScroll,true);assert.equal(rarity.value,'5');
  const fire=elements.children[1];fire.focus();x.resize(true);
  assert.equal(body.lastElementChild,elements);assert.equal(x.document.activeElement,fire);
  assert.equal(fire.lastFocusOptions.preventScroll,true);
});
test('team filters keep the original ordering and install no catalogue viewport listener',()=>{
  const x=environment(), {filter,body,fields,elements}=filters(x,'team-character',{collapsible:false});
  assert.equal(filter.element.tag,'div');assert.equal(filter.element.querySelector('.character-filter-heading'),null);
  assert.equal(x.subscriptions(),0);assert.equal(body.lastElementChild,fields);
  x.resize(false);x.resize(true);assert.ok(body.children.indexOf(elements)<body.children.indexOf(fields));
});
function sidebar(x) {
  const shell=x.el('div','page-shell'), nav=x.el('aside','sidebar');shell.append(nav);x.document.append(shell);
  vm.runInNewContext(source('sidebar.js'),x.context);
  return {shell,nav,toolbar:shell.querySelector('.sidebar-toolbar'),button:shell.querySelector('.sidebar-toggle')};
}
test('mobile directory opens into view and Escape closes it with focus retained at its floating trigger',()=>{
  const x=environment(), {shell,nav,toolbar,button}=sidebar(x);
  assert.ok(shell.className.includes('catalog-home'));assert.equal(button.textContent,'目录');
  assert.equal(button.attributes['aria-controls'],'character-sidebar');assert.equal(nav.hidden,true);
  button.fire('click');assert.equal(nav.hidden,false);assert.equal(nav.scrolls,1);assert.equal(toolbar.hidden,false);
  assert.equal(button.textContent,'收起');assert.equal(button.attributes['aria-expanded'],'true');
  nav.fire('keydown',{key:'Escape'});assert.equal(nav.hidden,true);assert.equal(x.document.activeElement,button);
  assert.equal(x.storage.get('wf-wiki-sidebar-collapsed'),'true');
});
test('route changes and desktop widths preserve automatic sidebar hiding and manual preference',()=>{
  const x=environment();x.storage.set('wf-wiki-sidebar-collapsed','false');
  const {shell,nav,toolbar,button}=sidebar(x);
  assert.equal(nav.hidden,true);assert.equal(button.attributes['aria-expanded'],'false');
  button.fire('click');assert.equal(nav.hidden,false);assert.equal(x.storage.get('wf-wiki-sidebar-collapsed'),'false');
  x.context.location.hash='#team';x.window.fire('hashchange');
  assert.equal(toolbar.hidden,true);assert.equal(nav.hidden,true);assert.ok(!shell.className.includes('catalog-home'));
  x.context.location.hash='#';x.window.fire('hashchange');assert.equal(nav.hidden,true);assert.equal(toolbar.hidden,false);
  x.resize(false);assert.equal(nav.hidden,false);assert.equal(button.textContent,'‹ 收起目录');
  button.fire('click');button.fire('click');assert.equal(nav.scrolls,1);
  x.context.location.hash='#character/c123';x.window.fire('hashchange');
  x.resize(true);assert.equal(nav.hidden,true);assert.equal(toolbar.hidden,true);assert.ok(!shell.className.includes('catalog-home'));
  assert.equal(x.storage.get('wf-wiki-sidebar-collapsed'),'false');
  x.resize(false);assert.equal(nav.hidden,false);assert.equal(toolbar.hidden,false);
});
test('fresh mobile sessions default closed and never persist their temporary open state',()=>{
  const x=environment();x.storage.clear();const {nav,button}=sidebar(x);
  assert.equal(nav.hidden,true);button.fire('click');assert.equal(nav.hidden,false);
  button.fire('click');assert.equal(nav.hidden,true);button.fire('click');
  assert.equal(x.storage.size,0);
  x.resize(false);assert.equal(nav.hidden,false);
  button.fire('click');assert.equal(x.storage.get('wf-wiki-sidebar-collapsed'),'true');
  x.resize(true);assert.equal(nav.hidden,true);button.fire('click');assert.equal(nav.hidden,false);
  x.resize(false);assert.equal(nav.hidden,true);
});
test('shops keep the character sidebar hidden at mobile and desktop widths without changing its preference',()=>{
  for (const mobile of [true,false]) {
    const x=environment(mobile);x.storage.set('wf-wiki-sidebar-collapsed','false');
    const {shell,nav,toolbar}=sidebar(x);
    for (const hash of ['#shops','#shops/boss-coins','#tier-list']) {
      x.context.location.hash=hash;x.window.fire('hashchange');
      assert.equal(nav.hidden,true);assert.equal(toolbar.hidden,true);
      assert.ok(shell.className.includes('sidebar-collapsed'));
      assert.equal(x.storage.get('wf-wiki-sidebar-collapsed'),'false');
    }
    x.context.location.hash='#';x.window.fire('hashchange');
    assert.equal(toolbar.hidden,false);assert.equal(nav.hidden,mobile);
  }
});
