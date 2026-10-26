/* Shared character search/filter controls for the catalogue and team picker. */
(() => {
  'use strict';
  const fields = ['element', 'rarity', 'type', 'origin'];
  const elements = ['火', '水', '雷', '风', '光', '暗'];
  const normalized = (value) => String(value ?? '').normalize('NFKC').toLocaleLowerCase('zh-CN');
  const searchIndex = new WeakMap();
  const searchText = (character) => {
    const full = window.WFWikiData?.searchIndex()?.get(String(character.id));
    if (full !== undefined) return full;
    if (!searchIndex.has(character)) searchIndex.set(character, normalized(JSON.stringify(character)));
    return searchIndex.get(character);
  };
  function focusSearch(search) {
    const panel = search.closest('details.character-filters');
    if (panel) panel.open = true;
    search.focus();
  }
  function create({characters, ui, idPrefix, onChange = () => {}, onStateChange = () => {}, onReset, initialState = {}, collapsible = true, initiallyOpen = true}) {
    const {el, nativeIcon} = ui;
    const state = Object.fromEntries(['search', ...fields].map((key) => [key, String(initialState[key] ?? '')]));
    const root = el(collapsible ? 'details' : 'div', 'character-filters'); root.open = initiallyOpen;
    const heading = el('summary', 'character-filter-heading'); heading.append(el('h3', '', '查找角色'));
    const hint = el('span', 'character-filter-toggle-hint', initiallyOpen ? '收起 ▴' : '展开 ▾'); hint.setAttribute('aria-hidden', 'true');
    heading.append(hint);
    root.addEventListener('toggle', () => {hint.textContent = root.open ? '收起 ▴' : '展开 ▾';});
    const body = el('div', 'character-filter-body');
    const searchRow = el('div', 'character-filter-search-row');
    const resetButton = el('button', 'text-button', '重置筛选'); resetButton.type = 'button';
    const searchLabel = el('label', 'character-filter-search-label', '名字、别名、主题或技能');
    searchLabel.htmlFor = `${idPrefix}-search`;
    const search = el('input', 'character-filter-search'); search.id = searchLabel.htmlFor;
    search.type = 'search'; search.placeholder = '搜索名字、别名、主题或技能…'; search.autocomplete = 'off';
    const help = el('span', 'character-filter-search-help', '支持多关键词，以空格分隔'); help.id = `${idPrefix}-search-help`;
    search.setAttribute('aria-describedby', help.id); search.title = help.textContent;
    searchRow.append(searchLabel, search, resetButton, help);
    const elementRow = el('div', 'character-filter-elements'); elementRow.setAttribute('role', 'group'); elementRow.setAttribute('aria-label', '角色属性');
    const elementButtons = [];
    const selects = {};
    const choices = el('div', 'character-filter-fields');
    const searchStatus = el('p', 'character-filter-help'); searchStatus.setAttribute('role', 'status');
    const retry = el('button', 'text-button', '重试完整搜索'); retry.type = 'button'; retry.hidden = true;
    let searchTimer;
    let searchRevision = 0;
    const notify = async () => {
      clearTimeout(searchTimer);
      onStateChange({...state});
      const ticket = ++searchRevision;
      retry.hidden = true; searchStatus.textContent = '';
      if (state.search.trim() && window.WFWikiData && !window.WFWikiData.searchIndex()) {
        searchStatus.textContent = '正在载入技能与台词搜索…';
        try {await window.WFWikiData.loadSearchIndex();}
        catch {
          if (ticket !== searchRevision) return;
          searchStatus.textContent = '完整检索暂未载入，当前仅搜索基础资料。'; retry.hidden = false;
        }
      }
      if (ticket !== searchRevision || !root.isConnected) return;
      if (retry.hidden) searchStatus.textContent = '';
      onChange({...state});
    };
    retry.addEventListener('click', notify);
    function sync() {
      search.value = state.search;
      Object.entries(selects).forEach(([key, select]) => {select.value = state[key];});
      elementButtons.forEach(({button, value}) => button.setAttribute('aria-pressed', String(value === state.element)));
    }
    ['', ...elements].forEach((value) => {
      const button = el('button', 'character-filter-element'); button.type = 'button';
      button.setAttribute('aria-label', value ? `${value}属性` : '全部属性');
      button.title = value ? `${value}属性` : '全部属性';
      if (value) button.append(nativeIcon('elements', value, value));
      else button.append(el('span', '', '全部'));
      button.addEventListener('click', () => {state.element = value; sync(); notify();});
      elementButtons.push({button, value}); elementRow.append(button);
    });
    [['rarity', '星级', '全部星级'], ['type', '战斗类型', '全部类型'], ['origin', '收录来源', '全部来源']].forEach(([key, label, allLabel]) => {
      const field = el('label', 'character-filter-field'); field.htmlFor = `${idPrefix}-${key}`;
      field.append(el('span', '', label));
      const select = el('select'); select.id = field.htmlFor; select.setAttribute('aria-label', label);
      const all = el('option', '', allLabel); all.value = ''; select.append(all);
      const values = [...new Set(characters.map((character) => String(character[key] ?? '')).filter(Boolean))];
      if (key === 'rarity') values.sort((a, b) => Number(b) - Number(a));
      values.forEach((value) => {const option = el('option', '', key === 'rarity' ? `${value} 星` : value); option.value = value; select.append(option);});
      if (!values.includes(state[key])) state[key] = '';
      select.addEventListener('change', () => {state[key] = select.value; notify();});
      selects[key] = select; field.append(select); choices.append(field);
    });
    if (!elements.includes(state.element)) state.element = '';
    function reset(emit = true) {
      searchRevision++; searchStatus.textContent = ''; retry.hidden = true;
      clearTimeout(searchTimer);
      Object.keys(state).forEach((key) => {state[key] = '';}); sync();
      onStateChange({...state});
      if (emit) notify();
    }
    resetButton.addEventListener('click', () => {reset(false); if (onReset) onReset(); else notify();});
    search.addEventListener('input', () => {state.search = search.value; onStateChange({...state}); clearTimeout(searchTimer); searchTimer = setTimeout(notify, 80);});
    body.append(searchRow, searchStatus, retry, elementRow, choices);
    // Move the actual nodes so keyboard order follows the mobile catalogue layout.
    // The team picker retains its own order and never installs a viewport listener.
    if (idPrefix === 'catalog-character' && window.matchMedia) {
      const mobile = window.matchMedia('(max-width:640px)');
      const arrange = () => {
        const last = mobile.matches ? elementRow : choices;
        if (body.lastElementChild === last) return;
        const focused = document.activeElement;
        body.append(last);
        if (focused && last.contains(focused)) focused.focus({preventScroll: true});
      };
      mobile.addEventListener('change', arrange); arrange();
    }
    if (collapsible) root.append(heading);
    root.append(body);
    sync();
    window.WFWikiAliases?.watch(root, () => onChange({...state}));
    if (state.search.trim()) queueMicrotask(notify);
    return {
      element: root, search,
      matches(character) {
        return fields.every((key) => !state[key] || String(character[key] ?? '') === state[key])
          && normalized(state.search).trim().split(/\s+/).filter(Boolean).every((term) =>
            `${searchText(character)} ${normalized((window.WFWikiAliases?.values('character', character.id) || []).join(' '))}`.includes(term));
      },
      hasActiveFilters: () => Object.values(state).some((value) => value.trim()),
      getState: () => ({...state}),
      clearSearch(emit = true) {clearTimeout(searchTimer); searchRevision++; state.search = ''; searchStatus.textContent = ''; retry.hidden = true; sync(); if (emit) notify();},
      focus: () => focusSearch(search), reset,
    };
  }
  window.WFCharacterFilters = {create, focusSearch};
})();
