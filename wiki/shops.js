/* Shop views reuse exported reward rows and the existing weapon catalogue. */
(() => {
  'use strict';
  const pageSize = 60;
  const textOf = (shop) => [shop.title, ...shop.items.flatMap((row) => [...(row.rewards || []), ...(row.costs || [])].map((item) => item.name || ''))].join(' ').toLowerCase();
  const matches = (text, query) => query.trim().toLowerCase().split(/\s+/).filter(Boolean).every((word) => text.includes(word));
  function searchInput(ui, label) {
    const node = ui.el('input', 'shop-search'); node.type = 'search'; node.placeholder = label; node.setAttribute('aria-label', label); return node;
  }
  function catalogue(host, shops, data, ui) {
    const {el} = ui, R = window.WFWikiRewardView, toolbar = el('div', 'shop-toolbar'), search = searchInput(ui, '查找商店、武器或兑换物品…');
    const filter = el('select', 'shop-dungeon-filter'); filter.setAttribute('aria-label', '按关联副本筛选');
    const all = el('option', '', '全部副本'); all.value = ''; filter.append(all);
    const dungeonNames = new Map(R.list(data.dungeons?.items).map((item) => [item.id, item.title]));
    const linked = [...new Set(shops.flatMap((shop) => R.list(shop.dungeonIds)).filter((id) => dungeonNames.has(id)))];
    linked.sort((a, b) => dungeonNames.get(a).localeCompare(dungeonNames.get(b), 'zh-CN'));
    for (const id of linked) {const option = el('option', '', dungeonNames.get(id)); option.value = id; filter.append(option);}
    const grid = el('div', 'shop-grid'), status = el('p', 'muted shop-count'); status.setAttribute('role', 'status');
    const cards = shops.map((shop) => {
      const card = el('a', 'shop-card'); card.href = `#shops/${shop.id}`; card.title = shop.title;
      card.append(el('h2', '', shop.title), el('p', 'muted', `${shop.items.length} 项兑换资料`)); grid.append(card);
      return {card, shop, text:textOf(shop)};
    });
    function filterCards() {
      let count = 0;
      for (const row of cards) {
        row.card.hidden = Boolean(filter.value && !R.list(row.shop.dungeonIds).includes(filter.value)) || !matches(row.text, search.value);
        if (!row.card.hidden) count++;
      }
      status.textContent = shops.length ? `${count} 个商店${count ? '' : '，请调整查找条件'}` : '兑换商店资料尚未收录。';
    }
    search.addEventListener('input', filterCards); filter.addEventListener('change', filterCards);
    toolbar.append(search, filter); host.append(toolbar, status, grid); filterCards();
  }
  function rowView(row, lookup, ui) {
    const {el} = ui, R = window.WFWikiRewardView, card = el('article', 'shop-exchange');
    card.append(el('h3', '', '兑换获得'));
    card.append(row.rewards?.length ? R.rewardList(ui, row.rewards, lookup) : el('p', 'muted', '兑换奖励资料尚未收录。'));
    card.append(el('h4', '', '所需材料'));
    card.append(row.costs?.length ? R.rewardList(ui, row.costs, lookup) : el('p', 'muted', '兑换消耗资料尚未收录。'));
    const stock = row.stock === -1 ? '兑换次数不限' : Number.isInteger(row.stock) && row.stock >= 0 ? `配置库存：${row.stock}` : '库存资料待补';
    card.append(el('p', 'shop-stock muted', stock));
    if (row.availableFrom || row.availableUntil) card.append(el('p', 'shop-dates muted', `配置时间：${row.availableFrom || '起始时间待补'} ～ ${row.availableUntil || '结束时间待补'}`));
    const notes = R.notes(ui, row.notes); if (notes) card.append(notes); return card;
  }
  function detail(host, shop, data, ui) {
    const {el} = ui, R = window.WFWikiRewardView, lookup = R.context(data);
    const related = el('div', 'shop-related'), names = new Map(R.list(data.dungeons?.items).map((item) => [item.id, item.title]));
    for (const id of R.list(shop.dungeonIds)) {
      if (!R.validId(id) || !names.has(id)) continue;
      const link = el('a', 'dungeon-shop-link', `${names.get(id)} ›`); link.href = `#dungeons/${id}`; related.append(link);
    }
    if (related.children.length) host.append(related);
    const notes = R.notes(ui, shop.notes); if (notes) host.append(notes);
    const search = searchInput(ui, '查找此商店的物品或消耗…'), status = el('p', 'muted shop-count'); status.setAttribute('role', 'status');
    const grid = el('div', 'shop-exchanges'), more = el('button', 'secondary-button shop-more', '继续显示'); more.type = 'button';
    const rows = shop.items.map((row) => ({row, text:textOf({title:'', items:[row]})})); let limit = pageSize;
    function paint() {
      const items = rows.filter((row) => matches(row.text, search.value));
      grid.replaceChildren(...items.slice(0, limit).map(({row}) => rowView(row, lookup, ui)));
      more.hidden = items.length <= limit;
      status.textContent = rows.length ? `${items.length} 项兑换资料${items.length > limit ? `，已显示 ${limit} 项` : ''}` : '此商店的兑换物品资料尚未收录。';
    }
    search.addEventListener('input', () => {limit = pageSize; paint();}); more.addEventListener('click', () => {limit += pageSize; paint();});
    host.append(search, status, grid, more); paint();
  }
  window.renderWikiShops = (host, data, ui, options = {}) => {
    const {el} = ui, R = window.WFWikiRewardView, snapshot = data.rewards || {}, page = el('article', 'shops-page');
    const shops = R.list(snapshot.shops).filter((shop) => R.validId(shop?.id)).map((shop) => ({...shop, items:R.list(shop.items)}));
    const back = el('a', 'back-button', options.id ? '‹ 返回兑换商店' : '‹ 返回副本与模式'); back.href = options.id ? '#shops' : '#dungeons';
    page.append(back); host.replaceChildren(page);
    if (options.id) {
      const shop = shops.find((item) => item.id === options.id);
      page.append(el('h1', '', shop?.title || '商店资料尚未收录'));
      if (shop) detail(page, shop, data, ui);
    } else {page.append(el('h1', '', '兑换商店')); catalogue(page, shops, data, ui);}
    page.append(R.source(ui, snapshot.source));
  };
})();
