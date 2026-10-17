/* Dungeon snapshots stay readable when the separately managed guides are offline. */
(() => {
  'use strict';
  const categories = ['活动', '领主战', '降临讨伐', '模式'];
  const compactCategory = (value) => value === '领主战' || value === '降临讨伐';
  const directoryPriority = (item) => item.id === 'series-gauntlets' ? 0 : item.legacyGuide === 'five-boss' ? 1 : 2;
  const validId = (value) => typeof value === 'string' && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value);
  function imageUrl(value) {
    if (typeof value !== 'string' || !value || /[\\\u0000-\u001f]/.test(value)) return '';
    try {
      const parsed = new URL(value, window.location.href);
      if (window.location.protocol === 'file:' && /^media\/(?:[a-zA-Z0-9_-]+\/)*[a-zA-Z0-9_-]+\.(?:png|jpe?g|webp)$/.test(value)) return parsed.href;
      return /^https?:$/.test(parsed.protocol) && parsed.origin === window.location.origin && !parsed.username && !parsed.password ? parsed.href : '';
    } catch {return '';}
  }
  function image(ui, source, label, cls = '') {
    const url = imageUrl(source); if (!url) return null;
    const node = ui.el('img', cls); node.src = url; node.alt = label; node.loading = 'lazy'; node.decoding = 'async';
    node.addEventListener('error', () => {node.hidden = true;}); return node;
  }
  function button(ui, label, action, cls = 'secondary-button') {
    const node = ui.el('button', cls, label); node.type = 'button'; node.addEventListener('click', action); return node;
  }
  function recommendation(item, data, ui) {
    const C = window.WFCommunity, card = ui.el('article', 'dungeon-team-card');
    const link = ui.el('a', 'dungeon-team-link'); link.href = `#community/${encodeURIComponent(item.id)}`;
    link.append(ui.el('h3', '', item.title || '未命名队伍'));
    const meta = [item.element, C?.categoryLabel?.(item.category)].filter(Boolean).join(' · ');
    if (meta) link.append(ui.el('p', 'muted', meta));
    if (C?.board) link.append(C.board(item.team, data, ui, {preview:true}));
    link.setAttribute('aria-label', `查看推荐队伍：${item.title || '未命名队伍'}`); card.append(link);
    const code = window.WFCommunityGameCodes?.readonly(item, ui, {compact:true});
    if (code) card.append(code);
    return card;
  }
  function guideView(host, result, data, ui) {
    const {el} = ui, guide = result?.guide || {}, text = el('p', 'dungeon-guide-text', guide.text || '攻略待管理员补充。');
    const article = el('section', 'dungeon-guide'), gallery = el('div', 'dungeon-gallery');
    article.append(el('h2', '', '副本攻略'), text);
    for (const [index, item] of (Array.isArray(guide.images) ? guide.images : []).entries()) {
      const img = image(ui, item.url, `攻略图片 ${index + 1}`); if (!img) continue;
      const link = el('a', 'dungeon-image-link'); link.href = img.src; link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.append(img); gallery.append(link);
    }
    if (gallery.children.length) article.append(gallery);
    const teams = el('section', 'dungeon-recommendations'), grid = el('div', 'dungeon-team-grid');
    teams.append(el('h2', '', '推荐队伍'));
    const items = Array.isArray(result?.teams) ? result.teams : [];
    for (const item of items) if (item?.id) grid.append(recommendation(item, data, ui));
    teams.append(items.length ? grid : el('p', 'muted', '暂无推荐队伍，管理员可以关联已收录的公开盘。'));
    host.replaceChildren(article, teams);
  }
  function sourceNote(ui, source) {
    const labels = {verified:'已核对', 'gray-verified':'灰服已核对', snapshot:'资料快照', 'local-snapshot':'本地资料快照', partial:'部分资料待补', unverified:'待核对'};
    const status = /[\u3400-\u9fff]/.test(source?.status || '') ? source.status : labels[source?.status] || '';
    const label = [source?.label, source?.checkedAt ? `核对于 ${source.checkedAt}` : '', status].filter(Boolean).join(' · ');
    return ui.el('p', 'dungeon-source muted', label || '副本资料快照');
  }
  function catalog(host, snapshot, ui) {
    const {el} = ui, header = el('header', 'dungeon-header'), toolbar = el('div', 'dungeon-toolbar');
    header.append(el('h1', '', '副本与模式'));
    const shopLink = el('a', 'dungeon-shops-entry', '兑换商店 ›'); shopLink.href = '#shops'; header.append(shopLink);
    const battleLink = el('a', 'dungeon-shops-entry', '放置挑战 ›'); battleLink.href = '#battle'; header.append(battleLink);
    const search = el('input', 'dungeon-search'); search.type = 'search'; search.placeholder = '查找活动、副本或模式…'; search.setAttribute('aria-label', '查找副本或模式');
    const filters = el('div', 'dungeon-categories'); filters.setAttribute('role', 'group'); filters.setAttribute('aria-label', '副本分类');
    const grid = el('div', 'dungeon-grid dungeon-grid-compact'), status = el('p', 'dungeon-result-count muted'); status.setAttribute('role', 'status');
    const sourceItems = (snapshot.items || []).filter((item) => validId(item.id));
    const entries = window.WFDungeonSeries?.entries(sourceItems) || sourceItems;
    // Pin after aggregation so normal abyss, EX and fantasy still share one entry.
    const items = [...entries].sort((a, b) => directoryPriority(a) - directoryPriority(b)), cards = [];
    let category = '';
    const choices = [['', '全部'], ...categories.map((value) => [value, value])].map(([value, label]) => {
      const node = button(ui, label, () => {category = value; filter();}, 'dungeon-category');
      filters.append(node); return {node, value};
    });
    for (const item of items) {
      const node = el('a', `dungeon-card dungeon-card-compact${item.members ? ' dungeon-series-card' : ''}`); node.href = `#dungeons/${encodeURIComponent(item.id)}`;
      const art = el('div', 'dungeon-card-art'), banner = image(ui, item.entryImage || item.banner, item.title || '副本入口');
      if (banner) art.append(banner); else art.append(el('span', 'dungeon-art-placeholder', item.category || '副本'));
      const title = item.id === 'series-gauntlets' && item.variants
        ? item.variants.map(({label}) => label.replace('普通深渊', '深渊').replace('连战', '')).join(' · ') : item.title;
      const info = el('div', 'dungeon-card-info'), name = el('h2', '', title); name.title = title;
      info.append(name, el('p', 'dungeon-card-count', item.countText || `${item.category} · ${item.quests?.length || 0} 个关卡`));
      node.append(art, info); grid.append(node);
      const members = item.members || [item];
      cards.push({node, categories:item.categories || [item.category], search: `${item.title || ''} ${item.summary || ''} ${members.map((member) => `${member.title || ''} ${member.summary || ''} ${(member.quests || []).map((quest) => quest.name || '').join(' ')}`).join(' ')}`.toLowerCase()});
    }
    function filter() {
      const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean); let count = 0;
      for (const card of cards) {card.node.hidden = Boolean(category && !card.categories.includes(category)) || !words.every((word) => card.search.includes(word)); if (!card.node.hidden) count++;}
      choices.forEach(({node, value}) => node.setAttribute('aria-pressed', String(category === value)));
      status.textContent = `${count} 个入口${count ? '' : '，请尝试其他筛选'}`;
    }
    search.addEventListener('input', filter); toolbar.append(search, filters);
    host.replaceChildren(header, toolbar, status, grid, sourceNote(ui, snapshot.source)); filter();
  }
  window.WFDungeons = {validId, imageUrl, image, button, guideView, recommendation};
  window.renderWikiDungeons = async (host, data, ui, options = {}) => {
    const snapshot = data.dungeons || {items:[]};
    if (!options.id) {catalog(host, snapshot, ui); return {};}
    const series = window.WFDungeonSeries?.group(snapshot.items || [], options.id);
    if (series) return window.WFDungeonSeries.render(host, series, data, ui, options, window.renderWikiDungeons);
    const item = snapshot.items?.find((entry) => validId(entry.id) && entry.id === options.id), {el} = ui;
    const page = el('article', 'dungeon-detail'), back = el('a', 'back-button', '‹ 返回副本与模式'); back.href = '#dungeons';
    if (item && window.WFDungeonSeries?.group(snapshot.items || [], item.seriesId)) {back.href = `#dungeons/${encodeURIComponent(item.seriesId)}`; back.textContent = '‹ 返回所属系列';}
    if (!options.embedded) page.append(back); host.replaceChildren(page);
    if (!item) {page.append(el('h1', '', '未找到此副本'), el('p', 'muted', '请返回目录查找现有副本。')); return {};}
    const compact = compactCategory(item.category), heading = el('header', `dungeon-header${compact ? ' dungeon-header-compact' : ''}`), headingText = el('div');
    headingText.append(el('span', 'badge', item.category), el(options.embedded ? 'h2' : 'h1', '', item.title)); heading.append(headingText); page.append(heading);
    const hero = image(ui, compact ? item.entryImage || item.banner : item.banner || item.entryImage, `${item.title} ${compact ? '入口' : '横幅'}`, `dungeon-hero${compact ? ' dungeon-hero-compact' : ''}`);
    if (hero) {if (compact) heading.replaceChildren(hero, headingText); else page.append(hero);}
    if (item.summary) page.append(el('p', 'dungeon-summary', item.summary));
    const floorHost = window.WFDungeonFloors?.scopes(item).length > 1 ? el('div', 'dungeon-floor-host') : null;
    if (floorHost) page.append(floorHost);
    const previews = [...new Set([item.entryImage, ...(compact ? [item.banner] : []), ...(item.previewImages || [])].filter((value) => value && (compact || value !== item.banner)))];
    if (previews.length) {
      const fold = el('details', 'dungeon-fold'), gallery = el('div', 'dungeon-gallery');
      fold.append(el('summary', '', `入口与模式预览 · ${previews.length}`), gallery);
      fold.addEventListener('toggle', () => {
        if (!fold.open || gallery.children.length) return;
        previews.forEach((url, index) => {const img = image(ui, url, `${item.title} 预览 ${index + 1}`); if (img) gallery.append(img);});
      }); page.append(fold);
    }
    if (item.quests?.length) {
      const fold = el('details', 'dungeon-fold'), list = el('ul', 'dungeon-quest-list'); fold.append(el('summary', '', `关卡查询 · ${item.quests.length}`), list);
      item.quests.forEach((quest) => list.append(el('li', '', [quest.name, quest.difficulty, quest.element].filter(Boolean).join(' · ')))); page.append(fold);
    }
    const legacyHost = el('div', 'dungeon-legacy-guide');
    if (item.legacyGuide === 'five-boss') {
      const legacy = el('details', 'dungeon-fold dungeon-legacy'); let rendered = false;
      legacy.append(el('summary', '', '五重决战 · 波次、Boss 与机制查询（本地机制快照）'), legacyHost);
      legacy.addEventListener('toggle', () => {
        if (!legacy.open || rendered || !options.renderLegacyGuide) return;
        rendered = true; options.renderLegacyGuide(legacyHost);
      }); page.append(legacy);
    }
    window.WFWikiRewardView?.renderDungeon(page, item.id, data, ui);
    const request = (...args) => window.WFCommunity.client.request(...args);
    const hash = window.location.hash, current = () => page.isConnected && host.contains(page) && window.location.hash === hash;
    let identity;
    async function renderGuide(target, scope) {
      const status = el('p', 'dungeon-status muted', '正在读取攻略与推荐队伍…'); status.setAttribute('role', 'status');
      const guides = el('div'), admin = el('div', 'dungeon-admin-host'); target.append(status, guides, admin);
      let serial = 0;
      const active = () => current() && target.isConnected;
      async function load() {
        const ticket = ++serial; status.textContent = '正在读取攻略与推荐队伍…';
        try {
          const result = await request(`/dungeons/${encodeURIComponent(scope.id)}`);
          if (!active() || serial !== ticket) return;
          guideView(guides, result, data, ui); status.replaceChildren();
        } catch (error) {
          if (!active() || serial !== ticket) return;
          status.replaceChildren(el('span', '', '在线攻略暂时不可用；上方副本资料仍可查看。'), button(ui, '重试', load));
        }
      }
      identity ||= request('/admin/me').catch(() => null);
      const management = window.WFDungeonsAdmin?.attach(admin, scope, data, ui, {current:active, identity, onSaved: (result) => {
        if (!active()) return; serial++; status.replaceChildren(); guideView(guides, result, data, ui);
      }});
      await Promise.all([load(), management]);
    }
    const floors = window.WFDungeonFloors?.mount(floorHost || page, item, ui, renderGuide);
    const ready = floors ? floors.ready : renderGuide(page, item);
    page.append(sourceNote(ui, item.source || snapshot.source)); await ready;
    return {legacyHost, item};
  };
})();
