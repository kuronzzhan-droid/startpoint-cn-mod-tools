/* Local tier board with an explicit, separately verified community submission. */
window.renderWikiTierList = function renderWikiTierList(host, data, ui, options) {
  'use strict';
  options ||= {};
  const {el, nativeIcon} = ui;
  const characters = (data.characters || []).filter((item) => item && item.id != null);
  const ordered = [...characters].sort(window.WFCharacterOrder.compare);
  const byId = new Map(characters.map((item) => [String(item.id), item]));
  const state = window.WFTierListState.create({characters});
  const labels = ['夯', '顶级', '人上人', 'NPC', '拉完了'];
  const page = el('div', 'tier-page');
  const toolbar = el('div', 'tier-toolbar'), avatarControls = el('div');
  const action = (label, callback) => {
    const button = el('button', 'secondary-button', label); button.type = 'button';
    button.addEventListener('click', callback); toolbar.append(button); return button;
  };
  const board = el('div', 'tier-board'); board.setAttribute('aria-label', '角色排行');
  const status = el('p', 'tier-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const pool = el('section', 'tier-pool tier-zone'), poolHeading = el('div', 'tier-pool-heading');
  const count = el('span', 'inline-count'), poolGrid = el('div', 'tier-pool-grid');
  poolHeading.append(el('h2', '', '待排行角色'), count);
  const zones = new Map(), cards = new Map();
  let selected = '', dragging = '', community;
  const portraits = window.WFCatalogAvatars.create({host: avatarControls, catalog: page, characters, ui, label: '排行角色头像'});
  function announce(message = '') {
    status.textContent = state.persistenceError() || message;
    status.hidden = !status.textContent;
  }
  function select(id) {
    selected = id;
    cards.forEach((card, key) => {
      card.classList.toggle('is-selected', key === id); card.setAttribute('aria-pressed', String(key === id));
    });
    announce(id ? `已选中 ${byId.get(id).name}，点击档位、分界线或待排行区放置；Esc 取消。` : '已取消选择。');
  }
  function place(id, row, beforeId) {
    if (!byId.has(id)) return;
    const moved = state.move(id, row, beforeId);
    selected = ''; dragging = ''; render();
    if (moved) announce(`${byId.get(id).name} 已移至${zones.get(row).label}。已自动保存。`);
    zones.get(row).node.focus({preventScroll: true});
  }
  function registerZone(node, row, label, slots) {
    node.dataset.row = row; node.tabIndex = 0; node.setAttribute('role', 'group');
    node.setAttribute('aria-label', `放到${label}`);
    zones.set(row, {node, slots, label});
    const targetAvatar = (event) => event.target.closest?.('.tier-avatar');
    node.addEventListener('click', (event) => {
      if (!selected || event.target.closest?.('button,input,select,summary,a,[role="combobox"]') || targetAvatar(event)) return;
      place(selected, row);
    });
    node.addEventListener('keydown', (event) => {
      if (event.target !== node || !selected || !['Enter', ' '].includes(event.key)) return;
      event.preventDefault(); place(selected, row);
    });
    const acceptDrag = (event) => {
      if (!dragging) return;
      event.preventDefault(); event.dataTransfer.dropEffect = 'move'; node.classList.add('is-drop-target');
    };
    node.addEventListener('dragenter', acceptDrag);
    node.addEventListener('dragover', acceptDrag);
    node.addEventListener('dragleave', (event) => {
      if (!node.contains(event.relatedTarget)) node.classList.remove('is-drop-target');
    });
    node.addEventListener('drop', (event) => {
      if (!dragging) return;
      event.preventDefault(); node.classList.remove('is-drop-target');
      place(dragging, row, targetAvatar(event)?.dataset.characterId);
    });
  }
  labels.forEach((label, index) => {
    const row = el('section', `tier-zone tier-row tier-row-${index}`), slots = el('div', 'tier-slots');
    row.append(el('h2', 'tier-label', label), slots); registerZone(row, `tier${index}`, label, slots); board.append(row);
    if (index === labels.length - 1) return;
    const boundary = el('section', 'tier-zone tier-boundary'), lineSlots = el('div', 'tier-slots');
    const lineLabel = `${label} ↔ ${labels[index + 1]}`;
    boundary.append(el('span', 'tier-label', lineLabel), lineSlots);
    registerZone(boundary, `between${index}`, `${label}与${labels[index + 1]}之间`, lineSlots); board.append(boundary);
  });
  registerZone(pool, 'pool', '待排行区', poolGrid);
  const filters = window.WFCharacterFilters.create({characters, ui, idPrefix: 'tier-character', collapsible: false, onChange: renderPool});
  const filterBody = filters.element.querySelector('.character-filter-body');
  const filterControls = el('div', 'tier-filter-controls');
  const searchRow = filterBody.querySelector('.character-filter-search-row');
  const resetButton = searchRow.querySelector('.text-button');
  filterControls.append(searchRow, filterBody.querySelector('.character-filter-fields'), resetButton);
  filterBody.prepend(filterControls);
  pool.append(poolHeading, filters.element, poolGrid);
  // Pool controls do not place the selected portrait while the user is filtering.
  filters.element.addEventListener('click', (event) => event.stopPropagation());
  ordered.forEach((character) => {
    const id = String(character.id), card = el('button', 'tier-avatar'); card.type = 'button'; card.draggable = true;
    const label = `${character.name}${character.theme ? `（${character.theme}）` : ''}，${character.element}属性，${character.rarity}星`;
    card.title = label; card.setAttribute('aria-label', label); card.dataset.characterId = id;
    card.append(portraits.picture(character, '', ''), nativeIcon('elements', character.element, character.element, 'tier-avatar-element'));
    window.WFCharacterFrame.apply(card, character);
    card.addEventListener('click', (event) => {
      event.stopPropagation();
      if (selected && selected !== id) {place(selected, card.closest('.tier-zone').dataset.row, id); return;}
      select(selected === id ? '' : id);
    });
    card.addEventListener('dragstart', (event) => {
      dragging = id; select(id); event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('application/x-wf-tier-character', id);
    });
    card.addEventListener('dragend', () => {
      dragging = ''; zones.forEach(({node}) => node.classList.remove('is-drop-target'));
    });
    cards.set(id, card);
  });
  function renderPool() {
    const assigned = state.assignedIds();
    const available = ordered.filter((character) => !assigned.has(String(character.id)) && filters.matches(character));
    poolGrid.replaceChildren(...available.map((character) => cards.get(String(character.id))));
    if (!available.length) poolGrid.append(el('span', 'tier-placeholder', '没有符合筛选的待排行角色'));
    count.textContent = `${available.length} / ${characters.length - assigned.size}`;
  }
  function render() {
    const rows = state.getRows();
    Object.entries(rows).forEach(([key, ids]) => {
      const slots = zones.get(key).slots;
      slots.replaceChildren(...ids.map((id) => cards.get(id)));
      if (!ids.length) slots.append(el('span', 'tier-placeholder', key.startsWith('between') ? '放在线上' : '拖入头像 / 点选放置'));
    });
    renderPool();
    cards.forEach((card, id) => {card.classList.toggle('is-selected', selected === id); card.setAttribute('aria-pressed', String(selected === id));});
    undo.disabled = !state.canUndo(); clear.disabled = state.assignedIds().size === 0; announce(); community?.refreshState();
  }
  const undo = action('撤销', () => {if (state.undo()) {selected = ''; render(); announce('已撤销上一步。');}});
  const remove = action('移回待排行', () => {if (selected) place(selected, 'pool'); else announce('先点选要移回的角色。');});
  remove.title = '选中榜内角色后点击，或直接拖回下方待排行区';
  const clear = action('清空排行', () => {if (state.clear()) {selected = ''; render(); announce('排行已清空，可点击撤销恢复。');}});
  const help = el('details', 'tier-help tier-personal-help'), helpSummary = el('summary', '', '说明');
  helpSummary.setAttribute('aria-label', '查看手排操作说明');
  const helpBody = el('div', 'tier-help-body');
  helpBody.id = 'tier-personal-help-body'; helpBody.hidden = true;
  helpSummary.setAttribute('aria-controls', helpBody.id);
  help.addEventListener('toggle', () => {helpBody.hidden = !help.open;});
  helpBody.append(el('p', '', '拖动角色到档位或分界线；手机也可先点头像，再点位置。选中角色后可移回待排行，Esc 取消选择。'),
    el('p', '', '本地自动保存，点击提交才计入大家排行。每天可提交一次（北京时间换日），整份排行替换自己的旧票，公共榜次日更新。提交空榜可撤回旧票。'));
  help.append(helpSummary); toolbar.append(avatarControls, help, helpBody);
  page.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') select('');
    if (event.key === 'Delete' && selected && !event.target.closest('input,textarea,select,[role="combobox"],[role="listbox"]')) {
      event.preventDefault(); place(selected, 'pool');
    }
  });
  host.replaceChildren(page);
  community = window.WFTierListCommunity.create({host: page, data, ui, state, initialView: options.initialView});
  community.mineHost.append(toolbar, board, status, pool); render();
};
