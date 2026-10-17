/* Local-only ranking state shared by drag, tap and keyboard placement. */
((root) => {
  'use strict';
  const rowKeys = ['tier0', 'between0', 'tier1', 'between1', 'tier2', 'between2', 'tier3', 'between3', 'tier4'];
  const storageKey = 'wf-tier-list-v1', version = 1, historyLimit = 30;
  const empty = () => Object.fromEntries(rowKeys.map((row) => [row, []]));
  const copy = (rows) => Object.fromEntries(rowKeys.map((row) => [row, [...rows[row]]]));
  function create(options = {}) {
    const ids = new Set((options.characters || []).map((character) => character.id).filter((id) => typeof id === 'string' && id));
    const history = [];
    let rows = empty(), storage, error = '';
    try { storage = options.storage === undefined ? root.localStorage : options.storage; }
    catch (_) { error = '浏览器无法读取本地保存；当前排行仍可编辑。'; }
    function read() {
      try {
        if (!storage) throw new Error('storage_unavailable');
        const raw = storage.getItem(storageKey);
        if (raw === null) return;
        const saved = JSON.parse(raw);
        if (saved?.version !== version || !saved.rows || typeof saved.rows !== 'object') throw new Error('invalid_version');
        const seen = new Set();
        for (const row of rowKeys) {
          if (!Array.isArray(saved.rows[row])) continue;
          rows[row] = saved.rows[row].filter((id) => {
            if (typeof id !== 'string' || !ids.has(id) || seen.has(id)) return false;
            seen.add(id); return true;
          });
        }
      } catch (_) { error = '本地排行记录无法读取；当前排行仍可编辑并重新保存。'; }
    }
    function persist() {
      try {
        if (!storage) throw new Error('storage_unavailable');
        storage.setItem(storageKey, JSON.stringify({version, rows})); error = '';
      } catch (_) { error = '本地保存失败；当前排行仍可使用，刷新后可能丢失。'; }
    }
    function change(next) {
      if (rowKeys.every((row) => rows[row].length === next[row].length && rows[row].every((id, index) => id === next[row][index]))) return false;
      history.push(rows); if (history.length > historyLimit) history.shift();
      rows = next; persist(); return true;
    }
    read();
    return {
      getRows: () => copy(rows),
      assignedIds: () => new Set(rowKeys.flatMap((row) => rows[row])),
      persistenceError: () => error,
      canUndo: () => history.length > 0,
      move(id, row, beforeId) {
        if (!ids.has(id) || (row !== 'pool' && !rowKeys.includes(row))) return false;
        if (beforeId === id && row !== 'pool' && rows[row].includes(id)) return false;
        const next = copy(rows);
        for (const key of rowKeys) next[key] = next[key].filter((other) => other !== id);
        if (row !== 'pool') {
          const index = next[row].indexOf(beforeId);
          next[row].splice(index < 0 ? next[row].length : index, 0, id);
        }
        return change(next);
      },
      clear: () => change(empty()),
      undo() {
        if (!history.length) return false;
        rows = history.pop(); persist(); return true;
      },
    };
  }
  const api = {create, rowKeys: Object.freeze([...rowKeys]), storageKey};
  root.WFTierListState = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
