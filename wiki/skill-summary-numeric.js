/* Summarize recorded effects without adding branches, hits or program sources together. */
window.renderWikiSkillSummaryNumeric = function(target, skill, ui) {
  'use strict';
  const {el, list, text} = ui;
  const values = (row) => list(row.values).filter((value) => value && value.value != null && text(value.value).trim());
  const context = (row) => list(row.context).map((value) => text(value));
  const sameContext = (a, b) => JSON.stringify(context(a)) === JSON.stringify(context(b));
  const sources = [{title:'技能主体', details:skill.numericDetails}, ...list(skill.relatedPrograms).map((program, index) => ({
    title:`关联效果 ${index + 1}${program?.kind ? ` · ${text(program.kind)}` : ''}`, details:program?.numericDetails,
  }))].map((source) => ({...source, rows:list(source.details?.rows).filter((row) => row && values(row).length)}));
  const entries = sources.flatMap((source) => source.rows.map((row, index) => ({source, row, index})));
  const formulas = entries.filter(({row}) => row.kind === 'formula');
  const damage = (row) => row.kind === 'damage' || row.label === '固定伤害';
  const effects = entries.filter(({row}) => row.kind !== 'formula').sort((a,b) => Number(damage(b.row)) - Number(damage(a.row)));
  const root = el('section', 'skill-summary-numeric');
  root.setAttribute('aria-label', '技能倍率与效果数值');
  const preview = el('div', 'summary-numeric-preview');
  preview.append(el('span', 'summary-numeric-level', skill.levelMode === 'initial' ? '初始' : '满级'));
  const get = (row, label) => values(row).find((value) => value.label === label)?.value;
  const damageEntries = effects.filter(({row}) => damage(row));
  const chip = (label, note = '', compact = false) => {
    const node = el('span', `summary-numeric-chip${compact ? ' summary-numeric-brief-formula' : ''}`, label);
    if (note) node.setAttribute('title', note);
    preview.append(node);
  };
  const multiplierEntries = damageEntries.filter(({row}) => get(row, '单次命中倍率') != null || get(row, '伤害倍率') != null);
  if (multiplierEntries.length) {
    const multipliers = [...new Set(multiplierEntries.map(({row}) => text(get(row, '单次命中倍率') ?? get(row, '伤害倍率'))))];
    const constants = multipliers.every((value) => /^[+-]?\d+(?:\.\d+)?倍$/.test(value));
    // Public rows do not prove that every hit lands or executes; never manufacture a total.
    chip(constants ? `单次倍率 ${multipliers.slice(0, 2).join(' / ')}${multipliers.length > 2 ? ' …' : ''}` : `单次倍率${multiplierEntries.length > 1 ? '（首项）' : ''} ${multipliers[0]}`,
      constants ? '各伤害条目的单次倍率，不相加为总倍率；命中次数与条件见详细数值。' : `单次倍率：${multipliers[0]}；含成长或动态公式，具体条件与其他条目见详细数值。`, !constants);
    if (!constants) chip('依条件变化');
    else if (multiplierEntries.some(({row}) => context(row).length) || multiplierEntries.length > 1) chip('分段／条件见详情');
    else if (damageEntries.length > multiplierEntries.length) chip('另含其他伤害');
  } else if (effects.length) {
    const primary = damageEntries.length ? damageEntries : effects;
    const seen = new Set();
    for (const {row, source} of primary) {
      const key = ['效果量','比例','数值','持续时间','增加层数'].find((label) => get(row, label) != null);
      if (!key) continue;
      const base = key === '比例' ? text(get(row, '计算基准')) : '';
      const duration = key !== '持续时间' ? get(row, '持续时间') : '';
      const label = `${text(row.label, '效果')} ${base}${text(get(row, key))}${duration ? ` · ${duration}` : ''}`;
      if (seen.has(label)) continue;
      seen.add(label); chip(label, `${source.title}${context(row).length ? ` · 条件：${context(row).join(' / ')}` : ''}`);
      if (seen.size === 2) break;
    }
    if (!seen.size) chip('效果数值见详情');
    if (primary.some(({row}) => context(row).length)) chip('依条件生效');
  } else chip('倍率与效果数值未记录');
  root.append(preview);
  function fold(host, label, build) {
    const box = el('details', 'summary-numeric-more'); box.append(el('summary', '', label)); let built = false;
    box.addEventListener('toggle', () => {if (box.open && !built) {build(box); built = true;}}); host.append(box); return box;
  }
  function fields(host, items) {
    const order = ['单次命中倍率','伤害倍率','区间命中次数设定','命中次数上限','最短命中间隔','持续时间','判定持续','效果量'];
    const rank = (value) => order.includes(value.label) ? order.indexOf(value.label) : order.length;
    const table = el('dl', 'summary-numeric-values');
    [...items].sort((a,b) => rank(a)-rank(b)).forEach((value) => {
      table.append(el('dt', '', text(value.label, '参数')), el('dd', '', text(value.value)));
    }); host.append(table);
  }
  function basic(entry, isFormula = false) {
    const {row, source, index} = entry;
    const item = el('div', isFormula ? 'summary-numeric-formula' : 'summary-numeric-item');
    item.append(el('p', 'summary-numeric-source', `${source.title} · 条目 ${index + 1}`),
      el('h5', '', text(row.label, isFormula ? '成长规则' : '效果')));
    if (context(row).length) item.append(el('p', 'summary-numeric-context', context(row).join(' / ')));
    fields(item, values(row)); return item;
  }
  function effect(entry) {
    const item = basic(entry), refs = [...new Set(values(entry.row).flatMap((value) => text(value.value).match(/成长变量\d+/g) || []))];
    if (!refs.length) return item;
    // These are matching records, not an inferred runtime binding across conditions or programs.
    const related = formulas.filter((definition) => definition.source === entry.source
      && values(definition.row).some((value) => refs.includes(value.label)));
    const exact = related.filter((definition) => sameContext(definition.row, entry.row));
    const showDefinitions = (host) => exact.forEach((definition) => {
      const block = el('div', 'summary-numeric-definition');
      block.append(el('span', '', '同条件记录：'));
      values(definition.row).filter((value) => refs.includes(value.label)).forEach((value) =>
        block.append(el('p', '', `${value.label} = ${text(value.value)}`)));
      host.append(block);
    });
    if (exact.length <= 2) showDefinitions(item);
    else fold(item, `同条件成长定义（${exact.length} 条，不自动合并）`, showDefinitions);
    const missing = refs.filter((ref) => !exact.some((definition) => values(definition.row).some((value) => value.label === ref)));
    if (missing.length) item.append(el('p', 'summary-numeric-note', missing.map((ref) => related.some((definition) => values(definition.row).some((value) => value.label === ref))
      ? `${ref} 未记录同条件定义，请展开“成长规则”查看其他条件。` : `${ref} 的定义未记录。`).join(' ')));
    return item;
  }
  if (entries.length || sources.some((source) => list(source.details?.notes).length)) fold(root, '详细数值', (details) => {
    details.append(el('p', 'summary-numeric-note', '单次倍率与命中次数设定分列；条目数不等于攻击段数，不同条件和来源不相加为总倍率。'));
    effects.slice(0, 6).forEach((entry) => details.append(effect(entry)));
    if (effects.length > 6) fold(details, `展开其余 ${effects.length - 6} 条效果`, (host) => effects.slice(6).forEach((entry) => host.append(effect(entry))));
    if (formulas.length) fold(details, `成长规则（${formulas.length} 条，按来源与条件查看）`, (host) => formulas.forEach((entry) => host.append(basic(entry, true))));
    if (sources.some((source) => list(source.details?.notes).length)) fold(details, '数值说明', (host) => {
      sources.forEach((source) => {
        if (!list(source.details?.notes).length) return;
        const block = el('div', 'summary-numeric-notes'); block.append(el('p', 'summary-numeric-source', source.title));
        list(source.details.notes).forEach((note) => block.append(el('p', 'summary-numeric-note', text(note)))); host.append(block);
      });
    });
  });
  target.append(root); return root;
};
