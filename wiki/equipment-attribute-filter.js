/* One shared attribute picker for the toolbar and the floating catalogue control. */
(() => {
  'use strict';
  const elements = ['火', '水', '雷', '风', '光', '暗'];
  let previous;
  window.WFEquipmentAttributeFilter = {
    create(ui, onChange, leadingControl) {
      previous?.destroy();
      const {el} = ui;
      let value = '', opened = false, opener, disposed = false;
      const button = el('button', 'secondary-button equipment-attribute-current');
      const floating = el('div', 'equipment-attribute-floating');
      const shortcut = el('button', 'equipment-attribute-shortcut');
      const shortcutIcon = el('span', 'equipment-attribute-shortcut-icon'); shortcutIcon.setAttribute('aria-hidden', 'true');
      const shortcutLabel = el('span', 'equipment-attribute-shortcut-label'); shortcut.append(shortcutIcon, shortcutLabel);
      floating.setAttribute('role', 'group'); floating.setAttribute('aria-label', '武器快捷操作');
      const panel = el('div', 'equipment-attribute-popover');
      const heading = el('div', 'equipment-attribute-heading');
      const closeButton = el('button', 'secondary-button', '关闭');
      const choices = el('div', 'equipment-attribute-options');
      const buttons = [];
      panel.id = 'weapon-attribute-picker'; panel.hidden = true;
      panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', '筛选武器属性');
      heading.append(el('strong', '', '武器属性'), closeButton); panel.append(heading, choices);
      [button, shortcut].forEach((trigger) => {
        trigger.type = 'button'; trigger.setAttribute('aria-controls', panel.id);
        trigger.setAttribute('aria-haspopup', 'dialog'); trigger.setAttribute('aria-expanded', 'false');
        trigger.addEventListener('click', () => opened ? close() : open(trigger));
      });
      closeButton.type = 'button'; closeButton.addEventListener('click', () => close(true));
      leadingControl?.addEventListener('click', () => close());
      ['', ...elements, '通用'].forEach((element) => {
        const option = el('button', 'secondary-button equipment-attribute-option'); option.type = 'button';
        option.setAttribute('data-weapon-element', element);
        option.setAttribute('aria-label', element ? `${element}属性武器` : '全部属性武器');
        option.append(elements.includes(element) && ui.elementBadge ? ui.elementBadge(element) : el('span', '', element || '全部'));
        option.addEventListener('click', () => {
          if (value !== element) {value = element; update(); onChange();}
          close(true);
        });
        buttons.push({option, element}); choices.append(option);
      });
      floating.append(...(leadingControl ? [leadingControl] : []), panel, shortcut);
      function update() {
        button.textContent = `属性：${value || '全部'}`;
        shortcutLabel.textContent = value || '全部';
        shortcut.setAttribute('aria-label', `筛选武器属性，当前${value || '全部'}`);
        shortcut.title = `筛选武器属性，当前${value || '全部'}`;
        shortcut.setAttribute('data-filtered', String(Boolean(value)));
        buttons.forEach(({option, element}) => option.setAttribute('aria-pressed', String(element === value)));
      }
      function close(focus = false) {
        opened = false; panel.hidden = true;
        [button, shortcut].forEach((trigger) => trigger.setAttribute('aria-expanded', 'false'));
        document.removeEventListener('pointerdown', outside);
        document.removeEventListener('keydown', keyboard);
        if (focus && opener?.isConnected) opener.focus();
      }
      function open(trigger) {
        opened = true; opener = trigger; panel.hidden = false;
        [button, shortcut].forEach((item) => item.setAttribute('aria-expanded', 'true'));
        document.addEventListener('pointerdown', outside);
        document.addEventListener('keydown', keyboard);
        buttons.find((item) => item.element === value)?.option.focus();
      }
      function outside(event) {if (!floating.contains(event.target) && !button.contains(event.target)) close();}
      function keyboard(event) {if (event.key === 'Escape') {event.preventDefault(); close(true);}}
      function routeChanged() {controller.destroy();}
      const observer = typeof MutationObserver === 'function' ? new MutationObserver(() => {
        if (!floating.isConnected) controller.destroy();
      }) : null;
      const controller = {
        button, floating,
        matches(entry) {return !value || (elements.includes(entry.element) ? entry.element : '通用') === value;},
        destroy() {
          if (disposed) return; disposed = true; close(); observer?.disconnect();
          floating.remove(); button.remove(); window.removeEventListener('hashchange', routeChanged);
          if (previous === controller) previous = null;
        },
      };
      window.addEventListener('hashchange', routeChanged);
      if (document.body) observer?.observe(document.body, {childList:true, subtree:true});
      update(); previous = controller; return controller;
    },
  };
})();
