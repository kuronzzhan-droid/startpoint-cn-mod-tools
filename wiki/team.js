/* Editing stays local; administrator collection is a separate explicit action. */
(() => {
  'use strict';
  const S = window.WFTeamState;
  let team = S.empty(), undo = [], chosen = {group: 'main', index: 0};
  let inspected = {group: 'main', index: 0};
  let characterFilterState = {}, equipmentFilterState = {}, name = '我的队伍';
  const labels = {main: '主位', unison: '合击', weapon: '装备', soul: '魂珠'};
  let imported;
  function arrangePanels() {
    if (!window.matchMedia) return;
    const layout = document.querySelector('#extra-view .team-layout');
    if (!layout) return;
    const mode = window.matchMedia('(max-width:820px)').matches ? 'phone'
      : window.matchMedia('(max-width:1150px)').matches ? 'narrow' : 'wide';
    if (layout.dataset.order === mode) return;
    const main = layout.querySelector('.team-main'), board = layout.querySelector('.team-board');
    const library = layout.querySelector('.team-library');
    const inspector = layout.querySelector('.team-inspector-scroll-region') || layout.querySelector('.team-inspector');
    if (!inspector) return;
    const focused = document.activeElement, keepFocus = layout.contains(focused);
    // Move existing panels so Tab order follows the responsive visual order.
    if (mode === 'wide') {main.append(board); layout.append(inspector, main, library);}
    else if (mode === 'narrow') layout.append(inspector, board, library, main);
    else layout.append(board, library, inspector, main);
    layout.dataset.order = mode;
    if (keepFocus) focused.focus({preventScroll:true});
  }
  window.addEventListener?.('resize', arrangePanels);
  window.WFTeamImport = {load(value, title, selection) {imported = {team: S.copy(value), title, selection};}};
  window.renderWikiTeam = (host, data, ui) => {
    window.WFTeamScrollRail?.reset();
    const {el, picture, elementBadge} = ui;
    const characters = new Map(data.characters.map((c) => [String(c.id), c]));
    const equipment = new Map((data.equipment || []).map((w) => [String(w.id), w]));
    const equipmentCompare = window.WFEquipmentOrder.createCompare(data.equipment || []);
    const sortedCharacters = [...characters.values()].sort(window.WFCharacterOrder.compareTeam);
    const sortedEquipment = [...equipment.values()].sort(equipmentCompare);
    let matchedCharacters, matchedEquipment, equipmentTarget = 'weapon';
    if (imported) {
      undo.push(S.copy(team));
      team = S.validate(imported.team, characters, equipment);
      name = String(imported.title || '推荐队伍').slice(0, 60);
      inspected = ['main','unison'].includes(imported.selection?.group) && [0,1,2].includes(imported.selection?.index)
        ? {...imported.selection} : {group:'main',index:0}; imported = null;
    }
    team = S.validate(team, characters, equipment);
    const board = el('div', 'team-board game-panel');
    const library = el('section', 'team-library game-panel');
    const controls = el('div', 'team-controls team-toolbar'); controls.setAttribute('aria-label', '队伍操作');
    const status = el('p', 'team-status'); status.setAttribute('role', 'status');
    const avatarControls = el('div', 'team-avatar-controls');
    const avatars = window.WFCatalogAvatars?.create({host: avatarControls, catalog: host,
      characters: data.characters, ui, label: '编队头像'});
    const inspector = window.WFTeamInspector?.create(data, ui, avatars);
    const title = el('input', 'team-name-input'); title.value = name; title.maxLength = 60; title.setAttribute('aria-label', '队伍名称');
    title.addEventListener('input', () => {name = title.value;});
    const boardHeading = el('div', 'team-board-heading'); boardHeading.append(el('h2', '', '队伍编成'), title);
    function button(label, action, className = 'secondary-button') {
      const b = el('button', className, label); b.type = 'button'; b.addEventListener('click', action); return b;
    }
    function change(next) {
      if (JSON.stringify(next) === JSON.stringify(team)) {paintBoard(); return;}
      undo.push(S.copy(team)); undo = undo.slice(-50); team = next; paintBoard();
    }
    function assign(id, kind = '') {
      const expected = S.isCharacter(chosen.group) ? 'character' : 'equipment';
      if (kind && kind !== expected) {status.textContent = '请把角色放入主位或合击位，把武器放入装备或魂珠槽。'; return;}
      if (S.isCharacter(chosen.group)) inspected = {...chosen};
      change(S.place(team, chosen.group, chosen.index, id, characters, equipment));
    }
    function chooseSlot(group, index) {
      chosen = {group, index};
      if (!S.isCharacter(group)) equipmentTarget = group;
    }
    const picker = el('select', 'team-saved-picker'); picker.setAttribute('aria-label', '已保存队伍');
    let pickerRecords = [];
    function refreshSaved() {
      try {
        pickerRecords = saved.records(); picker.replaceChildren(el('option', '', '快速装入'));
        pickerRecords.forEach((item) => {const o = el('option', '', item.name || '未命名队伍'); o.value = String(item.key); picker.append(o);});
        picker.options[0].value = '';
      } catch (error) {status.textContent = error.message;}
    }
    function loadSaved(item) {
      change(S.validate(item.team, characters, equipment)); name = item.name || '我的队伍'; title.value = name;
      status.textContent = `已装入「${name}」。`;
    }
    const saved = window.WFTeamSaved.create({ui, characters, avatars,
      getCurrent: () => ({name, team: S.copy(team)}), onLoad: loadSaved,
      onChange: refreshSaved, onStatus: message => {status.textContent = message;}});
    picker.addEventListener('change', () => {
      const item = pickerRecords.find(record => String(record.key) === picker.value);
      if (item && picker.value !== '') saved.load(item);
    });
    controls.append(button('保存队伍', () => saved.save(), 'primary-button'), button('已保存队伍', () => saved.open()), picker,
      button('撤销', () => {if (undo.length) {team = undo.pop(); paintBoard();}}),
      button('清空队伍', () => change(S.empty())));
    const collect = button('管理员保存队伍', () => window.WFCommunity.openSubmit({team: S.copy(team), title: name, data, ui}), 'primary-button');
    collect.hidden = true; controls.append(collect);
    window.WFCommunity?.client?.request('/admin/me').then((identity) => {
      if (identity?.id && identity?.email && controls.isConnected) collect.hidden = false;
    }).catch(() => {});
    const recommendations = el('a', 'text-button', '查看配队大全'); recommendations.href = '#community'; controls.append(recommendations);
    controls.append(avatarControls);
    const codeLookup = el('details', 'team-code-lookup'); codeLookup.open = false;
    codeLookup.append(el('summary', 'text-button', '查询 Wiki 队伍码'));
    codeLookup.addEventListener('toggle', () => {
      if (codeLookup.open && codeLookup.children.length === 1) codeLookup.append(window.WFCommunity.codeSearch({data, ui, previewOnly:true}));
    });
    function paintBoard() {
      board.replaceChildren(boardHeading);
      const grid = el('div', 'team-columns');
      for (let index = 0; index < 3; index++) {
        const column = el('div', 'team-column'); column.setAttribute('role', 'group'); column.setAttribute('aria-label', `${index + 1}号位`);
        const stack = el('div', 'team-card-stack'); column.append(stack);
        if (index === 0) stack.append(el('span', 'team-leader-flag', '队长'));
        for (const group of ['main', 'weapon', 'soul', 'unison']) {
          const source = S.isCharacter(group) ? characters : equipment;
          const item = source.get(team[group][index]);
          const wrap = el('div', `team-slot-wrap team-slot-wrap-${group}`);
          const slot = item && !S.isCharacter(group) ? el('a', `team-slot team-slot-${group}`)
            : item ? button('', () => {inspected = {group,index}; paintBoard();}, `team-slot team-slot-${group}`)
            : button('', () => {chooseSlot(group, index); paintBoard(); paintLibrary();}, `team-slot team-slot-${group}`);
          if (item && !S.isCharacter(group)) {
            slot.href = `#weapon/${encodeURIComponent(item.id)}`;
            slot.addEventListener('click', () => window.WFTeamInspector?.remember('weapon', item.id));
          }
          if (item && S.isCharacter(group)) slot.setAttribute('aria-current', String(inspected.group === group && inspected.index === index));
          slot.classList.toggle('selected', chosen.group === group && chosen.index === index);
          slot.setAttribute('aria-label', `${index + 1}号${labels[group]}：${item?.name || '空位'}`);
          slot.title = `${labels[group]} · ${item?.name || '点击选择或拖入'}`;
          slot.append(el('span', 'team-slot-label', labels[group]));
          if (item) {
            slot.append(S.isCharacter(group) && avatars ? avatars.picture(item, item.name, 'team-slot-image')
              : picture(item.icon, item.name, 'team-slot-image'));
            if (S.isCharacter(group)) {
              slot.append(elementBadge(item.element));
              window.WFCharacterFrame?.apply(slot, item);
              window.WFCharacterBadges?.append(slot, item, ui);
            }
          } else slot.append(el('span', 'team-slot-empty', '+'));
          slot.querySelectorAll('img').forEach((img) => {img.draggable = false;});
          slot.draggable = Boolean(item);
          slot.addEventListener('dragstart', (event) => {event.dataTransfer.setData('application/x-wf-wiki', JSON.stringify({id: team[group][index], kind: S.isCharacter(group) ? 'character' : 'equipment'}));});
          slot.addEventListener('dragover', (event) => {event.preventDefault(); slot.classList.add('drag-over');});
          slot.addEventListener('dragleave', () => slot.classList.remove('drag-over'));
          slot.addEventListener('drop', (event) => {
            event.preventDefault(); slot.classList.remove('drag-over');
            try {
              const value = JSON.parse(event.dataTransfer.getData('application/x-wf-wiki'));
              if (value.kind !== (S.isCharacter(group) ? 'character' : 'equipment')) {
                status.textContent = '角色只能放入主位或合击位，武器只能放入装备或魂珠槽。'; return;
              }
              chooseSlot(group, index); assign(value.id, value.kind); paintBoard(); paintLibrary();
            }
            catch {status.textContent = '请从本页角色或武器列表拖入。';}
          });
          wrap.append(slot);
          if (item) {
            const replace = button('换', () => {chooseSlot(group, index); paintBoard(); paintLibrary();}, 'team-slot-replace');
            replace.setAttribute('aria-label', `替换${index + 1}号${labels[group]}`); replace.title = `替换${labels[group]}`; wrap.append(replace);
          }
          if (item) {const remove = button('×', () => change(S.place(team, group, index, '', characters, equipment)), 'team-slot-remove'); remove.setAttribute('aria-label', `移除${index + 1}号${labels[group]}`); remove.title = `移除${labels[group]}`; wrap.append(remove);}
          stack.append(wrap);
        }
        grid.append(column);
      }
      board.append(grid); inspector?.show(team[inspected.group][inspected.index]);
      candidatePools.select(S.isCharacter(chosen.group) ? 'character' : 'equipment', team[chosen.group][chosen.index]);
    }
    const equipmentFilters = window.WFTeamEquipmentFilters.create({equipment:[...equipment.values()], ui,
      initialState:equipmentFilterState, onStateChange:(state) => {equipmentFilterState = state;}, onChange:() => {matchedEquipment = null; paintLibrary();}});
    const characterFilters = window.WFCharacterFilters.create({characters: [...characters.values()], ui,
      idPrefix: 'team-character', initialState: characterFilterState, collapsible: false,
      onStateChange: (state) => {characterFilterState = state;}, onChange: () => {matchedCharacters = null; paintLibrary();}});
    const modeSwitch = el('div', 'team-mode-switch'); modeSwitch.setAttribute('role', 'group'); modeSwitch.setAttribute('aria-label', '候选类别');
    function switchMode(mode) {
      if ((mode === 'character' && S.isCharacter(chosen.group)) || chosen.group === mode) return;
      chooseSlot(mode === 'character' ? 'main' : mode, chosen.index); paintBoard(); paintLibrary();
    }
    const characterButton = button('角色', () => switchMode('character'), 'team-mode-button');
    const equipmentButton = button('武器·魂珠', () => switchMode(equipmentTarget), 'team-mode-button');
    modeSwitch.append(characterButton, equipmentButton);
    const targets = el('div', 'team-equipment-targets'); targets.setAttribute('role', 'group'); targets.setAttribute('aria-label', '装配目标');
    const weaponButton = button('装备', () => switchMode('weapon'), 'team-mode-button');
    const soulButton = button('魂珠', () => switchMode('soul'), 'team-mode-button');
    weaponButton.setAttribute('aria-label', '装配到装备'); soulButton.setAttribute('aria-label', '装配到魂珠');
    targets.append(el('span', '', '装配到'), weaponButton, soulButton);
    const candidatePools = window.WFTeamCandidates.create({ui, avatars, onAssign:assign});
    const heading = el('h2'), libraryHeading = el('div', 'team-library-heading'); libraryHeading.append(heading, modeSwitch);
    library.append(libraryHeading, targets, characterFilters.element, equipmentFilters.element, candidatePools.element);
    function paintLibrary() {
      const characterMode = S.isCharacter(chosen.group);
      heading.textContent = `选择${labels[chosen.group]} · ${chosen.index + 1}号位`;
      characterButton.setAttribute('aria-pressed', String(characterMode));
      equipmentButton.setAttribute('aria-pressed', String(!characterMode));
      weaponButton.setAttribute('aria-pressed', String(chosen.group === 'weapon'));
      soulButton.setAttribute('aria-pressed', String(chosen.group === 'soul'));
      characterFilters.element.hidden = !characterMode;
      equipmentFilters.element.hidden = characterMode; targets.hidden = characterMode;
      if (!characterMode) equipmentFilters.setMode(chosen.group);
      // Sorting is fixed for this catalogue; only filter and alias changes invalidate matches.
      const items = characterMode ? (matchedCharacters ||= sortedCharacters.filter(characterFilters.matches))
        : (matchedEquipment ||= sortedEquipment.filter(equipmentFilters.matches));
      candidatePools.show(characterMode ? 'character' : 'equipment', items, chosen.group, team[chosen.group][chosen.index]);
    }
    const mainColumn = el('div', 'team-main'); mainColumn.append(board);
    const layout = el('div', 'team-layout');
    if (inspector) layout.append(window.WFTeamScrollRail?.wrap(inspector.element, ui, '角色面板', 'team-inspector-scroll-region') || inspector.element);
    layout.append(mainColumn, library);
    const help = el('details', 'team-help'); help.open = false;
    const helpTitle = el('summary'); helpTitle.append(el('h1', '', '配队模拟'));
    help.append(helpTitle, el('p', 'section-intro', '拖拽头像到槽位，或点空位／「换」后选择候选。点击盘中的角色头像，在角色面板查看技能与能力；第一列主位为队长。'),
      el('p', 'muted', '用于编成与查阅效果；主位限制、触发条件和武器特殊规则请结合说明判断。本页不模拟战斗过程或计算实战伤害。'));
    host.replaceChildren(help, controls, status, codeLookup, layout);
    refreshSaved(); paintBoard(); paintLibrary(); arrangePanels();
  };
})();
