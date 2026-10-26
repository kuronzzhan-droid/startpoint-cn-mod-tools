/* Explicit, per-operation verification. No verification token is persisted. */
(() => {
  'use strict';
  const C = window.WFCommunity;
  let scriptPromise;
  function loadTurnstile() {
    if (window.turnstile?.render) return Promise.resolve(window.turnstile);
    if (!scriptPromise) scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const timeout = setTimeout(() => fail(), 15000);
      const fail = () => {clearTimeout(timeout); script.remove(); reject(new Error('人机验证加载失败，请检查网络后重试。'));};
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'; script.async = true;
      script.addEventListener('load', () => {clearTimeout(timeout); window.turnstile?.render ? resolve(window.turnstile) : fail();}, {once: true});
      script.addEventListener('error', fail, {once: true}); document.head.append(script);
    }).catch((error) => {scriptPromise = null; throw error;});
    return scriptPromise;
  }
  C.challenge = (host, config, action, ui, onChange = () => {}) => {
    const {el} = ui;
    let token = '', widget, disposed = false, busy = false;
    const notice = el('p', 'community-verification-status', '请完成人机验证后再提交。'); notice.setAttribute('role', 'status');
    const target = el('div', 'community-verification-widget');
    const retry = el('button', 'secondary-button', '重新加载验证'); retry.type = 'button'; retry.hidden = true;
    host.append(notice, target, retry);
    const update = (value, text) => {if (!disposed) {token = value; notice.textContent = text; onChange(Boolean(token));}};
    const local = config.development === true && ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
    async function mount() {
      if (disposed || busy) return;
      busy = true; retry.hidden = true;
      try {
        if (local) {
          const button = el('button', 'secondary-button', '本机测试：完成验证'); button.type = 'button';
          button.addEventListener('click', async () => {
            button.disabled = true;
            try {
              const value = await C.client.request(`/development-challenge?action=${encodeURIComponent(action)}`);
              update(value.token, '本机测试验证完成（仅此本地预览）。');
            } catch (error) {update('', C.message(error));} finally {button.disabled = false;}
          });
          target.replaceChildren(el('p', 'muted', '这是本机测试验证，公开网站使用真实人机验证。'), button);
        } else {
          if (!config.siteKey) throw new Error('社区的人机验证尚未配置，暂时无法完成此操作。');
          const turnstile = await loadTurnstile(); if (disposed) return;
          widget = turnstile.render(target, {sitekey: config.siteKey, action, size: 'flexible', language: 'zh-cn',
            theme: document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light',
            'response-field': false, callback: (value) => update(value, '验证完成。'),
            'expired-callback': () => update('', '验证已过期，请重新完成验证。'),
            'error-callback': () => {update('', '验证失败，请重试。'); retry.hidden = false;},
          });
        }
      } catch (error) {update('', C.message(error)); retry.hidden = false;} finally {busy = false;}
    }
    function reset() {
      if (disposed) return;
      update('', '请重新完成人机验证。');
      if (widget !== undefined) window.turnstile.reset(widget);
    }
    retry.addEventListener('click', () => {
      if (widget !== undefined) {window.turnstile.remove(widget); widget = undefined;}
      target.replaceChildren(); mount();
    });
    mount();
    return {take: () => {const value = token; token = ''; onChange(false); return value;}, reset,
      destroy: () => {disposed = true; token = ''; if (widget !== undefined) window.turnstile?.remove(widget);}};
  };
  C.dialog = (title, ui) => {
    const {el} = ui, previous = document.activeElement;
    const dialog = el('dialog', 'community-dialog'); const heading = el('h2', '', title);
    heading.id = `community-dialog-${Math.random().toString(36).slice(2)}`;
    dialog.setAttribute('aria-labelledby', heading.id);
    const close = el('button', 'secondary-button', '关闭'); close.type = 'button';
    close.addEventListener('click', () => dialog.close());
    const header = el('div', 'community-dialog-header'); header.append(heading, close); dialog.append(header);
    let cleanup = () => {};
    const hashchange = () => dialog.close();
    dialog.addEventListener('close', () => {cleanup(); window.removeEventListener('hashchange', hashchange); dialog.remove(); if (previous?.isConnected) previous.focus();}, {once: true});
    window.addEventListener('hashchange', hashchange);
    document.body.append(dialog); dialog.showModal();
    return {element: dialog, cleanup: (callback) => {cleanup = callback;}};
  };
})();
