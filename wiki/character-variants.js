/* Load the small, verified family index only when a character overview asks for it. */
(() => {
  'use strict';
  const mounts = new WeakMap();
  let pending = null;
  const data = () => window.WF_WIKI || {};
  function valid(value) {
    if (!value || value.schemaVersion !== 1 || !/^[a-f0-9]{16}$/.test(value.dataVersion || '') || !value.groups || typeof value.groups !== 'object') return false;
    const version = data().meta?.characterVariants?.version;
    if (version && value.dataVersion !== version) return false;
    const ids = new Set((data().characters || []).map((character) => String(character.id)));
    return Object.entries(value.groups).every(([id, members]) => ids.has(id) && Array.isArray(members)
      && members.length >= 2 && members.length <= ids.size && members.includes(id)
      && new Set(members).size === members.length && members.every((member) => ids.has(member)));
  }
  function load() {
    if (valid(window.WF_CHARACTER_VARIANTS)) return Promise.resolve(window.WF_CHARACTER_VARIANTS);
    if (pending) return pending;
    pending = new Promise((resolve, reject) => {
      const entry = data().meta?.characterVariants || {url: 'data/character-variants.js'};
      if (entry.url !== 'data/character-variants.js') {reject(new Error('角色版本资料地址无效。')); return;}
      const script = document.createElement('script');
      let finished = false;
      const finish = (error) => {
        if (finished) return; finished = true; clearTimeout(timer); script.remove();
        if (error) reject(error); else resolve(window.WF_CHARACTER_VARIANTS);
      };
      const timer = setTimeout(() => finish(new Error('角色版本资料加载超时。')), 20000);
      script.src = entry.url + (entry.version ? `?v=${encodeURIComponent(entry.version)}` : ''); script.async = true;
      script.onload = () => finish(valid(window.WF_CHARACTER_VARIANTS) ? null : new Error('角色版本资料不完整，请刷新重试。'));
      script.onerror = () => finish(new Error('角色版本资料暂时无法加载。'));
      document.head.append(script);
    }).finally(() => {pending = null;});
    return pending;
  }
  window.WFCharacterVariants = {async mount(host, character, ui, {onNavigate} = {}) {
    const token = {}; mounts.set(host, token); host.replaceChildren();
    const {el, picture, safeUrl} = ui;
    try {
      const index = await load();
      if (mounts.get(host) !== token || !host.isConnected) return;
      const members = index.groups[String(character.id)];
      if (!members?.length) return;
      const byId = new Map((data().characters || []).map((entry) => [String(entry.id), entry]));
      const section = el('section', 'character-variants'); section.setAttribute('aria-label', '同角色其他版本');
      section.append(el('h2', '', '同角色其他版本'));
      const links = el('div', 'character-variants-list');
      for (const id of members) {
        const entry = byId.get(id); if (!entry) continue;
        const current = id === String(character.id), label = [entry.title, entry.theme, entry.origin === '官方原版' ? '' : entry.origin].filter(Boolean).join(' · ');
        const link = el('a', 'character-variant'); link.href = `#character/${id}`;
        link.title = `${entry.name} · ${label}`; link.setAttribute('aria-label', `${entry.name}，${label}${current ? '，当前版本' : '，查看此版本'}`);
        if (current) link.setAttribute('aria-current', 'page');
        link.append(picture(safeUrl(entry.avatars?.before) || safeUrl(entry.icon), entry.name, 'character-variant-avatar'));
        link.append(el('span', 'character-variant-label', current ? '当前版本' : entry.theme || entry.title || entry.name));
        link.addEventListener('click', (event) => {
          if (!event.defaultPrevented && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && !event.button) onNavigate?.(id);
        });
        links.append(link);
      }
      section.append(links); host.append(section);
    } catch (error) {
      if (mounts.get(host) !== token || !host.isConnected) return;
      const retry = el('button', 'text-button', '重新加载其他版本'); retry.type = 'button'; retry.title = error.message;
      retry.addEventListener('click', () => window.WFCharacterVariants.mount(host, character, ui, {onNavigate})); host.append(retry);
    }
  }};
})();
