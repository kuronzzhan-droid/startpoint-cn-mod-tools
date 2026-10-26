const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const tick = () => new Promise(setImmediate);
class Node {
  constructor(tag, className = '', text = '') {Object.assign(this, {tag, className, textContent: text, children: [], attributes: {}, dataset: {}, events: {}});}
  get textContent() {return this.text + this.children.map((node) => node.textContent).join('');}
  set textContent(value) {this.text = value; this.children = [];}
  append(...nodes) {this.children.push(...nodes);}
  setAttribute(key, value) {this.attributes[key] = value;}
  getAttribute(key) {return this.attributes[key];}
  addEventListener(name, action) {this.events[name] = action;}
  fire(name = 'click') {return this.events[name]?.();}
  querySelectorAll(selector) {return this.children.flatMap((node) => [...(node.className.split(' ').includes(selector.slice(1)) ? [node] : []), ...node.querySelectorAll(selector)]);}
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
}
const source = fs.readFileSync(path.join(__dirname, '../wiki/catalog-ratings.js'), 'utf8');
const characters = ['火', '火', '火', '水', '水', '水'].map((element, index) => ({id: `c${index}`, element}));
const response = {items: [{id: 'c0', average: 2, voters: 8}, {id: 'c1', average: 0, voters: 1},
  {id: 'c3', average: 5, voters: 1}, {id: 'c4', average: 2, voters: 6}]};
