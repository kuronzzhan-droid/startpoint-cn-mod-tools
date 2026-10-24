const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const tick = () => new Promise(setImmediate);
class Node {
  constructor(tag, className = '', text = '') {
    Object.assign(this, {tag, className, ownText: String(text), children: [], events: {}, attributes: {}, dataset: {}, disabled: false, hidden: false});
    this.classList = {toggle: (name, on) => {const names = new Set(this.className.split(' ')); on ? names.add(name) : names.delete(name); this.className = [...names].join(' ');}};
  }
  append(...nodes) {nodes.forEach(node => {node.parent = this; this.children.push(node);});}
  prepend(...nodes) {nodes.forEach(node => {node.parent = this;}); this.children.unshift(...nodes);}
  replaceChildren(...nodes) {this.children.forEach(node => {node.parent = null;}); this.children = []; this.ownText = ''; this.append(...nodes);}
  get textContent() {return this.ownText + this.children.map(node => node.textContent).join('');}
  set textContent(value) {this.replaceChildren(); this.ownText = String(value);}
  setAttribute(key, value) {this.attributes[key] = String(value);}
  addEventListener(event, action) {this.events[event] = action;}
  get isConnected() {return Boolean(this.connected || this.parent?.isConnected);}
  all(match) {return this.children.flatMap(node => [...(match(node) ? [node] : []), ...node.all(match)]);}
  querySelector(selector) {return this.all(node => selector.startsWith('.') ? node.className.split(' ').includes(selector.slice(1)) : node.tag === selector)[0] || null;}
  async fire(event = 'click', args = {}) {if (!this.disabled) return this.events[event]?.({target: this, preventDefault() {}, ...args});}
  focus() {this.focused = true;}
}
const el = (...args) => new Node(...args);
const cls = (root, name) => root.all(node => node.className.split(' ').includes(name))[0];
const all = (root, name) => root.all(node => node.className.split(' ').includes(name));
const button = (root, label) => root.all(node => node.tag === 'button' && node.textContent === label)[0];
const visibleText = root => root.hidden ? '' : root.ownText
  + root.children.filter(node => root.tag !== 'details' || root.open || node.tag === 'summary').map(visibleText).join('');
const detailSwitch = root => root.all(node => node.attributes.role === 'switch' && node.attributes['aria-label'] === '显示全部评分详情')[0];
const rowKeys = ['tier0', 'between0', 'tier1', 'between1', 'tier2', 'between2', 'tier3', 'between3', 'tier4'];
const rows = () => Object.fromEntries(rowKeys.map(key => [key, []]));
const me = {rows: rows(), submittedToday: false, nextVoteAt: Date.parse('2026-10-01T16:00:00Z'), updatedAt: null, rankedCharacters: 0, challengeAction: 'submit_tier_ranking'};
const record = (id, patch = {}) => ({id, average: 4.5, voters: 2, rankScore: 24 / 7, row: 'provisional', ...patch});
const data = {characters: [{id: 'c1', name: '甲', element: '火'}, {id: 'c2', name: '乙', element: '水'}, {id: 'c3', name: '丙', element: '火'}]};
const aggregate = (placement = [record('c1'), record('c2'), record('c3')], rating = []) => ({rankings: {placement, rating},
  formula: {method: 'bayesian', priorVoters: 5, placementPrior: 3, ratingPrior: 2.5, tierMethod: 'raw-average', minimumTierVoters: 3}});
