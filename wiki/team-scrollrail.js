/* A persistent mobile scroll handle; the content keeps its native scrolling. */
(() => {
  'use strict';
  const mounted = new Set();
  let nextId = 0;
  const reset = () => {for (const dispose of [...mounted]) dispose();};
  window.addEventListener('hashchange', () => {if (window.location.hash !== '#team') reset();});
  function wrap(viewport, ui, label, className = '') {
    const {el} = ui, root = el('div', `team-scroll-region ${className}`.trim());
    const rail = el('div', 'team-scrollrail'), thumb = el('span', 'team-scrollrail-thumb');
    const mobile = window.matchMedia('(max-width:820px)');
    viewport.id ||= `team-scrollport-${++nextId}`;
    viewport.tabIndex = 0;
    rail.tabIndex = 0; rail.setAttribute('role', 'scrollbar');
    rail.setAttribute('aria-controls', viewport.id); rail.setAttribute('aria-orientation', 'vertical');
    rail.setAttribute('aria-label', `${label}滚动条`); rail.setAttribute('aria-valuemin', '0'); rail.setAttribute('aria-valuemax', '100');
    rail.title = `上下拖动浏览${label}`; thumb.setAttribute('aria-hidden', 'true');
    rail.append(thumb); root.append(viewport, rail);
    let disposed = false, frame = 0, pointer = null, grabOffset = 0;
    const range = () => Math.max(0, viewport.scrollHeight - viewport.clientHeight);
    function geometry() {
      const height = rail.clientHeight;
      const size = Math.min(height, Math.max(36, height * viewport.clientHeight / Math.max(1, viewport.scrollHeight)));
      return {size, travel: Math.max(0, height - size)};
    }
    function update() {
      if (disposed) return;
      const maximum = range(), active = mobile.matches && maximum > 1;
      rail.hidden = !active;
      rail.setAttribute('aria-disabled', String(!active));
      const fraction = maximum ? Math.max(0, Math.min(1, viewport.scrollTop / maximum)) : 0;
      rail.setAttribute('aria-valuenow', String(Math.round(fraction * 100)));
      if (!active) {finish(); return;}
      const {size, travel} = geometry();
      thumb.style.height = `${size}px`;
      thumb.style.transform = `translateY(${fraction * travel}px)`;
    }
    function schedule() {
      if (!disposed && !frame) frame = requestAnimationFrame(() => {frame = 0; update();});
    }
    function move(clientY) {
      const {travel} = geometry();
      const position = clientY - rail.getBoundingClientRect().top - grabOffset;
      viewport.scrollTop = travel ? Math.max(0, Math.min(1, position / travel)) * range() : 0;
      update();
    }
    function finish() {
      if (pointer === null) return;
      const id = pointer; pointer = null;
      if (rail.hasPointerCapture?.(id)) rail.releasePointerCapture(id);
    }
    function down(event) {
      if (disposed || !mobile.matches || range() <= 1 || event.button !== 0 || event.isPrimary === false) return;
      event.preventDefault(); event.stopPropagation();
      const {size, travel} = geometry();
      grabOffset = thumb.contains(event.target) ? event.clientY - rail.getBoundingClientRect().top - viewport.scrollTop / range() * travel : size / 2;
      pointer = event.pointerId; rail.setPointerCapture(pointer); rail.focus({preventScroll:true});
      move(event.clientY);
    }
    function drag(event) {
      if (event.pointerId !== pointer) return;
      event.preventDefault(); event.stopPropagation(); move(event.clientY);
    }
    function up(event) {if (event.pointerId === pointer) {event.stopPropagation(); finish();}}
    function keyboard(event) {
      const maximum = range(); if (!mobile.matches || maximum <= 1) return;
      const delta = {ArrowDown:40, ArrowUp:-40, PageDown:viewport.clientHeight * .9, PageUp:-viewport.clientHeight * .9}[event.key];
      if (delta === undefined && !['Home','End'].includes(event.key)) return;
      event.preventDefault(); event.stopPropagation();
      viewport.scrollTop = event.key === 'Home' ? 0 : event.key === 'End' ? maximum : Math.max(0, Math.min(maximum, viewport.scrollTop + delta));
      update();
    }
    const stop = (event) => event.stopPropagation();
    const cancelDrag = (event) => {event.preventDefault(); event.stopPropagation();};
    rail.addEventListener('pointerdown', down); rail.addEventListener('pointermove', drag);
    rail.addEventListener('pointerup', up); rail.addEventListener('pointercancel', up); rail.addEventListener('lostpointercapture', finish);
    rail.addEventListener('keydown', keyboard); rail.addEventListener('touchstart', stop, {passive:true});
    rail.addEventListener('dragstart', cancelDrag);
    viewport.addEventListener('scroll', update, {passive:true}); viewport.addEventListener('load', schedule, true); viewport.addEventListener('toggle', schedule, true);
    mobile.addEventListener('change', schedule);
    const resize = typeof ResizeObserver === 'function' ? new ResizeObserver(schedule) : null;
    resize?.observe(viewport); resize?.observe(rail);
    const mutation = typeof MutationObserver === 'function' ? new MutationObserver(schedule) : null;
    mutation?.observe(viewport, {childList:true, subtree:true, characterData:true});
    function dispose() {
      if (disposed) return;
      disposed = true; finish(); if (frame) cancelAnimationFrame(frame);
      resize?.disconnect(); mutation?.disconnect(); mobile.removeEventListener('change', schedule);
      viewport.removeEventListener('scroll', update); viewport.removeEventListener('load', schedule, true); viewport.removeEventListener('toggle', schedule, true);
      rail.removeEventListener('pointerdown', down); rail.removeEventListener('pointermove', drag); rail.removeEventListener('pointerup', up);
      rail.removeEventListener('pointercancel', up); rail.removeEventListener('lostpointercapture', finish); rail.removeEventListener('keydown', keyboard);
      rail.removeEventListener('touchstart', stop); rail.removeEventListener('dragstart', cancelDrag);
      mounted.delete(dispose);
    }
    mounted.add(dispose); schedule(); return root;
  }
  window.WFTeamScrollRail = {wrap, reset};
})();
