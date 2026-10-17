/* Collapsing navigation changes layout only, keeping filters and routes intact. */
(() => {
  'use strict';
  const shell = document.querySelector('.page-shell');
  const sidebar = shell?.querySelector('.sidebar');
  if (!shell || !sidebar) return;
  const storageKey = 'wf-wiki-sidebar-collapsed';
  const mobile = window.matchMedia?.('(max-width:640px)');
  const mobileCatalog = () => Boolean(mobile?.matches && !location.hash.slice(1));
  let collapsed = false, mobileExpanded = false;
  try { collapsed = localStorage.getItem(storageKey) === 'true'; } catch { /* Optional persistence. */ }
  sidebar.id = 'character-sidebar';
  const toolbar = document.createElement('div'); toolbar.className = 'sidebar-toolbar';
  const button = document.createElement('button'); button.type = 'button'; button.className = 'sidebar-toggle';
  button.setAttribute('aria-controls', sidebar.id);
  const paint = () => {
    const page = location.hash.slice(1).split('/')[0];
    const automatic = ['team', 'community', 'weapons', 'weapon', 'five-boss', 'dungeons', 'shops', 'tier-list'].includes(page)
      || (mobile?.matches && page === 'character');
    if (!mobileCatalog()) mobileExpanded = false;
    const closed = mobileCatalog() ? !mobileExpanded : collapsed;
    shell.classList.toggle('catalog-home', !page);
    shell.classList.toggle('sidebar-collapsed', closed || automatic);
    sidebar.hidden = closed || automatic;
    toolbar.hidden = automatic;
    const label = closed ? '展开角色目录' : '收起角色目录';
    button.textContent = mobileCatalog() ? (closed ? '目录' : '收起') : (closed ? '› 展开目录' : '‹ 收起目录');
    button.setAttribute('aria-label', label); button.title = label;
    button.setAttribute('aria-expanded', String(!closed));
  };
  const setCollapsed = (value) => {
    collapsed = value; paint();
    try { localStorage.setItem(storageKey, String(collapsed)); } catch { /* Layout still works. */ }
  };
  button.addEventListener('click', () => {
    if (mobileCatalog()) {
      mobileExpanded = !mobileExpanded; paint();
      if (mobileExpanded) sidebar.scrollIntoView({block: 'start'});
    } else setCollapsed(!collapsed);
  });
  const closeWithEscape = (event) => {
    if (event.key !== 'Escape' || !mobileCatalog() || !mobileExpanded) return;
    event.preventDefault(); mobileExpanded = false; paint(); button.focus({preventScroll: true});
  };
  sidebar.addEventListener('keydown', closeWithEscape); button.addEventListener('keydown', closeWithEscape);
  mobile?.addEventListener('change', paint);
  window.addEventListener('hashchange', paint);
  toolbar.append(button); shell.prepend(toolbar); paint();
})();
