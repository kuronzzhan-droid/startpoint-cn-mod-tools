/* Read-only catalogue counts: one batch, shared in-flight work, no polling or view writes. */
(() => {
  'use strict';
  let snapshot, pending;
  function validate(value) {
    if (!Array.isArray(value?.items) || typeof value.asOf !== 'string' || typeof value.nextRefreshAt !== 'string'
      || !Number.isFinite(Date.parse(value.asOf)) || !Number.isFinite(Date.parse(value.nextRefreshAt))
      || Date.parse(value.nextRefreshAt) <= Date.parse(value.asOf)) throw new Error('invalid_views');
    const records = new Map();
    for (const item of value.items) {
      if (typeof item?.id !== 'string' || !item.id || records.has(item.id) || !Number.isSafeInteger(item.views) || item.views < 0) throw new Error('invalid_views');
      records.set(item.id, item.views);
    }
    return {records, asOf:value.asOf, nextRefreshAt:value.nextRefreshAt};
  }
  function request() {
    if (pending) return pending;
    if (snapshot && Date.parse(snapshot.nextRefreshAt) > Date.now()) return Promise.resolve(snapshot);
    pending = Promise.resolve().then(() => window.WFCommunity.client.request('/views/characters'))
      .then(value => (snapshot = validate(value))).finally(() => {pending = undefined;});
    return pending;
  }
  window.WFCatalogViews = {create({host, ui, onChange}) {
    const {el} = ui, status = el('div', 'catalog-view-status'), message = el('span');
    const retry = el('button', 'text-button', '重试查看次数'); retry.type = 'button';
    status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite'); status.append(message, retry); host.append(status);
    let phase = 'idle', published, loading;
    const count = id => published?.records.get(String(id));
    function paintStatus() {
      status.hidden = phase === 'idle' || phase === 'ready'; retry.hidden = phase !== 'error';
      message.textContent = phase === 'loading' ? '正在加载查看次数…' : phase === 'offline' ? '离线版无法读取查看次数，缺少数据显示 —。'
        : published ? '查看次数更新失败，保留上次统计。' : '查看次数暂时无法加载，缺少数据显示 —。';
    }
    function paint(card) {
      const value = count(card.dataset.catalogViewId), badge = card.querySelector('.card-views');
      const label = value === undefined ? '查看 —' : `查看 ${value.toLocaleString('zh-CN')} 次`;
      badge.textContent = label;
      badge.title = published ? `${label}；每 30 分钟汇总，统计于 ${new Date(published.asOf).toLocaleString('zh-CN')}` : '查看次数尚未加载';
    }
    function load() {
      if (loading) return loading;
      if (phase === 'error' || phase === 'offline' || (phase === 'ready' && Date.parse(published.nextRefreshAt) > Date.now())) return Promise.resolve();
      if (location.protocol === 'file:') {phase = 'offline'; paintStatus(); return Promise.resolve();}
      phase = 'loading'; paintStatus();
      loading = request().then(value => {published = value; phase = 'ready'; onChange();})
        .catch(() => {phase = 'error';}).finally(() => {loading = undefined; paintStatus();});
      return loading;
    }
    retry.addEventListener('click', () => {if (phase === 'error') {phase = 'idle'; load();}});
    paintStatus();
    return {load, count,
      compare(a, b, direction = 'desc') {
        const av = count(a.id), bv = count(b.id);
        if ((av === undefined) !== (bv === undefined)) return av === undefined ? 1 : -1;
        return av === undefined ? 0 : (av - bv) * (direction === 'asc' ? 1 : -1);
      },
      decorate(card, character) {
        card.dataset.catalogViewId = String(character.id);
        card.querySelector('.card-footer').append(el('span', 'card-views')); paint(card);
      },
      paintMounted(catalog) {catalog.querySelectorAll('.character-card').forEach(paint);},
    };
  }};
})();
