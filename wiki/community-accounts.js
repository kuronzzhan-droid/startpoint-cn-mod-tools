/* Only the owner can obtain or mutate this list; no role is accepted from a form. */
(() => {
  'use strict';
  const C = window.WFCommunity;
  async function render(host, ui, identity) {
    const {el} = ui, A = window.WFCommunityAuth, request = (...args) => C.client.request(...args);
    if (!['owner','deputy'].includes(identity?.role)) {host.replaceChildren(el('p', '', '只有站长或副站长可以管理管理员账号。')); return;}
    const page = el('section', 'community-accounts'), heading = el('header', 'community-accounts-heading');
    const notice = el('p', 'community-auth-status'); notice.setAttribute('role', 'status');
    const list = el('div', 'community-accounts-list'), createHost = el('div');
    let loading = false, busy = false, generation = 0, createFields, suggestion;
    function button(label, fn) {const node = el('button', 'secondary-button', label); node.type = 'button'; node.addEventListener('click', fn); return node;}
    function statusMessage(error) {
      if (error?.code === 'edit_conflict' || error?.code === 'account_conflict') return '账号已被其他操作更新，请刷新后再修改。';
      if (error?.code === 'duplicate_email' || error?.code === 'email_exists') return '该邮箱已经存在，请检查账号列表。';
      if (error?.status === 403) return '没有修改该账号的权限，请重新登录确认身份。';
      if (error?.code === 'user_limit') return '管理员账号数量已达到上限。';
      return A.message(error);
    }
    const secrets = new Set();
    const clear = () => secrets.forEach((node) => {node.value = '';});
    function cleanup() {clear(); window.removeEventListener?.('wf-page-leave', cleanup);}
    host.authCleanup?.(); host.authCleanup = cleanup; window.addEventListener?.('wf-page-leave', cleanup, {once:true});
    heading.append(el('h2', '', '管理员账号'), button('关闭账号管理', () => {cleanup(); host.replaceChildren();}));
    page.append(heading, el('p', 'muted', '普通管理员可维护配队大全；副站长还可管理普通管理员。新账号及重置密码后，首次登录必须修改临时密码。'), notice, createHost, list);
    host.replaceChildren(page);
    function create() {
      const form = el('form', 'community-account-create');
      const email = A.field(ui, '新管理员邮箱', 'email', 'off'), password = A.field(ui, '临时密码', 'password', 'new-password');
      secrets.add(password.input);
      const role = el('select'); role.setAttribute('aria-label', '账号权限');
      for (const [value, text] of [['editor','普通管理员'],['deputy','副站长']]) {const option = el('option', '', text); option.value = value; role.append(option);}
      role.value = 'editor';
      const save = el('button', 'primary-button', '创建管理员'); save.type = 'submit';
      form.append(email.wrapper, password.wrapper);
      if (identity.role === 'owner') {const field = el('label', 'community-auth-field'); field.append(el('span', '', '账号权限'), role); form.append(field);}
      form.append(save); createHost.replaceChildren(form); createFields = {email:email.input,password:password.input,role};
      form.addEventListener('submit', async (event) => {
        event.preventDefault(); if (busy) return;
        if (password.input.value.length < 8 || password.input.value.length > 128) {notice.textContent = '临时密码须为 8–128 个字符。'; return;}
        busy = true; save.disabled = true; notice.textContent = '正在创建…';
        try {
          const result = await request('/admin/users', {email:email.input.value.trim(), password:password.input.value,
            role:identity.role === 'owner' ? role.value : 'editor'}, 'POST');
          if (!result.id) throw new Error('invalid_response');
          email.input.value = ''; await load(); if (page.isConnected) notice.textContent = '管理员已创建。请自行把邮箱与临时密码告知对方；首次登录需修改密码。';
        } catch (error) {if (page.isConnected) notice.textContent = statusMessage(error);}
        finally {password.input.value = ''; busy = false; save.disabled = false;}
      });
    }
    function row(user) {
      const node = el('article', 'community-account-row'), actions = el('div', 'community-account-actions');
      node.append(el('strong', '', user.email), el('p', 'muted',
        `${user.role === 'owner' ? '站长' : user.role === 'deputy' ? '副站长' : '普通管理员'} · ${user.enabled ? '已启用' : '已停用'}${user.mustChangePassword ? ' · 登录后需改密' : ''}`));
      if (user.role === 'owner' || identity.role === 'deputy' && user.role === 'deputy') {
        node.append(el('p', 'muted', user.id === identity.id ? '自己的密码通过“修改密码”更新。' : '此账号不在你的管理权限内。')); return node;
      }
      const resetHost = el('div');
      async function update(body, success) {
        if (busy) return;
        busy = true; notice.textContent = '正在更新账号…';
        try {
          const result = await request(`/admin/users/${encodeURIComponent(user.id)}`, {expectedRevision:user.revision, ...body}, 'PATCH');
          if (!result.id || Number(result.revision) <= Number(user.revision)) throw new Error('invalid_response');
          await load(); if (page.isConnected) notice.textContent = success;
        } catch (error) {if (page.isConnected) notice.textContent = statusMessage(error);}
        finally {clear(); busy = false;}
      }
      actions.append(button(user.enabled ? '停用账号' : '启用账号', () => update({enabled:!user.enabled}, user.enabled ? '账号已停用，其现有登录已失效。' : '账号已启用。')),
        button('重置临时密码', () => {
          clear();
          const form = el('form', 'community-account-reset'), password = A.field(ui, `新临时密码：${user.email}`, 'password', 'new-password');
          secrets.add(password.input); const save = el('button', 'primary-button', '确认重置'); save.type = 'submit';
          form.append(password.wrapper, save, button('取消重置', () => {password.input.value = ''; resetHost.replaceChildren();}));
          form.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (password.input.value.length < 8 || password.input.value.length > 128) {notice.textContent = '临时密码须为 8–128 个字符。'; return;}
            await update({password:password.input.value}, '临时密码已重置，旧登录已失效；对方下次登录必须修改密码。');
          }); resetHost.replaceChildren(form);
        }));
      node.append(actions, resetHost); return node;
    }
    async function load() {
      if (loading) return;
      loading = true; const ticket = ++generation; notice.textContent = '正在载入账号…';
      try {
        const result = await request('/admin/users');
        if (!page.isConnected || ticket !== generation) return;
        if (!Array.isArray(result.items)) throw new Error('invalid_response');
        clear(); secrets.clear(); create(); list.replaceChildren(...result.items.map(row)); notice.textContent = `共 ${result.items.length} 个账号。`;
        suggestion = identity.role === 'owner' && typeof result.deputySuggestion?.email === 'string' ? result.deputySuggestion.email : '';
        suggested.hidden = !suggestion;
      } catch (error) {if (page.isConnected) notice.textContent = statusMessage(error);}
      finally {loading = false;}
    }
    const suggested = button('添加预设副站长', () => {
      if (!suggestion || !createFields) return;
      clear(); createFields.email.value = suggestion; createFields.role.value = 'deputy'; createFields.password.focus();
      notice.textContent = '已填入预设副站长邮箱，请设置临时密码并点击“创建管理员”。';
    }); suggested.hidden = true;
    heading.append(suggested, button('刷新账号', load)); await load();
  }
  window.WFCommunityAccounts = {render};
})();
