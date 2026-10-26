/* Browser-only records; retain the original v1 array and unknown legacy fields. */
((root) => {
  'use strict';
  const key = 'wf-wiki-teams-v1';
  const copy = value => JSON.parse(JSON.stringify(value));
  const valid = item => item && typeof item.name === 'string' && item.team && typeof item.team === 'object' && !Array.isArray(item.team);
  const fail = (code, message) => Object.assign(new Error(message), {code});
  const title = value => {
    const name = String(value || '').trim();
    if (!name || name.length > 60) throw fail('name', '请输入 1–60 字的队伍名称。');
    return name;
  };
  function create(storage = () => localStorage) {
    function snapshotOf(source, entries) {
      const records = entries.flatMap((item, index) => valid(item) ? [{...copy(item), key: index}] : []);
      return {source, records, skipped: entries.length - records.length};
    }
    function read() {
      let source, entries;
      try {source = storage().getItem(key) ?? null;}
      catch {throw fail('read', '无法读取此浏览器的队伍，请检查浏览器存储权限。原记录未改动。');}
      try {entries = source === null ? [] : JSON.parse(source); if (!Array.isArray(entries)) throw new Error();}
      catch {throw fail('format', '本地队伍记录格式异常，已停止写入以保留原记录。');}
      return snapshotOf(source, entries);
    }
    function write(snapshot, operation) {
      if (!snapshot || read().source !== snapshot.source) throw fail('stale', '队伍列表已在其他页面修改，请刷新列表后再试。');
      const entries = JSON.parse(snapshot.source || '[]');
      operation(entries);
      const source = JSON.stringify(entries);
      try {storage().setItem(key, source);}
      catch {throw fail('write', '未能保存更改，原队伍仍保留。请检查存储空间或导出队伍备份。');}
      return snapshotOf(source, entries);
    }
    const get = (entries, index) => {
      if (!Number.isInteger(index) || !valid(entries[index])) throw fail('missing', '这支队伍已不存在，请刷新列表。');
      return entries[index];
    };
    function unique(entries, name, except = -1) {
      if (entries.some((item, index) => index !== except && valid(item) && item.name === name)) {
        throw fail('exists', '已有同名队伍，请换一个名称；保存当前编成时可明确选择覆盖。');
      }
    }
    return {
      read,
      add(snapshot, record) {return write(snapshot, entries => {
        const name = title(record.name); unique(entries, name);
        if (!valid({...record, name})) throw fail('team', '队伍数据无效。');
        entries.unshift({...copy(record), name});
      });},
      replace(snapshot, index, record) {return write(snapshot, entries => {
        const current = get(entries, index), name = title(record.name); unique(entries, name, index);
        if (!valid({...record, name})) throw fail('team', '队伍数据无效。');
        entries[index] = {...current, ...copy(record), name};
      });},
      rename(snapshot, index, value) {return write(snapshot, entries => {
        const current = get(entries, index), name = title(value); unique(entries, name, index); current.name = name;
      });},
      remove(snapshot, index) {return write(snapshot, entries => {get(entries, index); entries.splice(index, 1);});},
      copyName(snapshot, value) {
        const base = title(value), names = new Set(snapshot.records.map(item => item.name));
        for (let number = 1; ; number++) {
          const suffix = `（副本${number === 1 ? '' : number}）`, name = base.slice(0, 60 - suffix.length) + suffix;
          if (!names.has(name)) return name;
        }
      },
    };
  }
  const api = {key, create}; root.WFTeamSavedStore = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
