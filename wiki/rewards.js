/* Reward records are presentation data; absent rows never imply an empty game reward pool. */
(() => {
  'use strict';
  const labels = {item:'道具', equipment:'武器', character:'角色', beads:'星导石', mana:'玛纳', exp:'经验', degree:'称号', unknown:'奖励'};
  const validId = (id) => typeof id === 'string' && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id);
  const list = (value) => Array.isArray(value) ? value : [];
  function context(data) {
    return {equipment:new Map(list(data.equipment).map((item) => [item.id, item])),
      characters:new Map(list(data.characters).map((item) => [item.id, item]))};
  }
  function notes(ui, values, cls = 'reward-notes') {
    const node = ui.el('ul', cls);
    for (const value of list(values)) if (typeof value === 'string' && value.trim()) node.append(ui.el('li', '', value));
    return node.children.length ? node : null;
  }
  function reward(ui, item, lookup) {
    const {el} = ui, equipment = /^w[0-9a-f]{12}$/.test(item.equipmentId || '') ? lookup.equipment.get(item.equipmentId) : null;
    const character = /^c[0-9a-f]{12}$/.test(item.characterId || '') ? lookup.characters.get(item.characterId) : null;
    const node = el(equipment || character ? 'a' : 'div', 'reward-card');
    if (equipment) node.href = `#weapon/${equipment.id}`;
    else if (character) node.href = `#character/${character.id}`;
    const icon = equipment && window.WFDungeons?.image(ui, equipment.icon, equipment.name || item.name, 'reward-icon');
    if (icon) node.append(icon);
    const text = el('span', 'reward-card-text');
    text.append(el('strong', '', item.name || equipment?.name || character?.name || '未收录的奖励'),
      el('span', 'reward-amount', item.amountText || '数量资料待补'));
    if (item.probabilityText) text.append(el('span', 'reward-probability', item.probabilityText));
    node.append(text, el('span', 'reward-kind', labels[item.kind] || '奖励')); return node;
  }
  function rewardList(ui, values, lookup) {
    const grid = ui.el('div', 'reward-grid');
    for (const item of list(values)) if (item && typeof item === 'object') grid.append(reward(ui, item, lookup));
    return grid;
  }
  function source(ui, record) {
    return ui.el('p', 'reward-source muted', [record?.label || '奖励资料快照', record?.checkedAt ? `核对于 ${record.checkedAt}` : ''].filter(Boolean).join(' · '));
  }
  function renderDungeon(host, id, data, ui) {
    const {el} = ui, record = data.rewards?.dungeons?.[id], panel = el('section', 'dungeon-rewards');
    panel.append(el('h2', '', '掉落与兑换'));
    if (!record) {
      panel.append(el('p', 'muted', '此副本的掉落与兑换资料尚未收录。')); host.append(panel); return;
    }
    const shopIds = list(record.shopIds).filter(validId), shops = new Map(list(data.rewards?.shops).map((shop) => [shop.id, shop]));
    const links = el('div', 'dungeon-shop-links');
    for (const shopId of shopIds) {
      const shop = shops.get(shopId); if (!shop) continue;
      const link = el('a', 'dungeon-shop-link', `${shop.title} ›`); link.href = `#shops/${shopId}`; links.append(link);
    }
    if (links.children.length) panel.append(links);
    const lookup = context(data), quests = list(record.quests);
    for (const quest of quests) {
      const fold = el('details', 'dungeon-fold reward-quest');
      fold.append(el('summary', '', [quest.name || '未命名关卡', quest.difficulty].filter(Boolean).join(' · ')));
      fold.addEventListener('toggle', () => {
        if (!fold.open || fold.children.length > 1) return;
        const body = el('div', 'reward-quest-body'); let count = 0;
        for (const [key, title] of [['firstClear', '首次通关'], ['sPlus', 'S+ 评价'], ['drops', '关卡掉落']]) {
          if (!list(quest[key]).length) continue;
          body.append(el('h3', '', title), rewardList(ui, quest[key], lookup)); count++;
        }
        const detailNotes = notes(ui, quest.notes);
        if (!count && !detailNotes) body.append(el('p', 'muted', '此关卡的奖励明细尚未收录。'));
        if (detailNotes) body.append(detailNotes);
        fold.append(body);
      }); panel.append(fold);
    }
    if (!quests.length) panel.append(el('p', 'muted', '关卡掉落资料尚未收录。'));
    if (!links.children.length) panel.append(el('p', 'muted', '对应兑换商店资料尚未收录。'));
    const recordNotes = notes(ui, record.notes); if (recordNotes) panel.append(recordNotes);
    panel.append(source(ui, data.rewards?.source)); host.append(panel);
  }
  window.WFWikiRewardView = {validId, list, context, notes, rewardList, source, renderDungeon};
})();
