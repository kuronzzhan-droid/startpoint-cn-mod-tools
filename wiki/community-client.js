/* Public community data uses its own same-origin API, never the game server. */
((root) => {
  'use strict';
  const damageTypes = {skill: '技能伤害', ability: '能力伤害', powerflip: '强化弹射伤害', direct: '直接攻击伤害'};
  const teamCategories = ['萌新启航', '原版毕业队', 'MOD毕业队', '最新最潮盘', '玩具盘'];
  const categoryLabel = (value) => teamCategories.includes(value) ? value : '未分类';
  const teamSections = {original: '原版', abyss: '深渊', fantasy: '幻想', 'abyss-ex': '深渊EX', 'five-boss': '五重', '': '其他'};
  const sectionLabel = (value) => Object.hasOwn(teamSections, value) ? teamSections[value] : teamSections[''];
  const sourceUrl = 'https://docs.qq.com/sheet/DSVNsWE5yWUNoR0Ju';
  const groups = ['main', 'unison', 'weapon', 'soul'];
  const elementLabel = (value) => value === 'universal' ? '宇宙' : value;
  const teamCopy = (team) => Object.fromEntries(groups.map((key) => [key,
    Array.from({length: 3}, (_, index) => typeof team?.[key]?.[index] === 'string' ? team[key][index] : '')]));
  function teamError(team, data) {
    const characters = new Map((data.characters || []).map((item) => [item.id, item]));
    const equipment = new Map((data.equipment || []).map((item) => [item.id, item]));
    const seen = new Set();
    for (const group of groups) for (const id of team[group]) {
      if (!id) {if (group === 'main') return '请先填好三个主位角色。'; continue;}
      if (group === 'main' || group === 'unison') {
        if (!characters.has(id)) return '队伍中有当前图鉴未收录的角色。';
        if (seen.has(id)) return '同一角色不能重复编入队伍。';
        seen.add(id);
      } else if (!equipment.has(id) || (group === 'soul' && !equipment.get(id).soul?.available)) {
        return '请检查装备和魂珠，当前图鉴未收录或不可作为魂珠的条目不能收录。';
      }
    }
    return '';
  }
  function query(filters, cursor = '') {
    const params = new URLSearchParams();
    if (typeof filters.q === 'string' && filters.q.trim()) params.set('q', filters.q.trim().normalize('NFC'));
    if (filters.element) params.set('element', filters.element);
    if (filters.section === 'general' || (filters.section && Object.hasOwn(teamSections, filters.section))) params.set('section', filters.section);
    if (['has','none'].includes(filters.code)) params.set('code', filters.code);
    if (teamCategories.includes(filters.category) || filters.category === 'uncategorized') params.set('category', filters.category);
    const selected = Object.keys(damageTypes).filter((key) => filters.damageTypes?.includes(key));
    if (selected.length) params.set('damage', selected.join(','));
    params.set('sort', filters.sort === 'latest' ? 'latest' : 'popular');
    if (cursor) params.set('cursor', cursor);
    return params.toString();
  }
  function message(error) {
    if (error?.status === 429) return `操作较频繁，请等待 ${Math.max(1, Math.ceil(error.retryAfter || 60))} 秒后再试。`;
    if (error?.code === 'already_liked') return '今天已经为这张盘点过赞了，明天（北京时间）可以再来。';
    if (error?.code === 'duplicate') return '相同阵容已收录，不需要重复提交。';
    return error?.message || '暂时无法连接配队社区，请稍后重试。';
  }
  function createApi(fetcher, protocol) {
    let configPromise, configRequest;
    // Presentation-only memory: protected actions always ask the server again.
    let identity, identityVersion = 0;
    const identityListeners = new Set(), identityRequests = new Map();
    const identityPath = (path) => path === '/auth/me' || path === '/admin/me';
    function updateIdentity(value) {
      identity = value?.id && typeof value.email === 'string' && value.enabled !== false
        ? Object.freeze({id:value.id, email:value.email, role:value.role, mustChangePassword:value.mustChangePassword === true}) : null;
      for (const listener of identityListeners) {try {listener(identity);} catch { /* UI listeners cannot change API outcomes. */ }}
    }
    async function send(path, body, method = body ? 'POST' : 'GET') {
      if (!/^https?:$/.test(protocol)) throw new Error('离线版可编辑和保存队伍；配队大全与点赞请前往公开网站。');
      const version = identityVersion;
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      try {
        const response = await fetcher(`/api/community${path}`, {
          method, credentials: 'same-origin', signal: controller.signal,
          headers: {Accept: 'application/json', ...(body ? {'Content-Type': 'application/json'} : {})},
          ...(body ? {body: JSON.stringify(body)} : {}),
        });
        let value;
        try {value = await response.json();} catch {throw new Error('此站暂未启用配队社区，仍可使用本地队伍编成。');}
        if (!response.ok) {
          if (response.status === 401 && version === identityVersion && (identityPath(path) || path.startsWith('/admin/'))) updateIdentity(null);
          const error = new Error(value.message || '配队社区暂时无法完成此操作。');
          Object.assign(error, {status: response.status, code: value.error, data: value,
            retryAfter: Number(value.retryAfter || response.headers?.get('Retry-After')) || 0});
          throw error;
        }
        if (method === 'POST' && ['/auth/login','/auth/bootstrap','/auth/password','/auth/logout'].includes(path)) {
          identityVersion++; identityRequests.clear(); updateIdentity(path === '/auth/logout' ? null : value);
        } else if (method === 'GET' && identityPath(path) && version === identityVersion) updateIdentity(value);
        return value;
      } catch (error) {
        if (error.name === 'AbortError') throw new Error('连接超时，请重试；填写的内容仍保留。');
        if (error instanceof TypeError) throw new Error('网络连接失败，请重试；填写的内容仍保留。');
        throw error;
      } finally {clearTimeout(timeout);}
    }
    function fetchConfig() {
      if (!configRequest) configRequest = send('/config').finally(() => {configRequest = null;});
      return configRequest;
    }
    async function request(path, body, method = body ? 'POST' : 'GET') {
      if (path === '/config' && method === 'GET') return fetchConfig();
      // Initial visible-page statistics and a page's own config share one cookie.
      // Wait for that response before a concurrent rating/like may create an identity.
      if (configRequest) await configRequest.catch(() => {});
      if (method === 'GET' && identityPath(path)) {
        if (!identityRequests.has(path)) {
          const pending = send(path, body, method).finally(() => {if (identityRequests.get(path) === pending) identityRequests.delete(path);});
          identityRequests.set(path, pending);
        }
        return identityRequests.get(path);
      }
      return send(path, body, method);
    }
    return {request, identity: () => identity, observeIdentity: (listener) => {
      identityListeners.add(listener); listener(identity); return () => identityListeners.delete(listener);
    }, config: ({refresh = false} = {}) => {
      if (refresh) configPromise = null;
      if (!configPromise) configPromise = fetchConfig().then((value) => {
        if (!value.enabled) throw new Error('此站暂未启用配队社区，仍可使用本地队伍编成。');
        return value;
      }).catch((error) => {configPromise = null; throw error;});
      return configPromise;
    }};
  }
  const api = {damageTypes, teamCategories, categoryLabel, teamSections, sectionLabel, sourceUrl, elementLabel, teamCopy, teamError, query, message, createApi};
  if (root.location && root.fetch) api.client = createApi(root.fetch.bind(root), root.location.protocol);
  root.WFCommunity = Object.assign(root.WFCommunity || {}, api);
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
