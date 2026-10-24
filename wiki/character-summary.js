/* Lightweight overview; full portraits, voices and remaining numeric effects load on demand. */
window.renderWikiCharacterSummary = function renderWikiCharacterSummary(host, character, meta, ui, options) {
  'use strict';
  options = options || {};
  const {el, list, object, text, picture, nativeIcon, elementBadge, rarityBadge, formatNumber} = ui;
  let effectMode = 'max';
  const effectViews = [];
  const projectEffect = (entry, kind = 'effect') => window.WFCharacterLevels?.projectEntry(entry, effectMode, {kind, includeNumeric: kind === 'skill'}) || entry;
  const root = el('section', 'character-summary');
  root.dataset.element = ({火:'fire', 水:'water', 雷:'thunder', 风:'wind', 光:'light', 暗:'dark'})[character.element] || 'other';
  root.setAttribute('aria-label', `${text(character.name, '角色')}概览`);
  function detailsButton(label, tab, className = '') {
    const button = el('button', `summary-detail-button ${className}`, label); button.type = 'button';
    button.disabled = typeof options.onOpenDetails !== 'function';
    button.addEventListener('click', () => options.onOpenDetails?.(tab));
    return button;
  }
  const actions = el('nav', 'summary-actions'); actions.setAttribute('aria-label', '角色详细资料');
  actions.append(detailsButton('立绘·铭牌·语音', 'profile'), detailsButton('查看完整数值', 'skills'));
  root.append(actions);

  const header = el('header', 'summary-header');
  const avatar = el('div', 'summary-avatar'); avatar.append(picture(character.icon, text(character.name), ''));
  window.WFCharacterFrame?.apply(avatar, character);
  const identity = el('div', 'summary-identity');
  identity.append(el('p', 'summary-title', text(character.title)));
  const name = el('div', 'summary-name'); name.append(el('h1', '', text(character.name, '未命名角色')), rarityBadge(character.rarity));
  identity.append(name);
  const tags = el('div', 'summary-tags');
  window.WFCharacterBadges?.append(tags, character, ui, true);
  list(character.themes || (character.theme ? [character.theme] : [])).forEach((theme) => tags.append(el('span', 'summary-theme', theme)));
  if (list(character.aliases).length) tags.append(el('span', 'summary-aliases', character.aliases.join(' / ')));
  identity.append(tags);
  const type = el('div', 'summary-type');
  type.append(elementBadge(character.element), nativeIcon('types', character.type, ''), el('span', '', text(character.type, '类型未记录')));
  header.append(avatar, identity, type); root.append(header);
  const variants = el('div', 'summary-variants'); root.append(variants);
  window.WFCharacterVariants?.mount(variants, character, ui, {onNavigate:options.onVariantNavigate});
  window.WFWikiAliases?.mount(root, 'character', character.id, ui);
  window.WFCharacterRating?.mount(root, character, ui);
  window.WFCharacterViews?.mount(root, character, ui, {record:Boolean(options.publicOverview)});

  const stats = object(character.stats);
  const levels = list(stats.levels).filter((row) => row && row.level != null && row.level !== '' && Number.isFinite(Number(row.level)));
  const highest = levels.reduce((best, row) => !best || Number(row.level) >= Number(best.level) ? row : best, null);
  const fields = el('dl', 'summary-fields');
  const entries = [['种族', list(character.races).join(' / ')], ['定位', character.role],
    ['攻击', highest?.atk == null ? '' : formatNumber(highest.atk)], ['HP', highest?.hp == null ? '' : formatNumber(highest.hp)],
    ['性别', character.gender], ['CV（资料表）', character.cv]];
  entries.forEach(([label, value]) => {
    const field = el('div', 'summary-field'); field.append(el('dt', '', label), el('dd', '', text(value, '未记录'))); fields.append(field);
  });
  root.append(fields, el('p', 'summary-stat-note', `${highest ? `Lv. ${text(highest.level)} 基础数值` : '基础数值未记录'} · 未计觉醒、玛纳板、装备与能力加成`));
  if (text(character.editorNote).trim()) root.append(el('p', 'summary-editor-note', character.editorNote));
  const levelToolbar = el('div', 'summary-level-toolbar');
  levelToolbar.setAttribute('role', 'group'); levelToolbar.setAttribute('aria-label', '技能与能力等级');
  levelToolbar.append(el('span', '', '技能与能力等级'));
  const levelButtons = ['initial', 'max'].map((mode) => {
    const button = el('button', '', mode === 'initial' ? '初始' : '满级'); button.type = 'button';
    button.setAttribute('aria-pressed', String(mode === effectMode));
    button.disabled = typeof window.WFCharacterLevels?.projectEntry !== 'function';
    button.addEventListener('click', () => {
      effectMode = mode;
      levelButtons.forEach((item, index) => item.setAttribute('aria-pressed', String(['initial', 'max'][index] === mode)));
      showSkill(chosen); effectViews.forEach(({host, entry}) => effects(host, entry));
    });
    levelToolbar.append(button); return button;
  });
  root.append(levelToolbar);

  function section(label, className = '') {
    const section = el('section', `summary-section ${className}`);
    section.append(el('h2', 'summary-section-label', label)); return section;
  }
  function effects(host, entry) {
    const shown = projectEffect(entry); host.replaceChildren();
    if (shown.levelNote) host.append(el('p', 'summary-level-note', shown.levelNote));
    if (!window.renderWikiAbilityRows?.(host, shown, meta, ui)) {
      host.append(el('p', 'summary-copy', text(shown.description, '当前资料中暂无效果说明。')));
    }
    // Authored summaries stay primary; row-level conditions remain available without repeating long text.
    host.querySelectorAll('.ability-effect-disclosure').forEach((detail) => {detail.open = false;});
  }
  const skillSection = section('技能', 'summary-skill');
  const skills = list(character.skills).filter((skill) => skill && (skill.name || skill.description || skill.gauge != null
    || list(skill.numericDetails?.rows).length || list(skill.relatedPrograms).some((program) => list(program?.numericDetails?.rows).length)));
  const skillChoices = el('div', 'summary-skill-choices'); skillChoices.setAttribute('role', 'group'); skillChoices.setAttribute('aria-label', '技能形态');
  const skillBody = el('div', 'summary-skill-body');
  const skillLabel = (skill) => text(skill.label, `${skill.kind === 'switched' ? '切换后技能 · ' : ''}${({1:'普通技能',2:'进化技能',3:'二次进化技能'})[skill.level] || '主动技能'}`);
  let chosen = -1;
  const mainIndexes = skills.map((skill, index) => ({skill, index})).filter(({skill}) => skill.kind !== 'switched');
  (mainIndexes.length ? mainIndexes : skills.map((skill, index) => ({skill, index}))).forEach(({skill, index}) => {
    if (chosen < 0 || (Number(skill.level) || 0) >= (Number(skills[chosen].level) || 0)) chosen = index;
  });
  const buttons = skills.map((skill, index) => {
    const button = el('button', '', skillLabel(skill)); button.type = 'button';
    button.addEventListener('click', () => showSkill(index)); skillChoices.append(button); return button;
  });
  function showSkill(index) {
    const skill = projectEffect(skills[index], 'skill'); if (!skill) return;
    chosen = index; buttons.forEach((button, i) => button.setAttribute('aria-pressed', String(i === index)));
    const heading = el('div', 'summary-skill-heading');
    heading.append(el('h3', '', text(skill.name, '技能名称未记录')));
    const energy = el('span', 'summary-energy');
    energy.append(el('span', '', text(skill.gaugeLabel, '满技能等级所需能量')), el('strong', '', skill.gauge == null ? '未记录' : formatNumber(skill.gauge)));
    heading.append(energy);
    const nodes = [heading, el('p', 'summary-copy', text(skill.description, '当前资料中暂无技能说明。'))];
    if (skill.levelNote) nodes.push(el('p', 'summary-level-note', skill.levelNote));
    if (skill.kind === 'switched' && character.switch?.label) {
      nodes.push(el('p', 'summary-switch-note', `切换条件：${character.switch.label}${character.switch.conditionName ? ` · ${character.switch.conditionName}` : ''}`));
    }
    skillBody.replaceChildren(...nodes);
    window.renderWikiSkillSummaryNumeric?.(skillBody, skill, ui);
  }
  if (skills.length) {skillSection.append(skillChoices, skillBody); showSkill(chosen);}
  else skillSection.append(el('p', 'summary-copy', '当前资料中没有可展示的主动技能。'));
  root.append(skillSection);

  const leader = object(character.leader), leaderSection = section('队长技', 'summary-leader');
  if (leader.name) leaderSection.append(el('h3', 'summary-effect-name', leader.name));
  const leaderBody = el('div', 'summary-effect-body'); effects(leaderBody, leader);
  effectViews.push({host: leaderBody, entry: leader}); leaderSection.append(leaderBody); root.append(leaderSection);
  const abilitySection = section('角色能力', 'summary-abilities');
  const abilities = list(character.abilities).filter((ability) => ability && typeof ability === 'object');
  abilities.map((ability, index) => ({ability, slot: ability.slot ?? index + 1})).sort((a, b) => Number(a.slot) - Number(b.slot)).forEach(({ability, slot}) => {
    const row = el('section', 'summary-ability');
    const label = `能力 ${text(slot)}`; row.append(el('h3', 'summary-ability-label', label));
    const body = el('div', 'summary-ability-body');
    if (ability.name && ability.name !== label) body.append(el('h4', 'summary-effect-name', ability.name));
    const content = el('div', 'summary-effect-body'); effects(content, ability);
    effectViews.push({host: content, entry: ability}); body.append(content); row.append(body); abilitySection.append(row);
  });
  if (!abilities.length) abilitySection.append(el('p', 'summary-copy', '当前资料中暂无能力说明。'));
  root.append(abilitySection);
  const footer = el('div', 'summary-footer');
  footer.append(detailsButton('查看完整数值', 'skills'), detailsButton('试听语音与台词', 'voices'));
  root.append(footer); host.replaceChildren(root);
  if (options.publicOverview) window.WFCharacterTeams?.mount(root, character, ui, {characters:options.characters || []});
  return root;
};
