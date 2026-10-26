/* Character summaries list public recommendations; private collections stay server-side. */
(() => {
  'use strict';
  window.WFCharacterTeams = {mount(host, character, ui, options = {}) {
    const {el, picture} = ui, C = window.WFCommunity, id = String(character?.id || '');
    const startingHash = window.location?.hash;
    const byId = new Map((options.characters || []).map(item => [String(item.id), item]));
    if (id) byId.set(id, {...byId.get(id), ...character, id});
    const root = el('section', 'character-teams'); root.setAttribute('aria-label', '包含此角色的公开配队');
    const heading = el('header', 'character-teams-heading');
    heading.append(el('h2', '', '相关配队'), el('span', 'character-teams-hint', '公开队伍 · 按点赞排序'));
    const status = el('p', 'character-teams-status'); status.setAttribute('role', 'status');
    const grid = el('div', 'character-teams-grid'), actions = el('div', 'character-teams-actions');
    const more = el('button', 'secondary-button', '加载更多配队'), retry = el('button', 'secondary-button', '重试加载');
    more.type = retry.type = 'button'; more.hidden = retry.hidden = true; actions.append(more, retry);
    root.append(heading, status, grid, actions); host.append(root);
    const entries = new Map(); let cursor = '', failedCursor = '', busy = false, disposed = false, attached = root.isConnected, unsubscribe, observer;
    function destroy() {
      if (disposed) return;
      disposed = true; observer?.disconnect(); observer = undefined; unsubscribe?.(); unsubscribe = undefined;
      window.removeEventListener?.('wf-page-leave', destroy);
    }
    function current() {
      if (disposed) return false;
      if (window.location?.hash !== startingHash || (!root.isConnected && attached)) {destroy(); return false;}
      attached ||= root.isConnected; return true;
    }
    function positions(team) {
      const found = [];
      for (const group of ['main', 'unison']) for (let index = 0; index < 3; index++) {
        if (team?.[group]?.[index] === id) found.push({group, index, label: group === 'main'
          ? (index === 0 ? '队长 · 1号主位' : `${index + 1}号主位`) : `${index + 1}号合击`});
      }
      return found;
    }
    const avatars = {picture(item, alt, className) {
      const form = window.WFCatalogAvatars?.getForm?.() === 'after' ? 'after' : 'before';
      const urls = [item.avatars?.[form], item.icon, item.avatars?.before, item.avatars?.after];
      const url = urls.map(value => ui.safeUrl ? ui.safeUrl(value) : value).find(Boolean) || '';
      return picture(url, alt, className);
    }};
    function board(item, found) {
      const ids = new Set([...item.team.main, ...item.team.unison]);
      const characters = [...ids].map(key => byId.get(key)).filter(Boolean);
      const preview = C.board(item.team, {characters}, ui, {preview: true, avatars});
      found.forEach(({group, index}) => {
        const slot = preview.querySelectorAll(`.community-slot-${group}`)[index];
        if (slot) {slot.className += ' is-character-match'; slot.title = `当前角色 · ${slot.title || character.name || ''}`;}
      });
      return preview;
    }
    function card(item, found) {
      const link = el('a', 'character-team-card'); link.href = `#community/${encodeURIComponent(item.id)}`;
      link.setAttribute('aria-label', `查看队伍：${item.title || '未命名队伍'}；${character.name || '当前角色'}位于${found.map(value => value.label).join('、')}`);
      const tags = el('div', 'character-team-tags');
      tags.append(el('span', '', C.sectionLabel(item.section)), el('span', '', C.categoryLabel(item.category)));
      const position = el('p', 'character-team-position', found.map(value => value.label).join(' / '));
      const previewHost = el('div', 'character-team-preview'); previewHost.append(board(item, found));
      link.append(el('h3', '', item.title || '未命名队伍'), tags, position, previewHost);
      entries.set(item.id, {item, found, previewHost}); return link;
    }
    async function load(pageCursor = '') {
      if (busy || !current()) return;
      busy = true; failedCursor = pageCursor; root.setAttribute('aria-busy', 'true');
      more.disabled = retry.disabled = true; retry.hidden = true;
      status.textContent = entries.size ? '正在加载更多配队…' : '正在查找相关配队…';
      try {
        const params = new URLSearchParams({character: id, sort: 'popular'}); if (pageCursor) params.set('cursor', pageCursor);
        const value = await C.client.request(`/teams?${params}`); if (!current()) return;
        if (!value || !Array.isArray(value.items) || (value.nextCursor != null && typeof value.nextCursor !== 'string')
          || (pageCursor && value.nextCursor === pageCursor)) throw new Error('配队资料暂时不可用，请重试。');
        value.items.forEach(item => {
          if (!item || typeof item.id !== 'string' || !item.id || entries.has(item.id)
            || (item.visibility != null && item.visibility !== 'public') || (item.status != null && item.status !== 'approved')) return;
          const team = C.teamCopy(item.team), found = positions(team);
          if (found.length) grid.append(card({...item, team}, found));
        });
        cursor = value.nextCursor || ''; more.hidden = !cursor;
        status.textContent = entries.size ? `已显示 ${entries.size} 支公开配队，点击查看完整阵容。`
          : cursor ? '本页暂无匹配配队，可继续加载。' : `暂无包含${character.name || '此角色'}的公开配队。`;
      } catch (error) {
        if (current()) {status.textContent = C.message?.(error) || error?.message || '配队加载失败，请重试。'; retry.hidden = false; more.hidden = true;}
      } finally {
        busy = false; if (current()) {root.setAttribute('aria-busy', 'false'); more.disabled = retry.disabled = false;}
      }
    }
    more.addEventListener('click', () => load(cursor)); retry.addEventListener('click', () => load(failedCursor));
    window.addEventListener?.('wf-page-leave', destroy);
    unsubscribe = window.WFCatalogAvatars?.subscribe?.(() => {
      if (!current()) return;
      entries.forEach(({item, found, previewHost}) => previewHost.replaceChildren(board(item, found)));
    });
    if (!/^https?:$/.test(window.location?.protocol)) status.textContent = '离线版无法读取相关配队，请到在线网站查看。';
    else if (!id || !C?.client || !C?.board) status.textContent = '配队服务尚未准备好，请刷新页面重试。';
    else if (window.IntersectionObserver) {
      status.textContent = '滑到这里后加载相关配队。';
      observer = new window.IntersectionObserver(items => {
        if (!items.some(item => item.isIntersecting) || !current()) return;
        observer?.disconnect(); observer = undefined; load();
      }, {rootMargin: '160px'});
      observer.observe(root);
    } else load();
    return {element: root, destroy};
  }};
})();