function setup(handler = async () => response, protocol = 'https:', onChangeHook) {
  const calls = [], events = {}, host = new Node('div'), sort = new Node('select'), catalog = new Node('div'); sort.value = 'default';
  const window = {addEventListener: (name, action) => {events[name] = action;},
    WFCharacterOrder: {compare: (a, b) => a.id.localeCompare(b.id)},
    WFCommunity: {client: {request: (...args) => {calls.push(args); return handler(...args);}}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/rating-score.js'), 'utf8'), {window});
  vm.runInNewContext(source, {window, location: {protocol}});
  let changes = 0;
  const controller = window.WFCatalogRatings.create({characters, sort, host, ui: {el: (...args) => new Node(...args)},
    onChange() {changes++; controller.paintMounted(catalog); onChangeHook?.(controller);}});
  const card = (id) => {
    const card = new Node('a', 'character-card'); card.title = '角色'; card.setAttribute('aria-label', '角色，查看详情');
    card.append(new Node('div', 'card-meta')); catalog.append(card); controller.decorate(card, {id}); return card;
  };
  return {window, controller, calls, host, sort, catalog, card, get changes() {return changes;},
    order(mode) {sort.value = mode; return [...characters].sort(controller.compare).map((item) => item.id);},
    vote(id, value) {events['wf-character-rating-updated']({detail: {id, ...value}});},
    status: () => host.querySelector('.catalog-rating-status'), retry: () => host.querySelector('.text-button').fire()};
}

test('catalogue requests one aggregate only on demand, coalesces concurrent loads and reuses results', async () => {
  let resolve; const x = setup(() => new Promise((done) => {resolve = done;}));
  assert.equal(x.calls.length, 0); assert.equal(x.sort.children.length, 0, 'criterion options are owned by the entry, not duplicate direction options');
  const first = x.controller.load(); x.controller.load(); await tick();
  assert.equal(x.calls.length, 1); assert.deepEqual(x.calls[0], ['/ratings/characters']);
  assert.equal(x.status().hidden, false); assert.match(x.status().children[0].textContent, /正在加载/);
  resolve(response); await first; await x.controller.load(); assert.equal(x.calls.length, 1); assert.equal(x.status().hidden, true);
});

test('attribute and global sorting handle both directions, real zero, missing values and stable ties', async () => {
  const x = setup(); await x.controller.load();
  assert.deepEqual(x.order('rating-element-desc'), ['c0', 'c1', 'c2', 'c3', 'c4', 'c5']);
  assert.deepEqual(x.order('rating-element-asc'), ['c1', 'c0', 'c2', 'c4', 'c3', 'c5']);
  assert.deepEqual(x.order('rating-global-desc'), ['c3', 'c4', 'c0', 'c1', 'c2', 'c5']);
  assert.deepEqual(x.order('rating-global-asc'), ['c1', 'c0', 'c4', 'c3', 'c2', 'c5']);
  x.controller.update('c0', {average: 2.5, voters: 8});
  x.controller.update('c2', {average: 2.5, voters: 9});
  x.controller.update('c4', {average: 2.5, voters: 12});
  assert.deepEqual(x.order('rating-element-desc'), ['c2', 'c0', 'c1', 'c3', 'c4', 'c5']);
  assert.deepEqual(x.order('rating-element-asc'), ['c1', 'c2', 'c0', 'c4', 'c3', 'c5']);
  assert.deepEqual(x.order('rating-global-desc'), ['c3', 'c4', 'c2', 'c0', 'c1', 'c5']);
  assert.deepEqual(x.order('rating-global-asc'), ['c1', 'c4', 'c2', 'c0', 'c3', 'c5']);
  assert.equal(x.controller.isRatingSort(), true); x.sort.value = 'default'; assert.equal(x.controller.isRatingSort(), false);
});

test('card score and accessible title distinguish unloaded, unrated and zero without replacing card nodes', async () => {
  const x = setup(), zero = x.card('c1'), missing = x.card('c2');
  assert.equal(zero.querySelector('.card-rating').textContent, '评分 —'); assert.match(zero.title, /尚未加载/);
  await x.controller.load(); assert.equal(x.catalog.children[0], zero);
  assert.equal(zero.querySelector('.card-rating').textContent, '评分 0.0'); assert.match(zero.title, /0.0 \/ 5 · 1 人/);
  assert.match(zero.getAttribute('aria-label'), /0.0/); assert.equal(missing.querySelector('.card-rating').textContent, '评分 —');
  assert.match(missing.title, /未评分/);
});

test('an accepted single-character result wins over an in-flight batch, without pretending the batch is loaded', async () => {
  let resolve; const x = setup(() => new Promise((done) => {resolve = done;})); const card = x.card('c0');
  x.window.WFCatalogRatings.update('c0', {average: 1, voters: 1});
  const pending = x.controller.load(); await tick(); assert.equal(x.calls.length, 1);
  x.vote('c0', {average: 4.5, voters: 12, myScore: 5}); resolve(response); await pending;
  assert.equal(card.querySelector('.card-rating').textContent, '评分 4.5');
  assert.deepEqual(x.order('rating-global-desc').slice(0, 2), ['c0', 'c3']);
  const before = x.changes; x.controller.update('c0', {average: 4.5, voters: 12}); assert.equal(x.changes, before);
});

test('failed batches do not turn missing scores into zero or auto-loop; explicit retry loads a fresh batch', async () => {
  let attempts = 0; const x = setup(async () => {if (++attempts === 1) throw new Error('offline'); return response;});
  const card = x.card('c0'); await x.controller.load(); assert.equal(x.status().hidden, false);
  assert.match(x.status().children[0].textContent, /暂时未能加载/); assert.equal(x.status().children[1].hidden, false);
  assert.equal(card.querySelector('.card-rating').textContent, '评分 —');
  await x.controller.load(); assert.equal(x.calls.length, 1); x.retry(); await tick();
  assert.equal(x.calls.length, 2); assert.equal(card.querySelector('.card-rating').textContent, '评分 2.0');
});

test('invalid aggregates are rejected atomically and offline catalogues stay network-free', async () => {
  const x = setup(async () => ({items: [...response.items, {id: 'c5', average: null, voters: 1}]}));
  const card = x.card('c0'); await x.controller.load(); assert.equal(card.querySelector('.card-rating').textContent, '评分 —');
  assert.equal(x.status().children[1].hidden, false);
  assert.equal(x.controller.update('unknown', {average: 5, voters: 1}), false);
  assert.equal(x.controller.update('c0', {average: 0, voters: 0}), false);
  assert.equal(x.controller.update('c0', {average: Infinity, voters: 1}), false);
  const offline = setup(undefined, 'file:'); await offline.controller.load(); await offline.controller.load();
  assert.equal(offline.calls.length, 0); assert.match(offline.status().children[0].textContent, /离线版/);
  assert.equal(offline.status().children[1].hidden, true);
});

test('one extreme vote cannot outrank established high or low ratings; filtering does not change scores', async () => {
  const x = setup(async () => ({items: [
    {id: 'c0', average: 5, voters: 1}, {id: 'c1', average: 4.5, voters: 100},
    {id: 'c3', average: 0, voters: 1}, {id: 'c4', average: 1, voters: 100},
  ]}));
  const one = x.card('c0'); await x.controller.load();
  assert.deepEqual(x.order('rating-global-desc'), ['c1', 'c0', 'c3', 'c4', 'c2', 'c5']);
  assert.deepEqual(x.order('rating-global-asc'), ['c4', 'c3', 'c0', 'c1', 'c2', 'c5']);
  assert.deepEqual(x.order('rating-element-desc').slice(0, 3), ['c1', 'c0', 'c2']);
  assert.equal(one.querySelector('.card-rating').textContent, '评分 5.0');
  assert.match(one.title, /1 人 · 排序分 2\.92/);
  x.sort.fire('change'); assert.match(x.status().textContent, /按票数修正排序.*真实均分/);
  assert.equal(x.calls.length, 1);
});

test('server score precision survives accepted detail updates and invalid rank scores do not replace data', async () => {
  const x = setup(async () => ({items: [
    {id: 'c0', average: 4, voters: 10, rankScore: 3.49999},
    {id: 'c1', average: 4, voters: 10, rankScore: 3.50001},
  ]}));
  await x.controller.load(); assert.deepEqual(x.order('rating-global-desc').slice(0, 2), ['c1', 'c0']);
  x.vote('c0', {average: 4, voters: 10, rankScore: 3.50002});
  assert.deepEqual(x.order('rating-global-desc').slice(0, 2), ['c0', 'c1']);
  assert.equal(x.controller.update('c0', {average: 4, voters: 10, rankScore: NaN}), false);
  assert.equal(x.controller.update('c0', {average: 4, voters: 10, rankScore: null}), false);
});

test('daily catalogue remains a single published snapshot even when a personal vote arrives during or after loading', async () => {
  let resolve; const x = setup(() => new Promise(done => {resolve = done;}));
  const card = x.card('c0'), pending = x.controller.load(); await tick();
  x.vote('c0', {average: 5, voters: 99});
  resolve({...response, asOf:'2099-01-01T04:00:00Z', nextRefreshAt:'2099-01-01T16:00:00Z', stale:false});
  await pending;
  assert.equal(card.querySelector('.card-rating').textContent, '评分 2.0');
  assert.equal(x.controller.update('c0', {average: 5, voters: 100}), false);
  assert.equal(card.querySelector('.card-rating').textContent, '评分 2.0');
  await x.controller.load(); assert.equal(x.calls.length, 1);
  assert.match(x.status().textContent, /每日汇总.*次日计入/); assert.match(x.status().title, /北京时间/);
});

test('expired daily catalogue loads again only on demand and rejects invalid snapshot timestamps', async () => {
  let attempts = 0;
  const x = setup(async () => ({...response, asOf:'2020-01-01T04:00:00Z',
    nextRefreshAt:++attempts === 1 ? '2020-01-01T16:00:00Z' : '2099-01-01T16:00:00Z', stale:false}));
  await x.controller.load(); assert.equal(x.calls.length, 1);
  await tick(); assert.equal(x.calls.length, 1);
  await x.controller.load(); assert.equal(x.calls.length, 2);
  await x.controller.load(); assert.equal(x.calls.length, 2);
  const invalid = setup(async () => ({...response, asOf:'broken', nextRefreshAt:'broken', stale:false}));
  await invalid.controller.load(); assert.match(invalid.status().textContent, /未能加载/);
});

test('rendering a stale daily score sort can reenter load without hiding its refresh notice or starting another request', async () => {
  let renders = 0;
  const x = setup(async () => ({...response, asOf:'2020-01-01T04:00:00Z', nextRefreshAt:'2020-01-01T16:00:00Z', stale:true}),
    'https:', controller => {renders++; controller.load();});
  x.sort.value = 'rating-global-desc';
  await x.controller.load(); await tick();
  assert.equal(renders, 1); assert.equal(x.calls.length, 1);
  assert.equal(x.status().hidden, false);
  assert.match(x.status().textContent, /今日汇总更新中，显示上次结果/);
});
