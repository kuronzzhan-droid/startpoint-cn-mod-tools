/* One public aggregate request for the catalogue; never fetch individual votes. */
(() => {
  'use strict';
  const ranking = window.WFRatingScore;
  const modes = [['rating-element-desc', '属性内评分从高到低'], ['rating-element-asc', '属性内评分从低到高'],
    ['rating-global-desc', '全体评分从高到低'], ['rating-global-asc', '全体评分从低到高']];
  const elements = ['火', '水', '雷', '风', '光', '暗'];
  const rank = (value) => elements.includes(value) ? elements.indexOf(value) : elements.length;
  const normalize = (value) => {
    if (!value || !Number.isSafeInteger(value.voters) || value.voters < 0) return null;
    if (value.voters === 0) return value.average === null ? {average: null, voters: 0, rankScore: null} : null;
    if (typeof value.average !== 'number' || !Number.isFinite(value.average) || value.average < 0 || value.average > 5) return null;
    // Older cached responses may omit rankScore; use the same policy until they expire.
    const rankScore = value.rankScore === undefined ? ranking.score(value.average, value.voters) : value.rankScore;
    return Number.isFinite(rankScore) && rankScore >= 0 && rankScore <= 5
      ? {average: value.average, voters: value.voters, rankScore} : null;
  };
  const api = window.WFCatalogRatings = {create({characters, sort, host, ui, onChange}) {
    const {el} = ui, ids = new Set(characters.map((character) => String(character.id)));
    const records = new Map(), updated = new Map();
    let phase = 'idle', revision = 0, pending = null, published;
    const status = el('div', 'catalog-rating-status'), message = el('span');
    status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    const retry = el('button', 'text-button', '重试评分'); retry.type = 'button';
    status.append(message, retry); host.append(status);
    const isRatingSort = () => ['rating', 'rating-element'].includes(sort.value) || modes.some(([value]) => value === sort.value);
    function paintStatus() {
      status.hidden = phase === 'idle' || (phase === 'ready' && !isRatingSort());
      retry.hidden = phase !== 'error';
      message.textContent = phase === 'ready' ? `按票数修正排序；卡片显示真实均分，未评分排末尾。每日汇总，新评分次日计入。${published?.stale ? '今日汇总更新中，显示上次结果。' : ''}` : phase === 'loading' ? '正在加载玩家评分…' : phase === 'offline'
        ? '离线版无法读取玩家评分；缺少评分显示 —。' : '评分暂时未能加载，缺少评分显示 —。';
      status.title = published?.asOf ? `汇总时间：${new Date(published.asOf).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai'})}（北京时间）` : '';
    }
    function paint(card) {
      const value = records.get(card.dataset.catalogRatingId), rated = value && value.voters > 0;
      const label = rated ? `评分 ${value.average.toFixed(1)} / 5 · ${value.voters} 人 · 排序分 ${value.rankScore.toFixed(2)}`
        : phase === 'ready' ? '评分 —（未评分）' : '评分 —（尚未加载）';
      const badge = card.querySelector('.card-rating');
      badge.textContent = '评分 ';
      badge.append(el('strong', 'card-rating-value', rated ? value.average.toFixed(1) : '—')); badge.title = label;
      card.title = `${card.dataset.catalogBaseTitle} · ${label}`;
      card.setAttribute('aria-label', `${card.dataset.catalogBaseLabel}，${label}`);
    }
    function update(id, value) {
      // Detail-page results include the player's fresh vote. Do not mix them
      // into a published daily catalogue and silently change its ordering.
      if (published) return false;
      id = String(id); const record = normalize(value);
      if (!ids.has(id) || !record) return false;
      const previous = records.get(id);
      records.set(id, record); updated.set(id, ++revision);
      if (previous?.average !== record.average || previous?.voters !== record.voters || previous?.rankScore !== record.rankScore) onChange();
      return true;
    }
    async function load() {
      if (pending) return pending;
      if (phase === 'ready' && published && Date.parse(published.nextRefreshAt) <= Date.now()) phase = 'idle';
      if (phase === 'ready' || phase === 'error' || phase === 'offline') return pending;
      if (location.protocol === 'file:') {phase = 'offline'; paintStatus(); return;}
      phase = 'loading'; paintStatus(); const started = revision;
      pending = Promise.resolve().then(() => window.WFCommunity.client.request('/ratings/characters')).then((response) => {
        if (!Array.isArray(response?.items)) throw new Error('invalid_ratings');
        const daily = response.asOf !== undefined;
        if (daily && (!Number.isFinite(Date.parse(response.asOf)) || !Number.isFinite(Date.parse(response.nextRefreshAt))
          || Date.parse(response.nextRefreshAt) <= Date.parse(response.asOf) || typeof response.stale !== 'boolean')) throw new Error('invalid_ratings');
        const received = new Map();
        for (const item of response.items) {
          const record = normalize(item);
          if (!record || typeof item.id !== 'string' || received.has(item.id)) throw new Error('invalid_ratings');
          if (ids.has(item.id)) received.set(item.id, record);
        }
        for (const id of ids) {
          if (!daily && (updated.get(id) || 0) > started) continue;
          if (received.has(id)) records.set(id, received.get(id)); else records.delete(id);
        }
        published = daily ? {asOf:response.asOf, nextRefreshAt:response.nextRefreshAt, stale:response.stale} : undefined;
        phase = 'ready'; onChange();
      }).catch(() => {phase = 'error';}).finally(() => {pending = null; paintStatus();});
      return pending;
    }
    retry.addEventListener('click', () => {if (phase === 'error') {phase = 'idle'; load();}});
    sort.addEventListener('change', paintStatus);
    api.update = update;
    window.addEventListener('wf-character-rating-updated', (event) => {
      if (event.detail) update(event.detail.id, event.detail);
    });
    paintStatus();
    return {isRatingSort, load, update,
      compare(a, b, direction = sort.value.endsWith('-asc') ? 'asc' : 'desc') {
        if (sort.value === 'rating-element' || sort.value.startsWith('rating-element-')) {
          const group = rank(a.element) - rank(b.element); if (group) return group;
        }
        const av = records.get(String(a.id)), bv = records.get(String(b.id));
        return ranking.compare(av, bv, direction) || window.WFCharacterOrder.compare(a, b);
      },
      decorate(card, character) {
        card.dataset.catalogRatingId = String(character.id);
        card.dataset.catalogBaseTitle = card.title;
        card.dataset.catalogBaseLabel = card.getAttribute('aria-label');
        (card.querySelector('.card-stats') || card.querySelector('.card-meta')).append(el('span', 'card-rating')); paint(card);
      },
      paintMounted(catalog) {catalog.querySelectorAll('.character-card').forEach(paint);},
    };
  }};
})();
