/* Full portraits use public hashed media only; tilt runs solely during mouse interaction. */
(() => {
  'use strict';
  const mediaUrl = (value) => typeof value === 'string' && /^media\/[a-f0-9]{64}\.(?:webp|png|jpe?g|avif)$/.test(value) ? value : '';
  window.WFPortraitCards = {create({ui}) {
    const {el} = ui, cards = new Set();
    const fine = window.matchMedia?.('(hover: hover) and (pointer: fine)');
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const narrow = window.matchMedia?.('(max-width: 768px)');
    let active = null, frame = 0, watching = false, suspended = false;
    const enabled = () => fine?.matches === true && reduced?.matches === false && narrow?.matches === false
      && !suspended && typeof window.requestAnimationFrame === 'function';
    const properties = ['--portrait-rotate-x','--portrait-rotate-y','--portrait-shift-x','--portrait-shift-y'];
    function reset() {
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      if (active) {
        active.card.classList.remove('portrait-card-active');
        properties.forEach((property) => active.card.style.removeProperty(property));
      }
      active = null;
    }
    function render() {
      frame = 0;
      if (!active || !active.card.isConnected || !enabled() || document.hidden) {reset(); return;}
      const {card, rect, x, y} = active;
      const clamp = (value) => Math.max(-1, Math.min(1, value));
      const dx = clamp((x - rect.left) / rect.width * 2 - 1), dy = clamp((y - rect.top) / rect.height * 2 - 1);
      card.style.setProperty('--portrait-rotate-x', `${(-dy * 6).toFixed(2)}deg`);
      card.style.setProperty('--portrait-rotate-y', `${(dx * 8).toFixed(2)}deg`);
      card.style.setProperty('--portrait-shift-x', `${(dx * 8).toFixed(2)}px`);
      card.style.setProperty('--portrait-shift-y', `${(dy * 8).toFixed(2)}px`);
    }
    function move(event) {
      if (event.pointerType !== 'mouse' || !enabled() || document.hidden) return;
      const card = event.currentTarget;
      if (!active || active.card !== card) {
        reset();
        const rect = card.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        active = {card, rect}; card.classList.add('portrait-card-active');
      }
      active.x = event.clientX; active.y = event.clientY;
      if (!frame) frame = window.requestAnimationFrame(render);
    }
    function leave(event) {if (active?.card === event.currentTarget) reset();}
    function policyChange() {if (!enabled()) reset();}
    function visibility() {if (document.hidden) reset();}
    const bindings = [['pointerenter',move],['pointermove',move],['pointerleave',leave],['pointercancel',leave],['blur',leave]];
    function watch(value) {
      if (watching === value) return;
      const method = value ? 'addEventListener' : 'removeEventListener';
      [fine, reduced, narrow].forEach((media) => media?.[method]?.('change', policyChange));
      window[method]('scroll', reset, true); window[method]('resize', reset); window[method]('hashchange', reset);
      document[method]('visibilitychange', visibility); watching = value;
    }
    function paint(node, character, form = 'before', alt = '') {
      const label = form === 'after' ? '觉醒后' : '觉醒前';
      const portraits = (Array.isArray(character?.portraits) ? character.portraits : []).filter((item) => item && mediaUrl(item.url));
      const preferred = portraits.find((item) => item.label === label), selected = preferred || portraits[0];
      node.title = selected && !preferred ? `未收录${label}立绘，显示现有立绘` : '';
      if (!selected) {node.replaceChildren(el('span', 'portrait-card-placeholder', '未收录立绘')); return node;}
      const description = alt || `${character?.name || '角色'} · ${selected.label || '立绘'}`;
      const current = node.querySelector('img');
      if (current?.getAttribute('src') === selected.url) {current.alt = description; return node;}
      const image = el('img', 'portrait-card-image');
      image.loading = 'lazy'; image.decoding = 'async'; image.draggable = false; image.alt = description;
      image.setAttribute('src', selected.url);
      image.addEventListener('error', () => {
        if (node.querySelector('img') === image) node.replaceChildren(el('span', 'portrait-card-placeholder', '立绘暂时无法加载'));
      }, {once:true});
      node.replaceChildren(image); return node;
    }
    return {
      picture(character, form = 'before', alt = '') {return paint(el('span', 'portrait-card-media'), character, form, alt);},
      paint,
      attach(card) {
        if (cards.has(card)) return card;
        card.classList.add('portrait-card'); cards.add(card);
        bindings.forEach(([type, listener]) => card.addEventListener(type, listener, {passive:true})); watch(!suspended); return card;
      },
      pause() {suspended = true; reset(); watch(false);},
      resume() {suspended = false; if (cards.size) watch(true);},
      destroy() {
        reset(); cards.forEach((card) => bindings.forEach(([type, listener]) => card.removeEventListener(type, listener)));
        cards.clear(); watch(false); suspended = false;
      },
    };
  }};
})();
