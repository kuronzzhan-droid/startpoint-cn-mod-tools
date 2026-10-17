/* Restriction badges come only from structured, verified row conditions. */
(() => {
  'use strict';
  const knownKinds = new Set(['main', 'unison', 'selfElement', 'resonance']);
  window.renderWikiAbilityRows = function renderWikiAbilityRows(container, entry, meta, ui) {
    const {el, list, object, text, safeUrl, nativeIcon} = ui;
    const rows = list(entry.rows).filter((row) => row && text(row.description).trim());
    if (!rows.length) return false;
    const assets = object(meta.uiAssets);
    function conditionBadge(condition) {
      const badge = el('span', `ability-condition ability-condition-${condition.kind}`);
      const iconUrl = safeUrl(object(assets.abilityConditions)[condition.icon]);
      if (iconUrl) badge.append(nativeIcon('abilityConditions', condition.icon, ''));
      else if (condition.element && safeUrl(object(assets.elements)[condition.element])) {
        badge.append(nativeIcon('elements', condition.element, ''));
      }
      badge.append(el('span', '', condition.label));
      return badge;
    }
    function restrictions(value) {
      const data = object(value);
      // Unrecognized or compound groups remain in the complete effect text.
      if (!['AND', 'OR'].includes(data.operator)) return null;
      const sourceItems = list(data.items);
      const items = sourceItems.filter((item) => item && knownKinds.has(item.kind) && text(item.label).trim());
      if (data.operator === 'OR' && items.length !== sourceItems.length) return null;
      if (!items.length) return null;
      const bar = el('div', 'ability-restrictions');
      bar.setAttribute('aria-label', '本条效果的生效限制');
      items.forEach((item, index) => {
        if (index) bar.append(el('span', 'ability-condition-operator', data.operator === 'OR' ? '或' : '且'));
        bar.append(conditionBadge(item));
      });
      return bar;
    }
    const effects = el('ol', 'ability-effect-list');
    rows.forEach((row, index) => {
      const effect = el('li', 'ability-effect-row');
      const number = el('span', 'ability-effect-number', String(index + 1).padStart(2, '0'));
      number.setAttribute('aria-hidden', 'true');
      const body = el('div', 'ability-effect-body');
      const conditions = restrictions(row.restrictions);
      if (conditions) body.append(conditions);
      body.append(el('p', 'ability-effect-description', row.description));
      effect.append(number, body); effects.append(effect);
    });
    const authored = entry.descriptionSource === '游戏面板覆盖文案';
    const automatic = entry.descriptionSource === '数据行自动解析';
    if ((authored || !automatic) && text(entry.description).trim()) {
      container.append(el('p', 'description ability-authored-description', entry.description));
      const detail = el('details', 'ability-effect-disclosure'); detail.open = true;
      detail.append(el('summary', '', `逐条效果与限制 · ${rows.length} 条`), effects);
      container.append(detail);
    } else container.append(effects);
    return true;
  };
})();
