/* Scroll control stays independent of catalogue routes and filters. */
(() => {
  'use strict';
  const button = document.getElementById('back-to-top');
  if (!button) return;
  const home = document.getElementById('back-to-home');
  const update = () => {
    button.hidden = window.scrollY < 320;
    if (home) home.hidden = !window.location.hash || ['#', '#main-content'].includes(window.location.hash);
  };
  window.addEventListener('scroll', update, {passive: true});
  window.addEventListener('hashchange', update);
  home?.addEventListener('click', () => window.scrollTo({top: 0, behavior: 'instant'}));
  button.addEventListener('click', () => {
    const staticMotion = window.matchMedia('(max-width: 768px), (hover: none) and (pointer: coarse), (prefers-reduced-motion: reduce)').matches;
    window.scrollTo({top: 0, behavior: staticMotion ? 'instant' : 'smooth'});
  });
  update();
})();
