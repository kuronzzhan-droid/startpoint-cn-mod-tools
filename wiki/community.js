/* Published recommendations open their complete plate in the local team editor. */
(() => {
  'use strict';
  const C = window.WFCommunity;
  const groupNames = {main: '主位', unison: '合击', weapon: '装备', soul: '魂珠'};
  C.board = (input, data, ui, options = {}) => {
    const {el, picture} = ui, team = C.teamCopy(input);
    const characters = new Map((data.characters || []).map((item) => [item.id, item]));
    const equipment = new Map((options.preview ? [] : data.equipment || []).map((item) => [item.id, item]));
    const board = el('div', 'community-board'); board.setAttribute('aria-label', options.preview ? '队伍角色预览' : '队伍阵容');
    for (let index = 0; index < 3; index++) {
      const column = el('div', 'community-board-column');
      for (const group of options.preview ? ['main', 'unison'] : ['main', 'weapon', 'soul', 'unison']) {
        const character = group === 'main' || group === 'unison';
        const item = (character ? characters : equipment).get(team[group][index]);
        const slot = el(item && !options.preview ? 'a' : 'span', `community-slot community-slot-${group}`);
        slot.setAttribute('aria-label', `${index + 1}号${groupNames[group]}：${item?.name || (team[group][index] ? '当前图鉴未收录' : '空位')}`);
        if (item) {
          slot.title = `${groupNames[group]} · ${item.name}`;
          if (!options.preview) slot.href = `#${character ? 'character' : 'weapon'}/${encodeURIComponent(item.id)}`;
          if (!options.preview && character && options.onCharacter) {
            slot.href = '#team'; slot.addEventListener('click', (event) => {event.preventDefault(); options.onCharacter({group,index});});
          }
          slot.append(character && options.avatars ? options.avatars.picture(item, item.name, 'community-slot-image')
            : picture(item.icon, item.name, 'community-slot-image'));
          if (character) {
            window.WFCharacterFrame?.apply(slot, item);
            window.WFCharacterBadges?.append(slot, {origin:item.origin}, ui);
          }
        } else slot.append(el('span', '', team[group][index] ? '?' : '—'));
        const leader = index === 0 && group === 'main';
        const role = el('span', `community-slot-label${leader ? ' community-slot-leader' : ''}`, leader ? '' : groupNames[group]);
        if (leader) {role.setAttribute('aria-label', '队长'); role.title = '队长';}
        slot.append(role);
        if (options.showNames) {
          const entry = el('div', `community-slot-entry community-slot-entry-${group}`);
          entry.append(slot, el('span', 'community-slot-name', item?.name || (team[group][index] ? '未收录' : '空位'))); column.append(entry);
        } else column.append(slot);
      }
      board.append(column);
    }
    return board;
  };
  C.source = (ui) => {
    const line = ui.el('p', 'community-source', '资料参考：');
    const link = ui.el('a', 'text-button', '腾讯文档《配队大全》（原表）'); link.href = C.sourceUrl; link.target = '_blank'; link.rel = 'noopener noreferrer';
    line.append(link); return line;
  };
  function likeButton(item, ui, remembered) {
    const button = ui.el('button', 'community-like'), icon = ui.el('span', 'community-like-icon');
    const count = ui.el('strong', 'community-like-count');
    button.type = 'button'; icon.setAttribute('aria-hidden', 'true'); button.append(icon, count);
    const day = () => new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);
    function update(result) {
      if (Number.isFinite(Number(result.likes))) item.likes = Math.max(0, Number(result.likes));
      if (result.likedToday !== undefined) item.likedToday = result.likedToday;
      if (item.likedToday) remembered.set(item.id, {day:day(), likes:item.likes});
      count.textContent = String(item.likes || 0); button.disabled = Boolean(item.likedToday);
      button.setAttribute('aria-pressed', String(Boolean(item.likedToday)));
      button.setAttribute('aria-label', `${item.likedToday ? '今天已点赞' : '为此队伍点赞'}：${item.title}，${item.likes || 0} 赞`);
      button.title = item.likedToday ? '今天已点赞' : '为这支队伍点赞';
    }
    const previous = remembered.get(item.id);
    update(previous?.day === day() ? {likedToday:true, likes:Math.max(item.likes || 0, previous.likes || 0)} : item);
    button.addEventListener('click', () => {if (!button.disabled) C.openLike(item, ui, update);});
    return button;
  }
  window.renderWikiCommunity = async (host, data, ui, options = {}) => {
    const {el} = ui, startingHash = location.hash;
    let revision = 0, nextCursor = '', config;
    const liked = new Map();
    const filters = {q: '', section: '', element: '', category: '', code: '', damageTypes: [], sort: 'popular'};
    const header = el('header', 'community-header'), links = el('div', 'community-header-links');
    const intro = el('p', 'section-intro community-intro', '点击队伍查看编成与角色面板，为实用的盘子点赞。');
    const sections = el('div', 'community-sections'); sections.setAttribute('role', 'group'); sections.setAttribute('aria-label', '推荐队伍玩法分区');
    const sectionButtons = [['','全部'], ...Object.entries(C.teamSections).filter(([value]) => value), ['general', C.sectionLabel('')]].map(([value,label]) => {
      const button = el('button', 'community-section-button', label); button.type = 'button';
      button.setAttribute('aria-label', `玩法分区：${label}`);
      button.addEventListener('click', () => {filters.section = value; load();}); sections.append(button); return {button,value};
    });
    const toolbar = el('div', 'community-toolbar');
    const element = el('select'); element.setAttribute('aria-label', '推荐队伍属性');
    const all = el('option', '', '全部属性'); all.value = ''; element.append(all);
    const category = el('select'); category.setAttribute('aria-label', '推荐队伍分类');
    [['','全部分类'], ...C.teamCategories.map((value) => [value,value]), ['uncategorized','未分类']].forEach(([value,label]) => {
      const option = el('option', '', label); option.value = value; category.append(option);
    });
    const sort = el('select'); sort.setAttribute('aria-label', '推荐队伍排序');
    [['popular', '最多点赞'], ['latest', '最新收录']].forEach(([value, label]) => {const option = el('option', '', label); option.value = value; sort.append(option);});
    const edit = el('a', 'primary-button', '本地配队模拟'); edit.href = '#team';
    links.append(edit); header.append(el('h1', '', options.id ? '推荐队伍' : '配队大全'), links);
    const reset = el('button', 'text-button community-filter-reset', '重置筛选'); reset.type = 'button';
    toolbar.append(element, sort, reset);
    const advanced = el('details', 'community-advanced-filters'); advanced.open = false;
    const advancedSummary = el('summary'), activeSummary = el('span', 'community-active-filters');
    advancedSummary.append(el('span', '', '更多筛选'), activeSummary);
    const advancedBody = el('div', 'community-advanced-body'), categoryField = el('label', 'community-category-filter');
    categoryField.append(el('span', '', '配队分类'), category);
    const code = el('select'); code.setAttribute('aria-label', '推荐队伍码状态');
    [['','全部队伍码状态'],['has','已有队伍码'],['none','暂无队伍码']].forEach(([value,label]) => {
      const option = el('option', '', label); option.value = value; code.append(option);
    });
    const codeField = el('label', 'community-category-filter'); codeField.append(el('span', '', '队伍码'), code);
    code.addEventListener('change', () => {filters.code = code.value; load();});
    const damage = el('fieldset', 'community-damage-options'); damage.append(el('legend', '', '伤害类型（多选时同时满足）'));
    Object.entries(C.damageTypes).forEach(([value, label]) => {
      const wrap = el('label', 'community-check'), input = el('input'); input.type = 'checkbox'; input.value = value;
      input.addEventListener('change', () => {filters.damageTypes = [...damage.querySelectorAll('input:checked')].map((node) => node.value); load();});
      wrap.append(input, el('span', '', label)); damage.append(wrap);
    });
    const extraSelects = el('div', 'community-extra-selects'); extraSelects.append(categoryField,codeField);
    advancedBody.append(toolbar, extraSelects, damage); advanced.append(advancedSummary, advancedBody);
    function syncFilters() {
      element.value = filters.element; category.value = filters.category; sort.value = filters.sort; code.value = filters.code;
      sectionButtons.forEach(({button,value}) => button.setAttribute('aria-pressed', String(filters.section === value)));
      const active = [...(filters.element ? [C.elementLabel(filters.element)] : []), ...(filters.category ? [C.categoryLabel(filters.category)] : []), ...(filters.code ? [filters.code === 'has' ? '已有队伍码' : '暂无队伍码'] : []), ...filters.damageTypes.map((value) => C.damageTypes[value])];
      activeSummary.textContent = `${filters.sort === 'latest' ? '最新收录' : '最多点赞'} · ${active.length ? active.join(' · ') : '全部属性'}`;
      reset.disabled = !filters.q && !filters.section && !filters.element && !active.length && filters.sort === 'popular';
    }
    reset.addEventListener('click', () => {
      Object.assign(filters, {q:'',section:'',element:'',category:'',code:'',damageTypes:[],sort:'popular'});
      search?.resetView();
      damage.querySelectorAll('input').forEach((input) => {input.checked = false;}); load();
    });
    const status = el('p', 'community-status'); status.setAttribute('role', 'status');
    const cards = el('div', options.id ? 'community-grid community-single' : 'community-grid');
    const avatarControls = el('div', 'community-avatar-controls');
    const avatars = window.WFCatalogAvatars?.create({host: avatarControls, catalog: cards,
      characters: data.characters || [], ui, label: '配队大全头像'});
    if (!options.id) toolbar.append(avatarControls);
    const more = el('button', 'secondary-button community-more', '加载更多'); more.type = 'button'; more.hidden = true;
    const retry = el('button', 'secondary-button', '重试连接'); retry.type = 'button'; retry.hidden = true;
    const directory = el('div', 'community-directory');
    directory.append(sections, ...(options.id ? [avatarControls] : []), advanced, status, cards, more, retry, C.source(ui));
    const search = !options.id && C.codeSearch({data, ui, onActiveChange: (active) => {directory.hidden = active;},
      onKeywordSearch: (term) => {filters.q = term; return load();}});
    host.replaceChildren(...(!options.id && C.announcement ? [C.announcement(ui)] : []), header, intro, ...(search ? [search] : []), directory);
    if (options.id) {
      toolbar.hidden = true; sections.hidden = true; advanced.hidden = true;
      const back = el('a', 'back-button', '‹ 返回配队大全'); back.href = '#community'; host.prepend(back);
    }
    const mounted = () => cards.isConnected && location.hash === startingHash;
    const current = (ticket) => mounted() && revision === ticket;
    function card(item) {
      const node = el('article', 'community-card');
      function enter(selection) {
        if (!window.WFTeamImport?.load) {status.textContent = '编成编辑器暂未准备好，请刷新后重试。'; return;}
        window.WFTeamImport.load(C.teamCopy(item.team), item.title, selection); location.hash = '#team';
      }
      function tags() {
        const badges = el('div', 'community-tags'); badges.append(el('span', 'badge community-section-badge', C.sectionLabel(item.section)),
          el('span', 'badge', C.categoryLabel(item.category)), el('span', 'badge', C.elementLabel(item.element)));
        (item.damageTypes || []).filter((key) => C.damageTypes[key]).forEach((key) => badges.append(el('span', 'badge', C.damageTypes[key])));
        return badges;
      }
      const gameCode = window.WFCommunityGameCodes?.readonly(item, ui, {compact:true});
      if (!options.id) {
        const preview = el('a', 'community-card-preview'); preview.href = `#community/${encodeURIComponent(item.id)}`;
        preview.setAttribute('aria-label', `查看队伍：${item.title}`);
        preview.append(el('h2', '', item.title), tags(), C.board(item.team, data, ui, {preview:true, avatars})); node.append(preview);
        const codeRow = el('header', 'community-card-header');
        codeRow.append(gameCode || el('span', 'muted community-no-code', '暂无队伍码'));
        node.append(codeRow, likeButton(item, ui, liked));
        return node;
      }
      const heading = el('h2'); const link = el('a', '', item.title); link.href = '#team';
      link.addEventListener('click', (event) => {event.preventDefault(); enter();}); heading.append(link);
      const date = new Date(item.createdAt), time = el('time', 'muted', Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('zh-CN', {timeZone: 'Asia/Shanghai'}));
      if (!Number.isNaN(date.getTime())) time.dateTime = date.toISOString();
      const cardHeader = el('header', 'community-card-header'), headingArea = el('div', 'community-card-heading');
      headingArea.append(heading, tags());
      cardHeader.append(headingArea, gameCode || el('span', 'muted community-no-code', '暂无队伍码'));
      node.append(cardHeader, C.board(item.team, data, ui, {onCharacter:enter, avatars, showNames:Boolean(options.id)}));
      if (item.notes) {const notes = el('details', 'community-notes'); notes.open = Boolean(options.id); notes.append(el('summary', '', '用途与操作说明'), el('p', '', item.notes)); node.append(notes);}
      const actions = el('div', 'community-actions');
      const use = el('button', 'primary-button', '装入编成'); use.type = 'button';
      use.addEventListener('click', () => enter());
      actions.append(use, likeButton(item, ui, liked));
      const footer = el('footer', 'community-card-footer'), credit = el('div', 'community-card-credit');
      credit.append(el('p', 'community-author', `作者：${item.author || '未署名'}`), time);
      footer.append(credit, actions); node.append(footer); return node;
    }
    async function load(append = false) {
      syncFilters();
      const ticket = ++revision; more.disabled = true; retry.hidden = true; status.textContent = '正在载入推荐队伍…';
      if (!append) {cards.replaceChildren(); nextCursor = ''; more.hidden = true;}
      try {
        const result = await C.client.request(options.id ? `/teams/${encodeURIComponent(options.id)}` : `/teams?${C.query(filters, append ? nextCursor : '')}`);
        if (!current(ticket)) return;
        const items = options.id ? [result.team || result] : result.items || [];
        // Public API is authoritative; never surface explicitly non-public records.
        const publicItems = items.filter((item) => item && item.id && item.visibility !== 'private' && (!item.status || item.status === 'approved'));
        publicItems.forEach((item) => cards.append(card(item)));
        nextCursor = result.nextCursor || ''; more.hidden = !nextCursor || Boolean(options.id);
        const prefix = filters.q ? `“${filters.q}” · ` : '';
        status.textContent = prefix + (cards.children.length ? `已显示 ${cards.children.length} 支推荐队伍` : '暂时没有符合条件的推荐队伍。');
      } catch (error) {
        if (current(ticket)) {status.textContent = C.message(error); retry.hidden = false;}
      } finally {if (current(ticket)) more.disabled = false;}
    }
    async function connect() {
      const ticket = ++revision; status.textContent = '正在连接配队社区…'; retry.hidden = true;
      try {
        config = await C.client.config(); if (!mounted()) return;
        element.replaceChildren(all);
        (config.elements || []).forEach((value) => {const option = el('option', '', C.elementLabel(value)); option.value = value; element.append(option);});
        element.value = filters.element; if (current(ticket)) load();
      } catch (error) {if (current(ticket)) {status.textContent = C.message(error); retry.hidden = false;}}
    }
    element.addEventListener('change', () => {filters.element = element.value; load();});
    category.addEventListener('change', () => {filters.category = category.value; load();});
    sort.addEventListener('change', () => {filters.sort = sort.value; load();});
    more.addEventListener('click', () => load(true)); retry.addEventListener('click', () => config ? load() : connect());
    syncFilters(); await connect();
  };
})();
