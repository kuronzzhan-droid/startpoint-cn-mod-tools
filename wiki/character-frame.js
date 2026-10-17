/* Explicit character-only decoration; never discovers or changes equipment. */
(() => {
  'use strict';
  const elements = new Map([
    ['火', 'fire'], ['水', 'water'], ['雷', 'thunder'],
    ['风', 'wind'], ['光', 'light'], ['暗', 'dark'],
  ]);
  function apply(node, character) {
    if (!node?.classList) return node;
    const element = elements.get(character?.element);
    const rarity = Number(character?.rarity);
    if (!element || !Number.isInteger(rarity) || rarity < 1 || rarity > 5) {
      node.classList.remove('wf-character-frame');
      delete node.dataset.frameElement; delete node.dataset.frameRarity;
      return node;
    }
    node.classList.add('wf-character-frame');
    node.dataset.frameElement = element;
    node.dataset.frameRarity = String(rarity);
    return node;
  }
  window.WFCharacterFrame = {apply};
})();
