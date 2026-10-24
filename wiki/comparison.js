/* Official-to-current comparisons display authored text, never source code. */
window.renderWikiComparison = function renderWikiComparison(target, comparison, ui) {
  'use strict';
  const {el, list, object, text} = ui;
  const data = object(comparison);
  const baseline = object(data.baseline);
  const intro = el('div', 'comparison-intro');
  intro.append(el('strong', '', '官方原版 → 当前版本'),
    el('p', '', `对照基准：${text(baseline.name, '同一角色')} · 官方 ${text(baseline.version, '未记录')}`));
  target.append(intro);
  if (list(data.summary).length) {
    const summary = el('ul', 'comparison-summary');
    list(data.summary).forEach((item) => summary.append(el('li', '', item)));
    target.append(summary);
  }
  const sections = list(data.sections).filter((section) => section && section.status !== 'unchanged');
  if (!sections.length) {
    target.append(el('p', 'note-box', data.status === 'unchanged' ? '当前收录资料与官方原版一致。' : '当前没有可展示的逐项对照。'));
    return;
  }
  sections.forEach((section) => {
    const group = el('section', 'comparison-group');
    group.append(el('h3', 'section-title', text(section.label, '角色调整')));
    list(section.items).filter((item) => item && item.status !== 'unchanged').forEach((item) => {
      const card = el('div', 'comparison-item');
      card.append(el('h4', '', text(item.label, '调整项目')));
      const columns = el('div', 'comparison-columns');
      [['before', '官方原版'], ['after', '当前版本']].forEach(([key, label]) => {
        const value = object(item[key]);
        const side = el('div', `comparison-side ${key}`);
        side.append(el('span', 'comparison-side-label', label));
        if (value.name) side.append(el('strong', '', value.name));
        side.append(el('p', '', text(value.text, item[key] == null ? '无此项' : '此项未提供文字描述')));
        if (value.numericDetails) window.renderWikiNumericDetails(side, value.numericDetails, ui);
        columns.append(side);
      });
      card.append(columns);
      group.append(card);
    });
    target.append(group);
  });
};
