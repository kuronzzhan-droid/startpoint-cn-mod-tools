/* Local preferences and settled best results only; never persist live battle state. */
((root) => {
  'use strict';
  const key = 'wf-wiki-battle-v1', schema = 1;
  const object = value => value && typeof value === 'object' && !Array.isArray(value);
  const finite = (value, max) => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= max;
  const integer = (value, max) => Number.isSafeInteger(value) && finite(value, max);
  const clone = value => JSON.parse(JSON.stringify(value));
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const empty = () => ({schema, settings:{muted:false, volume:.65}, squad:[], campaign:{},
    endless:{bestWave:0, bestKills:0}, modified:{settings:0, squad:0}});
  function create({storage, characterIds = [], stageIds = []} = {}) {
    const characters = new Set(characterIds), stages = new Set(stageIds), listeners = new Set();
    let state = empty(), destroyed = false, dirty = false, lastError = '';
    const validSquad = ids => Array.isArray(ids) && ids.length <= 6 && new Set(ids).size === ids.length
      && ids.every(id => typeof id === 'string' && characters.has(id));
    const settingsValid = value => object(value) && typeof value.muted === 'boolean' && finite(value.volume, 1);
    const stampValid = value => integer(value, Number.MAX_SAFE_INTEGER - 1);
    function normalize(raw) {
      if (raw === null) return empty();
      if (typeof raw !== 'string' || raw.length > 65536) throw new Error('invalid save');
      const value = JSON.parse(raw);
      if (!object(value) || value.schema !== schema || !settingsValid(value.settings) || !validSquad(value.squad)
        || !object(value.campaign) || !object(value.endless)
        || !integer(value.endless.bestWave, 1e6) || !integer(value.endless.bestKills, 1e6)) throw new Error('invalid save');
      const modified = value.modified ?? {settings:0, squad:0};
      if (!object(modified) || !stampValid(modified.settings) || !stampValid(modified.squad)) throw new Error('invalid stamp');
      const campaign = Object.fromEntries(Object.entries(value.campaign).map(([id, result]) => {
        if (!stages.has(id) || !object(result) || result.completed !== true || !finite(result.bestTime, 1e9)) {
          throw new Error('invalid campaign');
        }
        return [id, {completed:true, bestTime:result.bestTime}];
      }));
      return {schema, settings:{muted:value.settings.muted, volume:value.settings.volume}, squad:[...value.squad],
        campaign, endless:{bestWave:value.endless.bestWave, bestKills:value.endless.bestKills},
        modified:{settings:modified.settings, squad:modified.squad}};
    }
    function merge(a, b) {
      const result = clone(a);
      for (const field of ['settings', 'squad']) {
        if (b.modified[field] >= a.modified[field]) {
          result[field] = clone(b[field]); result.modified[field] = b.modified[field];
        }
      }
      result.campaign = Object.fromEntries([...stages].flatMap(id => {
        const first = Object.hasOwn(a.campaign, id) ? a.campaign[id] : null;
        const second = Object.hasOwn(b.campaign, id) ? b.campaign[id] : null;
        if (!first && !second) return [];
        return [[id, {completed:true, bestTime:Math.min(first?.bestTime ?? Infinity, second?.bestTime ?? Infinity)}]];
      }));
      result.endless = {bestWave:Math.max(a.endless.bestWave, b.endless.bestWave),
        bestKills:Math.max(a.endless.bestKills, b.endless.bestKills)};
      return result;
    }
    const area = () => storage === undefined ? root.localStorage : storage;
    function load() {
      let raw;
      try {raw = area().getItem(key);}
      catch {return {error:'本机记录未保存：浏览器存储不可用，仍可继续游戏。'};}
      try {return {value:normalize(raw), raw};}
      catch {return {error:'本机记录未保存：记录格式或版本无效，原记录未改动。'};}
    }
    function result(error = lastError) {
      return {ok:!error, value:clone(state), ...(error ? {error} : {})};
    }
    function notify() {
      for (const fn of listeners) {try {fn(result());} catch { /* A subscriber cannot prevent saving. */ }}
    }
    function refresh() {
      const disk = load();
      if (disk.value) state = merge(state, disk.value);
      if (disk.error) lastError = disk.error;
      else if (!dirty) lastError = '';
      return disk;
    }
    function modify(change) {
      if (destroyed) return result('本机记录已关闭。');
      const disk = refresh(), next = clone(state);
      change(next);
      if (!same(next, state)) {state = next; dirty = true;}
      // A storage event may have rescued a better result than a racing disk write.
      // Repair it only on the next explicit user save, never from a polling loop.
      if (disk.value && !same(state, disk.value)) dirty = true;
      if (!dirty) return result();
      if (disk.error) {notify(); return result();}
      try {
        const raw = JSON.stringify(state);
        if (raw !== disk.raw) area().setItem(key, raw);
        dirty = false; lastError = '';
      } catch {lastError = '本机记录未保存：存储空间不足或写入被阻止，当前游戏仍可继续。';}
      notify(); return result();
    }
    function stamp(next, field) {
      next.modified[field] = Math.min(Number.MAX_SAFE_INTEGER - 1,
        Math.max(Date.now(), state.modified.settings + 1, state.modified.squad + 1));
    }
    function validResult(value) {
      return object(value) && ['campaign', 'endless'].includes(value.mode) && stages.has(value.stageId)
        && typeof value.won === 'boolean' && finite(value.time, 1e9)
        && integer(value.wave, 1e6) && value.wave >= 1 && integer(value.kills, 1e6);
    }
    return {
      read() {if (!destroyed) refresh(); return result();},
      writeSettings(value) {
        if (!object(value) || (Object.hasOwn(value, 'muted') && typeof value.muted !== 'boolean')
          || (Object.hasOwn(value, 'volume') && !finite(value.volume, 1))) return result('声音设置无效。');
        return modify(next => {
          const settings = {muted:Object.hasOwn(value, 'muted') ? value.muted : next.settings.muted,
            volume:Object.hasOwn(value, 'volume') ? value.volume : next.settings.volume};
          if (!same(next.settings, settings)) {next.settings = settings; stamp(next, 'settings');}
        });
      },
      writeSquad(ids) {
        if (!validSquad(ids)) return result('请选择最多六位不同且可用的 MOD 角色。');
        return modify(next => {if (!same(next.squad, ids)) {next.squad = [...ids]; stamp(next, 'squad');}});
      },
      record(value) {
        if (!validResult(value)) return result('战果记录无效，本机成绩未改动。');
        return modify(next => {
          if (value.mode === 'campaign' && value.won) {
            const previous = Object.hasOwn(next.campaign, value.stageId) ? next.campaign[value.stageId].bestTime : Infinity;
            Object.defineProperty(next.campaign, value.stageId, {enumerable:true, configurable:true, writable:true,
              value:{completed:true, bestTime:Math.min(previous, value.time)}});
          } else if (value.mode === 'endless') {
            next.endless.bestWave = Math.max(next.endless.bestWave, value.wave);
            next.endless.bestKills = Math.max(next.endless.bestKills, value.kills);
          }
        });
      },
      mergeExternal(raw) {
        if (destroyed) return result('本机记录已关闭。');
        let next;
        try {next = merge(state, normalize(raw));}
        catch {return result('其他页面的本机记录无效，当前记录未改动。');}
        if (!same(next, state)) {state = next; notify();}
        return result();
      },
      subscribe(fn) {
        if (destroyed || typeof fn !== 'function') return () => {};
        listeners.add(fn); return () => listeners.delete(fn);
      },
      destroy() {destroyed = true; listeners.clear();},
    };
  }
  const api = {create, key, schema}; root.WFBattleStorage = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
