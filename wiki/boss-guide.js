/* The original five-boss queries remain available inside the unified directory. */
window.renderWikiBossGuide = (host, data, ui, options = {}) => {
  const {lazyDetails, renderReadable} = window.WFWikiReadable;
  const box = ui.el('div', 'boss-guide'), guide = data.bossGuide;
  if (guide) {
    box.append(ui.el('h2', '', guide.title), ui.el('p', 'section-intro', guide.summary));
    box.append(ui.el('p', 'note-box', '以下机制来自本地资料快照，可能与灰服当前关卡不同；灰服入口与关卡名称请以目录上方的来源说明为准。'));
    if (!options.mechanicsOnly) renderReadable(box, {entry:guide.entry, rewards:guide.rewards}, ui);
    renderReadable(box, {notes:guide.notes}, ui);
    box.append(ui.el('h2', '', '路线与各波敌人'));
    (guide.stages || []).forEach((stage) => {
      box.append(lazyDetails(ui, `${stage.round === 1 ? '上半场' : '下半场'} · ${stage.name}`, 'guide-item', (section) => {
        const detail = {...stage}; delete detail.name; delete detail.round;
        renderReadable(section, detail, ui);
      }));
    });
    box.append(lazyDetails(ui, 'Boss 机制速查', 'guide-item', (section) => renderReadable(section, guide.bosses, ui)));
  } else box.append(ui.el('p', '', '当前快照暂无五重决战资料。'));
  host.replaceChildren(box);
};
