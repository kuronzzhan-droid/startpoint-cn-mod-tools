/* One portrait preference; broadcast only to controls that are still mounted. */
(() => {
  'use strict';
  const storageKey = 'wf-wiki-catalog-avatar', controllers = new Set(), listeners = new Set();
  let form = 'before';
  try { if (localStorage.getItem(storageKey) === 'after') form = 'after'; } catch { /* Offline storage may be disabled. */ }
  function prune() {
    controllers.forEach((controller) => {if (controller.group.isConnected === false) controllers.delete(controller);});
  }
  function setForm(value) {
    prune();
    const next = value === 'after' ? 'after' : 'before';
    if (next === form) return;
    form = next;
    try { localStorage.setItem(storageKey, form); } catch { /* The current page still switches. */ }
    [...controllers].forEach((controller) => controller.sync());
    [...listeners].forEach((listener) => listener(form));
  }
  window.WFCatalogAvatars = {
    getForm: () => form, setForm,
    subscribe(listener) {listeners.add(listener); return () => listeners.delete(listener);},
    create({host, catalog, characters, ui, label = '角色图鉴头像', onChange}) {
    prune();
    const {el, picture, safeUrl} = ui;
    const byId = new Map(characters.map((character) => [String(character.id), character]));
    const group = el('div', 'catalog-avatar-controls catalog-layout-group');
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', label);
    group.title = '切换图鉴、编队和配队大全的角色头像；没有对应头像时使用已收录头像';
    group.append(el('span', 'catalog-layout-label', '头像'));
    const choices = [['before', '觉醒前'], ['after', '觉醒后']];
    const buttons = choices.map(([value, label]) => {
      const button = el('button', 'catalog-layout-button', label);
      button.type = 'button';
      button.dataset.avatarForm = value;
      button.addEventListener('click', () => setForm(value));
      group.append(button);
      return button;
    });
    const paint = (host, character) => {
      const avatars = character.avatars || {};
      const wanted = safeUrl(avatars[form]);
      const url = wanted || safeUrl(character.icon) || safeUrl(avatars.before) || safeUrl(avatars.after);
      host.title = wanted ? '' : '未收录此状态的头像，显示现有头像';
      const current = host.querySelector('img');
      if (current && current.getAttribute('src') === url) return;
      const image = picture(url, host.dataset.avatarAlt || '', '');
      image.draggable = false;
      host.replaceChildren(image);
    };
    const updateButtons = () => buttons.forEach((button) =>
      button.setAttribute('aria-pressed', String(button.dataset.avatarForm === form)));
    function sync() {
      updateButtons();
      catalog.querySelectorAll('[data-catalog-avatar]').forEach((node) => {
        const character = byId.get(node.dataset.catalogAvatar);
        if (character) paint(node, character);
      });
      onChange?.(form);
    }
    updateButtons();
    host.append(group);
    controllers.add({group, sync});
    return {getForm: () => form, setForm, picture(character, alt = '', className = '') {
      const node = el('span', `catalog-avatar ${className}`.trim());
      node.dataset.catalogAvatar = String(character.id);
      node.dataset.avatarAlt = alt;
      paint(node, character);
      return node;
    }};
  }};
})();
