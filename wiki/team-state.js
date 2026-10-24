/* Shared, validated state for pointer, keyboard and saved-team operations. */
((root) => {
  'use strict';
  const groups = ['main', 'unison', 'weapon', 'soul'];
  const empty = () => Object.fromEntries(groups.map((group) => [group, ['', '', '']]));
  const copy = (team) => Object.fromEntries(groups.map((group) => [group, [...team[group]]]));
  const isCharacter = (group) => group === 'main' || group === 'unison';
  function validate(value, characters, equipment) {
    const team = empty();
    const seen = new Set();
    for (const group of groups) {
      if (!Array.isArray(value?.[group])) continue;
      value[group].slice(0, 3).forEach((raw, i) => {
        const id = typeof raw === 'string' ? raw : '';
        const source = isCharacter(group) ? characters : equipment;
        if (!source.has(id) || (isCharacter(group) && seen.has(id))) return;
        if (group === 'soul' && !source.get(id).soul?.available) return;
        team[group][i] = id;
        if (isCharacter(group)) seen.add(id);
      });
    }
    return team;
  }
  function place(team, group, index, id, characters, equipment) {
    if (!groups.includes(group) || !Number.isInteger(index) || index < 0 || index > 2) return team;
    const next = copy(team);
    if (!id) { next[group][index] = ''; return next; }
    const source = isCharacter(group) ? characters : equipment;
    if (!source.has(id) || (group === 'soul' && !source.get(id).soul?.available)) return team;
    if (isCharacter(group)) {
      for (const other of ['main', 'unison']) {
        const old = next[other].indexOf(id);
        if (old >= 0) next[other][old] = next[group][index];
      }
    }
    next[group][index] = id;
    return next;
  }
  function ruleNotes(team, equipment, rules) {
    if (!rules) return [];
    const notes = [], equipped = [];
    for (let i = 0; i < 3; i++) if (team.main[i]) {
      for (const group of ['weapon', 'soul']) {
        const item = equipment.get(team[group][i]); if (item) equipped.push(item);
      }
    }
    const curses = equipped.filter((item) => item.category === '诅咒武器').length;
    if (curses >= rules.curseExclusion.threshold) notes.push(`当前装备 ${curses} 件诅咒武器：它们的本体与强化能力全部失效，HP / 攻击白值保留。`);
    if (equipped.some((item) => item.category === '悖论武器')) {
      const others = equipped.length - 1;
      notes.push(others >= rules.paradoxDecay.offAtOtherCount ? `悖论之外有 ${others} 件装备或魂珠：悖论整件能力失效，HP / 攻击白值保留。` : `悖论之外有 ${others} 件装备或魂珠，适用对应衰减档；诅咒代价不随增益衰减。`);
    }
    return notes;
  }
  const api = {groups, empty, copy, validate, place, isCharacter, ruleNotes};
  root.WFTeamState = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