function setup(handler = async pathname => pathname.endsWith('/me') ? me : aggregate(), options = {}) {
  const calls = [], dialogs = [], challenges = [], transitions = [], subscriptions = [], events = new Map(); let configCalls = 0, portraitsCreated = 0, unsubscribed = 0;
  let statsSnapshot = {status: options.protocol === 'file:' ? 'offline' : 'loading', data: null};
  const statsListeners = new Set(), siteStats = {subscribe(callback) {
    subscriptions.push(callback); statsListeners.add(callback); callback(statsSnapshot);
    return () => {if (statsListeners.delete(callback)) unsubscribed++;};
  }};
  const C = {client: {request: async (...args) => {calls.push(args); return handler(...args);}, config: async () => {configCalls++; return options.config ? options.config() : {enabled: true};}}, message: error => error.message};
  C.dialog = title => {const modal = {title, element: el('dialog'), cleanup(callback) {this.clean = callback;}, close() {this.clean?.(); this.element.connected = false;}}; modal.element.connected = true; dialogs.push(modal); return modal;};
  C.challenge = (_host, _config, action, _ui, onChange) => {
    const challenge = {action, resets: 0, destroyed: false, token: '', ready(token = 'one-use') {this.token = token; onChange(true);},
      take() {const token = this.token; this.token = ''; onChange(false); return token;}, reset() {this.resets++; onChange(false);}, destroy() {this.destroyed = true;}};
    challenges.push(challenge); return challenge;
  };
  const window = {WFCommunity: C, WFSiteStats: options.stats === false ? undefined : siteStats, location: {protocol: options.protocol || 'https:'},
    addEventListener: (name, callback) => events.set(name, callback), removeEventListener: name => events.delete(name), WFCatalogAvatars: {
    create({host}) {portraitsCreated++; host.append(el('div', 'avatar-control')); return {picture: character => el('span', 'portrait', character.name)};},
  }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/rating-score.js'), 'utf8'), {window});
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/tier-list-community.js'), 'utf8'), {window, Date});
  const host = el('main'); host.connected = options.connected !== false; let localRows = rows();
  const state = {getRows: () => JSON.parse(JSON.stringify(localRows)), assignedIds: () => new Set(Object.values(localRows).flat()), canUndo: () => false, persistenceError: () => options.persistenceError || ''};
  // Individual voting tests explicitly start on the personal view; the entry-point test omits it.
  const initialView = options.defaultView ? {} : {initialView: 'mine'};
  const ui = {el, nativeIcon: (_group, value) => el('img', 'element-icon', value)};
  let controller;
  if (options.renderPage) {
    window.WFCharacterOrder = {compare: (a, b) => a.id.localeCompare(b.id)};
    window.WFTierListState = {create: () => state}; window.WFCharacterFrame = {apply() {}};
    window.WFCharacterFilters = {create() {
      const element = el('section', 'character-filters'), body = el('div', 'character-filter-body');
      const searchRow = el('div', 'character-filter-search-row'); searchRow.append(el('button', 'text-button'));
      body.append(searchRow, el('div', 'character-filter-fields')); element.append(body);
      return {element, matches: () => true};
    }};
    const create = window.WFTierListCommunity.create;
    window.WFTierListCommunity.create = args => (controller = create(args));
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/tier-list.js'), 'utf8'), {window});
    window.renderWikiTierList(host, data, ui, options.defaultView ? undefined : initialView);
  } else controller = window.WFTierListCommunity.create({host, data, state, ...initialView, ui, onViewChange: value => transitions.push(value)});
  return {host, controller, calls, dialogs, challenges, transitions, subscriptions, events, statsListeners, unsubscribed: () => unsubscribed,
    emitStats(snapshot) {statsSnapshot = snapshot; for (const callback of statsListeners) callback(snapshot);},
    setRows: value => {localRows = value;}, portraitsCreated: () => portraitsCreated, configCalls: () => configCalls};
}

const siteStats = (ratingVoters = 17, tierVoters = 11, totalVoters = Math.max(ratingVoters, tierVoters)) => ({totalVoters, ratingVoters, tierVoters, onlineVisitors: 4, asOf: '2026-09-30T12:00:00.000Z', presenceWindowSeconds: 300});

test('default entry shows everyone ranking and switching to mine preserves the unsubmitted local draft', async () => {
  const x = setup(undefined, {defaultView: true, renderPage: true});
  assert.equal(cls(x.host, 'tier-header'), undefined); assert.doesNotMatch(visibleText(x.host), /从夯到拉|自己排一排/);
  assert.equal(x.controller.mineHost.hidden, true); assert.equal(cls(x.host, 'tier-public-view').hidden, false);
  assert.equal(button(x.host, '大家排行').attributes['aria-selected'], 'true');
  assert.equal(cls(x.host, 'tier-submit-bar').hidden, true);
  await tick(); assert.equal(x.calls.length, 1); assert.equal(x.calls[0][0], '/tier-rankings');
  assert.equal(x.challenges.length, 0); assert.equal(x.configCalls(), 0);
  const draft = rows(); draft.tier0 = ['c1']; x.setRows(draft);
  await button(x.host, '我的排行').fire();
  assert.equal(x.controller.mineHost.hidden, false); assert.equal(cls(x.host, 'tier-submit-bar').hidden, false);
  assert.match(cls(x.host, 'tier-submit-status').textContent, /本地已排 1 位角色/);
  assert.equal(x.calls.length, 1); assert.equal(x.challenges.length, 0);
  const personal = setup(undefined, {renderPage: true});
  assert.equal(personal.controller.mineHost.hidden, false); assert.deepEqual(personal.calls, []);
  assert.equal(button(personal.host, '我的排行').attributes['aria-selected'], 'true');
});

test('compact public controls keep help collapsed and local controls never request new data', async () => {
  const x = setup(undefined, {defaultView: true, renderPage: true}); await tick();
  const help = cls(x.host, 'tier-public-help'), nav = cls(x.host, 'tier-community-nav');
  assert.equal(help.tag, 'details'); assert.ok(!help.open);
  assert.equal(cls(x.host, 'tier-community-tabs').parent, nav);
  assert.equal(cls(x.host, 'tier-ranking-sources').parent, cls(x.host, 'tier-public-toolbar'));
  assert.equal(cls(x.host, 'tier-public-toolbar').children[1].children[0].className, 'avatar-control');
  assert.equal(detailSwitch(x.host).parent, nav);
  assert.equal(detailSwitch(x.host).textContent, '详情');
  assert.doesNotMatch(visibleText(x.host), /中立分|每日汇总|点击头像查看均分|未评分角色不入|刷新/);
  assert.equal(cls(x.host, 'tier-public-status').hidden, true);
  const publicPanel = cls(nav, 'tier-help-body'), helpSlot = nav.children.indexOf(help);
  assert.equal(help.children.length, 1); assert.equal(help.children[0].tag, 'summary');
  assert.equal(help.children[0].attributes['aria-controls'], publicPanel.id);
  help.open = true; await help.fire('toggle');
  assert.equal(nav.children.indexOf(help), helpSlot); assert.equal(publicPanel.hidden, false);
  assert.match(visibleText(x.host), /中立分.*每日汇总|每日汇总.*中立分/);
  assert.match(visibleText(x.host), /刷新/);
  assert.equal(button(x.host, '刷新').attributes['aria-label'], '刷新大家排行');
  help.open = false; await help.fire('toggle'); assert.equal(publicPanel.hidden, true);
  await detailSwitch(x.host).fire();
  await x.host.all(node => node.attributes['aria-label'] === '火属性排行')[0].fire();
  await button(x.host, '角色评分').fire();
  assert.match(visibleText(x.host), /暂无已汇总投票/);
  assert.doesNotMatch(visibleText(x.host), /未评分角色不入此榜/);
  assert.equal(x.calls.length, 1); assert.equal(x.challenges.length, 0);
  await button(x.host, '我的排行').fire();
  assert.equal(detailSwitch(x.host).hidden, true);
  assert.equal(help.hidden, true);
  const personalHelp = cls(x.host, 'tier-personal-help'); assert.ok(!personalHelp.open);
  const personalPanel = cls(cls(x.host, 'tier-toolbar'), 'tier-help-body');
  assert.equal(personalHelp.children.length, 1); assert.equal(personalPanel.hidden, true);
  assert.equal(cls(x.host, 'tier-status').hidden, true);
  assert.doesNotMatch(visibleText(x.host), /每天可提交一次|手机也可先点头像/);
  personalHelp.open = true; await personalHelp.fire('toggle');
  assert.equal(personalPanel.hidden, false); assert.match(visibleText(x.host), /手机也可先点头像/);
  personalHelp.open = false; await personalHelp.fire('toggle'); assert.equal(personalPanel.hidden, true);
  assert.ok(button(x.host, '提交我的排行')); assert.ok(button(x.host, '移回待排行'));
  assert.equal(x.calls.length, 1);
});

test('an expanded public help panel follows its view without moving the disclosure or leaking into mine', async () => {
  const value = {...aggregate(), asOf:'2099-01-01T04:00:00Z', nextRefreshAt:'2099-01-01T16:00:00Z', stale:false};
  const x = setup(async () => value, {defaultView:true}); await tick();
  const nav = cls(x.host, 'tier-community-nav'), help = cls(nav, 'tier-public-help'), panel = cls(nav, 'tier-help-body');
  const originalChildren = [...nav.children];
  help.open = true; await help.fire('toggle'); assert.equal(panel.hidden, false);
  x.controller.setView('mine'); assert.equal(panel.hidden, true);
  await help.fire('toggle'); assert.equal(panel.hidden, true);
  x.controller.setView('community'); assert.equal(panel.hidden, false);
  assert.deepEqual(nav.children, originalChildren); assert.equal(x.calls.length, 1);
});

test('collapsed help never hides loading, errors or a local save failure', async () => {
  let reject;
  const x = setup(() => new Promise((_resolve, fail) => {reject = fail;}), {defaultView: true});
  assert.match(visibleText(x.host), /正在载入大家排行/);
  assert.equal(cls(x.host, 'tier-public-status').hidden, false);
  reject(new Error('连接超时')); await tick();
  assert.match(visibleText(x.host), /连接超时.*重试/);
  assert.equal(cls(x.host, 'tier-public-status').hidden, false);
  assert.ok(!cls(x.host, 'tier-public-help').open);
  const local = setup(undefined, {renderPage:true, persistenceError:'保存失败，请检查浏览器存储空间'});
  assert.match(visibleText(local.host), /保存失败，请检查浏览器存储空间/);
  assert.equal(cls(local.host, 'tier-status').hidden, false);
});

test('public participation uses distinct site statistics and keeps the same scope while filtering characters', async () => {
  const x = setup(); x.controller.setView('community'); await tick(); const summary = cls(x.host, 'tier-public-participation');
  assert.match(summary.textContent, /参与—人.*评分—人.*手排—人.*正在统计/);
  assert.equal(x.subscriptions.length, 1); assert.equal(x.calls.length, 1);
  x.emitStats({status: 'ready', data: siteStats()});
  assert.match(summary.textContent, /参与17人.*评分17人.*手排11人.*定时更新/);
  assert.equal(summary.parent, cls(x.host, 'tier-public-heading'));
  assert.equal(all(summary, 'tier-participation-count').length, 3);
  assert.match(all(summary, 'tier-participation-count')[0].title, /合并去重的全站人数/);
  assert.doesNotMatch(summary.textContent, /活跃|在线/);
  assert.equal(cls(summary, 'tier-participation-status').hidden, true);
  assert.match(summary.title, /全站参与人数.*定时更新/);
  await x.host.all(node => node.attributes['aria-label'] === '火属性排行')[0].fire();
  assert.match(summary.textContent, /参与17人.*评分17人.*手排11人/); assert.equal(x.calls.length, 1);
  assert.equal(all(x.host, 'tier-public-card').length, 2);
  x.emitStats({status: 'ready', data: {...siteStats(18, 12), onlineVisitors: 6}}); assert.match(summary.textContent, /评分18人.*手排12人/);
  assert.equal(x.calls.length, 1); assert.equal(x.subscriptions.length, 1);
});


test('participation freshness stays visible when stale, without a duplicate online sample', () => {
  const x = setup(), summary = cls(x.host, 'tier-public-participation');
  x.emitStats({status: 'ready', data: {...siteStats(), participationAsOf:'2026-09-30T11:50:00.000Z', participationStale:true}});
  assert.match(summary.textContent, /参与人数更新中/); assert.equal(cls(summary, 'tier-participation-status').hidden, false);
  assert.match(cls(summary, 'tier-participation-status').title, /参与人数统计于/);
  x.emitStats({status: 'ready', data: {...siteStats(), onlineVisitors:undefined, presenceWindowSeconds:120}});
  assert.doesNotMatch(summary.textContent, /活跃|在线|更新中/);
  assert.equal(cls(summary, 'tier-participation-status').hidden, true);
  assert.equal(cls(summary, 'tier-participation-status').title, '');
});

test('total participation uses the server union count instead of adding overlapping rating and tier voters', () => {
  const x = setup(), summary = cls(x.host, 'tier-public-participation');
  const missingTotal = siteStats(); delete missingTotal.totalVoters;
  x.emitStats({status: 'ready', data: missingTotal}); assert.match(summary.textContent, /参与—人.*统计暂不可用/);
  x.emitStats({status: 'ready', data: siteStats(17, 11, 22)});
  assert.match(summary.textContent, /参与22人.*评分17人.*手排11人/); assert.doesNotMatch(summary.textContent, /参与28人/);
  x.emitStats({status: 'error', data: null}); assert.match(summary.textContent, /参与22人.*上次统计/);
  x.emitStats({status: 'ready', data: siteStats(0, 0, 0)}); assert.match(summary.textContent, /参与0人.*定时更新/);
});

test('unknown or failed participation counts never become zero and last good totals remain marked stale', async () => {
  const x = setup(), summary = cls(x.host, 'tier-public-participation');
  x.emitStats({status: 'error', data: null}); assert.match(summary.textContent, /评分—人.*手排—人.*统计暂不可用/);
  x.emitStats({status: 'ready', data: siteStats(0, 0)}); assert.match(summary.textContent, /评分0人.*手排0人.*定时更新/);
  x.emitStats({status: 'ready', data: siteStats(5, 9)});
  x.emitStats({status: 'error', data: null}); assert.match(summary.textContent, /评分5人.*手排9人.*更新失败.*上次统计/);
  x.emitStats({status: 'loading', data: siteStats(5, 9)}); assert.match(summary.textContent, /评分5人.*手排9人.*更新中/);
  x.emitStats({status: 'offline', data: null}); assert.match(summary.textContent, /评分5人.*手排9人.*离线.*上次统计/);
  x.emitStats({status: 'ready', data: siteStats(-1, '8')}); assert.match(summary.textContent, /评分5人.*手排9人.*更新失败.*上次统计/);
});

test('offline or unavailable statistics have a short status without inventing participation', () => {
  const offline = setup(undefined, {protocol: 'file:'}), missing = setup(undefined, {stats: false});
  assert.match(cls(offline.host, 'tier-public-participation').textContent, /评分—人.*手排—人.*离线，暂无统计/);
  assert.match(cls(missing.host, 'tier-public-participation').textContent, /评分—人.*手排—人.*统计暂不可用/);
  assert.deepEqual(offline.calls, []); assert.deepEqual(missing.calls, []);
});

test('page leave unsubscribes immediately and late shared-stat callbacks cannot update a destroyed board', () => {
  const x = setup(), summary = cls(x.host, 'tier-public-participation'); x.emitStats({status: 'ready', data: siteStats()});
  const before = summary.textContent; x.events.get('wf-page-leave')();
  assert.equal(x.unsubscribed(), 1); assert.equal(x.statsListeners.size, 0); assert.equal(x.events.size, 0);
  x.subscriptions[0]({status: 'ready', data: siteStats(99, 99)}); assert.equal(summary.textContent, before);
  x.controller.destroy(); assert.equal(x.unsubscribed(), 1);
});

test('a not-yet-inserted board can receive initial statistics and later detachment releases its subscription', () => {
  const x = setup(undefined, {connected: false}), summary = cls(x.host, 'tier-public-participation');
  assert.equal(x.unsubscribed(), 0); x.host.connected = true; x.emitStats({status: 'ready', data: siteStats()});
  assert.match(summary.textContent, /评分17人.*手排11人/); x.host.connected = false;
  x.emitStats({status: 'ready', data: siteStats(20, 20)}); assert.equal(x.unsubscribed(), 1); assert.match(summary.textContent, /评分17人.*手排11人/);
});

test('my view and unsent local edits do not fetch rankings, request verification or submit votes', async () => {
  const x = setup(); assert.deepEqual(x.calls, []); assert.equal(x.portraitsCreated(), 0); assert.equal(x.challenges.length, 0);
  const local = rows(); local.tier0 = ['c1']; x.setRows(local); x.controller.refreshState();
  assert.match(x.host.textContent, /本地已排 1 位角色/); assert.deepEqual(x.calls, []); assert.equal(x.configCalls(), 0);
  assert.equal(x.controller.mineHost.hidden, false); assert.equal(cls(x.host, 'tier-public-view').hidden, true);
});

test('public view defaults to avatar buttons with rating text hidden and no score in hover or accessible names', async () => {
  const value = aggregate([record('c1'), record('c2')]);
  const x = setup(async () => value); x.controller.setView('community'); await tick();
  assert.equal(x.calls.length, 1); assert.equal(x.calls[0][0], '/tier-rankings'); assert.equal(x.portraitsCreated(), 1);
  const cards = all(x.host, 'tier-public-card'); assert.equal(cards.length, 2);
  assert.equal(cards[0].tag, 'button'); assert.equal(cards[0].type, 'button'); assert.equal(cards[0].href, undefined);
  assert.equal(cards[0].attributes['data-character-id'], 'c1'); assert.equal(cards[0].title, '甲');
  assert.equal(cards[0].attributes['aria-label'], '查看甲的排行详情');
  for (const card of cards) {
    assert.equal(cls(card, 'tier-public-card-text').hidden, true);
    assert.doesNotMatch(visibleText(card), /4\.50|0\.00|手排|评分|暂无/);
    assert.doesNotMatch(card.title, /4\.50|0\.00|手排|评分|暂无/);
  }
  assert.equal(detailSwitch(x.host).attributes['aria-checked'], 'false');
  assert.match(cards[0].textContent, /均分 4\.50.*2 人 · 暂定排序 3\.43/);
  assert.equal(button(x.host, '手动排行').attributes['aria-pressed'], 'true');
  assert.equal(button(x.host, '角色评分').attributes['aria-pressed'], 'false');
  assert.doesNotMatch(x.host.textContent, /70%|30%|综合得分/);
  assert.equal(x.controller.mineHost.hidden, true); assert.equal(button(x.host, '大家排行').attributes['aria-selected'], 'true');
});

test('element tabs filter cached rows without requests and preserve server tie order', async () => {
  const x = setup(async () => aggregate([record('c3'), record('c1'), record('c2')])); x.controller.setView('community'); await tick();
  const fire = x.host.all(node => node.attributes['aria-label'] === '火属性排行')[0]; await fire.fire();
  assert.deepEqual(all(x.host, 'tier-public-card').map(card => card.attributes['data-character-id']), ['c3', 'c1']); assert.equal(x.calls.length, 1);
  assert.match(cls(x.host, 'tier-public-summary').textContent, /火属性榜 · 2/);
  await x.host.all(node => node.attributes['aria-label'] === '暗属性排行')[0].fire();
  assert.equal(all(x.host, 'tier-public-card').length, 0); assert.match(cls(x.host, 'tier-public-summary').textContent, /暗属性还没有已汇总/);
  await button(x.host, '总榜').fire(); assert.equal(all(x.host, 'tier-public-card').length, 3); assert.equal(x.calls.length, 1);
});

test('nine real-average tiers precede a separate provisional area with visible filtered counts', async () => {
  const placement = [record('c3', {average: 5, voters: 3, rankScore: 3.75, row: 'tier0'}),
    record('c2', {voters: 3, rankScore: 3.5625, row: 'between0'}),
    record('c1', {average: 5, voters: 1, rankScore: 10 / 3})];
  const x = setup(async () => aggregate(placement)); x.controller.setView('community'); await tick();
  const results = cls(x.host, 'tier-public-results'), board = cls(results, 'tier-public-board'), provisional = cls(results, 'tier-public-provisional');
  assert.equal(results.children[0], board); assert.equal(results.children[1], provisional);
  assert.deepEqual(board.children.map(row => row.attributes['data-row']), rowKeys);
  assert.deepEqual(all(board.children[0], 'tier-public-card').map(card => card.attributes['data-character-id']), ['c3']);
  assert.deepEqual(all(board.children[1], 'tier-public-card').map(card => card.attributes['data-character-id']), ['c2']);
  assert.deepEqual(all(provisional, 'tier-public-card').map(card => card.attributes['data-character-id']), ['c1']);
  assert.match(provisional.textContent, /暂定1 位角色/);
  assert.match(cls(provisional, 'tier-provisional-heading').title, /不足 3 票，尚未定级/);
  assert.match(cls(x.host, 'tier-public-formula').textContent, /满 3 票按真实均分分档.*不足则暂定.*档内排序参考 5 份中立分/);
  assert.match(cls(x.host, 'tier-public-summary').textContent, /已定级 2 · 暂定 1/);
  await detailSwitch(x.host).fire();
  assert.ok(all(x.host, 'tier-public-card-text').every(node => !node.hidden));
  assert.match(visibleText(provisional), /均分 5\.00.*1 人 · 暂定排序 3\.33/);
  await x.host.all(node => node.attributes['aria-label'] === '火属性排行')[0].fire();
  assert.match(cls(x.host, 'tier-public-summary').textContent, /已定级 1 · 暂定 1/);
  assert.ok(all(x.host, 'tier-public-card-text').every(node => !node.hidden));
  await x.host.all(node => node.attributes['aria-label'] === '水属性排行')[0].fire();
  assert.match(cls(x.host, 'tier-provisional-count').textContent, /0 位角色/);
  assert.equal(all(cls(x.host, 'tier-public-provisional'), 'tier-public-card').length, 0);
  assert.match(cls(x.host, 'tier-public-provisional').textContent, /暂无暂定角色/); assert.equal(x.calls.length, 1);
});

test('a third real vote moves a character from provisional to its real-average tier on refresh', async () => {
  let reads = 0;
  const x = setup(async () => aggregate([++reads === 1 ? record('c1', {average: 5, voters: 2, rankScore: 25 / 7})
    : record('c1', {average: 5, voters: 3, rankScore: 3.75, row: 'tier0'})]));
  x.controller.setView('community'); await tick();
  assert.equal(all(cls(x.host, 'tier-public-provisional'), 'tier-public-card').length, 1);
  assert.equal(all(cls(x.host, 'tier-public-board'), 'tier-public-card').length, 0);
  await button(x.host, '刷新').fire();
  assert.equal(all(cls(x.host, 'tier-public-provisional'), 'tier-public-card').length, 0);
  const top = cls(x.host, 'tier-public-board').children[0];
  assert.equal(all(top, 'tier-public-card')[0].attributes['data-character-id'], 'c1');
  await all(top, 'tier-public-card')[0].fire();
  assert.match(x.dialogs[0].element.textContent, /真实均分5\.00.*夯.*3 位玩家.*已满 3 票/);
});

test('rounded displayed averages never replace authoritative server tiers at a rounding boundary', async () => {
  // Raw means just above and below 4.75 both display 4.75 but legitimately occupy different tiers.
  const x = setup(async () => aggregate([record('c1', {average: 4.75, voters: 200, rankScore: 4.7097, row: 'tier0'}),
    record('c2', {average: 4.75, voters: 200, rankScore: 4.7024, row: 'between0'})]));
  x.controller.setView('community'); await tick();
  const board = cls(x.host, 'tier-public-board');
  assert.equal(all(board.children[0], 'tier-public-card')[0].attributes['data-character-id'], 'c1');
  assert.equal(all(board.children[1], 'tier-public-card')[0].attributes['data-character-id'], 'c2');
  assert.equal(all(x.host, 'tier-public-card').length, 2);
});

test('invalid provisional thresholds, zero voters and the old tier policy are rejected visibly', async () => {
  const invalid = [aggregate([record('c1', {row: 'tier0'})]), aggregate([record('c1', {voters: 3})]),
    aggregate([record('c1', {voters: 0})]), aggregate([record('c1', {row: 'unknown'})])];
  const old = aggregate(); delete old.formula.tierMethod; invalid.push(old);
  for (const value of invalid) {
    const x = setup(async () => value); x.controller.setView('community'); await tick();
    assert.equal(all(x.host, 'tier-public-card').length, 0);
    assert.match(cls(x.host, 'tier-public-status').textContent, /资料异常.*重试/);
  }
});

test('source switches preserve the attribute and exact server scores without blending or fetching again', async () => {
  const placement = [record('c3', {average: 5, voters: 1, rankScore: 10 / 3, row: 'provisional'}), record('c2')];
  const rating = [record('c1', {average: 4.5, voters: 10, rankScore: 23 / 6, row: 'between0'}),
    record('c3', {average: 0, voters: 1, rankScore: 25 / 12, row: 'provisional'})];
  const x = setup(async () => aggregate(placement, rating)); x.controller.setView('community'); await tick();
  const fire = x.host.all(node => node.attributes['aria-label'] === '火属性排行')[0]; await fire.fire();
  await detailSwitch(x.host).fire();
  const before = all(x.host, 'tier-public-card')[0].textContent;
  await button(x.host, '角色评分').fire();
  assert.equal(fire.attributes['aria-pressed'], 'true'); assert.equal(button(x.host, '角色评分').attributes['aria-pressed'], 'true');
  assert.deepEqual(all(x.host, 'tier-public-card').map(card => card.attributes['data-character-id']), ['c1', 'c3']);
  assert.match(cls(x.host, 'tier-public-summary').textContent, /角色评分 · 火属性榜/);
  assert.match(all(x.host, 'tier-public-card')[0].textContent, /均分 4\.50.*10 人 · 档内排序 3\.83/);
  assert.match(all(x.host, 'tier-public-card')[1].textContent, /均分 0\.00.*1 人 · 暂定排序 2\.08/);
  assert.match(cls(x.host, 'tier-public-summary').textContent, /已定级 1 · 暂定 1/);
  assert.match(cls(x.host, 'tier-provisional-count').textContent, /1 位角色/);
  await button(x.host, '手动排行').fire();
  assert.match(cls(x.host, 'tier-public-summary').textContent, /已定级 0 · 暂定 1/);
  assert.equal(all(x.host, 'tier-public-card')[0].textContent, before); assert.equal(x.calls.length, 1);
});

test('switching source during an initial read uses the current source when the response arrives', async () => {
  let resolve; const x = setup(() => new Promise(done => {resolve = done;}));
  x.controller.setView('community'); await button(x.host, '角色评分').fire();
  resolve(aggregate([record('c1')], [record('c2', {average: 5, voters: 1, rankScore: 35 / 12, row: 'provisional'})])); await tick();
  assert.deepEqual(all(x.host, 'tier-public-card').map(card => card.attributes['data-character-id']), ['c2']);
  assert.match(cls(x.host, 'tier-public-summary').textContent, /角色评分/);
});

test('clicking an avatar opens its authoritative score breakdown and separate character detail link', async () => {
  const x = setup(async () => aggregate([record('c1', {average: 4.5, voters: 7, rankScore: 3.875, row: 'between0'})]));
  x.controller.setView('community'); await tick(); await all(x.host, 'tier-public-card')[0].fire();
  assert.equal(x.dialogs.length, 1); const dialog = x.dialogs[0].element;
  assert.match(x.dialogs[0].title, /甲.*手动排行/); assert.match(cls(dialog, 'tier-score-headline').textContent, /真实均分4\.50.*夯 ↔ 顶级/);
  const stats = all(dialog, 'tier-score-stat');
  assert.equal(stats.length, 1); assert.match(stats[0].textContent, /档内排序分3\.887\s*位玩家/);
  assert.match(dialog.textContent, /按真实均分分档.*仅决定档内顺序/);
  assert.match(dialog.textContent, /5 份中立分.*3 分.*不增加玩家票数.*不混合另一类投票/);
  const links = dialog.all(node => node.tag === 'a'); assert.equal(links.length, 1); assert.equal(links[0].href, '#character/c1');
  assert.equal(x.calls.length, 1); assert.equal(x.challenges.length, 0); assert.equal(detailSwitch(x.host).attributes['aria-checked'], 'false');
  x.dialogs[0].close(); assert.equal(cls(all(x.host, 'tier-public-card')[0], 'tier-public-card-text').hidden, true);
});

test('the rating board preserves actual zero but never fills an empty placement board with rating votes', async () => {
  const x = setup(async () => aggregate([], [record('c2', {average: 0, voters: 1, rankScore: 12.5 / 6, row: 'provisional'})]));
  x.controller.setView('community'); await tick();
  assert.equal(all(x.host, 'tier-public-card').length, 0); assert.match(cls(x.host, 'tier-public-summary').textContent, /手动排行.*还没有已汇总的玩家投票/);
  await button(x.host, '角色评分').fire(); await all(x.host, 'tier-public-card')[0].fire();
  const dialog = x.dialogs[0].element;
  assert.match(cls(dialog, 'tier-score-headline').textContent, /真实均分0\.00.*暂定，尚未定级/);
  assert.match(dialog.textContent, /当前 1 票，未满 3 票，仅作暂定/);
  const stats = all(dialog, 'tier-score-stat');
  assert.equal(stats.length, 1); assert.match(stats[0].textContent, /暂定排序分2\.081\s*位玩家/);
  assert.match(dialog.textContent, /每份 2\.5 分/); assert.equal(dialog.all(node => node.tag === 'a')[0].href, '#character/c2');
  assert.equal(x.calls.length, 1);
  await button(x.host, '手动排行').fire(); assert.equal(all(x.host, 'tier-public-card').length, 0);
});

test('global details switch changes all card visibility locally and survives attribute filtering', async () => {
  const x = setup(); x.controller.setView('community'); await tick(); const toggle = detailSwitch(x.host);
  assert.equal(toggle.attributes['aria-checked'], 'false'); await toggle.fire();
  assert.equal(toggle.attributes['aria-checked'], 'true');
  for (const card of all(x.host, 'tier-public-card')) {
    assert.equal(cls(card, 'tier-public-card-text').hidden, false); assert.match(visibleText(card), /均分 4\.50.*2 人 · 暂定排序 3\.43/);
  }
  await x.host.all(node => node.attributes['aria-label'] === '火属性排行')[0].fire();
  assert.equal(all(x.host, 'tier-public-card').length, 2); assert.equal(toggle.attributes['aria-checked'], 'true');
  assert.ok(all(x.host, 'tier-public-card-text').every(text => text.hidden === false));
  await toggle.fire(); assert.equal(toggle.attributes['aria-checked'], 'false');
  await button(x.host, '总榜').fire(); assert.equal(all(x.host, 'tier-public-card').length, 3);
  assert.ok(all(x.host, 'tier-public-card-text').every(text => text.hidden === true)); assert.equal(x.calls.length, 1);
  assert.equal(x.dialogs.length, 0); assert.equal(x.challenges.length, 0);
});

test('late or detached public responses never overwrite another view; returning requests current data', async () => {
  const waiting = []; const x = setup(() => new Promise(resolve => waiting.push(resolve)));
  x.controller.setView('community'); x.controller.setView('mine'); waiting[0](aggregate()); await tick();
  assert.equal(all(x.host, 'tier-public-card').length, 0); assert.equal(x.controller.mineHost.hidden, false);
  x.controller.setView('community'); assert.equal(x.calls.length, 2); x.host.connected = false; waiting[1](aggregate()); await tick();
  assert.equal(all(x.host, 'tier-public-card').length, 0);
});

test('failed or malformed aggregate reads have an explicit retry instead of a fake empty score', async () => {
  let reads = 0; const x = setup(async () => ++reads === 1 ? aggregate([record('c1', {rankScore: null})]) : aggregate());
  x.controller.setView('community'); await tick(); assert.equal(all(x.host, 'tier-public-card').length, 0);
  assert.match(cls(x.host, 'tier-public-status').textContent, /资料异常.*重试/);
  await button(x.host, '刷新').fire(); assert.equal(all(x.host, 'tier-public-card').length, 3);
  const empty = setup(async () => aggregate([])); empty.controller.setView('community'); await tick();
  assert.equal(all(empty.host, 'tier-public-card').length, 0); assert.match(cls(empty.host, 'tier-public-status').textContent, /暂无已汇总投票/);
});

test('submit requires a one-use challenge and explicit confirmation, uses a board snapshot, then reads the daily published board', async () => {
  const x = setup(async (pathname, body) => pathname === '/tier-rankings/me' ? me : body
    ? {...me, rows: body.rows, submittedToday: true, rankedCharacters: 1} : aggregate());
  const local = rows(); local.between0 = ['c1']; x.setRows(local);
  await button(x.host, '提交我的排行').fire(); await tick(); const modal = x.dialogs[0], confirm = button(modal.element, '验证后确认提交');
  assert.equal(x.challenges[0].action, 'submit_tier_ranking'); assert.equal(confirm.disabled, true);
  await confirm.fire(); assert.equal(x.calls.filter(call => call[1]).length, 0);
  x.setRows(rows()); x.challenges[0].ready('verified'); await confirm.fire();
  const post = x.calls.find(call => call[1]); assert.equal(post[1].turnstileToken, 'verified'); assert.deepEqual(post[1].rows.between0, ['c1']);
  assert.match(modal.element.textContent, /排行已保存，次日计入/); assert.equal(confirm.disabled, true); assert.equal(x.challenges[0].resets, 1);
  modal.close(); assert.equal(x.challenges[0].destroyed, true); x.controller.setView('community'); await tick();
  assert.equal(x.calls.filter(call => call[0] === '/tier-rankings' && !call[1]).length, 1); assert.equal(all(x.host, 'tier-public-card').length, 3);
});

test('daily public board shows its actual snapshot time and reuses it across view switches until expiry', async () => {
  const snapshot = {...aggregate(), asOf:'2099-01-01T04:00:00Z', nextRefreshAt:'2099-01-01T16:00:00Z', stale:false};
  const x = setup(async () => snapshot);
  x.controller.setView('community'); await tick();
  assert.match(cls(x.host, 'tier-public-updated').textContent, /今日汇总：北京时间.*下次/);
  x.controller.setView('mine'); x.controller.setView('community'); await tick(); assert.equal(x.calls.length, 1);
  await button(x.host, '刷新').fire(); assert.equal(x.calls.length, 2);
  const stale = setup(async () => ({...snapshot, stale:true})); stale.controller.setView('community'); await tick();
  assert.match(cls(stale.host, 'tier-public-updated').textContent, /上次汇总.*今日数据更新中/);
});

test('a daily block prevents verification and resubmission, and 409 responses also lock the dialog', async () => {
  const locked = {...me, submittedToday: true}; const x = setup(async () => locked);
  await button(x.host, '提交我的排行').fire(); await tick(); assert.equal(x.challenges.length, 0);
  assert.match(x.dialogs[0].element.textContent, /今天已提交过排行/); assert.equal(x.calls.length, 1);
  const y = setup(async (_pathname, body) => {if (body) throw Object.assign(new Error('already'), {code: 'already_ranked', status: 409, data: locked}); return me;});
  await button(y.host, '提交我的排行').fire(); await tick(); y.challenges[0].ready();
  await button(y.dialogs[0].element, '验证后确认撤回').fire(); assert.match(y.dialogs[0].element.textContent, /今天已提交过排行/);
  assert.equal(button(y.dialogs[0].element, '验证后确认撤回').disabled, true);
});

test('canceling during personal-state or verification reads does not create a late challenge', async () => {
  let resolve; const x = setup(() => new Promise(done => {resolve = done;}));
  await button(x.host, '提交我的排行').fire(); x.dialogs[0].close(); resolve(me); await tick(); assert.equal(x.challenges.length, 0);
  const y = setup(async () => me, {config: () => new Promise(done => {resolve = done;})});
  await button(y.host, '提交我的排行').fire(); await tick(); y.dialogs[0].close(); resolve({enabled: true}); await tick(); assert.equal(y.challenges.length, 0);
});

test('empty-board withdrawal is an explicit verified whole-board replacement', async () => {
  const x = setup(async (_pathname, body) => body ? {...me, rows: body.rows, submittedToday: true} : me);
  await button(x.host, '提交我的排行').fire(); await tick(); assert.match(x.dialogs[0].element.textContent, /撤回你之前全部手排票/);
  x.challenges[0].ready(); await button(x.dialogs[0].element, '验证后确认撤回').fire();
  const post = x.calls.find(call => call[1]); assert.equal(Object.values(post[1].rows).flat().length, 0);
  assert.match(x.dialogs[0].element.textContent, /已撤回之前的手排票/);
});

test('an uncertain submit is never reported as accepted and reconnect checks the daily record before a new challenge', async () => {
  let submitted = false;
  const x = setup(async (_pathname, body) => {
    if (body) {submitted = true; throw new Error('连接超时');}
    return {...me, submittedToday: submitted};
  });
  await button(x.host, '提交我的排行').fire(); await tick(); x.challenges[0].ready();
  const dialog = x.dialogs[0].element; await button(dialog, '验证后确认撤回').fire();
  assert.match(dialog.textContent, /连接超时/); assert.doesNotMatch(dialog.textContent, /已撤回之前/);
  assert.equal(button(dialog, '验证后确认撤回').disabled, true);
  await button(dialog, '重新连接排行服务').fire();
  assert.match(dialog.textContent, /今天已提交过排行/); assert.equal(x.challenges.length, 1);
  assert.equal(x.challenges[0].destroyed, true); assert.equal(x.calls.filter(call => call[1]).length, 1);
});

test('offline mode keeps local editing available and never fetches or starts verification', async () => {
  const x = setup(async () => {throw new Error('must not fetch');}, {protocol: 'file:'});
  assert.equal(button(x.host, '提交我的排行').disabled, true); x.controller.setView('community'); await tick();
  assert.deepEqual(x.calls, []); assert.match(cls(x.host, 'tier-public-status').textContent, /离线版无法读取/);
  x.controller.setView('mine'); assert.equal(x.controller.mineHost.hidden, false);
});
