/* Team inspection loads full character data without navigating away from the plate. */
(() => {
  'use strict';
  let detailOrigin = null;
  function matches(route) {
    if (!detailOrigin) return false;
    const parts = route.replace(/^#/, '').split('/');
    let id; try {id = decodeURIComponent(parts[1] || '');} catch {return false;}
    return detailOrigin.has(`${parts[0]}/${id}`);
  }
  window.addEventListener('hashchange', () => {if (!matches(window.location.hash)) detailOrigin = null;});
  function remember(kind, id) {
    if (!['character','weapon'].includes(kind) || !id) return;
    detailOrigin = new Set([`${kind}/${String(id)}`]);
  }
  // Keep explicitly followed variants in one browsing chain, including Back/Forward.
  function rememberVariant(id) {
    if (id && matches(window.location.hash)) detailOrigin.add(`character/${String(id)}`);
  }
  function attachReturn(host, route, ui) {
    if (!matches(route)) return;
    const summaryBack = host.querySelector('.summary-back-link');
    if (summaryBack) {summaryBack.href = '#team'; summaryBack.textContent = '‹ 返回当前编队'; return;}
    const link = ui.el('a', 'back-button team-return-link', '‹ 返回当前编队'); link.href = '#team';
    host.prepend(link);
  }
  function create(data, ui, avatars) {
    const {el} = ui, root = el('aside', 'team-inspector'); root.setAttribute('aria-label', '编队角色面板');
    const heading = el('div', 'team-inspector-heading'), body = el('div', 'team-inspector-body');
    const status = el('p', 'team-inspector-status'); status.setAttribute('role', 'status');
    const details = el('a', 'text-button', '查看完整资料'); details.hidden = true;
    heading.append(el('h2', '', '角色面板'), details); root.append(heading, status, body);
    const characters = new Map((data.characters || []).map((item) => [String(item.id), item]));
    let revision = 0, currentId = '', state = '';
    details.addEventListener('click', () => remember('character', currentId));
    async function show(value, force = false) {
      const id = String(value || ''); if (!force && id === currentId && state && state !== 'error') return;
      currentId = id; const ticket = ++revision; state = 'loading'; details.hidden = true; body.replaceChildren();
      const current = () => root.isConnected && ticket === revision && currentId === id && window.location.hash === '#team';
      const brief = characters.get(id);
      if (!brief) {state = 'empty'; status.textContent = '点击盘子里的角色头像，在这里查看属性、技能、队长技与能力。'; return;}
      status.textContent = `正在载入 ${brief.name || '角色'} 的资料…`;
      try {
        const character = window.WFWikiData?.loadCharacter ? await window.WFWikiData.loadCharacter(id) : brief;
        if (!current()) return;
        if (!character || String(character.id) !== id) throw new Error('未找到这位角色的完整资料。');
        if (typeof window.renderWikiCharacterSummary !== 'function') throw new Error('角色面板尚未加载，请刷新页面后重试。');
        window.renderWikiCharacterSummary(body, character, data.meta || {}, ui, {onOpenDetails: (tab) => {
          remember('character', id); window.location.hash = `#character/${encodeURIComponent(id)}/details/${tab || 'profile'}`;
        }, onVariantNavigate: (variantId) => remember('character', variantId)});
        const portrait = avatars && body.querySelector('.summary-avatar');
        if (portrait) portrait.replaceChildren(avatars.picture(character, character.name || '角色'));
        details.href = `#character/${encodeURIComponent(id)}/details/profile`; details.hidden = false;
        status.textContent = ''; state = 'ready';
      } catch (error) {
        if (!current()) return;
        state = 'error'; status.textContent = error.message || '角色资料暂时无法载入。';
        const retry = el('button', 'secondary-button', '重新载入角色资料'); retry.type = 'button'; retry.addEventListener('click', () => show(id, true)); body.append(retry);
      }
    }
    return {element:root, show};
  }
  window.WFTeamInspector = {create, remember, rememberVariant, attachReturn};
})();
