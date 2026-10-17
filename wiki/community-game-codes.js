/* Codes are issued by the community service for connected game servers. */
((root) => {
  'use strict';
  const validCode = (value) => typeof value === 'string' && /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{12}$/.test(value);
  const publicCode = (item) => item.visibility !== 'private' && (!item.status || item.status === 'approved') && validCode(item.gameCode) ? item.gameCode : '';
  const explanation = '仅接入本站队伍码的游戏服务器可用。';
  function codeView(code, ui, {compact = false} = {}) {
    const {el} = ui, box = el('div', `community-game-code${compact ? ' community-game-code-compact' : ''}`);
    const label = el(compact ? 'span' : 'label', 'community-game-code-label', compact ? '队伍码' : '游戏队伍码');
    const input = el('input', 'community-game-code-value'); input.type = 'text'; input.readOnly = true; input.value = code;
    input.setAttribute('aria-label', '游戏队伍码，可选中文本复制'); input.spellcheck = false;
    input.addEventListener('click', () => input.select());
    const copy = el('button', 'secondary-button', compact ? '复制' : '复制游戏码'); copy.type = 'button';
    copy.setAttribute('aria-label', '复制游戏队伍码');
    const status = el('span', 'community-game-code-copy-status'); status.setAttribute('role', 'status');
    copy.addEventListener('click', async (event) => {
      event?.stopPropagation?.(); copy.disabled = true; status.textContent = '';
      try {
        if (root.isSecureContext === false || !root.navigator?.clipboard?.writeText) throw new Error('clipboard unavailable');
        await root.navigator.clipboard.writeText(code); status.textContent = '已复制。';
      } catch {
        input.focus(); input.select(); status.textContent = '请复制上方已选中的队伍码。';
      } finally {copy.disabled = false;}
    });
    if (compact) {
      const row = el('div', 'community-game-code-row'); row.append(input, copy);
      box.append(label, row, status); box.title = explanation;
    } else {
      label.append(input);
      const actions = el('div', 'community-game-code-actions'); actions.append(copy, status);
      box.append(label, actions, el('p', 'muted community-game-code-note', explanation));
    }
    return box;
  }
  function readonly(item, ui, options) {const code = publicCode(item); return code ? codeView(code, ui, options) : null;}
  // The administrator API has already checked access to private team records.
  function adminReadonly(item, ui, options) {
    return item.status === 'approved' && validCode(item.gameCode) ? codeView(item.gameCode,ui,options) : null;
  }
  function controls(item, ui, request, {mutationBlocked = () => '', onBusyChange = () => {}} = {}) {
    const {el} = ui, section = el('details', 'community-game-code-manager');
    section.append(el('summary', '', '游戏队伍码管理'));
    const status = el('p', 'community-game-code-status'); status.setAttribute('role', 'status');
    const preview = el('div'), actions = el('div', 'community-game-code-actions');
    const make = el('button', 'secondary-button', '公开队伍码'), revoke = el('button', 'secondary-button', '停用游戏码');
    const refresh = el('button', 'secondary-button', '刷新状态');
    [make, revoke, refresh].forEach((button) => {button.type = 'button';});
    actions.append(make, revoke, refresh); section.append(preview, status, actions);
    if (item.visibility === 'private') section.append(el('p', 'muted community-game-code-note', '公开队伍码后，持有码的玩家可在已接入的游戏服务器导入阵容；队伍仍保存在我的空间，不进入配队大全。'));
    let state = {gameCode: null, active: false, teamRevision: Number(item.revision)}, busy = false, loaded = false, conflict = false, guardMessage = '';
    const base = `/admin/teams/${encodeURIComponent(item.id)}/game-code`;
    function paint() {
      const blocked = mutationBlocked();
      make.disabled = busy || conflict || Boolean(blocked) || item.status !== 'approved';
      revoke.disabled = busy || conflict || Boolean(blocked) || !state.active; refresh.disabled = busy;
      make.textContent = state.active ? '复用已公开队伍码' : '公开队伍码';
      if (blocked) status.textContent = blocked;
      else if (guardMessage && status.textContent === guardMessage) status.textContent = '已恢复到保存版本，可管理队伍码。';
      guardMessage = blocked;
    }
    function accept(result) {
      if (!result || typeof result.active !== 'boolean' || (result.active && !validCode(result.gameCode))) {
        throw new Error('服务端未返回有效的游戏码状态，请刷新核实。');
      }
      const revision = Number(result.teamRevision);
      if (!Number.isSafeInteger(revision) || revision !== state.teamRevision) {
        throw Object.assign(new Error('队伍版本已变化，请重新加载管理列表。'), {code: 'edit_conflict'});
      }
      state = {gameCode: result.active ? result.gameCode : null, active: result.active, teamRevision: revision};
      item.revision = revision; item.gameCode = state.gameCode;
      preview.replaceChildren(); if (state.active) preview.append(codeView(state.gameCode, ui));
      loaded = true;
    }
    async function run(operation) {
      if (busy || (operation !== 'refresh' && conflict)) return;
      if (operation !== 'refresh' && mutationBlocked()) {paint(); return;}
      if (operation === 'make' && item.status !== 'approved') {status.textContent = '已隐藏或停用的队伍不能公开队伍码。'; return;}
      if (operation !== 'refresh' && !Number.isSafeInteger(state.teamRevision)) {status.textContent = '队伍版本缺失，请重新加载管理列表。'; return;}
      busy = true; onBusyChange(); paint(); status.textContent = '正在读取服务端游戏码…';
      try {
        const result = await request(operation === 'revoke' ? `${base}/revoke` : base,
          operation === 'refresh' ? undefined : {expectedRevision: state.teamRevision}, operation === 'refresh' ? 'GET' : 'POST');
        if (!section.isConnected) return;
        accept(result); conflict = false;
        status.textContent = item.status !== 'approved' ? '已隐藏或停用的队伍不能公开队伍码。'
          : operation === 'revoke' ? '游戏码已停用，旧码将不能再导入。'
            : state.active ? '这是服务端保存的有效游戏码。' : '尚无队伍码。点击“公开队伍码”后才能分享给游戏玩家。';
      } catch (error) {
        if (!section.isConnected) return;
        conflict = conflict || error.code === 'edit_conflict';
        if (conflict) {preview.replaceChildren(); state.active = false; item.gameCode = null;}
        status.textContent = conflict ? '队伍已被修改，请重新加载管理列表后操作。' : root.WFCommunity.message(error);
      } finally {busy = false; if (section.isConnected) {paint(); onBusyChange();}}
    }
    section.addEventListener('toggle', () => {if (section.open && !loaded) run('refresh');});
    make.addEventListener('click', () => run('make')); revoke.addEventListener('click', () => run('revoke'));
    refresh.addEventListener('click', () => run('refresh')); paint();
    section.refreshAvailability = paint;
    section.isBusy = () => busy;
    return section;
  }
  const api = {validCode, publicCode, readonly, adminReadonly, controls}; root.WFCommunityGameCodes = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
