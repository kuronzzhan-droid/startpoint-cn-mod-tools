/* Keep an active editor mounted until navigation has been explicitly accepted. */
(() => {
  'use strict';
  const indexKey = '__wfWikiNavigationIndex';
  let guard = null, pending = false, permitted = null, restoring = null, restoreTimer;
  let settled = location.hash || '#';
  const nativeIndex = () => {
    const value = window.navigation?.currentEntry?.index;
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  };
  let cursor = nativeIndex() ?? (Number.isSafeInteger(window.history.state?.[indexKey]) ? window.history.state[indexKey] : 0);
  let settledIndex = cursor;
  const uncertain = new Set();
  const mark = () => window.history.replaceState({...window.history.state, [indexKey]:cursor}, '', location.hash || '#');
  mark();
  const canonical = (hash) => hash.startsWith('#') ? (hash || '#') : `#${hash}`;
  const active = () => guard && guard.isActive() ? guard : null;
  const protectedPage = () => Boolean(active()?.needsProtection());
  function readIndex() {
    const value = nativeIndex() ?? window.history.state?.[indexKey];
    if (Number.isSafeInteger(value)) cursor = value;
    else {cursor++; uncertain.add(cursor); mark();}
    return cursor;
  }
  function recoverUnknownEntry() {
    clearTimeout(restoreTimer);
    // Older browsers may contain entries created before this script. Keep that
    // entry, return to the editor, and release the lock even if its distance is unknown.
    cursor = readIndex() + 1; settledIndex = cursor;
    window.history.pushState({...window.history.state, [indexKey]:cursor}, '', settled);
    restoring = cursor;
    window.dispatchEvent(new window.Event('hashchange'));
  }
  function restoreEntry() {
    const current = readIndex();
    if (current === settledIndex) return;
    if (uncertain.has(current) || uncertain.has(settledIndex)) {recoverUnknownEntry(); return;}
    restoring = settledIndex;
    restoreTimer = setTimeout(recoverUnknownEntry, 1000);
    window.history.go(settledIndex - current);
  }
  async function confirmLeave(owner) {
    if (pending) return false;
    pending = true;
    try {return Boolean(await owner.canLeave()) && active() === owner;}
    catch {return false;}
    finally {pending = false;}
  }
  const api = window.WFNavigationGuard = {
    register(value) {
      guard = value; permitted = null;
      return () => {if (guard === value) {guard = null; permitted = null;}};
    },
    async navigate(target, beforeNavigate) {
      const hash = canonical(target), owner = active();
      if (pending || restoring !== null || hash === settled) return false;
      if (owner && protectedPage() && !await confirmLeave(owner)) {
        if ((location.hash || '#') !== settled) restoreEntry();
        return false;
      }
      if ((location.hash || '#') !== settled) {restoreEntry(); return false;}
      beforeNavigate?.();
      permitted = {hash, owner}; location.hash = hash;
      return true;
    },
    allow(target) {
      const hash = canonical(target), owner = active();
      const targetIndex = readIndex();
      if (restoring !== null) {
        if (targetIndex === restoring && hash === settled) {clearTimeout(restoreTimer); restoring = null;}
        else recoverUnknownEntry();
        return false;
      }
      if (pending) return false;
      if (permitted?.hash === hash && permitted.owner === owner) {
        permitted = null; settled = hash; settledIndex = targetIndex; return true;
      }
      permitted = null;
      if (!owner || !protectedPage()) {settled = hash; settledIndex = targetIndex; return true;}
      // Back/Forward already moved the history cursor. Keep its entry intact while
      // asking, and traverse back on cancellation instead of overwriting that entry.
      return confirmLeave(owner).then((accepted) => {
        if (!accepted || (location.hash || '#') !== hash || readIndex() !== targetIndex) {restoreEntry(); return false;}
        settled = hash; settledIndex = targetIndex; return true;
      });
    },
  };
  document.addEventListener('click', (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest?.('a[href]');
    if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || url.pathname !== location.pathname || url.search !== location.search) return;
    if (url.hash === '#main-content') {
      event.preventDefault(); event.stopImmediatePropagation();
      const main = document.getElementById('main-content'); main?.focus(); main?.scrollIntoView({block:'start'}); return;
    }
    if (!protectedPage()) return;
    event.preventDefault();
    // Allow the administrator's New Team handler to prepare its draft after approval.
    if (link.dataset.navigationGuard === 'custom') return;
    event.stopImmediatePropagation(); void api.navigate(url.hash || '#');
  }, true);
  window.addEventListener('beforeunload', (event) => {
    if (!protectedPage()) return;
    event.preventDefault(); event.returnValue = '';
  });
})();
