/* The global portrait shortcut sits next to the scroll-to-top control. */
(() => {
  'use strict';
  const avatars = window.WFCatalogAvatars;
  if (!avatars || !document.getElementById('back-to-top') || document.getElementById('avatar-shortcut')) return;
  const button = document.createElement('button');
  button.id = 'avatar-shortcut'; button.className = 'avatar-shortcut'; button.type = 'button';
  const label = document.createElement('span'), state = document.createElement('span');
  label.className = 'avatar-shortcut-label'; label.textContent = '头像';
  button.append(label, state); document.body.append(button);
  function updateVisibility() {
    const hash = window.location.hash || '', parts = hash.slice(1).split('/');
    const supported = ['', '#', '#main-content', '#team'].includes(hash)
      || (parts[0] === 'community' && parts.length <= 2 && parts[1] !== 'admin');
    button.hidden = !supported || window.scrollY < 320;
  }
  function updateChoice() {
    const after = avatars.getForm() === 'after';
    state.textContent = after ? '觉醒后' : '觉醒前';
    button.setAttribute('aria-label', '使用角色觉醒后头像');
    button.setAttribute('aria-pressed', String(after));
    button.title = `当前${state.textContent}头像，点击切换为${after ? '觉醒前' : '觉醒后'}`;
  }
  button.addEventListener('click', () => avatars.setForm(avatars.getForm() === 'after' ? 'before' : 'after'));
  avatars.subscribe(updateChoice);
  window.addEventListener('scroll', updateVisibility, {passive:true});
  window.addEventListener('hashchange', updateVisibility);
  updateChoice(); updateVisibility();
})();
