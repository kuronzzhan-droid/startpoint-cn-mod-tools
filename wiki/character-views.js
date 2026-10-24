/* Server-owned view totals; opening an embedded team panel never records a visit. */
((root) => {
  'use strict';
  function normalize(value, id) {
    if (!value || value.characterId !== id || !Number.isSafeInteger(value.views) || value.views < 0 || value.windowSeconds !== 1800)
      throw new Error('查看次数暂时不可用。');
    return {characterId:id,views:value.views,windowSeconds:1800};
  }
  function create(client) {
    const pending = new Map();
    function load(id, record = false) {
      const key = `${record ? 'record' : 'read'}:${id}`;
      if (!pending.has(key)) pending.set(key, (async () => {
        const path = `/characters/${encodeURIComponent(id)}/views`;
        if (!record) return normalize(await client.request(path), id);
        await client.config();
        let value;
        try {value = await client.request(path, {}, 'POST');}
        catch (error) {
          // A rate-limited network's visit goes uncounted; the panel still shows the current total.
          if (error?.status === 429) return normalize(await client.request(path), id);
          if (error?.status !== 428 || error?.code !== 'visitor_required') throw error;
          await client.config({refresh:true});
          value = await client.request(path, {}, 'POST');
        }
        return normalize(value, id);
      })().finally(() => pending.delete(key)));
      return pending.get(key);
    }
    return {load};
  }
  if (typeof module !== 'undefined') module.exports = {create,normalize};
  if (!root.WFCommunity?.client || !root.document) return;
  const service = create(root.WFCommunity.client);
  root.WFCharacterViews = {
    record(id) {return service.load(String(id), true);},
    mount(host, character, ui, options = {}) {
      const {el} = ui, id = String(character.id), startingHash = root.location.hash;
      const panel = el('div', 'character-view-count'), total = el('strong', '', '—');
      panel.setAttribute('aria-label', '角色查看次数');
      panel.title = '从功能上线后累计；同一访客在 30 分钟内重复查看这个角色只计一次。';
      panel.append(el('span', '', '已被查看'), total, el('span', '', '次'));
      const status = el('span', 'character-view-status'), retry = el('button', 'text-button', '重试');
      retry.type = 'button'; retry.hidden = true; panel.append(status,retry); host.append(panel);
      let busy = false;
      const current = () => panel.isConnected && root.location.hash === startingHash;
      async function load() {
        if (busy) return; busy = true; retry.hidden = true; status.textContent = '加载中…';
        try {
          const value = await service.load(id, Boolean(options.record));
          if (current()) {total.textContent = value.views.toLocaleString('zh-CN'); status.textContent = '';}
        } catch {
          if (current()) {status.textContent = '暂不可用'; retry.hidden = false;}
        } finally {busy = false;}
      }
      if (root.location.protocol === 'file:') status.textContent = '离线版不统计';
      else {retry.addEventListener('click', load); load();}
      return panel;
    },
  };
})(typeof window === 'undefined' ? globalThis : window);
