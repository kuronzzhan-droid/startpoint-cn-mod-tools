(() => {
  'use strict';
  function lazyDetails(ui, label, className, build) {
    const section = ui.el('details', className);
    section.append(ui.el('summary', '', label));
    let built = false;
    section.addEventListener('toggle', () => {
      if (section.open && !built) {build(section); built = true;}
    });
    return section;
  }
  const fieldNames = {name: '名称', description: '说明', level: '等级', maxLevel: '最高等级', hp: '生命值', element: '属性', attack: '攻击', atk: '攻击',
    count: '数量', amount: '数量', quantity: '数量', item: '材料', itemName: '材料', costs: '材料', mechanics: '机制', summary: '概览',
    entry: '进入方式', stages: '阶段', bosses: 'Boss', affixes: '词缀', rewards: '奖励', notes: '提示', title: '名称', rounds: '轮次',
    difficulty: '难度', waves: '波次', stage: '阶段', rule: '规则', effects: '效果', before: '原版', after: '当前', chance: '概率',
    rate: '概率', value: '数值', duration: '持续时间', unlock: '解锁', perRun: '每场', pool: '候选池', label: '名称', note: '说明',
    routeCount: '路线数量', upperRoutes: '上半场', lowerRoutes: '下半场', wave: '波次', hpDisplay: '生命值', scope: '范围',
    enabled:'当前开放',soloAvailable:'支持单人',maxPlayers:'最多人数',ticketName:'入场凭证',round:'场次',order:'波次',simultaneous:'同屏出场',
    fromLevel:'起始强化等级',toLevel:'强化至',perLevelCosts:'每级所需材料',requiredAwakeningLevel:'所需觉醒等级',total:'总计',
    hpText:'多人生命值',soloHpText:'单人生命值',trials:'试炼要求',entryMechanics:'开场机制',enemyConditions:'敌方状态',timeLimitSeconds:'限时（秒）',feverCapacity:'Fever容量'};
  function renderReadable(parent, value, ui, depth = 0) {
    const {el} = ui;
    if (value == null || value === '') return;
    if (typeof value !== 'object') {parent.append(el('p', '', typeof value === 'boolean' ? (value ? '是' : '否') : value)); return;}
    if (Array.isArray(value)) {
      value.forEach((entry) => {const box = el('div', depth < 2 ? 'guide-item' : 'guide-detail'); renderReadable(box, entry, ui, depth + 1); parent.append(box);}); return;
    }
    Object.entries(value).forEach(([key, child]) => {
      if (['id', 'sourceHashes', 'sourceFiles', 'sourceMissing', 'key', 'icon', 'meta', 'questId'].includes(key) || child == null || child === '') return;
      if ((key === 'hp' && value.hpText) || (key === 'soloHp' && value.soloHpText)) return;
      if (key === 'name' || key === 'title' || key === 'label') {parent.append(el(depth < 2 ? 'h2' : 'h3', '', child)); return;}
      if (typeof child === 'object') {
        const box = el('div', 'guide-field'); box.append(el('h4', '', fieldNames[key] || key)); renderReadable(box, child, ui, depth + 1); parent.append(box);
      } else parent.append(el('p', '', `${fieldNames[key] || key}：${typeof child === 'boolean' ? (child ? '是' : '否') : child}`));
    });
  }
  window.WFWikiReadable = {lazyDetails, renderReadable};
  window.renderWikiPage = (route, host, data, ui) => {
    if (route === 'battle') {window.renderWikiBattle(host, data, ui); return true;}
    if (route === 'tier-list') {window.renderWikiTierList(host, data, ui); return true;}
    if (route === 'team') {window.renderWikiTeam(host, data, ui); return true;}
    if (route === 'weapons') {window.renderWikiWeaponPage(host, data, ui); return true;}
    if (route.startsWith('weapon/')) {window.renderWikiWeaponPage(host, data, ui, decodeURIComponent(route.split('/')[1] || '')); return true;}
    if (route === 'shops' || route.startsWith('shops/')) {window.renderWikiShops(host, data, ui, {id: route.split('/')[1] || ''}); return true;}
    if (route === 'community/admin') {window.renderWikiCommunityAdmin(host, data, ui); return true;}
    if (route === 'community' || route.startsWith('community/')) {window.renderWikiCommunity(host, data, ui, {id: route.split('/')[1] || ''}); return true;}
    if (route === 'dungeons' || route.startsWith('dungeons/') || route === 'five-boss') {
      const id = route === 'five-boss' ? data.dungeons?.items.find((item) => item.legacyGuide === 'five-boss')?.id
        : route.split('/')[1] || '';
      if (route === 'five-boss' && !id) {window.renderWikiBossGuide(host, data, ui); return true;}
      window.renderWikiDungeons(host, data, ui, {id,
        renderLegacyGuide: (target) => window.renderWikiBossGuide(target, data, ui, {mechanicsOnly:true})});
      return true;
    }
    return false;
  };
})();
