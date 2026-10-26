/* Player-facing parameters only. Internal command names and paths stay out of the UI. */
window.renderWikiNumericDetails = function renderWikiNumericDetails(target, details, ui) {
  'use strict';
  const {el, list, object, text} = ui;
  const data = object(details);
  const rows = list(data.rows).filter((row) => row && list(row.values).length);
  if (!rows.length) return;
  const block = el('div', 'numeric-block');
  block.append(el('h4', 'numeric-title', '倍率与详细数值'));
  list(data.notes).forEach((note) => block.append(el('p', 'numeric-note', note)));
  rows.forEach((row, index) => {
    const group = el('div', 'numeric-effect');
    group.append(el('div', 'numeric-effect-title', text(row.label, `效果 ${index + 1}`)));
    if (list(row.context).length) group.append(el('p', 'numeric-context', row.context.join(' / ')));
    const table = el('dl', 'numeric-values');
    list(row.values).forEach((value) => {
      if (!value || value.value == null) return;
      table.append(el('dt', '', text(value.label, '参数')), el('dd', '', text(value.value)));
    });
    group.append(table);
    block.append(group);
  });
  target.append(block);
};
