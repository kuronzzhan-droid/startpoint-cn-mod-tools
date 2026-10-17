/* Project explicit initial/max endpoints without treating skill forms as levels. */
(() => {
  'use strict';
  const list = (value) => Array.isArray(value) ? value : [];
  const modeOf = (mode) => mode === 'initial' ? 'initial' : 'max';
  const pair = /([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(%|倍|秒|帧|次|个|层|点)?→([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(%|倍|秒|帧|次|个|层|点)?/g;
  function convert(value, mode) {
    let count = 0;
    if (typeof value !== 'string') return {value, count};
    const result = value.replace(pair, (whole, first, firstUnit, last, lastUnit, offset, source) => {
      // Canonical numeric pairs have no spaces; trigger/action arrows and chains are not endpoints.
      if (source[offset - 1] === '→' || source[offset + whole.length] === '→' || (firstUnit && lastUnit && firstUnit !== lastUnit)) return whole;
      count += 1;
      return (modeOf(mode) === 'initial' ? first : last) + (firstUnit || lastUnit || '');
    });
    return {value: result, count};
  }
  const projectText = (value, mode = 'max') => convert(value, mode).value;
  function numericDetails(data, mode) {
    if (!data || typeof data !== 'object') return data;
    return {...data,
      notes: list(data.notes).map((note) => typeof note === 'string' ? note.replace(/^箭头表示技能 Lv1→满级；/, `当前显示${modeOf(mode) === 'initial' ? '初始' : '满级'}技能值；`) : note),
      rows: list(data.rows).filter((row) => row && typeof row === 'object').map((row) => ({...row,
      context: list(row.context).map((value) => projectText(value, mode)),
      values: list(row.values).filter((value) => value && typeof value === 'object').map((value) => ({...value, value: projectText(value.value, mode)})),
    }))};
  }
  function projectEntry(entry, requestedMode = 'max', options = {}) {
    if (!entry || typeof entry !== 'object') return entry;
    const mode = modeOf(requestedMode), initial = mode === 'initial', skill = options.kind === 'skill';
    const out = {...entry, levelMode: mode};
    let endpoints = 0;
    if (entry.descriptionSource === '数据行自动解析') {
      const converted = convert(entry.description, mode); out.description = converted.value; endpoints += converted.count;
    }
    if (Array.isArray(entry.rows)) out.rows = entry.rows.map((row) => {
      if (!row || typeof row !== 'object') return row;
      const converted = convert(row.description, mode); endpoints += converted.count;
      return {...row, description: converted.value,
        levelNote: initial && !converted.count ? '未记录独立初始端点，单值保留作参考。' : ''};
    });
    const notes = [];
    if (initial) {
      if (entry.descriptionSource === '游戏面板覆盖文案' || (skill && entry.description)) {
        notes.push('未提供独立初始文案，主说明保留为参考；逐条数值仅取明确记录的初始端点。');
      } else if (endpoints) notes.push('初始值仅取明确记录的左端；未分级单值保留参考，不据此推算。');
      else notes.push('未记录独立初始端点，以下文案与单值保留作参考。');
    }
    if (skill) {
      const gauge = initial ? entry.gaugeMin : entry.gauge;
      out.gauge = gauge == null || gauge === '' ? null : gauge;
      out.gaugeLabel = `${initial ? '初始' : '满'}技能等级所需能量${entry.kind === 'switched' ? '（沿用对应形态）' : ''}`;
      if (out.gauge == null) notes.push(`${initial ? '初始' : '满级'}能量未记录。`);
    }
    out.levelNote = notes.join(' ');
    if (options.includeNumeric !== false) {
      if (entry.numericDetails) out.numericDetails = numericDetails(entry.numericDetails, mode);
      if (Array.isArray(entry.relatedPrograms)) out.relatedPrograms = entry.relatedPrograms.filter((program) => program && typeof program === 'object').map((program) => ({...program,
        ...(program.numericDetails ? {numericDetails: numericDetails(program.numericDetails, mode)} : {}),
      }));
    }
    return out;
  }
  function project(character, requestedMode = 'max', options = {}) {
    const mode = modeOf(requestedMode);
    return {...character, levelMode: mode,
      skills: list(character.skills).map((entry) => projectEntry(entry, mode, {...options, kind: 'skill'})),
      leader: projectEntry(character.leader, mode, options),
      abilities: list(character.abilities).map((entry) => projectEntry(entry, mode, options)),
    };
  }
  window.WFCharacterLevels = {project, projectEntry, projectText};
})();
