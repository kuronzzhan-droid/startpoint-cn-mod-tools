const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const tick = () => new Promise(setImmediate);
class Node {
  constructor(tag, className = '', text = '') {Object.assign(this, {tag, className, text, children:[], dataset:{}, attributes:{}, events:{}, hidden:false});}
  get textContent() {return this.text + this.children.map(node => node.textContent).join('');}
  set textContent(value) {this.text = value; this.children = [];}
  append(...nodes) {this.children.push(...nodes);}
  setAttribute(key, value) {this.attributes[key] = value;}
  addEventListener(name, callback) {this.events[name] = callback;}
  querySelectorAll(selector) {return this.children.flatMap(node => [...(node.className.split(' ').includes(selector.slice(1)) ? [node] : []), ...node.querySelectorAll(selector)]);}
  querySelector(selector) {return this.querySelectorAll(selector)[0];}
}
const response = (items = [{id:'a', views:0}, {id:'b', views:12}]) => ({items, asOf:'2026-10-02T10:00:00Z', nextRefreshAt:'2026-10-02T10:30:00Z'});
function setup(handler = async () => response(), protocol = 'https:') {
  let now = Date.parse('2026-10-02T10:15:00Z');
  class Clock extends Date {static now() {return now;}}
  const calls = [], window = {WFCommunity:{client:{request(...args) {calls.push(args);return handler(...args);}}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/catalog-views.js'), 'utf8'), {window, Date:Clock, location:{protocol}});
  function create(onChange) {
    const host = new Node('div'), catalog = new Node('div'); let changes = 0;
    const controller = window.WFCatalogViews.create({host, ui:{el:(...args) => new Node(...args)}, onChange() {changes++;controller.paintMounted(catalog);onChange?.(controller);}});
    function card(id) {const node = new Node('a','character-card'); node.append(new Node('div','card-footer'));catalog.append(node);controller.decorate(node,{id});return node;}
    return {controller, host, catalog, card, status:host.querySelector('.catalog-view-status'), retry:() => host.querySelector('.text-button').events.click(), changes:() => changes};
  }
  return {create, calls, now(value) {now = Date.parse(value);}};
}

test('all cards and controllers share a read-only batch with in-flight and half-hour cache reuse', async () => {
  let resolve; const x = setup(() => new Promise(done => {resolve = done;})), a = x.create(), b = x.create();
  const cards = [a.card('a'), a.card('b'), a.card('unknown')];
  assert.equal(x.calls.length, 0);assert.equal(cards[0].querySelector('.card-views').textContent, '查看 —');
  const first = a.controller.load(); for (let i=0;i<20;i++) {a.controller.load();b.controller.load();} await tick();
  assert.deepEqual(x.calls, [['/views/characters']]);resolve(response());await first;await tick();
  assert.equal(cards[0].querySelector('.card-views').textContent, '查看 0 次');
  assert.equal(cards[1].querySelector('.card-views').textContent, '查看 12 次');
  assert.equal(cards[2].querySelector('.card-views').textContent, '查看 —');
  assert.equal(a.catalog.children[0], cards[0]);assert.equal(a.status.hidden, true);
  const later = x.create();await later.controller.load();await a.controller.load();
  assert.equal(later.controller.count('b'), 12);assert.equal(x.calls.length, 1);assert.equal(a.changes(), 1);
});

test('expiry triggers a new read only on demand and a refresh callback cannot recurse into more requests', async () => {
  let reads=0;
  const x=setup(async()=>({...response([{id:'a',views:++reads}]),nextRefreshAt:reads===1?'2026-10-02T10:30:00Z':'2026-10-02T11:00:00Z'}));
  const a=x.create(controller=>controller.load());await a.controller.load();x.now('2026-10-02T10:31:00Z');await tick();
  assert.equal(x.calls.length,1);await a.controller.load();await a.controller.load();
  assert.equal(x.calls.length,2);assert.equal(a.controller.count('a'),2);
});

test('both view directions keep unknowns last, preserve real zero and permit stable caller ties', async () => {
  const x=setup(async()=>response([{id:'a',views:0},{id:'b',views:12},{id:'c',views:12}])),a=x.create();await a.controller.load();
  const items=['unknown','b','a','c'].map(id=>({id}));
  const order=direction=>[...items].sort((left,right)=>a.controller.compare(left,right,direction)||left.id.localeCompare(right.id)).map(item=>item.id);
  assert.deepEqual(order('desc'),['b','c','a','unknown']);assert.deepEqual(order('asc'),['a','b','c','unknown']);
});

test('failure and invalid batches never invent zero or auto-retry, explicit retry recovers atomically', async () => {
  let reads=0;const x=setup(async()=>++reads===1?response([{id:'a',views:12},{id:'b',views:-1}]):response()),a=x.create(),card=a.card('a');
  await a.controller.load();assert.equal(a.controller.count('a'),undefined);assert.equal(card.querySelector('.card-views').textContent,'查看 —');
  assert.match(a.status.textContent,/暂时无法加载/);assert.equal(a.status.hidden,false);
  await a.controller.load();await tick();assert.equal(x.calls.length,1);a.retry();await tick();
  assert.equal(x.calls.length,2);assert.equal(a.controller.count('a'),0);assert.equal(a.status.hidden,true);
});

test('a failed refresh keeps old counts rather than discarding them and rejects unsafe integers or bad metadata', async () => {
  let reads=0;const x=setup(async()=>{if(++reads>1)throw new Error('503');return response();}),a=x.create();await a.controller.load();
  x.now('2026-10-02T10:31:00Z');await a.controller.load();assert.equal(a.controller.count('b'),12);assert.match(a.status.textContent,/保留上次统计/);
  for(const bad of [response([{id:'a',views:Number.MAX_SAFE_INTEGER+1}]),response([{id:'a',views:1.5}]),response([{id:'a',views:1},{id:'a',views:2}]),
    {...response(),asOf:'bad'}, {...response(),nextRefreshAt:'2026-10-02T09:59:00Z'}]) {
    const y=setup(async()=>bad),item=y.create();await item.controller.load();assert.equal(item.controller.count('a'),undefined);assert.equal(item.status.hidden,false);
  }
});

test('offline browsing makes no requests, even after repeated open or sort interactions', async () => {
  const x=setup(undefined,'file:'),a=x.create();for(let i=0;i<5;i++)await a.controller.load();
  assert.deepEqual(x.calls,[]);assert.match(a.status.textContent,/离线版/);assert.equal(a.status.children[1].hidden,true);
});
