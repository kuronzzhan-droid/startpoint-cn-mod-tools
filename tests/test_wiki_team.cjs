const test = require('node:test');
const assert = require('node:assert/strict');
const S = require('../wiki/team-state.js');
const characters = new Map([['a', {}], ['b', {}], ['c', {}]]);
const equipment = new Map([['x', {category:'诅咒武器',soul:{available:true}}], ['y', {category:'悖论武器',soul:{available:false}}]]);
const rules = {curseExclusion:{threshold:2},paradoxDecay:{offAtOtherCount:4}};
test('moving duplicate characters swaps main and unison without mutating history', () => {
  const initial = S.empty(); initial.main[0] = 'a'; initial.unison[1] = 'b';
  const changed = S.place(initial,'unison',1,'a',characters,equipment);
  assert.equal(changed.main[0],'b'); assert.equal(changed.unison[1],'a');
  assert.equal(initial.main[0],'a'); assert.equal(initial.unison[1],'b');
});
test('saved teams reject missing IDs, duplicate characters and unavailable souls', () => {
  const value = S.validate({main:['a','a','missing'],unison:['a','b'],weapon:['x'],soul:['y','x']},characters,equipment);
  assert.deepEqual(value.main,['a','','']); assert.deepEqual(value.unison,['','b','']);
  assert.deepEqual(value.soul,['','x','']);
  assert.equal(S.place(value,'weapon',0,'a',characters,equipment),value);
});
test('weapon rules count occupied main slots, including repeated weapons and souls', () => {
  const value = S.empty(); value.main=['a','b','c']; value.weapon=['y','x','x']; value.soul=['x','x',''];
  const notes = S.ruleNotes(value,equipment,rules).join(' ');
  assert.match(notes,/4 件诅咒/); assert.match(notes,/悖论整件能力失效/);
  value.main[2]=''; const reduced = S.ruleNotes(value,equipment,rules).join(' ');
  assert.match(reduced,/3 件诅咒/); assert.doesNotMatch(reduced,/悖论整件能力失效/);
});
