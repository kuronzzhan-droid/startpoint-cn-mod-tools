/* Touch swipes use the same links as the header; editing and local drags keep priority. */
(() => {
  'use strict';
  const nav = document.querySelector('.app-navigation'), main = document.getElementById('main-content');
  if (!nav || !main || !window.matchMedia) return;
  const links = [...nav.querySelectorAll('a[href^="#"]')];
  const routes = links.map(link => link.getAttribute('href').slice(1));
  const contentRoutes = new Set(routes);
  const mobile = window.matchMedia('(max-width:760px)');
  const header = nav.closest('.masthead');
  const hint = document.createElement('p'); hint.className = 'mobile-nav-hint';
  hint.textContent = '左右滑动栏目或页面空白处，切换页面'; hint.setAttribute('aria-hidden', 'true'); header?.append(hint);
  const interactive = 'input,textarea,select,button,summary,label,form,[contenteditable]:not([contenteditable="false"]),[role="combobox"],[role="scrollbar"],[draggable="true"]';
  const editable = 'input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="combobox"]';
  const dragAreas = '.team-board,.team-library,.tier-board,.tier-pool';
  let gesture = null, suppressClickUntil = 0, suppressPointerClick = false, navigating = false;
  const route = () => window.location.hash.replace(/^#/, '');
  const currentIndex = () => links.findIndex(link => link.getAttribute('aria-current') === 'page');
  const accounts = () => /^community\/accounts(?:\/|$)/.test(route());
  const element = target => target?.nodeType === 1 ? target : target?.parentElement;
  function available() {
    return mobile.matches && currentIndex() >= 0 && !accounts() && !navigating
      && ![...main.querySelectorAll('form')].some(form => form.getAttribute('role') !== 'search' && !form.closest('[hidden]'))
      && !document.querySelector('dialog[open],[aria-modal="true"]')
      && !document.activeElement?.matches?.(editable);
  }
  function hasHorizontalScroll(target, boundary) {
    for (let current = target; current && current !== boundary; current = current.parentElement) {
      if (current.scrollWidth > current.clientWidth + 1 && /(auto|scroll)/.test(window.getComputedStyle(current).overflowX)) return true;
    }
    return false;
  }
  function sync() {
    gesture = null;
    header?.classList.toggle('mobile-nav-ready', mobile.matches && currentIndex() >= 0 && !accounts());
  }
  function start(target, point, kind) {
    // A fresh touch belongs to a new tap, not the preceding swipe's synthetic click.
    gesture = null; suppressClickUntil = 0; suppressPointerClick = false;
    if (!available()) return;
    target = element(target);
    const onNav = target && nav.contains(target);
    if (!target || target.closest(interactive)) return;
    if (!onNav && (kind !== 'touch' || !contentRoutes.has(route()) || !main.contains(target)
      || target.closest(dragAreas))) return;
    // Preserve the browser's own edge/back gesture.
    if (point.clientX < 18 || point.clientX > window.innerWidth - 18) return;
    gesture = {kind, identifier: point.identifier ?? point.pointerId, x: point.clientX, y: point.clientY,
      at: Date.now(), hash: route(), index: currentIndex(), horizontal: false, scrollTarget: onNav ? null : target};
  }
  function move(event, point) {
    if (!available() || gesture.hash !== route() || !point) {gesture = null; return;}
    const x = Math.abs(point.clientX - gesture.x), y = Math.abs(point.clientY - gesture.y);
    if (!gesture.horizontal && y > 10 && y >= x) {gesture = null; return;}
    if (!gesture.horizontal && x >= 12 && x > y * 1.5) {
      // Read layout only once horizontal intent is clear, before claiming native scrolling.
      if (gesture.scrollTarget && hasHorizontalScroll(gesture.scrollTarget, main)) {gesture = null; return;}
      gesture.horizontal = true;
    }
    if (gesture.horizontal) {
      if (!event.cancelable) {gesture = null; return;}
      event.preventDefault();
    }
  }
  async function finish(point) {
    const current = gesture; gesture = null;
    if (!current || !available() || current.hash !== route() || !point) return;
    const x = point.clientX - current.x, y = point.clientY - current.y;
    const threshold = Math.min(80, Math.max(52, window.innerWidth * .15));
    if (!current.horizontal || Math.abs(x) < threshold || Math.abs(x) < Math.abs(y) * 1.5 || Date.now() - current.at > 1200) return;
    suppressClickUntil = Date.now() + 500; suppressPointerClick = current.kind === 'pointer';
    const next = current.index + (x < 0 ? 1 : -1);
    if (next < 0 || next >= routes.length) return;
    const destination = links[next].getAttribute('href');
    navigating = true;
    try {
      // Use the ordinary navigation guard so a draft cannot be silently discarded.
      const accepted = window.WFNavigationGuard ? await window.WFNavigationGuard.navigate(destination)
        : (window.location.hash = destination, true);
      if (accepted) window.scrollTo?.({top: 0, behavior: 'auto'});
    } catch { /* A failed confirmation keeps the current page. */ }
    finally {navigating = false;}
  }
  document.addEventListener('touchstart', event => {
    if (event.touches.length !== 1) {gesture = null; return;}
    start(event.target, event.touches[0], 'touch');
  }, {passive: true});
  document.addEventListener('touchmove', event => {
    if (gesture?.kind !== 'touch') return;
    if (event.touches.length !== 1) {gesture = null; return;}
    move(event, [...event.touches].find(point => point.identifier === gesture.identifier));
  }, {passive: false});
  document.addEventListener('touchend', event => {
    if (gesture?.kind !== 'touch') return;
    if (event.touches.length) {gesture = null; return;}
    void finish([...event.changedTouches].find(point => point.identifier === gesture.identifier));
  }, {passive: true});
  document.addEventListener('touchcancel', () => {gesture = null;}, {passive: true});
  // Mouse/pen dragging is limited to the navigation strip, never selectable page text.
  document.addEventListener('pointerdown', event => {
    if (event.pointerType === 'touch') return;
    if (event.button !== 0 || event.isPrimary === false) {gesture = null; return;}
    start(event.target, event, 'pointer');
  });
  document.addEventListener('pointermove', event => {
    if (gesture?.kind !== 'pointer' || event.pointerId !== gesture.identifier) return;
    move(event, event);
  });
  document.addEventListener('pointerup', event => {
    if (gesture?.kind === 'pointer' && event.pointerId === gesture.identifier) void finish(event);
  });
  document.addEventListener('pointercancel', () => {if (gesture?.kind === 'pointer') gesture = null;});
  nav.addEventListener('dragstart', event => {if (gesture?.kind === 'pointer') event.preventDefault();});
  document.addEventListener('click', event => {
    if (suppressClickUntil <= Date.now() || event.detail === 0 || (!suppressPointerClick && event.sourceCapabilities?.firesTouchEvents === false)) return;
    suppressClickUntil = 0; event.preventDefault(); event.stopPropagation();
  }, true);
  // The first router render may finish after the deferred scripts have loaded.
  if (window.MutationObserver) new window.MutationObserver(sync).observe(nav, {subtree:true, attributes:true, attributeFilter:['aria-current']});
  window.addEventListener('hashchange', sync); mobile.addEventListener?.('change', sync); sync();
})();
