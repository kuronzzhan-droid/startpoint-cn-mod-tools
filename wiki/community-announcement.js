/* One public snapshot per page visit; ticker animation performs no network polling. */
(() => {
  'use strict';
  const C = window.WFCommunity;
  C.announcement = (ui) => {
    const {el} = ui, initialHash = location.hash, box = el('aside', 'community-announcement'); box.hidden = true;
    box.setAttribute('aria-label', '配队公告');
    const row = el('div', 'community-announcement-row');
    const label = el('button', 'community-announcement-label', '公告'); label.type = 'button';
    label.setAttribute('aria-expanded', 'false'); label.setAttribute('aria-label', '查看完整公告');
    const viewport = el('div', 'community-announcement-viewport'), track = el('div', 'community-announcement-track');
    const text = el('span'), repeat = el('span'); repeat.setAttribute('aria-hidden', 'true');
    track.append(text, repeat); viewport.append(track);
    const pause = el('button', 'community-announcement-pause', '暂停'); pause.type = 'button';
    pause.setAttribute('aria-label', '暂停公告滚动'); pause.setAttribute('aria-pressed', 'false');
    const full = el('p', 'community-announcement-full'); full.hidden = true;
    label.addEventListener('click', () => {
      full.hidden = !full.hidden; label.setAttribute('aria-expanded', String(!full.hidden));
    });
    pause.addEventListener('click', () => {
      const paused = pause.getAttribute('aria-pressed') !== 'true';
      box.setAttribute('data-paused', String(paused)); pause.setAttribute('aria-pressed', String(paused));
      pause.textContent = paused ? '播放' : '暂停'; pause.setAttribute('aria-label', paused ? '播放公告滚动' : '暂停公告滚动');
    });
    row.append(label, viewport, pause); box.append(row, full);
    // Defer until the caller has mounted the section; a late response never revives a departed page.
    Promise.resolve().then(async () => {
      try {
        const value = await C.client.request('/announcement');
        if (!box.isConnected || location.hash !== initialHash || typeof value?.text !== 'string' || !value.text.trim()) return;
        text.textContent = value.text.replace(/\s*\n\s*/g, '　·　'); repeat.textContent = text.textContent;
        full.textContent = value.text; box.hidden = false;
        box.style?.setProperty('--announcement-duration', `${Math.max(20, Math.min(120, value.text.length / 4))}s`);
      } catch { /* A notice outage must not block team browsing; try again on the next page visit. */ }
    });
    return box;
  };
})();
