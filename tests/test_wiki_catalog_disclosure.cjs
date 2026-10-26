const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Node {
  constructor(tag, cls = '') {
    Object.assign(this, {tag, className: cls, children: [], dataset: {}, attributes: {}, events: {}, hidden: false, value: ''});
    this.classList = {add: (value) => {this.className += ` ${value}`;},
      remove: (value) => {this.className = this.className.split(' ').filter((name) => name !== value).join(' ');}};
  }
  get textContent() {return (this.text || '') + this.children.map((node) => node.textContent).join('');}
  set textContent(value) {this.text = String(value); this.replaceChildren();}
  append(...items) {
    for (const node of items) {
      if (node.tag === '#fragment') {this.append(...[...node.children]); continue;}
      if (node.parent) node.parent.children = node.parent.children.filter((item) => item !== node);
      node.parent = this; this.children.push(node);
    }
  }
  replaceChildren(...items) {this.children.forEach((node) => {node.parent = null;}); this.children = []; this.append(...items);}
  replaceWith(node) {const parent=this.parent;parent.children[parent.children.indexOf(this)]=node;node.parent=parent;this.parent=null;}
  setAttribute(key, value) {this.attributes[key] = value;}
  getAttribute(key) {return this.attributes[key];}
  addEventListener(name, fn) {(this.events[name] ||= new Set()).add(fn);}
  removeEventListener(name, fn) {this.events[name]?.delete(fn);}
  dispatchEvent(event) {for (const fn of this.events[event.type] || []) fn({...event, target:this, currentTarget:this});}
  fire(name) {this.dispatchEvent({type:name});}
  matches(selector) {return selector.startsWith('#') ? this.id === selector.slice(1) : selector.startsWith('.') ? this.className.split(' ').includes(selector.slice(1)) : this.tag === selector;}
  querySelectorAll(selector) {return this.children.flatMap((node) => [...(node.matches(selector) ? [node] : []), ...node.querySelectorAll(selector)]);}
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
  closest(selector) {return this.matches(selector) ? this : this.parent?.closest(selector) || null;}
  contains(node) {return node === this || this.children.some(child => child.contains(node));}
  focus() {this.focused = true;}
}
function setup(handler = async () => ({items: []}), {realRouter = false, sortValue = 'rating', viewsHandler = async () => ({items:[],asOf:'2026-01-01T00:00:00Z',nextRefreshAt:'2099-01-01T00:00:00Z'})} = {}) {
  const root = new Node('html'), catalog = new Node('section'); catalog.id = 'catalog-view'; root.append(catalog);
  const add = (id, tag = 'div', parent = root, cls = '') => {const node = new Node(tag, cls); node.id = id; parent.append(node); return node;};
  if (realRouter) {add('detail-view'); add('extra-view');}
  const controls = add('controls', 'div', catalog), display = add('display', 'div', controls, 'catalog-display-controls');
  add('catalog-character-filters', 'div', controls); add('catalog-avatar-controls', 'div', display);
  add('catalog-layout', 'select', display);
  const sort = add('sort-order', 'select', display); sort.value = sortValue;
  const direction = add('sort-direction', 'button', display);
  const heading = add('heading', 'div', catalog, 'section-heading'), title = new Node('h2'); heading.append(title);
  const count = add('result-count', 'span', title);
  ['filter-status', 'character-grid', 'empty-state', 'load-error', 'catalog-stats'].forEach((id) => add(id, 'div', catalog));
  ['header-version', 'nav-count', 'snapshot-note', 'category-nav', 'all-categories', 'empty-reset'].forEach((id) => add(id));
  const images=[];
  const document = Object.assign(new Node('#document'), {getElementById: (id) => root.querySelector(`#${id}`), querySelectorAll: (query) => root.querySelectorAll(query),
    createElement: (tag) => {const node=new Node(tag);if(tag==='img')images.push(node);return node;}, createDocumentFragment: () => new Node('#fragment'),
    documentElement: {style: {setProperty() {}}, classList: {add() {}}}});
  let callbacks, avatarOptions, avatarForm='before', avatarCreates = 0; const requests = [];
  const state = {search: '', element: '', rarity: '', type: '', origin: ''};
  const characters = [{id: 'c1', name: '甲', element: '火', rarity: 5}, {id: 'c2', name: '乙', element: '水', rarity: 4}].map((character,index)=>({...character,
    portraits:['觉醒前','觉醒后'].map((label,form)=>({label,url:`media/${'abcd'[index*2+form].repeat(64)}.webp`}))}));
  const window = Object.assign(new Node('#window'), {WF_WIKI: {meta: {}, characters},
    matchMedia: () => Object.assign(new Node('#media'), {matches:false}),
    WFCommunity: {client: {request: (...args) => {requests.push(args); return (args[0] === '/views/characters' ? viewsHandler : handler)(...args);}}},
    WFCharacterOrder: {compare: (a, b) => a.id.localeCompare(b.id)},
    WFCatalogAvatars: {create: (options) => {avatarOptions=options;return {getForm:()=>avatarForm,picture: () => {avatarCreates++; return new Node('img');}};}},
    WFCharacterFilters: {create(options) {callbacks = options; return {
      element: new Node('details'), getState: () => ({...state}),
      matches: (item) => (!state.element || state.element === item.element) && (!state.search || item.name.includes(state.search)),
      hasActiveFilters: () => Object.values(state).some(Boolean),
      reset() {Object.keys(state).forEach((key) => {state[key] = '';}); options.onStateChange({...state});},
    };}}, createWikiRouter: ({renderCatalog}) => renderCatalog});
  const storage=new Map();
  const context = {document, window, location: {hash: '', protocol: 'https:'}, Event:class {constructor(type){this.type=type;}},
    localStorage:{getItem:(key)=>storage.get(key),setItem:(key,value)=>storage.set(key,value)}};
  if (realRouter) {
    window.WFWikiData = {loadEquipment:async () => []}; window.renderWikiPage = () => true; window.scrollTo = () => {};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/router.js'),'utf8'), context);
  }
  for (const name of ['rating-score.js', 'portrait-cards.js', 'catalog-layout.js', 'catalog-disclosure.js', 'catalog-ratings.js', 'catalog-views.js', 'catalog-sort.js', 'app.js'])
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki', name), 'utf8'), context);
  return {catalog, display, count, heading, sort, direction, requests, filtersInitiallyOpen: callbacks.initiallyOpen, updateRating: (id, value) => window.WFCatalogRatings.update(id, value), get created() {return avatarCreates;},
    get portraitCreates() {return images.filter((node)=>node.className==='portrait-card-image').length;},
    layout(value) {document.getElementById('catalog-layout').children.find((node)=>node.dataset.layout===value).fire('click');},
    avatar(form) {avatarForm=form;avatarOptions.onChange?.(form);},
    document, window, context, grid: document.getElementById('character-grid'),
    cards: () => document.getElementById('character-grid').hidden ? [] : catalog.querySelectorAll('.character-card'),
    mountedCards: () => catalog.querySelectorAll('.character-card'), toggle: () => document.getElementById('catalog-list-toggle').fire('click'),
    change(values) {Object.assign(state, values); callbacks.onStateChange({...state}); callbacks.onChange({...state});},
    passive() {callbacks.onChange({...state});}, repeatNotify() {callbacks.onStateChange({...state}); callbacks.onChange({...state});}};
}

