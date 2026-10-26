/* Ordinary Wiki pages never request battle runtime, content or media. */
(() => {
  'use strict';
  const value = document.currentScript?.dataset?.battleVersion;
  const version = /^[a-zA-Z0-9_-]{1,64}$/.test(value || '') ? value : 'dev';
  const modules = ['targets', 'effects', 'waves', 'model', 'storage', 'media', 'clock', 'render', 'input', 'selection', 'page'];
  const pending = new Map(), ready = new Set();
  let loading;
  const contentReady = () => {
    const data = window.WF_BATTLE_CONTENT;
    return data?.schema === 1 && data.characters && Object.keys(data.characters).length > 0
      && data.media && Object.keys(data.characters).every(id => data.media[id])
      && Array.isArray(data.stages) && data.stages.length > 0 && typeof data.coffin?.url === 'string';
  };
  function resource(path, validate, stylesheet = false) {
    if (ready.has(path)) return Promise.resolve();
    if (pending.has(path)) return pending.get(path);
    const promise = new Promise((resolve, reject) => {
      const node = document.createElement(stylesheet ? 'link' : 'script');
      let finished = false;
      const finish = (error) => {
        if (finished) return;
        finished = true; clearTimeout(timer);
        if (error || !stylesheet) node.remove();
        if (error) reject(error); else {ready.add(path); resolve();}
      };
      const timer = setTimeout(() => finish(new Error('放置挑战加载超时，请重试。')), 30000);
      if (stylesheet) {node.rel = 'stylesheet'; node.href = `${path}?v=${version}`;}
      else {node.async = true; node.src = `${path}?v=${version}`;}
      node.onload = () => finish(validate() ? null : new Error('放置挑战资料不完整，请重试。'));
      node.onerror = () => finish(new Error('放置挑战暂时无法加载，请检查网络后重试。'));
      document.head.append(node);
    }).finally(() => pending.delete(path));
    pending.set(path, promise);
    return promise;
  }
  async function runtime() {
    for (const name of modules) {
      const key = name === 'page' ? 'renderWikiBattle' : `WFBattle${name[0].toUpperCase()}${name.slice(1)}`;
      await resource(`battle-${name}.js`, () => name === 'page' ? typeof window[key] === 'function' : Boolean(window[key]));
    }
  }
  window.WFBattleLoader = {
    load() {
      if (!loading) loading = Promise.all([
        resource('battle.css', () => true, true),
        resource('data/battle-content.js', contentReady),
        runtime(),
      ]).then(() => window.WF_BATTLE_CONTENT).finally(() => {loading = null;});
      return loading;
    },
  };
})();
