/* Use each character's verified native title image and acquisition condition. */
window.renderWikiNameplates = function renderWikiNameplates(host, character, ui) {
  'use strict';
  const {el, list, safeUrl, picture, text} = ui;
  const items = list(character.nameplates).filter((item) => item && safeUrl(item.url));
  const section = el('section', 'character-nameplates');
  section.setAttribute('aria-label', '角色专属铭牌');
  section.append(el('h2', '', '专属铭牌'));
  if (!items.length) section.append(el('p', 'muted', '当前资料未收录这位角色的专属铭牌。'));
  for (const item of items) {
    const figure = el('figure', 'character-nameplate');
    figure.append(picture(item.url, text(item.name, '角色专属铭牌'), 'character-nameplate-image'));
    const caption = el('figcaption');
    caption.append(el('strong', '', text(item.name, '专属铭牌')));
    if (item.label) caption.append(el('span', 'nameplate-label', item.label));
    if (item.acquisition) caption.append(el('p', '', item.acquisition));
    figure.append(caption); section.append(figure);
  }
  host.append(section);
};
