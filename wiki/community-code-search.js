/* Look up explicitly published Wiki codes without exposing private team metadata. */
(() => {
  'use strict';
  const C = window.WFCommunity, G = window.WFCommunityGameCodes;
  C.codeSearch = ({data, ui, onActiveChange = () => {}, onKeywordSearch, previewOnly = false}) => {
    const {el} = ui, startingHash = location.hash;
    const label = onKeywordSearch ? '搜索队伍或队伍码' : '搜索队伍码';
    const box = el('section', 'community-code-search'); box.setAttribute('aria-label', label);
    const form = el('form', 'community-code-search-form'); form.setAttribute('role', 'search');
    const input = el('input', 'community-code-search-input'); input.type = 'search';
    input.placeholder = onKeywordSearch ? '搜索队名、角色、攻略或队伍码' : '输入 12 位 Wiki 队伍码'; input.maxLength = 80;
    input.setAttribute('aria-label', label); input.autocomplete = 'off'; input.spellcheck = false;
    input.setAttribute('autocapitalize', 'characters'); input.setAttribute('enterkeyhint', 'search');
    const search = el('button', 'primary-button', '查找'); search.type = 'submit';
    const clear = el('button', 'text-button', previewOnly ? '清除' : '返回列表'); clear.type = 'button'; clear.hidden = true;
    const status = el('p', 'community-code-search-status'); status.setAttribute('role', 'status');
    const result = el('div', 'community-code-search-result');
    form.append(input, search, clear); box.append(form, status, result);
    let revision = 0, busy = false;
    const current = (ticket) => ticket === revision && box.isConnected && location.hash === startingHash;
    function reset() {
      ++revision; busy = false; search.disabled = false; search.textContent = '查找';
      result.replaceChildren(); status.textContent = ''; clear.hidden = true;
      box.setAttribute('aria-busy', 'false'); onActiveChange(false);
    }
    input.addEventListener('input', () => {reset(); clear.hidden = !input.value;});
    box.resetView = () => {reset(); input.value = '';};
    clear.addEventListener('click', () => {box.resetView(); input.focus(); if (onKeywordSearch) keyword('');});
    async function keyword(term) {
      const ticket = revision; busy = true; search.disabled = true; search.textContent = '查找中…';
      box.setAttribute('aria-busy', 'true');
      try {await onKeywordSearch(term);}
      catch (error) {if (current(ticket)) status.textContent = C.message(error);}
      finally {if (current(ticket)) {busy = false; search.disabled = false; search.textContent = '查找'; box.setAttribute('aria-busy', 'false');}}
    }
    function render(found, code) {
      const team = C.teamCopy(found.team), title = found.title || '队伍预览';
      const card = el('article', 'community-card community-code-result-card');
      card.append(el('h2', '', title), G.readonly({gameCode: code}, ui, {compact: true}));
      const preview = el('div', 'community-code-portraits');
      preview.append(C.board(team, data, ui, {preview: true})); card.append(preview);
      const details = el('details', 'community-code-details');
      details.append(el('summary', '', '查看角色、武器与魂珠'), C.board(team, data, ui, {showNames: true}));
      card.append(details);
      const error = C.teamError(team, data);
      if (!previewOnly) {
        const actions = el('div', 'community-actions'), use = el('button', 'primary-button', '装入 Wiki 编队'); use.type = 'button';
        use.disabled = Boolean(error); actions.append(use); card.append(actions);
        use.addEventListener('click', () => {
          if (use.disabled) return;
          try {
            window.WFTeamImport.load(C.teamCopy(team), title);
            location.hash = '#team';
          } catch (error) {status.textContent = C.message(error);}
        });
      }
      card.append(el('p', 'muted community-code-search-note', error
        ? `此阵容与当前图鉴不匹配：${error}` : previewOnly ? '查询仅供查看，不会改变当前编队。' : '游戏导入以账号实际持有的角色和装备为准。'));
      result.append(card);
    }
    form.addEventListener('submit', async (event) => {
      event.preventDefault(); if (busy) return;
      reset(); const term = input.value.trim().normalize('NFC');
      const code = term.normalize('NFKC').replace(/\s/g, '').toUpperCase();
      if (onKeywordSearch && !/^[A-Z0-9]{10}$/.test(code) && !/^[A-Z0-9]{12}$/.test(code)) {
        input.value = term; clear.hidden = !term; await keyword(term); return;
      }
      input.value = code;
      clear.hidden = false; onActiveChange(true);
      if (!G.validCode(code)) {
        status.textContent = /^[A-Z0-9]{10}$/.test(code)
          ? '这是 10 位游戏内队伍码，Wiki 暂不能查询，请在游戏内使用。'
          : '请输入完整的 12 位 Wiki 队伍码（字母和数字）。';
        return;
      }
      const ticket = revision; busy = true; search.disabled = true; search.textContent = '查找中…';
      box.setAttribute('aria-busy', 'true'); status.textContent = '正在查找队伍…';
      try {
        const found = await C.client.request(`/game-codes/${encodeURIComponent(code)}`);
        if (!current(ticket)) return;
        if (!found?.active) throw new Error('队伍码不存在或已失效。');
        if (typeof found.title !== 'string' || !['main','unison','weapon','soul'].every((key) =>
          Array.isArray(found.team?.[key]) && found.team[key].length === 3 && found.team[key].every((id) => typeof id === 'string'))) {
          throw new Error('队伍数据不完整，请稍后重试。');
        }
        await window.WFWikiData.loadEquipment();
        if (!current(ticket)) return;
        render(found, code); status.textContent = '已找到队伍';
      } catch (error) {
        if (current(ticket)) status.textContent = [404,410].includes(error.status)
          ? '队伍码不存在或已失效，请检查后重试。' : C.message(error);
      } finally {
        if (current(ticket)) {busy = false; search.disabled = false; search.textContent = '查找'; box.setAttribute('aria-busy', 'false');}
      }
    });
    return box;
  };
})();
