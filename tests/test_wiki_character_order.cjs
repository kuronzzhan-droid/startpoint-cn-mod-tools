const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const window = {};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/character-order.js'), 'utf8'), {window});
const item = (id, rarity, catalogOrder, origin = '官方原版', element = '火') => ({id, rarity, catalogOrder, origin, element});
const entries = [item('old5', 5, 1), item('new4mod', 4, 90, '新增MOD'), item('new5', 5, 70, '官方原版', '水'),
  item('old5mod', 5, 80, '新增MOD'), item('new5mod', 5, 99, '新增MOD', '暗'), item('old4', 4, 2)];
test('team picker sorts rarity descending, MOD first within rarity, then reverse catalogue order across elements', () => {
  assert.deepEqual([...entries].sort(window.WFCharacterOrder.compareTeam).map(x => x.id),
    ['new5mod', 'old5mod', 'new5', 'old5', 'new4mod', 'old4']);
});
test('missing order does not masquerade as the newest character', () => {
  assert.deepEqual([item('missing', 5, undefined), item('known', 5, 12)].sort(window.WFCharacterOrder.compareTeam).map(x => x.id), ['known', 'missing']);
});
test('catalogue retains element, rarity, official then MOD and ascending native order', () => {
  assert.deepEqual([...entries].sort(window.WFCharacterOrder.compare).map(x => x.id),
    ['old5', 'old5mod', 'old4', 'new4mod', 'new5', 'new5mod']);
});
