/* Keep the catalogue unmounted until first opened; later collapses retain one reusable view. */
(() => {
  'use strict';
  window.WFCatalogDisclosure = {create({catalog, ui, onToggle}) {
    const {el} = ui;
    const grid = catalog.querySelector('#character-grid');
    const count = catalog.querySelector('#result-count');
    const heading = count.closest('.section-heading');
    const title = count.closest('h2');
    const controls = catalog.querySelector('.catalog-display-controls');
    const toggle = el('button', 'catalog-list-toggle'); toggle.type = 'button';
    toggle.id = 'catalog-list-toggle'; toggle.setAttribute('aria-controls', grid.id);
    const label = el('span', 'catalog-list-label');
    const hint = el('span', 'catalog-list-hint'); hint.setAttribute('aria-hidden', 'true');
    toggle.append(hint, label, count); title.replaceChildren(toggle);
    heading.classList.add('catalog-list-toolbar'); heading.append(controls);
    let expanded = false, filterKey = '';
    function setOpen(value, notify = true) {
      expanded = Boolean(value);
      toggle.setAttribute('aria-expanded', String(expanded));
      label.textContent = expanded ? '收起角色列表' : '展开角色列表';
      hint.textContent = expanded ? '▴' : '▾';
      if (!expanded && document.activeElement && grid.contains(document.activeElement)) toggle.focus({preventScroll:true});
      grid.hidden = !expanded;
      if (notify) onToggle();
    }
    toggle.addEventListener('click', () => setOpen(!expanded));
    setOpen(false, false);
    return {
      isOpen: () => expanded,
      filterChanged(key, active) {
        if (key === filterKey) return;
        filterKey = key;
        // The caller renders once its debounced/async search has completed.
        if (active) setOpen(true, false);
      },
    };
  }};
})();
