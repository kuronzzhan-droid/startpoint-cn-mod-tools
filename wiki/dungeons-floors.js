/* Each selected floor owns its guide panel; switching floors keeps unsaved drafts. */
(() => {
  'use strict';
  const modes = {
    'event-rush-700098': {count:15, extra:'practice', label:'练习'},
    'event-rush-700099': {count:30, extra:'endless', label:'无尽'},
    'event-rush-700100': {count:30, extra:'endless', label:'无尽'},
  };
  function scopes(item) {
    const mode = Object.hasOwn(modes, item.id) && modes[item.id];
    if (!mode) return [];
    const result = [{...item, scopeLabel:'通用攻略', scopeDescription:'适用于整个模式的攻略与推荐队伍。'}], found = new Set();
    for (const quest of item.quests || []) {
      const match = typeof quest.name === 'string' && quest.name.match(/第\s*([1-9]\d*)\s*[层关關戰战]/);
      const key = match && Number(match[1]) <= mode.count ? match[1]
        : mode.extra === 'endless' && /无尽/.test(quest.name) ? 'endless'
          : mode.extra === 'practice' && /练习/.test(quest.name) ? 'practice' : '';
      if (!key || found.has(key)) continue;
      found.add(key);
      const label = /^\d+$/.test(key) ? `第 ${key} 层` : mode.label;
      result.push({...item, id:`${item.id}-floor-${key}`, title:`${item.title} · ${label}`,
        scopeLabel:label, scopeDescription:[quest.name, quest.element && `${quest.element}属性`].filter(Boolean).join(' · '),
        scopeOrder:/^\d+$/.test(key) ? Number(key) : mode.count + 1});
    }
    return [result[0], ...result.slice(1).sort((a, b) => a.scopeOrder - b.scopeOrder)];
  }
  function mount(host, item, ui, render) {
    const items = scopes(item); if (items.length < 2) return null;
    const {el} = ui, root = el('section', 'dungeon-floors'), navigation = el('div', 'dungeon-floor-choices');
    navigation.setAttribute('role', 'group'); navigation.setAttribute('aria-label', `${item.title}层数`);
    root.append(el('h2', '', '逐层攻略与配队'), navigation);
    const body = el('div', 'dungeon-floor-content'); root.append(body); host.append(root);
    const buttons = [], panels = new Map();
    async function choose(scope) {
      buttons.forEach(({node, value}) => node.setAttribute('aria-pressed', String(value.id === scope.id)));
      for (const [id, entry] of panels) entry.panel.hidden = id !== scope.id;
      if (panels.has(scope.id)) return panels.get(scope.id).pending;
      const panel = el('section', 'dungeon-floor-panel'); panel.setAttribute('aria-label', scope.title);
      panel.append(el('h3', 'dungeon-floor-title', scope.id === item.id ? '通用攻略' : scope.title),
        el('p', 'dungeon-floor-description muted', scope.scopeDescription));
      body.append(panel);
      // Keep each panel connected so switching does not discard its editor or draft.
      const entry = {panel}; panels.set(scope.id, entry); entry.pending = Promise.resolve(render(panel, scope));
      return entry.pending;
    }
    for (const scope of items) {
      const node = window.WFDungeons.button(ui, scope.scopeLabel, () => choose(scope), 'dungeon-floor-choice');
      navigation.append(node); buttons.push({node, value:scope});
    }
    return {ready:choose(items[0]), choose};
  }
  window.WFDungeonFloors = {scopes, mount};
})();
