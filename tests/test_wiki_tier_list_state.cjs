const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const api = require('../wiki/tier-list-state.js');
const characters = Array.from({length: 40}, (_, index) => ({id: `c${index}`}));
function memory(initial = null) {
  const values = new Map(initial === null ? [] : [[api.storageKey, initial]]);
  return {values, writes: 0, getItem(key) {return values.get(key) ?? null;}, setItem(key, value) {this.writes++; values.set(key, value);}};
}
const create = (storage = memory()) => api.create({characters, storage});

test('characters move between tiers, intermediate lines and pool without duplicates', () => {
  const state = create();
  assert.deepEqual(Object.keys(state.getRows()), api.rowKeys);
  for (const row of api.rowKeys) {
    assert.equal(state.move('c0', row), true);
    assert.deepEqual([...state.assignedIds()], ['c0']);
    assert.deepEqual(state.getRows()[row], ['c0']);
    assert.equal(Object.values(state.getRows()).flat().length, 1);
  }
  assert.equal(state.move('c0', 'pool'), true);
  assert.equal(state.assignedIds().size, 0);
});

test('placement preserves explicit order within and across rows', () => {
  const state = create();
  ['c0', 'c1', 'c2'].forEach((id) => state.move(id, 'tier0'));
  state.move('c2', 'tier0', 'c0'); assert.deepEqual(state.getRows().tier0, ['c2', 'c0', 'c1']);
  state.move('c2', 'tier0', 'c1'); assert.deepEqual(state.getRows().tier0, ['c0', 'c2', 'c1']);
  state.move('c0', 'tier0'); assert.deepEqual(state.getRows().tier0, ['c2', 'c1', 'c0']);
  state.move('c3', 'between0'); state.move('c1', 'between0', 'c3');
  assert.deepEqual(state.getRows().between0, ['c1', 'c3']);
  assert.deepEqual(state.getRows().tier0, ['c2', 'c0']);
  state.move('c1', 'between0', 'missing'); assert.deepEqual(state.getRows().between0, ['c3', 'c1']);
});

test('invalid and unchanged operations do not save or consume undo history', () => {
  const storage = memory(), state = create(storage);
  for (const [id, row] of [['unknown', 'tier0'], ['c0', 'bad'], ['', 'tier0'], [0, 'tier0'], ['c0', 'pool']]) {
    assert.equal(state.move(id, row), false);
  }
  assert.equal(state.clear(), false); assert.equal(state.canUndo(), false); assert.equal(storage.writes, 0);
  state.move('c0', 'tier0');
  assert.equal(state.move('c0', 'tier0'), false); assert.equal(state.move('c0', 'tier0', 'c0'), false);
  assert.equal(storage.writes, 1); assert.equal(state.undo(), true); assert.equal(state.undo(), false);
});

test('returned rows and assigned IDs cannot mutate current or undo state', () => {
  const state = create(); state.move('c0', 'between2');
  const rows = state.getRows(); rows.between2.push('c1'); rows.tier0 = ['c2'];
  const assigned = state.assignedIds(); assigned.clear(); assigned.add('unknown');
  assert.deepEqual(state.getRows().between2, ['c0']); assert.deepEqual(state.getRows().tier0, []);
  state.move('c1', 'between2'); state.undo(); assert.deepEqual([...state.assignedIds()], ['c0']);
});

test('saved rankings reload with row order, version and only enrolled unique characters', () => {
  const storage = memory(), state = create(storage);
  state.move('c1', 'between0'); state.move('c0', 'between0', 'c1'); state.move('c2', 'tier4');
  const serialized = JSON.parse(storage.getItem(api.storageKey)); assert.equal(serialized.version, 1);
  assert.deepEqual(create(storage).getRows(), state.getRows());
  serialized.rows.tier0 = ['c0', 'unknown', 'c0', null, 123, {id: 'c3'}];
  serialized.rows.between1 = 'c3'; serialized.rows.extra = ['c3'];
  storage.setItem(api.storageKey, JSON.stringify(serialized));
  const loaded = create(storage);
  assert.deepEqual(loaded.getRows().tier0, ['c0']); assert.deepEqual(loaded.getRows().between0, ['c1']);
  assert.deepEqual(loaded.getRows().between1, []); assert.deepEqual([...loaded.assignedIds()], ['c0', 'c1', 'c2']);
  assert.equal(loaded.canUndo(), false);
});

test('broken or incompatible saved data is not overwritten until a user change', () => {
  for (const raw of ['{bad json', 'null', '{"version":2,"rows":{}}', '{"version":1}']) {
    const storage = memory(raw), state = create(storage);
    assert.equal(state.assignedIds().size, 0); assert.ok(state.persistenceError()); assert.equal(storage.writes, 0);
    assert.equal(storage.getItem(api.storageKey), raw);
    assert.equal(state.move('c0', 'tier2'), true); assert.equal(state.persistenceError(), '');
    assert.deepEqual(create(storage).getRows().tier2, ['c0']);
  }
});

test('unavailable storage and later write failures preserve usable in-memory state', () => {
  const storage = {getItem() {throw new Error('blocked');}, setItem() {throw new Error('quota');}};
  const state = create(storage); assert.ok(state.persistenceError());
  state.move('c0', 'tier0'); state.move('c1', 'between3'); assert.equal(state.assignedIds().size, 2);
  assert.ok(state.persistenceError()); assert.equal(state.undo(), true); assert.deepEqual([...state.assignedIds()], ['c0']);
  storage.setItem = () => {}; state.move('c2', 'tier0'); assert.equal(state.persistenceError(), '');
});

test('a blocked default localStorage getter does not prevent creating or editing a ranking', () => {
  const window = {}; Object.defineProperty(window, 'localStorage', {get() {throw new Error('security');}});
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/tier-list-state.js'), 'utf8'), {window});
  const state = window.WFTierListState.create({characters});
  assert.ok(state.persistenceError()); assert.equal(state.move('c0', 'tier3'), true);
  assert.equal(state.getRows().tier3[0], 'c0');
});

test('clear is undoable and restored content is persisted', () => {
  const storage = memory(), state = create(storage);
  state.move('c0', 'tier4'); state.move('c1', 'between0'); const before = state.getRows();
  assert.equal(state.clear(), true); assert.equal(state.assignedIds().size, 0);
  assert.equal(state.undo(), true); assert.deepEqual(state.getRows(), before);
  assert.deepEqual(create(storage).getRows(), before);
});

test('undo retains the latest 30 edits and remains correct after divergent edits', () => {
  const state = create();
  for (let index = 0; index < 40; index++) state.move(`c${index}`, 'tier0');
  for (let index = 0; index < 30; index++) assert.equal(state.undo(), true);
  assert.equal(state.undo(), false); assert.equal(state.assignedIds().size, 10);
  state.move('c0', 'tier4'); state.undo(); state.move('c1', 'between1');
  assert.deepEqual(state.getRows().between1, ['c1']); assert.deepEqual(state.getRows().tier4, []);
  assert.equal(state.assignedIds().size, 10);
});
