/* Passwords stay in the active form only; the server owns every session decision. */
(() => {
  'use strict';
  const C = window.WFCommunity;
  const request = (...args) => C.client.request(...args);
  const messages = {
    invalid_credentials:'邮箱或密码不正确。', login_failed:'邮箱或密码不正确。',
    invalid_password:'密码须为 8–128 个字符。', password_policy:'密码须为 8–128 个字符。',
    password_change_required:'请先修改临时密码。', incorrect_password:'当前密码不正确。',
    invalid_current_password:'当前密码不正确。', same_password:'新密码必须与当前密码不同。',
    bootstrap_unavailable:'站长初始化尚未配置，请联系网站维护者。', bootstrap_complete:'站长已设置，请重新打开登录页。',
    setup_complete:'站长已设置，请重新打开登录页。', auth_not_configured:'管理员登录尚未配置，请联系网站维护者。',
    bootstrap_forbidden:'站长初始化信息不匹配或尚未开放，请检查邮箱与初始化密钥。',
    password_unchanged:'新密码必须与当前密码不同。', role_forbidden:'副站长只能管理普通管理员。',
    owner_immutable:'站长账号不能在账号列表中修改，请使用“修改密码”。',
    invalid_bootstrap_token:'初始化密钥无效，请检查后重试。', bootstrap_email_mismatch:'请填写部署时指定的站长邮箱。',
    invalid_email:'请填写有效的邮箱地址。', verification_failed:'验证未通过，请重新完成验证。',
    turnstile_failed:'验证未通过，请重新完成验证。', account_disabled:'该账号已停用，请联系站长。',
    challenge_unavailable:'验证服务暂时不可用，请稍后重新验证并登录。',
    challenge_failed:'人机验证失败或已过期，请重新验证。', challenge_required:'请先完成人机验证。',
  };
  function message(error) {
    if (error?.status === 429) return '操作较频繁，请稍后再试。';
    if (error?.status === 401 && !messages[error.code]) return '登录已失效，请重新登录。';
    return messages[error?.code] || '操作未完成，请检查网络或稍后重试。';
  }
  function button(ui, label, handler) {
    const node = ui.el('button', 'secondary-button', label); node.type = 'button'; node.addEventListener('click', handler); return node;
  }
  function field(ui, label, type, autocomplete) {
    const wrapper = ui.el('label', 'community-auth-field'), input = ui.el('input');
    input.type = type; input.required = true; input.autocomplete = autocomplete; input.setAttribute('aria-label', label);
    if (type === 'password') {input.minLength = 8; input.maxLength = 128;} else input.maxLength = 254;
    wrapper.append(ui.el('span', '', label), input); return {wrapper, input};
  }
  function mount(host, ui, title) {
    host.authCleanup?.();
    const form = ui.el('form', 'community-auth-form'), status = ui.el('p', 'community-auth-status');
    status.setAttribute('role', 'status'); form.append(ui.el('h2', '', title)); host.replaceChildren(form);
    const passwords = [], cleanups = [];
    const clear = () => passwords.forEach((input) => {input.value = '';});
    let cleaned = false;
    const cleanup = () => {if (cleaned) return; cleaned = true; clear(); cleanups.forEach((fn) => fn()); window.removeEventListener?.('wf-page-leave', cleanup);};
    host.authCleanup = cleanup; window.addEventListener?.('wf-page-leave', cleanup, {once:true});
    const add = (label, type, autocomplete) => {
      const value = field(ui, label, type, autocomplete); form.append(value.wrapper);
      if (type === 'password') passwords.push(value.input); return value.input;
    };
    const submit = (label, action, isReady = () => true) => {
      const save = ui.el('button', 'primary-button', label); save.type = 'submit'; form.append(status, save);
      let busy = false;
      form.addEventListener('submit', async (event) => {
        event.preventDefault(); if (busy || save.disabled || cleaned) return;
        busy = true; save.disabled = true; status.textContent = '正在提交…';
        try {await action();} catch (error) {if (form.isConnected) status.textContent = message(error);}
        finally {clear(); busy = false; if (!cleaned) save.disabled = !isReady();}
      });
      return save;
    };
    return {form, status, add, submit, clear, cleanup, cleanups};
  }
  function password(host, identity, ui, done, {beforeAction = () => true, onBusyChange = () => {}} = {}) {
    const box = mount(host, ui, identity.mustChangePassword ? '首次登录：修改临时密码' : '修改登录密码');
    box.form.append(ui.el('p', 'muted', '新密码为 8–128 个字符。修改成功后使用新密码继续登录。'));
    const current = box.add('当前密码', 'password', 'current-password');
    const next = box.add('新密码', 'password', 'new-password'), confirm = box.add('确认新密码', 'password', 'new-password');
    box.submit('保存新密码', async () => {
      if (next.value.length < 8 || next.value.length > 128) {box.status.textContent = messages.invalid_password; return;}
      if (next.value !== confirm.value) {box.status.textContent = '两次输入的新密码不一致。'; return;}
      if (next.value === current.value) {box.status.textContent = messages.same_password; return;}
      if (!await beforeAction()) {box.status.textContent = '已取消操作，队伍修改仍保留。'; return;}
      onBusyChange(true);
      try {await request('/auth/password', {currentPassword:current.value, newPassword:next.value}, 'POST');}
      finally {onBusyChange(false);}
      box.cleanup(); await done();
    });
    if (!identity.mustChangePassword) box.form.append(button(ui, '取消修改', async () => {if (await beforeAction()) {box.cleanup(); await done();}}));
    box.form.append(button(ui, '退出登录', async () => {
      if (!await beforeAction()) return;
      try {
        onBusyChange(true);
        try {await request('/auth/logout', {}, 'POST');} finally {onBusyChange(false);}
        box.cleanup(); await done();
      }
      catch (error) {box.status.textContent = message(error);}
    }));
  }
  function login(host, config, ui, done) {
    const setup = config.needsSetup === true, box = mount(host, ui, setup ? '设置站长账号' : '管理员登录');
    if (setup && config.bootstrapAvailable !== true) {
      box.form.append(ui.el('p', '', messages.bootstrap_unavailable)); return;
    }
    box.form.append(ui.el('p', 'muted', setup ? '使用部署时指定的站长邮箱，自行设置密码。邮箱仅用作登录名。' : '账号由站长创建，本站不开放注册。'));
    const email = box.add('登录邮箱', 'email', 'username'), secret = box.add(setup ? '站长密码' : '登录密码', 'password', setup ? 'new-password' : 'current-password');
    const confirm = setup ? box.add('确认站长密码', 'password', 'new-password') : null;
    const local = config.development === true && ['localhost','127.0.0.1','[::1]'].includes(window.location.hostname);
    const token = setup && !local ? box.add('初始化密钥', 'password', 'off') : null;
    if (token) {token.minLength = 1; token.maxLength = 512;}
    const challengeHost = ui.el('div', 'community-auth-challenge'); if (!setup) box.form.append(challengeHost);
    let challenge, verified = false;
    const save = box.submit(setup ? '创建站长账号' : '登录', async () => {
      if (secret.value.length < 8 || secret.value.length > 128) {box.status.textContent = messages.invalid_password; return;}
      if (confirm && secret.value !== confirm.value) {box.status.textContent = '两次输入的站长密码不一致。'; return;}
      const payload = {email:email.value.trim(), password:secret.value};
      if (setup && token) payload.bootstrapToken = token.value;
      if (!setup) {
        payload.turnstileToken = challenge?.take() || '';
        if (!payload.turnstileToken) {box.status.textContent = '请先完成人机验证。'; return;}
      }
      try {await request(setup ? '/auth/bootstrap' : '/auth/login', payload, 'POST'); box.cleanup(); await done();}
      finally {challenge?.reset();}
    }, () => setup || verified);
    if (!setup) {
      save.disabled = true;
      challenge = C.challenge(challengeHost, config, 'admin_login', ui, (ready) => {verified = ready; save.disabled = !ready;});
      box.cleanups.push(() => challenge.destroy());
    }
  }
  async function ensure(host, config, ui, ready) {
    host.authCleanup?.(); host.replaceChildren();
    if (config.needsSetup) {login(host, config, ui, ready); return null;}
    let identity;
    try {identity = await request('/auth/me');}
    catch (error) {if (error.status === 401) {login(host, config, ui, ready); return null;} throw error;}
    if (!identity?.id || !identity.email || !['owner','deputy','editor'].includes(identity.role)) throw new Error('invalid_identity');
    if (identity.mustChangePassword) {password(host, identity, ui, ready); return null;}
    return identity;
  }
  function controls(host, identity, ui, refresh, {beforeAction = () => true, onBusyChange = () => {}} = {}) {
    host.authCleanup?.(); host.replaceChildren();
    const actions = ui.el('div', 'community-auth-actions'), status = ui.el('p', 'community-auth-status'); status.setAttribute('role', 'status');
    const settings = ui.el('div');
    actions.append(button(ui, '修改密码', async () => {if (await beforeAction()) password(settings, identity, ui, refresh,{beforeAction,onBusyChange});}), button(ui, '退出登录', async () => {
      if (!await beforeAction()) return;
      try {
        onBusyChange(true);
        try {await request('/auth/logout', {}, 'POST');} finally {onBusyChange(false);}
        host.authCleanup?.(); settings.authCleanup?.(); await refresh();
      }
      catch (error) {status.textContent = message(error);}
    }));
    if (['owner','deputy'].includes(identity.role) && window.WFCommunityAccounts) actions.append(button(ui, '管理员账号', async () => {
      if (!await beforeAction()) return;
      settings.authCleanup?.(); await window.WFCommunityAccounts.render(settings, ui, identity);
    }));
    host.append(actions, status, settings);
    host.authCleanup = () => settings.authCleanup?.();
  }
  function header(link) {
    if (!link || !C?.client?.observeIdentity || link.adminCleanup) return;
    link.adminCleanup = C.client.observeIdentity((identity) => {
      link.title = identity?.email ? `已登录：${identity.email} · 打开管理` : '管理员登录';
      link.setAttribute('aria-label', link.title);
      link.setAttribute('data-authenticated', String(Boolean(identity)));
    });
    // One check when opening the site. Login/logout and other identity requests
    // update this label directly; navigation never schedules another check.
    if (C.client.identity() === undefined) C.client.config().then((config) => {
      if (!config.needsSetup && C.client.identity() === undefined) return request(config.authMode === 'password' ? '/auth/me' : '/admin/me');
    }).catch(() => {});
  }
  window.WFCommunityAuth = {ensure, controls, password, message, field, header};
  if (typeof document !== 'undefined') header(document.getElementById('site-admin'));
})();
