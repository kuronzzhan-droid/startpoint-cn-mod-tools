const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const api = require('../wiki/community-client.js');
const tick = () => new Promise(setImmediate);
class Node {
  constructor(tag, className = '', text = '') {Object.assign(this, {tag, className, ownText: String(text), children: [], events: {}, attributes: {}, dataset: {}, disabled: false, hidden: false});}
  append(...nodes) {nodes.forEach(node => {node.parent = this; this.children.push(node);});}
  replaceChildren(...nodes) {this.children.forEach(node => {node.parent = null;}); this.children = []; this.ownText = ''; this.append(...nodes);}
  get textContent() {return this.ownText + this.children.map(node => node.textContent).join('');}
  set textContent(value) {this.replaceChildren(); this.ownText = String(value);}
  setAttribute(name, value) {this.attributes[name] = String(value);}
  getAttribute(name) {return this.attributes[name];}
  addEventListener(name, fn) {this.events[name] = fn;}
  get isConnected() {return Boolean(this.connected || this.parent?.isConnected);}
  querySelectorAll(selector) {
    const match = node => selector.startsWith('.') ? node.className.split(' ').includes(selector.slice(1)) : node.tag === selector;
    return this.children.flatMap(node => [...(match(node) ? [node] : []), ...node.querySelectorAll(selector)]);
  }
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
  async fire(name = 'click') {if (!this.disabled) return this.events[name]?.({preventDefault() {}});}
}
const el = (...args) => new Node(...args);
const characters = Array.from({length: 7}, (_, index) => ({id: `c${index + 1}`, name: `角色${index + 1}`, icon: `icon-${index + 1}.webp`,
  avatars: {before: `before-${index + 1}.webp`, ...(index === 5 ? {} : {after: `after-${index + 1}.webp`})}}));
const team = api.teamCopy({main: ['c1', 'c2', 'c3'], unison: ['c4', 'c5', 'c6'], weapon: ['w1']});
const entry = (patch = {}) => ({id: 't1', title: '测试队伍', section: 'abyss', category: '萌新启航', team, ...patch});
function setup(handler = async () => ({items: [entry()], nextCursor: null}), options = {}) {
  const calls = [], boards = [], events = new Map(); let subscriptions = 0, activeSubscriptions = 0;
  const window = {location: {protocol: options.protocol || 'https:', hash: '#character/c1'}, WFCommunity: {...api, client: {
    request: async (...args) => {calls.push(args); return handler(...args);},
  }}, addEventListener: (name, fn) => events.set(name, fn), removeEventListener: name => events.delete(name)};
  if (options.IntersectionObserver) window.IntersectionObserver = options.IntersectionObserver;
  const storage = new Map([['wf-wiki-catalog-avatar', options.form || 'before']]);
  const context = {window, location: window.location, URLSearchParams, Date, localStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value)}};
  for (const file of ['catalog-avatars.js', 'community.js', 'character-teams.js']) vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki', file), 'utf8'), context);
  const originalBoard = window.WFCommunity.board;
  window.WFCommunity.board = (...args) => {boards.push(args); return originalBoard(...args);};
  const originalSubscribe = window.WFCatalogAvatars.subscribe;
  window.WFCatalogAvatars.subscribe = fn => {subscriptions++; activeSubscriptions++; const stop = originalSubscribe(fn); let stopped = false;
    return () => {if (!stopped) {stopped = true; activeSubscriptions--; stop();}};
  };
  if (options.noClient) delete window.WFCommunity.client;
  const host = el('main'); host.connected = true;
  const ui = {el, safeUrl: value => typeof value === 'string' ? value : '', picture: (src, alt, cls) => {const image = el('img', cls); image.setAttribute('src', src); image.alt = alt; image.loading = 'lazy'; return image;}};
  const controller = window.WFCharacterTeams.mount(host, options.character || characters[0], ui, {characters: options.characters || characters});
  return {window, host, controller, calls, boards, events, subscriptions: () => subscriptions, activeSubscriptions: () => activeSubscriptions};
}
const cards = x => x.host.querySelectorAll('.character-team-card');
const button = (x, label) => x.host.querySelectorAll('button').find(node => node.textContent === label);
const status = x => x.host.querySelector('.character-teams-status');

