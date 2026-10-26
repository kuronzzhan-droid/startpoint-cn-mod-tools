/* Progressively enhance single selects; the original control remains the form value. */
(() => {
  'use strict';
  const controls = new Map();
  let active = null, serial = 0;
  const make = (tag, cls) => Object.assign(document.createElement(tag), {className: cls});
  const eligible = (select) => !select.multiple && select.size <= 1;
  const disabled = (option) => option.disabled || option.parentElement?.disabled;
  function close() {
    if (!active) return;
    active.button.setAttribute('aria-expanded', 'false');
    active.button.removeAttribute('aria-activedescendant');
    active.menu.remove(); active.spacer?.remove(); active = null;
  }
  function position() {
    if (!active) return;
    const rect = active.button.getBoundingClientRect();
    if (!active.select.isConnected || !rect.width || !rect.height) {close(); return;}
    const viewport = window.visualViewport;
    const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
    const width = viewport?.width || window.innerWidth, height = viewport?.height || window.innerHeight;
    Object.assign(active.menu.style, {left: `${Math.max(left + 4, Math.min(rect.left, left + width - rect.width - 4))}px`,
      top: `${rect.bottom + 4}px`, width: `${Math.min(rect.width, width - 8)}px`,
      maxHeight: `${Math.max(0, Math.min(320, top + height - rect.bottom - 12))}px`});
  }
  function enhance(select) {
    if (controls.has(select) || !eligible(select)) return;
    const wrapper = make('span', 'wf-dropdown'), button = make('button', 'wf-dropdown-trigger');
    const text = make('span', 'wf-dropdown-value'), arrow = make('span', 'wf-dropdown-arrow');
    const menu = make('div', 'wf-dropdown-menu'), id = `wf-dropdown-${++serial}`;
    const originalTabIndex = select.getAttribute('tabindex'), originalAriaHidden = select.getAttribute('aria-hidden');
    arrow.textContent = '▾'; arrow.setAttribute('aria-hidden', 'true');
    button.type = 'button'; button.setAttribute('role', 'combobox');
    button.setAttribute('aria-haspopup', 'listbox'); button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-controls', id); menu.id = id; menu.setAttribute('role', 'listbox');
    select.before(wrapper); wrapper.append(select, button); button.append(text, arrow);
    select.classList.add('wf-dropdown-native'); select.tabIndex = -1; select.setAttribute('aria-hidden', 'true');
    const state = {select, wrapper, button, menu, cursor: -1, items: [], hooks: []};
    controls.set(select, state);
    function sync() {
      if (!eligible(select)) {destroy(); return;}
      wrapper.hidden = select.hidden;
      button.disabled = select.matches(':disabled');
      button.tabIndex = originalTabIndex === null ? 0 : Number(originalTabIndex);
      text.textContent = select.selectedOptions[0]?.label || '请选择';
      button.title = select.title || text.textContent;
      const labelledby = select.getAttribute('aria-labelledby');
      if (labelledby) button.setAttribute('aria-labelledby', labelledby);
      else button.removeAttribute('aria-labelledby');
      const label = select.getAttribute('aria-label') || Array.from(select.labels || []).map((node) => {
        const copy = node.cloneNode(true); copy.querySelectorAll('select,.wf-dropdown').forEach((child) => child.remove());
        return copy.textContent.trim();
      }).filter(Boolean).join(' ') || select.name || '选择选项';
      button.setAttribute('aria-label', label);
      for (const key of ['aria-describedby', 'aria-invalid', 'aria-required']) {
        const value = select.getAttribute(key) || (key === 'aria-required' && select.required ? 'true' : null);
        if (value) button.setAttribute(key, value); else button.removeAttribute(key);
      }
      if (active === state) {if (button.disabled) close(); else {render(); position();}}
    }
    function highlight(index) {
      state.cursor = index;
      state.items.forEach((item, i) => item?.classList.toggle('is-active', i === index));
      const item = state.items[index];
      if (item) {button.setAttribute('aria-activedescendant', item.id); item.scrollIntoView({block: 'nearest'});}
      else button.removeAttribute('aria-activedescendant');
    }
    function render() {
      menu.replaceChildren(); state.items = [];
      let group = null;
      Array.from(select.options).forEach((option, index) => {
        if (option.hidden || option.parentElement?.hidden) return;
        const parent = option.parentElement;
        if (parent.tagName === 'OPTGROUP' && parent !== group) {
          const heading = make('div', 'wf-dropdown-group'); heading.textContent = parent.label;
          heading.setAttribute('role', 'presentation'); menu.append(heading); group = parent;
        }
        const item = make('div', 'wf-dropdown-option'); item.id = `${id}-${index}`; item.textContent = option.label;
        item.setAttribute('role', 'option'); item.setAttribute('aria-selected', String(option.selected));
        item.setAttribute('aria-disabled', String(Boolean(disabled(option))));
        item.addEventListener('pointerdown', (event) => event.preventDefault());
        item.addEventListener('click', () => choose(index)); menu.append(item); state.items[index] = item;
      });
      const index = state.items[state.cursor] && !disabled(select.options[state.cursor]) ? state.cursor : select.selectedIndex;
      highlight(index);
    }
    function choose(index) {
      const option = select.options[index];
      if (!option || disabled(option) || button.disabled) return;
      const changed = select.selectedIndex !== index; select.selectedIndex = index;
      close(); sync(); button.focus();
      if (changed) for (const type of ['input', 'change']) select.dispatchEvent(new Event(type, {bubbles: true}));
    }
    function open() {
      sync(); if (button.disabled || !eligible(select)) return;
      close(); active = state; state.cursor = select.selectedIndex;
      button.setAttribute('aria-expanded', 'true');
      (select.closest('dialog[open]') || document.body).append(menu);
      // Make room below short-screen controls; never flip the list above its trigger.
      if (window.innerHeight - button.getBoundingClientRect().bottom < 120) button.scrollIntoView({block: 'center'});
      if (window.innerHeight - button.getBoundingClientRect().bottom < 120) {
        let scroller = wrapper.parentElement;
        while (scroller && scroller !== document.body && !/(auto|scroll)/.test(getComputedStyle(scroller).overflowY)) scroller = scroller.parentElement;
        state.spacer = make('div', 'wf-dropdown-space'); state.spacer.setAttribute('aria-hidden', 'true');
        (scroller || document.body).append(state.spacer);
        button.scrollIntoView({block: 'center'});
      }
      position(); render();
    }
    function move(step, edge) {
      const indices = Array.from(select.options).map((option, i) =>
        !disabled(option) && !option.hidden && !option.parentElement?.hidden ? i : -1).filter((i) => i >= 0);
      const current = indices.indexOf(state.cursor);
      highlight(edge === 'start' ? indices[0] : edge === 'end' ? indices.at(-1)
        : indices[Math.max(0, Math.min(indices.length - 1, current + step))]);
    }
    let search = '', searchAt = 0;
    button.addEventListener('click', () => active === state ? close() : open());
    button.addEventListener('keydown', (event) => {
      if (event.key === 'Tab') {close(); return;}
      if (event.key === 'Escape') {if (active === state) {event.preventDefault(); event.stopPropagation(); close();} return;}
      if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
        event.preventDefault(); if (active !== state) open();
        move(event.key === 'ArrowUp' ? -1 : 1, event.key === 'Home' ? 'start' : event.key === 'End' ? 'end' : '');
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault(); if (active === state) choose(state.cursor); else open();
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault(); if (active !== state) open();
        search = (Date.now() - searchAt > 700 ? '' : search) + event.key.toLocaleLowerCase(); searchAt = Date.now();
        const index = Array.from(select.options).findIndex((option) => !disabled(option) && !option.hidden
          && !option.parentElement?.hidden && option.label.toLocaleLowerCase().startsWith(search));
        if (index >= 0) highlight(index);
      }
    });
    const focus = () => button.focus(), invalid = (event) => {event.preventDefault(); sync(); button.setAttribute('aria-invalid', 'true'); focus();};
    select.addEventListener('focus', focus); select.addEventListener('invalid', invalid);
    select.addEventListener('change', sync); select.addEventListener('input', sync);
    // Local accessors observe application resets without changing any browser prototypes.
    for (const key of ['value', 'selectedIndex']) {
      if (Object.hasOwn(select, key)) continue;
      let proto = Object.getPrototypeOf(select), descriptor;
      while (proto && !(descriptor = Object.getOwnPropertyDescriptor(proto, key))) proto = Object.getPrototypeOf(proto);
      if (!descriptor?.set) continue;
      Object.defineProperty(select, key, {configurable: true, get() {return descriptor.get.call(this);},
        set(value) {descriptor.set.call(this, value); sync();}}); state.hooks.push(key);
    }
    function destroy() {
      if (active === state) close(); observer.disconnect(); controls.delete(select);
      select.removeEventListener('focus', focus); select.removeEventListener('invalid', invalid);
      select.removeEventListener('change', sync); select.removeEventListener('input', sync);
      state.hooks.forEach((key) => {delete select[key];}); select.classList.remove('wf-dropdown-native');
      if (originalTabIndex === null) select.removeAttribute('tabindex'); else select.setAttribute('tabindex', originalTabIndex);
      if (originalAriaHidden === null) select.removeAttribute('aria-hidden'); else select.setAttribute('aria-hidden', originalAriaHidden);
      if (wrapper.parentNode) wrapper.replaceWith(select); button.remove();
    }
    const observer = new MutationObserver(sync);
    observer.observe(select, {subtree: true, childList: true, characterData: true, attributes: true,
      attributeFilter: ['disabled', 'selected', 'label', 'value', 'hidden', 'multiple', 'size', 'required',
        'aria-label', 'aria-labelledby', 'aria-describedby', 'aria-invalid', 'aria-required', 'title']});
    Object.assign(state, {sync, destroy}); sync();
  }
  function scan(root = document) {
    if (root.matches?.('select')) enhance(root);
    root.querySelectorAll?.('select').forEach(enhance);
  }
  function start() {
    scan();
    new MutationObserver((records) => {
      records.forEach((record) => {
        record.addedNodes.forEach((node) => {if (node.nodeType === 1) scan(node);});
        if (record.type === 'attributes') {
          if (record.target.matches('select')) enhance(record.target);
          if (record.target.matches('fieldset')) record.target.querySelectorAll('select').forEach((select) => controls.get(select)?.sync());
        }
      });
      for (const [select, state] of controls) if (!select.isConnected) state.destroy();
    }).observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['disabled', 'multiple', 'size']});
    document.addEventListener('pointerdown', (event) => {if (active && !active.wrapper.contains(event.target) && !active.menu.contains(event.target)) close();});
    document.addEventListener('focusin', (event) => {if (active && !active.wrapper.contains(event.target) && !active.menu.contains(event.target)) close();});
    document.addEventListener('reset', () => setTimeout(() => {close(); controls.forEach((state) => state.sync());}, 0));
    window.addEventListener('resize', position); window.addEventListener('scroll', position, true);
    window.visualViewport?.addEventListener('resize', position); window.visualViewport?.addEventListener('scroll', position);
    window.addEventListener('hashchange', close);
  }
  window.WFDropdowns = {refresh: () => {scan(); controls.forEach((state) => state.sync());}, close};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true}); else start();
})();
