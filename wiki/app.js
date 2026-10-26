/* A self-contained, file:// compatible catalogue. No network or build runtime required. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const list = (value) => Array.isArray(value) ? value : [];
  const object = (value) => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  const text = (value, fallback = '') => value === undefined || value === null || value === ''
    ? fallback : typeof value === 'object' ? JSON.stringify(value) : String(value);
  const el = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = text(value);
    return node;
  };
  const safeUrl = (value) => {
    if (typeof value !== 'string' || !value.trim() || /[\u0000-\u001f\\]/.test(value)) return '';
    const candidate = value.trim();
    if (/^[a-z][a-z\d+.-]*:/i.test(candidate) && !/^https?:\/\//i.test(candidate)) return '';
    return candidate;
  };
  const safeData = (value) => JSON.parse(JSON.stringify(value, (_key, item) =>
    typeof item === 'string' && /(?:[A-Za-z]:[\\/]|file:\/\/)/.test(item) ? '本地来源（路径已省略）' : item));
  const disclosure = (label, value) => {
    const node = el('details', 'data-disclosure');
    node.append(el('summary', '', label));
    node.addEventListener('toggle', () => {
      if (node.open && node.childElementCount === 1) {
        node.append(el('pre', '', JSON.stringify(safeData(value), null, 2)));
      }
    });
    return node;
  };
  const elementClasses = {'火': 'fire', '水': 'water', '雷': 'thunder', '风': 'wind', '光': 'light', '暗': 'dark'};
  const nativeIcon = (group, key, fallback, className = '') => {
    const url = safeUrl(object(object(meta.uiAssets)[group])[key]);
    if (!url) return el('span', `native-icon native-fallback ${className}`, fallback);
    const img = el('img', `native-icon ${className}`);
    img.src = url;
    img.alt = '';
    img.loading = 'lazy';
    img.decoding = 'async';
    img.addEventListener('error', () => img.replaceWith(el('span', 'native-fallback', fallback)), {once: true});
    return img;
  };
  const elementBadge = (value) => {
    const badge = el('span', `element-badge element-${elementClasses[value] || 'other'}`);
    badge.append(nativeIcon('elements', value, value || '?'), el('span', '', value || '未知'));
    return badge;
  };
  const picture = (url, alt, className) => {
    const src = safeUrl(url);
    if (!src) return el('span', 'image-placeholder', '✧');
    const img = el('img', className);
    img.src = src;
    img.alt = alt;
    img.loading = 'lazy';
    img.decoding = 'async';
    img.addEventListener('error', () => img.replaceWith(el('span', 'image-placeholder', '✧')), {once: true});
    return img;
  };
  const formatNumber = (value) => {
    if (value === undefined || value === null || value === '') return '—';
    const n = Number(value);
    return Number.isFinite(n) ? n.toLocaleString('zh-CN') : text(value);
  };
  const stars = (value) => '★'.repeat(Math.min(6, Math.max(0, Number(value) || 0)));
  const rarityBadge = (value) => {
    const badge = el('span', 'rarity-stars');
    const url = safeUrl(object(object(meta.uiAssets).rarities)[String(value)]);
    if (url) {
      const image = el('img'); image.src = url; image.alt = `${value}星`; image.loading = 'lazy'; image.decoding = 'async'; badge.append(image);
    } else badge.append(el('span', 'stars', stars(value)));
    badge.setAttribute('aria-label', `${text(value, '未知')}星`);
    return badge;
  };
  const categories = ['毛茸异世界', '原创与变体', '原版角色改动', '官方原版', 'Boss角色', '小动物'];
  const categoryDescriptions = {
    '毛茸异世界': '来自毛茸异世界的同行者。',
    '原创与变体': '原创角色与新增变体，按当前已生效资料收录。',
    '原版角色改动': '保留原版角色身份，逐项对照官方版本与当前修改。',
    '官方原版': '收录官方可玩角色，支持属性、主题与技能搜索。',
    'Boss角色': '以 Boss 为原型的可玩角色，查阅他们的技能与能力。',
    '小动物': '小动物批次的角色资料，也包括机器人与幽魂。',
  };
  const categoryName = (character) => categories.includes(character.category) ? character.category : '原创与变体';
  const data = object(window.WF_WIKI);
  const meta = object(data.meta);
  const characters = list(data.characters).filter((c) => c && typeof c === 'object' && c.id != null);
  const helpers = {el, list, object, text, safeUrl, safeData, disclosure, elementBadge, picture, formatNumber, stars, rarityBadge, nativeIcon, categoryName};
  let selectedCategory = '';
  const catalogDisclosure = window.WFCatalogDisclosure.create({catalog: $('catalog-view'), ui: helpers, onToggle: renderCatalog});
  const characterFilters = window.WFCharacterFilters.create({characters, ui: helpers,
    idPrefix: 'catalog-character', initiallyOpen: false, onChange: renderCatalog, onStateChange: filterChanged, onReset: clearFilters});
  $('catalog-character-filters').append(characterFilters.element);
  const catalogPortraits = window.WFPortraitCards.create({ui: helpers});
  const catalogAvatars = window.WFCatalogAvatars.create({host: $('catalog-avatar-controls'),
    catalog: $('catalog-view'), characters, ui: helpers, onChange: () => {
      if ($('catalog-view').dataset.layout === 'portrait') renderCatalog();
    }});
  const catalogRatings = window.WFCatalogRatings.create({characters, sort: $('sort-order'),
    host: $('catalog-view').querySelector('.catalog-list-toolbar'), ui: helpers, onChange: () => {
      catalogRatings.paintMounted($('character-grid'));
      if (catalogRatings.isRatingSort()) renderCatalog();
    }});
  const catalogViews = window.WFCatalogViews.create({host: $('catalog-view').querySelector('.catalog-list-toolbar'), ui: helpers, onChange: () => {
    catalogViews.paintMounted($('character-grid'));
    if (catalogSort.isViewsSort()) renderCatalog();
  }});
  const catalogSort = window.WFCatalogSort.create({sort: $('sort-order'), button: $('sort-direction'),
    ratings: catalogRatings, views: catalogViews, onChange: renderCatalog});
  let mountedCatalogKey = '', mountedPortraitForm = '';

  [['--frame-window', 'frames', 'window'], ['--frame-button', 'frames', 'button'], ['--frame-status', 'frames', 'status'], ['--game-detail-bg', 'backgrounds', 'detail']].forEach(([variable, group, key]) => {
    const url = safeUrl(object(object(meta.uiAssets)[group])[key]);
    if (url) document.documentElement.style.setProperty(variable, `url(${JSON.stringify(url)})`);
  });
  if (safeUrl(object(object(meta.uiAssets).frames).window)) document.documentElement.classList.add('native-ui');

  function renderMeta() {
    const counts = object(meta.counts);
    $('header-version').textContent = text(meta.version);
    $('nav-count').textContent = characters.length;
    const stats = [
      [counts.total ?? characters.length, '收录'],
      [counts.newMod ?? characters.filter((c) => c.origin === '新增MOD').length, '新增 MOD'],
      [counts.modifiedOfficial ?? characters.filter((c) => c.origin === '改版官方').length, '官方改版'],
    ];
    stats.forEach(([value, label]) => {
      const stat = el('div', 'hero-stat');
      stat.append(el('strong', '', formatNumber(value)), el('span', '', label));
      $('catalog-stats').append(stat);
    });
    $('snapshot-note').append(el('span', '', `数据版本 ${text(meta.version, '未记录')}`));
    if (meta.generatedAt) {
      const date = new Date(meta.generatedAt);
      const formatted = Number.isNaN(date.getTime()) ? text(meta.generatedAt) : date.toLocaleString('zh-CN', {hour12: false});
      $('snapshot-note').append(el('span', '', `导出于 ${formatted}`));
    }
    if (meta.dataNote) $('snapshot-note').append(el('p', '', text(meta.dataNote)));
    if (meta.rosterRule) {
      const scope = el('details', 'data-disclosure');
      scope.append(el('summary', '', '收录范围说明'), el('p', '', meta.rosterRule));
      $('snapshot-note').append(scope);
    }
  }

  function renderCategoryNavigation() {
    categories.forEach((category, index) => {
      const button = el('button', 'category-button');
      button.type = 'button';
      button.dataset.category = category;
      button.setAttribute('aria-pressed', 'false');
      const symbol = el('span', 'category-symbol', ['✧', '◇', '⇄', '◎', '✦', '❧'][index]);
      symbol.setAttribute('aria-hidden', 'true');
      button.append(symbol, el('span', 'category-label', category),
        el('span', 'count-badge', characters.filter((character) => categoryName(character) === category).length));
      button.addEventListener('click', () => { selectedCategory = category; applyFilters(); });
      $('category-nav').append(button);
    });
    $('all-categories').addEventListener('click', () => { selectedCategory = ''; applyFilters(); });
  }

  function card(character) {
    const link = el('a', 'character-card');
    link.dataset.rarity = text(character.rarity);
    link.href = `#character/${encodeURIComponent(String(character.id))}`;
    link.setAttribute('aria-label', `${text(character.name, '未命名角色')}，${text(character.rarity)}星，${text(character.element)}属性，查看详情`);
    link.title = `${text(character.name)} · ${text(character.rarity)}星 · ${text(character.element)}属性`;
    const art = el('div', 'card-art');
    const portraitMode = $('catalog-view').dataset.layout === 'portrait';
    art.append(portraitMode ? catalogPortraits.picture(character, catalogAvatars.getForm(), text(character.name))
      : catalogAvatars.picture(character), elementBadge(character.element));
    window.WFCharacterFrame?.apply(art, character);
    window.WFCharacterBadges?.append(art, character, {el});
    const content = el('div', 'card-content');
    const nameRow = el('div', 'card-name-row');
    nameRow.append(el('h4', 'card-name', text(character.name, '未命名角色')), rarityBadge(character.rarity));
    const details = el('div', 'card-meta'), profession = el('span', 'card-profession');
    profession.append(nativeIcon('types', character.type, ''), el('span', '', text(character.type, '—')));
    details.append(profession, el('span', 'card-stats'));
    content.append(el('div', 'card-title', text(character.title, character.origin)), nameRow, details);
    const footer = el('div', 'card-footer'), tags = el('div', 'card-tags');
    if (categoryName(character) === '原版角色改动' && list(character.aliases).length) tags.append(el('span', 'alias-tag', character.aliases[0]));
    list(character.themes || (character.theme ? [character.theme] : [])).forEach((theme) => tags.append(el('span', 'theme-tag', theme)));
    if (character.earlyDesign === true) tags.append(el('span', 'editor-tag', '早期方案'));
    footer.append(tags); content.append(footer);
    link.append(art, content);
    if (portraitMode) catalogPortraits.attach(link);
    catalogRatings.decorate(link, character);
    catalogViews.decorate(link, character);
    return link;
  }

  function filteredCharacters() {
    const selected = characters.filter((c) => (!selectedCategory || categoryName(c) === selectedCategory)
      && characterFilters.matches(c));
    return selected.sort(catalogSort.compare);
  }

  function renderCatalog() {
    if ($('catalog-view').hidden) return;
    if (catalogDisclosure.isOpen() || catalogRatings.isRatingSort()) catalogRatings.load();
    if (catalogDisclosure.isOpen() || catalogSort.isViewsSort()) catalogViews.load();
    const selected = filteredCharacters();
    const container = $('character-grid'), portraitMode = $('catalog-view').dataset.layout === 'portrait';
    // Only one rendered view is retained. Identical results reuse the image nodes,
    // including standard/dense switches; the router releases them on page leave.
    const key = JSON.stringify([selectedCategory, portraitMode, selected.map(character => String(character.id))]);
    if (!catalogDisclosure.isOpen()) catalogPortraits.pause();
    else {
      if (mountedCatalogKey !== key || (!container.children.length && selected.length)) {
        catalogPortraits.destroy();
        const fragment = document.createDocumentFragment();
        if (selected.length) {
          const category = selectedCategory || '全部角色', group = el('section', 'catalog-group');
          if (selectedCategory) {
            const title = el('h3', 'group-title', category); title.id = 'catalog-group-0';
            title.append(el('span', 'group-count', `${selected.length} 位`));
            group.setAttribute('aria-labelledby', title.id);
            group.append(title, el('p', 'group-description', categoryDescriptions[category]));
          }
          const grid = el('div', 'character-grid'); selected.forEach(character => grid.append(card(character)));
          group.append(grid); fragment.append(group);
        }
        container.replaceChildren(fragment); mountedCatalogKey = key; mountedPortraitForm = catalogAvatars.getForm();
      } else if (portraitMode && mountedPortraitForm !== catalogAvatars.getForm()) {
        const portraits = container.querySelectorAll('.portrait-card-media');
        selected.forEach((character, index) => catalogPortraits.paint(portraits[index], character, catalogAvatars.getForm(), text(character.name)));
        mountedPortraitForm = catalogAvatars.getForm();
      }
      catalogPortraits.resume();
    }
    document.querySelectorAll('.category-button').forEach((button) =>
      button.setAttribute('aria-pressed', String(button.dataset.category === selectedCategory)));
    $('all-categories').setAttribute('aria-current', selectedCategory ? 'false' : 'page');
    $('result-count').textContent = `${selected.length} / ${characters.length}`;
    const filtered = selectedCategory || characterFilters.hasActiveFilters();
    $('filter-status').textContent = !catalogDisclosure.isOpen() ? '点击角色列表展开，或使用上方筛选查找角色。' : filtered ? `${selectedCategory || '全部分类'} · 找到 ${selected.length} 位角色` : '选择角色查看详情；原版角色改动单独列出官方与当前版本的差异。';
    $('empty-state').hidden = !catalogDisclosure.isOpen() || selected.length > 0 || characters.length === 0;
    $('load-error').hidden = characters.length > 0;
  }

  const route = window.createWikiRouter({data, meta, ui: helpers, renderCatalog,
    onCatalogLeave: () => catalogPortraits.destroy()});

  function filterChanged(state = characterFilters.getState()) {
    catalogDisclosure.filterChanged(JSON.stringify([selectedCategory, state]),
      Boolean(selectedCategory || Object.values(state).some((value) => String(value).trim())));
  }
  function applyFilters() {
    filterChanged();
    renderCatalog();
    if (location.hash) location.hash = '';
  }

  function clearFilters() {
    selectedCategory = '';
    characterFilters.reset(false);
    renderCatalog();
  }

  renderCategoryNavigation();
  $('catalog-view').addEventListener('cataloglayoutchange', renderCatalog);
  $('empty-reset').addEventListener('click', clearFilters);
  window.addEventListener('hashchange', route);
  document.addEventListener('keydown', (event) => {
    if (event.key !== '/' || event.altKey || event.ctrlKey || event.metaKey || event.target.closest('input, textarea, select, [contenteditable="true"]')) return;
    const hash = location.hash.slice(1);
    if (hash === 'team') {
      const search = document.querySelector('#extra-view .character-filters:not([hidden]) .character-filter-search, #extra-view .team-weapon-search:not([hidden])');
      if (search) {event.preventDefault(); window.WFCharacterFilters.focusSearch(search);}
      return;
    }
    if (hash && !hash.startsWith('character/')) return;
    event.preventDefault();
    if (hash) {location.hash = ''; route();}
    characterFilters.focus();
  });
  document.addEventListener('play', (event) => {
    if (event.target.tagName === 'AUDIO') document.querySelectorAll('audio').forEach((audio) => {
      if (audio !== event.target) audio.pause();
    });
  }, true);
  renderMeta();
  window.WFWiki = {data, ui: helpers, refresh: route};
  route();
})();
