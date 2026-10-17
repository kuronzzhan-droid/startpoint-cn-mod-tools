/* Keep activity metadata and banners out of the initial character catalogue. */
(() => {
  'use strict';
  let pending;
  const valid = (value) => value?.schemaVersion === 1 && Array.isArray(value.items)
    && value.items.every((item) => item && /^[a-z0-9][a-z0-9-]{0,79}$/.test(item.id)
      && typeof item.title === 'string' && typeof item.category === 'string');
  window.WFWikiData.loadDungeons = async () => {
    if (valid(window.WF_WIKI_DUNGEONS)) {
      window.WF_WIKI.dungeons = window.WF_WIKI_DUNGEONS;
      return window.WF_WIKI_DUNGEONS;
    }
    if (!pending) pending = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      let finished = false;
      const finish = (error) => {
        if (finished) return;
        finished = true; clearTimeout(timer); script.remove();
        if (error) reject(error);
        else {window.WF_WIKI.dungeons = window.WF_WIKI_DUNGEONS; resolve(window.WF_WIKI_DUNGEONS);}
      };
      const timer = setTimeout(() => finish(new Error('副本资料加载超时，请重试。')), 30000);
      script.src = 'dungeons-data.js'; script.async = true;
      script.onload = () => finish(valid(window.WF_WIKI_DUNGEONS) ? null : new Error('副本资料不完整，请重新导出或刷新。'));
      script.onerror = () => finish(new Error('副本资料暂未载入，请检查离线文件或重试。'));
      document.head.append(script);
    }).finally(() => {pending = null;});
    return pending;
  };
})();
