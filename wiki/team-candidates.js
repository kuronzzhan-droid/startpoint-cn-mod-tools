/* Keep mounted candidate pools and images when changing slot type or equipment target. */
(() => {
  'use strict';
  window.WFTeamCandidates = {create({ui, avatars, onAssign, scrollRail = true}) {
    const {el, picture, elementBadge} = ui, root = el('div', 'team-candidate-pools'), pools = new Map();
    let active = '';
    function poolFor(kind) {
      if (pools.has(kind)) return pools.get(kind);
      const viewport = el('div', 'team-candidates'); viewport.dataset.kind = kind;
      const panel = (scrollRail && window.WFTeamScrollRail?.wrap(viewport, ui, kind === 'character' ? '角色候选' : '武器与魂珠候选')) || viewport;
      panel.hidden = true; root.append(panel);
      const pool = {viewport, panel, records:new Map(), items:null, target:'', selected:'', form:avatars?.getForm()}; pools.set(kind, pool); return pool;
    }
    function recordFor(pool, kind, item) {
      if (pool.records.has(item)) return pool.records.get(item);
      const character = kind === 'character', button = el('button', 'team-candidate'); button.type = 'button'; button.draggable = true;
      button.addEventListener('click', () => {if (!button.disabled) onAssign(item.id, character ? 'character' : 'equipment');});
      button.addEventListener('dragstart', (event) => {
        if (button.disabled) {event.preventDefault(); return;}
        event.dataTransfer.setData('application/x-wf-wiki', JSON.stringify({id:item.id,kind:character ? 'character' : 'equipment'}));
      });
      const image = character && avatars ? avatars.picture(item, item.name, 'team-candidate-image') : picture(item.icon, item.name, 'team-candidate-image');
      if (character) {
        const details = [`${item.element || '未知'}属性`, item.rarity ? `${item.rarity}星` : '', item.type,
          ...(Array.isArray(item.themes) ? item.themes : [item.theme])].filter(Boolean).join(' · ');
        button.title = `${item.name} · ${details}`; button.setAttribute('aria-label', `选择${item.name}`); button.setAttribute('aria-description', details);
        const art = el('span', 'team-candidate-art'); art.append(image, elementBadge(item.element));
        window.WFCharacterFrame?.apply(art, item); window.WFCharacterBadges?.append(art, item, ui); button.append(art);
      } else button.append(image);
      const name = el('span', character ? 'team-candidate-name' : '', item.name); name.title = item.name; button.append(name);
      const metadata = character ? null : el('span', 'team-candidate-equipment-type'); if (metadata) button.append(metadata);
      const record = {button, image, metadata, form:avatars?.getForm(), target:''}; pool.records.set(item, record); return record;
    }
    function updateRecord(record, item, kind, target) {
      if (kind === 'character') {
        const form = avatars?.getForm();
        if (avatars && form !== record.form) {
          const urls = item.avatars || {}, wanted = ui.safeUrl(urls[form]);
          const url = wanted || ui.safeUrl(item.icon) || ui.safeUrl(urls.before) || ui.safeUrl(urls.after);
          // Mounted portraits have already been synced by the shared avatar controller.
          if (record.image.querySelector('img')?.getAttribute('src') !== url) {
            const fresh = avatars.picture(item, item.name, 'team-candidate-image');
            record.image.replaceChildren(...fresh.children); record.image.title = fresh.title;
          }
          record.image.title = wanted ? '' : '未收录此状态的头像，显示现有头像';
          record.form = form;
        }
      } else if (record.target !== target) {
        const soul = target === 'soul', unavailable = soul && item.soul?.available !== true;
        const name = `${item.name}${soul ? '魂珠' : ''}`;
        record.button.disabled = unavailable; record.button.draggable = !unavailable;
        record.button.title = unavailable ? `${item.name} · 暂无魂珠` : `${name} ${item.theme || ''}`;
        record.button.setAttribute('aria-label', `选择${name}`);
        record.metadata.textContent = `${unavailable ? '暂无魂珠' : soul ? '魂珠' : '武器'} · ${item.element || '未标注'}${item.rarity ? ` · ${item.rarity}★` : ''}`;
        record.target = target;
      }
    }
    function select(kind, id) {
      const pool = pools.get(kind); if (!pool || pool.selected === id) return;
      for (const [item, record] of pool.records) if (item.id === pool.selected || item.id === id) record.button.setAttribute('aria-pressed', String(item.id === id));
      pool.selected = id;
    }
    function show(kind, items, target, selected) {
      const pool = poolFor(kind);
      if (active !== kind) {
        for (const [name, entry] of pools) entry.panel.hidden = name !== kind;
        active = kind;
      }
      if (items !== pool.items) {
        const nodes = items.map(item => {
          const record = recordFor(pool, kind, item); updateRecord(record, item, kind, target);
          record.button.setAttribute('aria-pressed', String(item.id === selected)); return record.button;
        });
        if (!pool.items || items.length !== pool.items.length || items.some((item, i) => item !== pool.items[i])) {
          const scroll = pool.viewport.scrollTop;
          pool.viewport.replaceChildren(...(nodes.length ? nodes : [el('p', '', '没有匹配的候选。')]));
          pool.viewport.scrollTop = scroll;
        }
        pool.items = items;
      } else if (kind === 'character' && pool.form !== avatars?.getForm()) {
        for (const item of items) updateRecord(pool.records.get(item), item, kind, target);
      }
      if (kind === 'equipment' && pool.target !== target) {
        for (const item of items) updateRecord(pool.records.get(item), item, kind, target);
        pool.target = target;
      }
      pool.form = avatars?.getForm();
      select(kind, selected); return pool.viewport;
    }
    return {element:root, show, select};
  }};
})();
