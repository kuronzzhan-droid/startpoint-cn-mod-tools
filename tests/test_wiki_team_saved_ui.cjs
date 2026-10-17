const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const S = require('../wiki/team-state.js');
const Store = require('../wiki/team-saved-store.js');
class Node {
  constructor(tag, cls = '', text = '') {Object.assign(this, {tag, className: cls, ownText: text, children: [], events: {}, attributes: {}, value: '', hidden: false});}
  append(...nodes) {nodes.forEach(node => {node.parent = this; this.children.push(node);});}
  replaceChildren(...nodes) {this.children.forEach(node => {node.parent = null;}); this.children = []; this.ownText = ''; this.append(...nodes);}
  setAttribute(key, value) {this.attributes[key] = value;}
  addEventListener(event, callback) {(this.events[event] ||= []).push(callback);}
  get textContent() {return this.ownText + this.children.map(node => node.textContent).join('');}
  set textContent(value) {this.replaceChildren(); this.ownText = value;}
  get isConnected() {return this.root || Boolean(this.parent?.isConnected);}
  all(match) {return this.children.flatMap(node => [...(match(node) ? [node] : []), ...node.all(match)]);}
  remove() {if (this.parent) this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null;}
  showModal() {this.open = true;}
  close() {this.open = false; this.fire('close');}
  focus() {this.focused = true;}
  fire(event = 'click') {for (const fn of this.events[event] || []) fn({preventDefault() {}});}
}
const el = (...args) => new Node(...args);
const cls = (root, name) => root.all(node => node.className.split(' ').includes(name));
const button = (root, name) => root.all(node => node.tag === 'button' && node.textContent === name)[0];
const one = (root, name) => root.all(node => node.attributes['aria-label'] === name)[0];
const record = name => ({name, team: {...S.empty(), main: ['a', '', ''], unison: ['b', '', '']}});
function setup(entries = [record('火队'), record('水队')]) {
  let raw = JSON.stringify(entries), failWrite = false, failRead = false;
  const loaded = [], statuses = [], changed = [], document = {body: el('body'), activeElement: el('button')}; document.body.root = true;
  const storage = {getItem: () => {if (failRead) throw Error(); return raw;}, setItem: (_key, value) => {if (failWrite) throw Error(); raw = value;}};
  const window = {WFTeamState: S, WFTeamSavedStore: {create: () => Store.create(() => storage)}, addEventListener() {}, removeEventListener() {}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/team-saved.js'), 'utf8'), {window, document});
  const current = record('当前队伍'), characters = new Map([['a', {name: '甲', icon: 'a.png'}], ['b', {name: '乙', icon: 'b.png'}]]);
  const controller = window.WFTeamSaved.create({ui: {el, picture: (source, alt) => {const image = el('img'); image.src = source; image.alt = alt; return image;}},
    characters, getCurrent: () => current, onLoad: value => loaded.push(value), onChange: () => changed.push(true), onStatus: value => statuses.push(value)});
  return {controller, current, loaded, statuses, changed, body: document.body, records: () => JSON.parse(raw),
    failWrite: () => {failWrite = true;}, failRead: () => {failRead = true;}, replace: value => {raw = JSON.stringify(value);}};
}
test('manager shows named six-slot thumbnail cards, filters by name and loads only the chosen record', () => {
  const x = setup(); x.controller.open(); assert.equal(cls(x.body, 'team-saved-card').length, 2);
  assert.equal(cls(x.body, 'team-saved-portrait').length, 12); assert.equal(x.body.all(node => node.tag === 'img').length, 4);
  const search = one(x.body, '搜索已保存队伍'); search.value = '水'; search.fire('input');
  assert.equal(cls(x.body, 'team-saved-card').length, 1); assert.match(cls(x.body, 'team-saved-card')[0].textContent, /水队/);
  button(x.body, '装入编成').fire(); assert.equal(x.loaded[0].name, '水队'); assert.equal(x.body.children.length, 0);
  assert.deepEqual(x.current, record('当前队伍')); assert.equal(x.records().length, 2);
});
test('delete requires explicit confirmation and cancellation preserves both saved and current teams', () => {
  const x = setup(); x.controller.open(); const card = cls(x.body, 'team-saved-card')[0];
  button(card, '删除').fire(); assert.equal(cls(card, 'team-saved-confirm')[0].hidden, false); assert.equal(x.records().length, 2);
  button(cls(card, 'team-saved-confirm')[0], '取消').fire(); assert.equal(cls(card, 'team-saved-confirm')[0].hidden, true);
  button(card, '删除').fire(); button(card, '确认删除').fire();
  assert.deepEqual(x.records().map(item => item.name), ['水队']); assert.deepEqual(x.current, record('当前队伍'));
  assert.deepEqual(x.loaded, []); assert.equal(cls(x.body, 'team-saved-card').length, 1);
});
test('renaming operates on the selected record and preserves its composition and the current editor', () => {
  const x = setup(); x.controller.open(); const card = cls(x.body, 'team-saved-card')[0]; button(card, '重命名').fire();
  const input = one(card, '重命名 火队'); input.value = '新火队'; cls(card, 'team-saved-edit')[0].fire('submit');
  assert.deepEqual(x.records()[0], record('新火队')); assert.deepEqual(x.current, record('当前队伍')); assert.deepEqual(x.loaded, []);
});
test('saving an existing name waits for a clear overwrite or save-copy choice', () => {
  const x = setup(), next = {...record('火队'), team: S.empty()}; x.controller.save(next);
  assert.deepEqual(x.records()[0], record('火队')); button(x.body, '另存副本').fire();
  assert.deepEqual(x.records()[0], {...next, name: '火队（副本）'}); assert.deepEqual(x.records()[1], record('火队'));
  x.controller.save(next); button(x.body, '覆盖同名队伍').fire(); assert.deepEqual(x.records()[1], next);
});
test('write failure keeps saved cards and current composition and displays an actionable error', () => {
  const x = setup(); x.controller.open(); const before = x.records(); x.failWrite();
  const card = cls(x.body, 'team-saved-card')[0]; button(card, '删除').fire(); button(card, '确认删除').fire();
  assert.deepEqual(x.records(), before); assert.equal(cls(x.body, 'team-saved-card').length, 2);
  assert.match(cls(x.body, 'team-saved-status')[0].textContent, /未能保存更改.*原队伍仍保留/);
  assert.deepEqual(x.current, record('当前队伍')); assert.equal(x.changed.length, 0);
});
test('another page editing storage cannot make a stale delete hit the wrong saved team', () => {
  const x = setup(); x.controller.open(); const card = cls(x.body, 'team-saved-card')[0]; button(card, '删除').fire();
  x.replace([record('新的'), record('火队'), record('水队')]); button(card, '确认删除').fire();
  assert.deepEqual(x.records().map(item => item.name), ['新的', '火队', '水队']);
  assert.match(cls(x.body, 'team-saved-status')[0].textContent, /其他页面修改.*刷新/);
  button(x.body, '刷新').fire(); assert.equal(cls(x.body, 'team-saved-card').length, 3);
});
test('saving from inside the manager displays storage failures in the open dialog', () => {
  for (const fail of ['failWrite', 'failRead']) {
    const x = setup(); x.controller.open(); const before = x.records(); x[fail]();
    button(x.body, '保存当前编成').fire();
    assert.match(cls(x.body, 'team-saved-status')[0].textContent, fail === 'failWrite' ? /未能保存更改/ : /无法读取/);
    assert.deepEqual(x.records(), before); assert.equal(x.loaded.length, 0);
  }
});
test('loading a stale or unreadable saved card never changes the current composition or closes its manager', () => {
  for (const update of ['deleted', 'changed', 'reordered', 'unreadable']) {
    const x = setup(); x.controller.open(); const card = cls(x.body, 'team-saved-card')[0];
    if (update === 'deleted') x.replace([record('水队')]);
    else if (update === 'changed') x.replace([{...record('火队'), team: S.empty()}, record('水队')]);
    else if (update === 'reordered') x.replace([record('新队伍'), record('火队'), record('水队')]);
    else x.failRead();
    button(card, '装入编成').fire();
    assert.equal(x.loaded.length, 0); assert.equal(cls(x.body, 'team-saved-dialog').length, 1);
    assert.match(cls(x.body, 'team-saved-status')[0].textContent, update === 'unreadable' ? /无法读取/ : /当前编成未改动/);
    assert.deepEqual(x.current, record('当前队伍'));
  }
});
test('an unchanged chosen record can still load after another record was renamed', () => {
  const x = setup(); x.controller.open(); const first = cls(x.body, 'team-saved-card')[0];
  x.replace([record('火队'), record('改名的水队')]); button(first, '装入编成').fire();
  assert.equal(x.loaded.length, 1); assert.equal(x.loaded[0].name, '火队');
});
test('overlong legacy names show a recoverable validation error instead of throwing on save-copy', () => {
  const value = record('长'.repeat(61)), x = setup([value]); x.controller.save(value);
  assert.doesNotThrow(() => button(x.body, '另存副本').fire());
  assert.match(cls(x.body, 'team-saved-status')[0].textContent, /1–60/); assert.deepEqual(x.records(), [value]);
});