test('below-fold recommendations load once near the viewport and never load after page leave', async () => {
  const observers = [];
  class Observer {
    constructor(callback, options) {this.callback = callback; this.options = options; observers.push(this);}
    observe(node) {this.target = node;}
    disconnect() {this.disconnected = true;}
  }
  const x = setup(undefined, {IntersectionObserver: Observer}); await tick();
  assert.equal(x.calls.length, 0); assert.equal(observers[0].target, x.controller.element);
  observers[0].callback([{isIntersecting:false}]); await tick(); assert.equal(x.calls.length, 0);
  observers[0].callback([{isIntersecting:true}]); await tick();
  assert.equal(x.calls.length, 1); assert.equal(observers[0].disconnected, true); assert.equal(cards(x).length, 1);
  const y = setup(undefined, {IntersectionObserver: Observer});
  y.controller.destroy(); assert.equal(observers[1].disconnected, true);
  observers[1].callback([{isIntersecting:true}]); await tick(); assert.equal(y.calls.length, 0);
});

test('related teams query the exact character by popularity and use six-portrait public detail links without equipment', async () => {
  const x = setup(async () => ({items: [entry({id: 'team / &1', title: '<img src=x onerror=bad> 火队'})]})); await tick();
  const params = new URL(x.calls[0][0], 'https://wiki.test').searchParams;
  assert.equal(params.get('character'), 'c1'); assert.equal(params.get('sort'), 'popular'); assert.equal(x.calls.length, 1);
  const card = cards(x)[0]; assert.equal(card.href, '#community/team%20%2F%20%261');
  assert.equal(card.querySelectorAll('a').length, 0); assert.equal(card.querySelectorAll('.community-slot').length, 6);
  assert.equal(card.querySelectorAll('.community-slot-weapon').length, 0); assert.equal(card.querySelectorAll('.community-slot-soul').length, 0);
  assert.match(card.textContent, /<img src=x onerror=bad> 火队.*深渊.*萌新启航.*队长 · 1号主位/);
  assert.equal(card.querySelector('h3').children.length, 0); assert.equal(card.querySelectorAll('.is-character-match').length, 1);
  assert.match(card.attributes['aria-label'], /角色1位于队长 · 1号主位/);
  assert.equal(x.boards[0][1].characters.length, 6); assert.equal(x.boards[0][1].equipment, undefined); assert.equal(x.boards[0][3].preview, true);
  assert.equal(x.controller.element.attributes['aria-busy'], 'false'); assert.match(status(x).textContent, /已显示 1 支公开配队/);
});

test('matching main and unison slots are labeled while private, hidden, pending and unrelated entries never render', async () => {
  const x = setup(async () => ({items: [
    entry({id: 'main', team: api.teamCopy({main: ['c2', 'c1', 'c3']})}),
    entry({id: 'unison', team: api.teamCopy({main: ['c2', 'c3', 'c4'], unison: ['', '', 'c1']})}),
    entry({id: 'private', visibility: 'private'}), entry({id: 'hidden', status: 'hidden'}), entry({id: 'pending', status: 'pending'}),
    entry({id: 'other', title: 'c1', notes: 'c1', team: api.teamCopy({main: ['c10', 'c2', 'c3'], weapon: ['c1']})}),
  ]})); await tick();
  assert.deepEqual(cards(x).map(node => node.href), ['#community/main', '#community/unison']);
  assert.match(cards(x)[0].querySelector('.character-team-position').textContent, /2号主位/);
  assert.match(cards(x)[1].querySelector('.character-team-position').textContent, /3号合击/);
  assert.ok(cards(x)[0].querySelectorAll('.community-slot-main')[1].className.includes('is-character-match'));
  assert.ok(cards(x)[1].querySelectorAll('.community-slot-unison')[2].className.includes('is-character-match'));
});

test('more pages preserve character and opaque cursor, deduplicate entries and retain server order', async () => {
  let reads = 0; const x = setup(async () => ++reads === 1 ? {items: [entry()], nextCursor: 'opaque /&cursor'}
    : {items: [entry(), entry({id: 'second'}), entry({id: 'third'})], nextCursor: null}); await tick();
  const first = cards(x)[0]; await button(x, '加载更多配队').fire();
  const params = new URL(x.calls[1][0], 'https://wiki.test').searchParams;
  assert.equal(params.get('character'), 'c1'); assert.equal(params.get('sort'), 'popular'); assert.equal(params.get('cursor'), 'opaque /&cursor');
  assert.deepEqual(cards(x).map(node => node.href), ['#community/t1', '#community/second', '#community/third']);
  assert.equal(cards(x)[0], first); assert.equal(button(x, '加载更多配队').hidden, true); assert.match(status(x).textContent, /已显示 3 支/);
});

