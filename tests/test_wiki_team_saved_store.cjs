const test = require('node:test');
const assert = require('node:assert/strict');
const {create, key} = require('../wiki/team-saved-store.js');
const S = require('../wiki/team-state.js');
const record = name => ({name, team: {...S.empty(), main: ['a', '', '']}});
function setup(value) {
  let raw = value === undefined ? null : JSON.stringify(value), writes = 0, failRead = false, failWrite = false;
  const store = create(() => ({getItem(k) {assert.equal(k, key); if (failRead) throw Error(); return raw;},
    setItem(k, value) {assert.equal(k, key); if (failWrite) throw Error(); writes++; raw = value;}}));
  return {store, value: () => JSON.parse(raw), raw: () => raw, writes: () => writes,
    replace: value => {raw = value;}, failRead: () => {failRead = true;}, failWrite: () => {failWrite = true;}};
}
test('legacy v1 saves remain readable and loading never writes or mutates caller records', () => {
  const old = {...record('旧队伍'), legacy: {note: '保留'}}; const x = setup([old]);
  const snapshot = x.store.read(); snapshot.records[0].team.main[0] = 'changed';
  assert.deepEqual(x.value(), [old]); assert.equal(x.writes(), 0); assert.equal(snapshot.records[0].key, 0);
});
test('new saves use the existing key and array format and clone incoming teams', () => {
  const x = setup(), next = record('新队伍'); const saved = x.store.add(x.store.read(), next);
  next.team.main[0] = 'changed'; assert.deepEqual(x.value(), [record('新队伍')]);
  assert.equal(saved.records.length, 1); assert.equal(x.writes(), 1);
});
test('adding a duplicate refuses silent replacement; replacement is an explicit separate operation', () => {
  const x = setup([record('同名')]), snapshot = x.store.read(); const next = {...record('同名'), team: S.empty()};
  assert.throws(() => x.store.add(snapshot, next), {code: 'exists'}); assert.equal(x.writes(), 0);
  x.store.replace(snapshot, 0, next); assert.deepEqual(x.value(), [next]);
});
test('copy names stay unique and within the editable sixty-character limit', () => {
  const name = '名'.repeat(60), x = setup([record(name), record('同名（副本）'), record('同名（副本2）')]);
  assert.equal(x.store.copyName(x.store.read(), '同名'), '同名（副本3）');
  assert.equal(x.store.copyName(x.store.read(), name).length, 60);
});
test('renaming preserves team data and unknown fields and rejects collisions or blank titles', () => {
  const first = {...record('甲'), unknown: ['kept']}, x = setup([first, record('乙')]);
  assert.throws(() => x.store.rename(x.store.read(), 0, '乙'), {code: 'exists'});
  assert.throws(() => x.store.rename(x.store.read(), 0, ' '), {code: 'name'});
  x.store.rename(x.store.read(), 0, ' 改名 ');
  assert.deepEqual(x.value()[0], {...first, name: '改名'}); assert.deepEqual(x.value()[1], record('乙'));
});
test('removal affects exactly the selected saved record and retains non-displayable legacy entries', () => {
  const invalid = {legacy: true}, x = setup([invalid, record('甲'), record('乙')]);
  const snapshot = x.store.read(); assert.equal(snapshot.skipped, 1); assert.equal(snapshot.records[0].key, 1);
  x.store.remove(snapshot, 1); assert.deepEqual(x.value(), [invalid, record('乙')]);
});
test('stale snapshots cannot delete or overwrite a record moved by another page', () => {
  const x = setup([record('甲')]), snapshot = x.store.read(); x.replace(JSON.stringify([record('新'), record('甲')]));
  assert.throws(() => x.store.remove(snapshot, 0), {code: 'stale'});
  assert.throws(() => x.store.replace(snapshot, 0, record('覆盖')), {code: 'stale'});
  assert.equal(x.writes(), 0); assert.deepEqual(x.value().map(item => item.name), ['新', '甲']);
});
test('storage failures preserve both disk data and the prior snapshot for add, rename, delete and replace', () => {
  for (const operation of ['add', 'rename', 'remove', 'replace']) {
    const x = setup([record('甲')]), snapshot = x.store.read(), before = x.raw(); x.failWrite();
    const args = {add: [record('乙')], rename: [0, '乙'], remove: [0], replace: [0, record('乙')]}[operation];
    assert.throws(() => x.store[operation](snapshot, ...args), {code: 'write'});
    assert.equal(x.raw(), before); assert.equal(snapshot.records[0].name, '甲'); assert.equal(x.writes(), 0);
  }
});
test('corrupt and inaccessible storage never turns into an empty array eligible for overwrite', () => {
  for (const value of ['', '{', '{}', 'null']) {
    const x = setup(); x.replace(value); assert.throws(() => x.store.read(), {code: 'format'});
    assert.equal(x.raw(), value); assert.equal(x.writes(), 0);
  }
  const x = setup([record('甲')]); x.failRead(); assert.throws(() => x.store.read(), {code: 'read'}); assert.equal(x.writes(), 0);
});
