/* Dungeon rewards and shops load only when their pages are opened. */
(() => {
  'use strict';
  let pending;
  const valid = (value) => value?.schemaVersion === 1 && Array.isArray(value.shops)
    && value.dungeons && typeof value.dungeons === 'object' && !Array.isArray(value.dungeons)
    && value.shops.every((shop) => shop && /^[a-z0-9][a-z0-9-]{0,79}$/.test(shop.id)
      && typeof shop.title === 'string' && Array.isArray(shop.items));
  window.WFWikiData.loadRewards = async () => {
    if (valid(window.WF_WIKI_REWARDS)) {
      window.WF_WIKI.rewards = window.WF_WIKI_REWARDS;
      return window.WF_WIKI_REWARDS;
    }
    if (!pending) pending = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      let finished = false;
      const finish = (error) => {
        if (finished) return;
        finished = true; clearTimeout(timer); script.remove();
        if (error) reject(error);
        else {window.WF_WIKI.rewards = window.WF_WIKI_REWARDS; resolve(window.WF_WIKI_REWARDS);}
      };
      const timer = setTimeout(() => finish(new Error('掉落与商店资料加载超时，请重试。')), 30000);
      script.src = 'rewards-data.js'; script.async = true;
      script.onload = () => finish(valid(window.WF_WIKI_REWARDS) ? null : new Error('掉落与商店资料不完整，请重新导出或刷新。'));
      script.onerror = () => finish(new Error('掉落与商店资料暂未载入，请检查离线文件或重试。'));
      document.head.append(script);
    }).finally(() => {pending = null;});
    return pending;
  };
})();