test('pagination failure preserves cards and retry uses the same cursor with duplicate clicks blocked', async () => {
  let read = 0, fail; const x = setup(() => ++read === 1 ? Promise.resolve({items: [entry()], nextCursor: 'next'})
    : read === 2 ? new Promise((_resolve, reject) => {fail = reject;}) : Promise.resolve({items: [entry({id: 'next'})]})); await tick();
  const first = cards(x)[0], more = button(x, '加载更多配队'), pending = more.fire(); await more.fire();
  assert.equal(x.calls.length, 2); assert.equal(more.disabled, true); assert.equal(x.controller.element.attributes['aria-busy'], 'true');
  fail(new Error('网络失败')); await pending; assert.equal(cards(x)[0], first); assert.match(status(x).textContent, /网络失败/);
  const retry = button(x, '重试加载'); assert.equal(retry.hidden, false); await retry.fire();
  assert.equal(x.calls[1][0], x.calls[2][0]); assert.equal(cards(x).length, 2); assert.equal(retry.hidden, true);
});

test('empty, offline and unavailable service states are explicit and offline never makes a request', async () => {
  const empty = setup(async () => ({items: []})); await tick(); assert.match(status(empty).textContent, /暂无包含角色1的公开配队/);
  assert.equal(button(empty, '加载更多配队').hidden, true);
  const offline = setup(undefined, {protocol: 'file:'}), unavailable = setup(undefined, {noClient: true}); await tick();
  assert.equal(offline.calls.length, 0); assert.match(status(offline).textContent, /离线版无法读取/);
  assert.equal(unavailable.calls.length, 0); assert.match(status(unavailable).textContent, /配队服务尚未准备好/);
});

test('malformed pages and a repeated cursor are retryable errors, not a false empty result', async () => {
  const bad = setup(async () => ({items: null})); await tick(); assert.match(status(bad).textContent, /配队资料暂时不可用/); assert.equal(button(bad, '重试加载').hidden, false);
  let count = 0; const repeat = setup(async () => ({items: [entry({id: String(++count)})], nextCursor: 'same'})); await tick();
  await button(repeat, '加载更多配队').fire(); assert.equal(cards(repeat).length, 1); assert.match(status(repeat).textContent, /配队资料暂时不可用/);
});

test('leaving or replacing the summary discards late results and releases the one avatar subscription', async () => {
  for (const leave of ['event', 'route', 'detach']) {
    let resolve; const x = setup(() => new Promise(done => {resolve = done;})); const before = status(x).textContent;
    if (leave === 'event') x.events.get('wf-page-leave')();
    else if (leave === 'route') x.window.location.hash = '#character/c2';
    else x.host.replaceChildren(el('p', '', 'new character'));
    resolve({items: [entry()]}); await tick(); assert.equal(x.controller.element.querySelectorAll('.character-team-card').length, 0);
    assert.equal(x.controller.element.querySelector('.character-teams-status').textContent, before);
    assert.equal(x.activeSubscriptions(), 0); assert.equal(x.events.size, 0); x.controller.destroy(); assert.equal(x.activeSubscriptions(), 0);
  }
});

test('portraits follow the shared awakened preference across all cards and retain selected-role highlights without refetching', async () => {
  const x = setup(async () => ({items: [entry(), entry({id: 'two'})]}), {form: 'after'}); await tick();
  assert.equal(x.subscriptions(), 1); assert.equal(x.activeSubscriptions(), 1);
  assert.equal(cards(x)[0].querySelector('img').getAttribute('src'), 'after-1.webp');
  assert.equal(cards(x)[0].querySelectorAll('img').at(-1).getAttribute('src'), 'icon-6.webp');
  x.window.WFCatalogAvatars.setForm('before');
  assert.ok(cards(x).every(node => node.querySelector('img').getAttribute('src') === 'before-1.webp'));
  assert.ok(cards(x).every(node => node.querySelectorAll('.is-character-match').length === 1)); assert.equal(x.calls.length, 1);
  x.controller.destroy(); const image = cards(x)[0].querySelector('img'); x.window.WFCatalogAvatars.setForm('after');
  assert.equal(cards(x)[0].querySelector('img'), image); assert.equal(x.activeSubscriptions(), 0);
});

test('missing catalog briefs use placeholders while the viewed character still gets its own portrait', async () => {
  const x = setup(undefined, {characters: []}); await tick();
  assert.equal(cards(x)[0].querySelectorAll('.community-slot').length, 6); assert.equal(cards(x)[0].querySelectorAll('img').length, 1);
  assert.match(cards(x)[0].textContent, /\?/); assert.equal(x.boards[0][1].characters.length, 1);
});
