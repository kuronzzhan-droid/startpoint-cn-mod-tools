/* Shared weapon panels for the catalogue and an individual equipment page. */
(() => {
  'use strict';
  window.renderWikiWeaponPage = function (host, data, ui, entryId = '') {
    const {el} = ui;
    const categoryOrder = ['深渊武器', '诅咒武器', '悖论武器', '羁绊武器', '五重决战武器',
      '幻想武器', '女帝武器', '普莉莉艾武器', '机兵武器', '领主掉落与兑换',
      '临境域武器', '深层域武器', '装备扭蛋武器', '主线武器', '活动武器', '世界弹射器宝珠', '其他武器'];
    const categoryRank = (category) => {const rank = categoryOrder.indexOf(category); return rank < 0 ? categoryOrder.length : rank;};
    const equipmentCompare = window.WFEquipmentOrder.createCompare(data.equipment || []);
    const elementOrder = ['火', '水', '雷', '风', '光', '暗'];
    const elementRank = (entry) => {const rank = elementOrder.indexOf(entry.element); return rank < 0 ? elementOrder.length : rank;};
    const catalogueCompare = (a, b) => Number(Boolean(b.enhancement)) - Number(Boolean(a.enhancement))
      || (a.enhancement && b.enhancement ? elementRank(a) - elementRank(b) : 0) || equipmentCompare(a, b);
    const entries = [...(data.equipment || [])].filter((entry) => !entryId || entry.id === entryId)
      .sort((a, b) => categoryRank(a.category) - categoryRank(b.category) || catalogueCompare(a, b));
    const enhancedStates = new Map(), cards = new Map(), sections = new Map();
    const searchText = new Map(entries.map((entry) => [entry, JSON.stringify(entry).toLowerCase()]));
    const search = el('input'); search.type = 'search'; search.placeholder = '搜索武器、效果或关键词'; search.setAttribute('aria-label', '搜索武器');
    const filter = el('select'); filter.setAttribute('aria-label', '武器分类');
    const rarityFilter = el('select'); rarityFilter.setAttribute('aria-label', '武器星级');
    const rarities = [...new Set(entries.map((entry) => entry.rarity))].sort((a, b) => b - a);
    ['', ...rarities].forEach((rarity) => {
      const total = rarity === '' ? entries.length : entries.filter((entry) => entry.rarity === rarity).length;
      const option = el('option', '', `${rarity === '' ? '全部星级' : `${rarity}★`}（${total}）`);
      option.value = String(rarity); rarityFilter.append(option);
    });
    const enhancementFilter = el('select'); enhancementFilter.setAttribute('aria-label', '武器强化筛选');
    [['', '全部强化类型'], ['yes', '仅可强化武器'], ['no', '无强化武器']].forEach(([value, label]) => {const option = el('option', '', label); option.value = value; enhancementFilter.append(option);});
    const count = el('p', 'muted');
    const groups = el('div', 'equipment-groups');
    groups.id = 'weapon-catalogue-groups';
    const layoutKey = 'wf-wiki-equipment-layout-v2', layoutButtons = [];
    let layout = 'dense';
    try {if (localStorage.getItem(layoutKey) === 'standard') layout = 'standard';} catch {}
    function setLayout(value) {
      if (value === 'dense' && layout !== value) cards.forEach((card) => {card.open = false;});
      layout = value; groups.setAttribute('data-layout', layout);
      layoutButtons.forEach(({button, value: choice}) => button.setAttribute('aria-pressed', String(layout === choice)));
      try {localStorage.setItem(layoutKey, layout);} catch {}
    }
    const advanced = el('details', 'equipment-advanced-filters'), filterSummary = el('summary', '', '更多筛选');
    advanced.open = false;
    const filterFields = el('div', 'equipment-filter-fields'); filterFields.append(filter, rarityFilter, enhancementFilter);
    advanced.append(filterSummary, filterFields);
    ['全部武器', ...new Set(entries.map((entry) => entry.category))].forEach((label, i) => {
      const total = i ? entries.filter((entry) => entry.category === label).length : entries.length;
      const option = el('option', '', `${label}（${total}）`); option.value = i ? label : ''; filter.append(option);
    });
    const weaponCard = (entry) => window.WFEquipmentCard.create(entry, ui, {enhancedStates});
    let attributeFilter, groupToggle, groupToggleLabel;
    const visibleGroups = () => [...sections.values()].filter((group) => group.members.length);
    function syncGroupToggle() {
      if (!groupToggle) return;
      const shown = visibleGroups(), allOpen = Boolean(shown.length) && shown.every((group) => group.section.open);
      groupToggleLabel.textContent = allOpen ? '全部收起' : '全部展开';
      groupToggle.disabled = !shown.length;
      groupToggle.setAttribute('aria-expanded', String(allOpen));
      groupToggle.setAttribute('aria-checked', String(allOpen));
      groupToggle.title = groupToggle.disabled ? '没有符合筛选的武器' : `点击${groupToggle.textContent}当前筛选结果`;
    }
    function groupFor(category) {
      if (sections.has(category)) return sections.get(category);
      const section = el('details', 'equipment-group'), heading = el('summary', 'equipment-group-heading');
      const total = el('span', 'equipment-group-count'), content = el('div', 'equipment-group-body');
      section.open = false; heading.title = '点击展开或收起此分类';
      heading.append(el('h2', '', category), total); section.append(heading, content);
      const group = {section, total, members: [], mounted: []};
      group.mount = () => {
        const members = section.open ? group.members : [];
        if (members.length === group.mounted.length && members.every((entry, i) => entry === group.mounted[i])) return;
        const tiers = [];
        for (const enhanced of [true, false]) {
          const items = members.filter((entry) => Boolean(entry.enhancement) === enhanced);
          if (!items.length) continue;
          const tier = el('section', `equipment-tier ${enhanced ? 'equipment-tier-enhanceable' : 'equipment-tier-regular'}`);
          tier.append(el('h3', 'equipment-tier-heading', `${enhanced ? '可强化武器' : '普通武器'} · ${items.length} 件`));
          const grid = el('div', 'equipment-grid');
          grid.append(...items.map((entry) => {
            if (!cards.has(entry)) cards.set(entry, weaponCard(entry));
            return cards.get(entry);
          }));
          tier.append(grid); tiers.push(tier);
        }
        content.replaceChildren(...tiers);
        group.mounted = members;
      };
      section.addEventListener('toggle', () => {group.mount(); syncGroupToggle();});
      sections.set(category, group); return group;
    }
    function paint() {
      const q = search.value.trim().toLowerCase();
      const items = entries.filter((entry) => (!attributeFilter || attributeFilter.matches(entry)) && (!filter.value || entry.category === filter.value) &&
        (!rarityFilter.value || String(entry.rarity) === rarityFilter.value) &&
        (!enhancementFilter.value || Boolean(entry.enhancement) === (enhancementFilter.value === 'yes')) &&
        `${searchText.get(entry)} ${(window.WFWikiAliases?.values('weapon', entry.id) || []).join(' ').toLowerCase()}`.includes(q));
      count.textContent = `共 ${items.length} 件武器 · ${items.filter((entry) => entry.enhancement).length} 件可强化`;
      filterSummary.textContent = ['更多筛选', filter.value, rarityFilter.value ? `${rarityFilter.value}★` : '',
        enhancementFilter.value ? enhancementFilter.value === 'yes' ? '可强化' : '无强化' : ''].filter(Boolean).join(' · ');
      const grouped = new Map();
      items.forEach((entry) => {if (!grouped.has(entry.category)) grouped.set(entry.category, []); grouped.get(entry.category).push(entry);});
      sections.forEach((group, category) => {if (!grouped.has(category)) {group.members = []; group.mount();}});
      const shown = [];
      grouped.forEach((members, category) => {
        const group = groupFor(category), enhanced = members.filter((entry) => entry.enhancement).length;
        group.members = members; group.total.textContent = `${members.length} 件${enhanced ? ` · ${enhanced} 件可强化` : ''}`;
        group.mount(); shown.push(group.section);
      });
      if (!items.length) shown.push(el('p', 'equipment-empty', '没有符合条件的武器，请调整分类或搜索词。'));
      groups.replaceChildren(...shown);
      syncGroupToggle();
    }
    search.addEventListener('input', paint); filter.addEventListener('change', paint); rarityFilter.addEventListener('change', paint); enhancementFilter.addEventListener('change', paint);
    if (entryId) {
      const back = el('a', 'back-button', '‹ 返回武器图鉴'); back.href = '#weapons';
      host.replaceChildren(back);
      if (!entries.length) {host.append(el('p', 'note-box', '未找到这件武器。')); return;}
      const entry = entries[0], card = weaponCard(entry); card.open = true;
      document.title = `${entry.name} · 星见图鉴`;
      host.append(el('h1', '', entry.name)); window.WFWikiAliases?.mount(host, 'weapon', entry.id, ui); host.append(card); return;
    }
    groupToggle = el('button', 'equipment-attribute-shortcut equipment-group-toggle'); groupToggle.type = 'button';
    groupToggle.setAttribute('role', 'switch');
    groupToggle.setAttribute('aria-label', '展开全部武器分类');
    groupToggle.setAttribute('aria-controls', groups.id);
    const groupToggleTrack = el('span', 'equipment-mode-track'); groupToggleTrack.setAttribute('aria-hidden', 'true');
    groupToggleTrack.append(el('span', 'equipment-mode-thumb'));
    groupToggleLabel = el('span', 'equipment-group-toggle-label'); groupToggle.append(groupToggleTrack, groupToggleLabel);
    groupToggle.addEventListener('click', () => {
      const shown = visibleGroups(), open = shown.some((group) => !group.section.open);
      shown.forEach((group) => {group.section.open = open; group.mount();});
      syncGroupToggle();
    });
    const toolbar = el('div', 'equipment-toolbar'); attributeFilter = window.WFEquipmentAttributeFilter.create(ui, paint, groupToggle);
    const searchRow = el('div', 'equipment-search-row'); searchRow.append(search, attributeFilter.button); toolbar.append(searchRow, advanced);
    const layoutControls = el('div', 'equipment-layout-controls'); layoutControls.setAttribute('role', 'group'); layoutControls.setAttribute('aria-label', '武器排列');
    [['standard', '标准', 9], ['dense', '致密', 12]].forEach(([value, label, cells]) => {
      const button = el('button', 'catalog-layout-button equipment-layout-button'); button.type = 'button';
      button.setAttribute('aria-label', `武器${label}排列`); button.title = value === 'dense' ? '只显示图标，点击查看完整资料' : '显示武器名称、面板与强化选项';
      const icon = el('span', `catalog-layout-icon catalog-layout-icon-${cells}`); icon.setAttribute('aria-hidden', 'true');
      for (let i = 0; i < cells; i++) icon.append(el('span'));
      button.append(icon, el('span', '', label)); button.addEventListener('click', () => setLayout(value));
      layoutButtons.push({button, value}); layoutControls.append(button);
    });
    const resultBar = el('div', 'equipment-result-bar'); resultBar.append(count, layoutControls);
    const header = el('header', 'equipment-page-header'), help = el('details', 'equipment-help'); help.open = false;
    help.append(el('summary', '', '使用说明'), el('p', '', '默认查看满级效果与最高强化图标。点击分类展开；致密排列中点击图标查看资料，并可切换武器／魂珠、强化形态和效果等级。可强化武器优先，同组按属性、高星和图鉴倒序排列。'));
    header.append(el('h1', '', '武器图鉴'), help);
    host.replaceChildren(header, toolbar, resultBar, groups, attributeFilter.floating);
    setLayout(layout); paint();
    window.WFWikiAliases?.watch(host, paint);
  };
})();