test('the real app creates no cards until first open and later collapses retain one hidden view', () => {
  const x = setup(); assert.equal(x.created, 0); assert.equal(x.cards().length, 0);
  assert.equal(x.filtersInitiallyOpen,false);
  assert.equal(x.count.textContent, '2 / 2'); assert.equal(x.display.parent, x.heading);
  assert.equal(x.catalog.querySelector('.catalog-list-label').textContent, '展开角色列表');
  x.passive(); assert.equal(x.created, 0);
  x.toggle(); assert.equal(x.cards().length, 2); assert.equal(x.created, 2);
  const original = x.cards();
  assert.equal(x.catalog.querySelector('.catalog-list-label').textContent, '收起角色列表');
  x.toggle(); assert.equal(x.cards().length, 0);
  assert.deepEqual(x.mountedCards(), original); assert.equal(x.grid.hidden, true);
  x.passive(); x.sort.fire('change'); assert.equal(x.created, 2); assert.equal(x.cards().length, 0);
  x.toggle(); assert.deepEqual(x.cards(), original); assert.equal(x.created, 2);
});

test('rapid reopen reuses portrait nodes and an in-flight rating request, and focus returns to the toggle', async () => {
  let resolve; const x = setup(() => new Promise(done => {resolve = done;}));
  x.toggle(); const original = x.cards();
  for (let i = 0; i < 20; i++) {x.toggle(); x.toggle();}
  assert.deepEqual(x.cards(), original); assert.equal(x.created, 2);
  await new Promise(setImmediate); assert.equal(x.requests.length, 2);
  assert.deepEqual(x.requests.map(item=>item[0]).sort(),['/ratings/characters','/views/characters']);
  x.document.activeElement = original[0]; x.toggle();
  assert.equal(x.document.getElementById('catalog-list-toggle').focused, true);
  assert.equal(x.grid.hidden, true);
  resolve({items: []}); await new Promise(setImmediate);
  x.toggle(); assert.deepEqual(x.cards(), original); assert.equal(x.requests.length, 2);
});

