/* Saved cloud records: previews and actions never mutate an unsaved editor. */
(() => {
  'use strict';
  const C = window.WFCommunity;
  window.WFCommunityAdminCards = {
    create(item, {data, ui, avatars, onEdit, onDelete, onRestore}) {
      const {el} = ui, card = el('article', 'admin-team-row');
      const heading = el('div', 'admin-card-heading'), badges = el('div', 'admin-card-badges');
      const removed = item.status === 'hidden';
      heading.append(el('h2', '', item.title));
      badges.append(el('span', `admin-state ${removed ? 'admin-state-deleted' : item.visibility === 'private' ? 'admin-state-private' : 'admin-state-public'}`,
        removed ? '回收站' : item.visibility === 'private' ? '个人空间' : '已在大全公开'));
      heading.append(badges); card.append(heading);
      const tags = el('p', 'admin-card-tags');
      [C.sectionLabel(item.section), C.categoryLabel(item.category), C.elementLabel(item.element)].filter(Boolean)
        .forEach(label => tags.append(el('span', '', label)));
      card.append(tags);
      const preview = el('button', 'admin-card-preview'); preview.type = 'button';
      preview.setAttribute('aria-label', `编辑队伍：${item.title}`);
      preview.addEventListener('click', () => onEdit(item));
      if (C.board && ui.picture) preview.append(C.board(item.team, data, ui, {preview:true, avatars}));
      else {
        const characters = new Map((data.characters || []).map(entry => [entry.id, entry]));
        preview.append(el('span', 'admin-team-main', (item.team?.main || []).map(id => characters.get(id)?.name || '空位').join(' / ')));
      }
      card.append(preview);
      const updated = item.updatedAt && !Number.isNaN(Date.parse(item.updatedAt)) ? new Date(item.updatedAt).toLocaleDateString('zh-CN') : '';
      card.append(el('p', 'admin-team-meta', [item.author || '未署名', updated && `更新 ${updated}`].filter(Boolean).join(' · ')));
      const code = !removed && window.WFCommunityGameCodes?.adminReadonly(item, ui, {compact:true});
      card.append(code || el('p', 'admin-card-code-empty', removed ? '已停用，原队伍码不可用' : '尚未公开队伍码'));
      const actions = el('div', 'admin-card-actions');
      const action = (label, fn, cls) => {const b = el('button', cls || 'secondary-button', label); b.type = 'button'; b.addEventListener('click', () => fn(item)); return b;};
      actions.append(action('编辑队伍', onEdit, 'primary-button'));
      if (removed) actions.append(action('恢复队伍', onRestore));
      else actions.append(action('删除', onDelete, 'admin-delete-button'));
      card.append(actions); return card;
    },
  };
})();
