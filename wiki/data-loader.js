/* Classic scripts keep split data usable on both static hosts and file://. */
(() => {
  'use strict';
  const data = window.WF_WIKI || {};
  const chunks = data.dataManifest?.chunks || {};
  const pending = new Map();
  const characters = new Map((data.characters || []).map((c) => [String(c.id), c]));
  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  let search = null;
  function load(key, fallback, validate) {
    if (!data.dataManifest) return Promise.resolve(fallback);
    const registry = window.WF_WIKI_CHUNKS || {};
    if (own(registry, key) && validate(registry[key])) return Promise.resolve(registry[key]);
    if (pending.has(key)) return pending.get(key);
    const entry = chunks[key];
    if (!entry || !/^data\/[a-zA-Z0-9_-]+\.js$/.test(entry.url)) {
      return Promise.reject(new Error('资料分包缺失，请刷新页面或重新取得完整离线包。'));
    }
    const promise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      let finished = false;
      const finish = (error) => {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        script.remove();
        if (error) reject(error); else resolve(window.WF_WIKI_CHUNKS[key]);
      };
      const timer = setTimeout(() => finish(new Error('资料加载超时，请重试。')), 30000);
      script.src = entry.url;
      script.async = true;
      script.onload = () => {
        const value = (window.WF_WIKI_CHUNKS || {})[key];
        finish(validate(value) ? null : new Error('资料分包不完整，请刷新后重试。'));
      };
      script.onerror = () => finish(new Error('资料暂时无法载入，请检查网络或离线文件后重试。'));
      document.head.append(script);
    }).finally(() => pending.delete(key));
    pending.set(key, promise);
    return promise;
  }
  window.WFWikiData = {
    loadCharacter(id) {
      if (!characters.has(String(id))) return Promise.resolve(null);
      return load(`character:${id}`, characters.get(String(id)), (value) => value && String(value.id) === String(id));
    },
    async loadEquipment() {
      const value = await load('equipment', data, (value) => value && Array.isArray(value.equipment));
      data.equipment = value.equipment || [];
      data.equipmentMeta = value.equipmentMeta || {};
      return data.equipment;
    },
    async loadBossGuide() {
      data.bossGuide = await load('bossGuide', data.bossGuide || {}, (value) => value && typeof value === 'object');
      return data.bossGuide;
    },
    async loadSearchIndex() {
      if (!data.dataManifest) return null;
      if (!search) {
        const value = await load('search', null, (value) => value && typeof value === 'object'
          && [...characters.keys()].every((id) => typeof value[id] === 'string'));
        search = new Map(Object.entries(value).map(([id, text]) => [id, text.normalize('NFKC').toLocaleLowerCase('zh-CN')]));
      }
      return search;
    },
    searchIndex: () => search,
  };
})();