test('batch ratings are lazy and update mounted card text without recreating portraits; rating sort preserves filters and collapse', async () => {
  let resolve; const x = setup(() => new Promise((done) => {resolve = done;}), {sortValue:'rarity'});
  await new Promise(setImmediate); assert.equal(x.requests.length, 0);
  x.toggle(); await new Promise(setImmediate); assert.equal(x.requests.length, 2); const original = x.cards()[0];
  resolve({items: [{id: 'c1', average: 0, voters: 1}, {id: 'c2', average: 5, voters: 1}]}); await new Promise(setImmediate);
  assert.equal(x.cards()[0], original); assert.equal(x.created, 2);
  assert.equal(original.querySelector('.card-rating').textContent, '评分 0.0');
  x.sort.value = 'rating'; x.sort.fire('change'); assert.equal(x.cards()[0].href, '#character/c2');
  x.change({element: '火'}); assert.equal(x.cards().length, 1); assert.equal(x.cards()[0].href, '#character/c1');
  x.toggle(); const before = x.created; x.updateRating('c1', {average: 4, voters: 2}); x.passive();
  assert.equal(x.cards().length, 0); assert.equal(x.created, before); assert.equal(x.requests.length, 2);
});

test('new ratings repaint reused cards even when their rating-sort order does not change', async () => {
  const x = setup(async () => ({items: [{id:'c1', average:4, voters:10}, {id:'c2', average:2, voters:10}]}));
  x.toggle(); await new Promise(setImmediate);
  x.sort.value = 'rating'; x.sort.fire('change'); const first = x.cards()[0], created = x.created;
  x.updateRating('c1', {average:4.5, voters:11});
  assert.equal(x.cards()[0], first); assert.equal(x.created, created);
  assert.equal(first.querySelector('.card-rating').textContent, '评分 4.5');
});

test('selecting rating sort while collapsed loads one batch without mounting any card', async () => {
  const x = setup(); x.sort.value = 'rating-element'; x.direction.fire('click'); x.sort.fire('change'); await new Promise(setImmediate);
  assert.equal(x.requests.length, 1); assert.equal(x.created, 0); assert.equal(x.cards().length, 0);
});

test('real app defaults to descending scores and paints a delayed batch of views on reused hidden cards', async () => {
  let resolve;
  const x = setup(async()=>({items:[{id:'c1',average:4,voters:10},{id:'c2',average:2,voters:10}]}),
    {viewsHandler:()=>new Promise(done=>{resolve=done;})});
  await new Promise(setImmediate);assert.equal(x.requests.length,1);assert.equal(x.sort.value,'rating');
  assert.equal(x.direction.textContent,'↓ 倒序');x.toggle();const original=x.cards();x.toggle();await new Promise(setImmediate);
  resolve({items:[{id:'c1',views:0},{id:'c2',views:9}],asOf:'2026-01-01T00:00:00Z',nextRefreshAt:'2099-01-01T00:00:00Z'});await new Promise(setImmediate);
  assert.equal(x.cards().length,0);assert.equal(original[0].querySelector('.card-views').textContent,'查看 0 次');
  x.toggle();assert.deepEqual(x.cards(),original);assert.equal(x.created,2);
  assert.equal(original[0].querySelector('.card-stats').children[0].className,'card-rating');
  assert.equal(original[0].querySelector('.card-footer').children[0].className,'card-tags');
  assert.equal(original[0].querySelector('.card-footer').children[1].className,'card-views');
  x.sort.value='views';x.sort.fire('change');assert.equal(x.cards()[0].href,'#character/c2');
  x.direction.fire('click');assert.equal(x.cards()[0].href,'#character/c1');
  assert.deepEqual(x.requests.map(item=>item[0]).sort(),['/ratings/characters','/views/characters']);
});

test('active user filters reopen results; passive aliases and delayed duplicate notifications preserve manual collapse', () => {
  const x = setup(); x.change({element: '火'}); assert.equal(x.cards().length, 1);
  x.toggle(); assert.equal(x.cards().length, 0); const before = x.created;
  x.passive(); x.repeatNotify(); assert.equal(x.created, before); assert.equal(x.cards().length, 0);
  x.change({element: '水'}); assert.equal(x.cards().length, 1);
  x.toggle(); x.change({element: '', search: '甲'}); assert.equal(x.cards().length, 1);
});

