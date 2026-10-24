/* Preserve native catalogue order inside each element and rarity group. */
(() => {
  'use strict';
  const elements = ['火', '水', '雷', '风', '光', '暗'];
  const element = (value) => elements.includes(value) ? elements.indexOf(value) : elements.length;
  const mod = (character) => ['新增MOD', '灰服独立角色资料'].includes(character.origin) ? 1 : 0;
  const order = (character) => Number.isFinite(Number(character.catalogOrder)) ? Number(character.catalogOrder) : Number.MAX_SAFE_INTEGER;
  const latest = (character) => character.catalogOrder != null && Number.isFinite(Number(character.catalogOrder))
    ? Number(character.catalogOrder) : -1;
  window.WFCharacterOrder = {compare: (a, b) => element(a.element) - element(b.element)
    || Number(b.rarity || 0) - Number(a.rarity || 0) || mod(a) - mod(b) || order(a) - order(b),
  compareTeam: (a, b) => Number(b.rarity || 0) - Number(a.rarity || 0)
    || mod(b) - mod(a) || latest(b) - latest(a) || element(a.element) - element(b.element)};
})();