test('real layout buttons and app keep portrait cards uncreated while collapsed, including awakening and passive refreshes',()=>{
  const x=setup();x.layout('portrait');x.avatar('after');x.passive();
  assert.equal(x.catalog.dataset.layout,'portrait');assert.equal(x.portraitCreates,0);assert.equal(x.created,0);assert.equal(x.cards().length,0);
  x.toggle();const cards=x.cards();assert.equal(cards.length,2);assert.equal(x.portraitCreates,2);assert.equal(x.created,0);
  cards.forEach((card,index)=>{
    assert.match(card.className,/portrait-card/);const image=card.querySelector('.portrait-card-image');
    assert.equal(image.getAttribute('src'),`media/${'bd'[index].repeat(64)}.webp`);assert.equal(image.loading,'lazy');assert.equal(image.decoding,'async');
  });
  x.toggle();assert.equal(x.cards().length,0);
  assert.equal(x.window.events.scroll.size,0,'collapsing pauses global portrait interaction listeners');
  x.toggle();assert.deepEqual(x.cards(),cards);assert.equal(x.portraitCreates,2);assert.equal(x.window.events.scroll.size,1);
  x.toggle();
  x.layout('dense');x.layout('portrait');x.avatar('before');x.passive();assert.equal(x.portraitCreates,2);assert.equal(x.cards().length,0);
  x.toggle();assert.deepEqual(x.cards(),cards);assert.equal(x.portraitCreates,4);
  assert.equal(x.cards()[0].querySelector('.portrait-card-image').getAttribute('src'),`media/${'a'.repeat(64)}.webp`);
});

test('real app replaces standard avatars with the selected portrait form on layout change and cleans it when returning',()=>{
  const x=setup();x.toggle();assert.equal(x.created,2);assert.equal(x.portraitCreates,0);
  x.layout('portrait');const before=x.cards();assert.equal(x.portraitCreates,2);
  assert.equal(before[0].querySelector('.portrait-card-image').getAttribute('src'),`media/${'a'.repeat(64)}.webp`);
  x.avatar('after');assert.equal(x.portraitCreates,4);assert.equal(before[0].events.pointermove.size,1);
  const after=x.cards();assert.equal(after[0].querySelector('.portrait-card-image').getAttribute('src'),`media/${'b'.repeat(64)}.webp`);
  assert.deepEqual(after,before,'awakening updates images without replacing the cards');
  x.layout('standard');assert.equal(x.created,4);assert.equal(x.portraitCreates,4);assert.equal(after[0].events.pointermove.size,0);
  assert.equal(x.catalog.querySelectorAll('.portrait-card-media').length,0);
});

test('density switches reuse avatars, while a cleared router view and changed ordering rebuild only the current view', () => {
  const x = setup(); x.toggle(); const first = x.cards();
  x.layout('dense'); assert.deepEqual(x.cards(), first); assert.equal(x.created, 2);
  x.toggle(); x.sort.value = 'rarity'; x.sort.fire('change'); assert.equal(x.created, 2);
  x.toggle(); assert.deepEqual(x.cards(), first);
  x.grid.replaceChildren(); x.passive(); assert.equal(x.cards().length, 2); assert.equal(x.created, 4);
  assert.notEqual(x.cards()[0], first[0]); assert.equal(x.mountedCards().length, 2);
});

test('real router preserves portrait interaction for unknown hashes and denied navigation, releasing it only on accepted page leave', async () => {
  const x = setup(undefined,{realRouter:true}); x.layout('portrait'); x.toggle();
  const cards = x.cards(), first = cards[0];
  const go = async hash => {x.context.location.hash = hash; x.window.fire('hashchange'); await new Promise(setImmediate);};
  for (const hash of ['#missing-page','#main-content']) {
    await go(hash); assert.equal(x.cards()[0],first);
    assert.equal(first.events.pointermove.size,1); assert.equal(x.window.events.scroll.size,1);
  }
  let resolve;
  x.window.WFNavigationGuard = {allow:() => new Promise(done => {resolve=done;})};
  x.context.location.hash = '#team'; x.window.fire('hashchange');
  assert.equal(first.events.pointermove.size,1); resolve(false); await new Promise(setImmediate);
  assert.equal(x.catalog.hidden,false); assert.equal(x.cards()[0],first); assert.equal(first.events.pointermove.size,1);
  x.window.WFNavigationGuard.allow = () => true;
  await go('#team'); assert.equal(x.catalog.hidden,true); assert.equal(x.mountedCards().length,0);
  assert.equal(first.events.pointermove.size,0); assert.equal(x.window.events.scroll.size,0);
  await go('#'); assert.equal(x.catalog.hidden,false); assert.equal(x.cards().length,2);
  assert.notEqual(x.cards()[0],first); assert.equal(x.cards()[0].events.pointermove.size,1);
});
