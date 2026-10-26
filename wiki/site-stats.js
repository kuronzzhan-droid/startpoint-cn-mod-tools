/* Visible tabs share public statistics and cooldowns; no identity is stored here. */
((root) => {
  'use strict';
  const interval = 1800000, failureDelays = [1800000,3600000,7200000,14400000], day = 86400000;
  const storageKey = 'wf-wiki-site-stats-v2', lockName = 'wf-wiki-site-stats';
  const timestamp = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value) && Number.isFinite(Date.parse(value));
  function normalize(value) {
    if (!value || !['totalVoters','ratingVoters','tierVoters','onlineVisitors'].every(key => Number.isSafeInteger(value[key]) && value[key] >= 0)
      || value.totalVoters < Math.max(value.ratingVoters,value.tierVoters) || value.totalVoters > value.ratingVoters + value.tierVoters
      || ![120,300,1800].includes(value.presenceWindowSeconds) || !timestamp(value.asOf)
      || (value.participationAsOf === undefined) !== (value.participationStale === undefined)
      || (value.participationAsOf !== undefined && !timestamp(value.participationAsOf))
      || (value.participationStale !== undefined && typeof value.participationStale !== 'boolean'))
      throw new Error('统计数据暂时不可用。');
    return Object.freeze({totalVoters:value.totalVoters,ratingVoters:value.ratingVoters,tierVoters:value.tierVoters,onlineVisitors:value.onlineVisitors,
      asOf:value.asOf,presenceWindowSeconds:value.presenceWindowSeconds,
      ...(value.participationAsOf !== undefined ? {participationAsOf:value.participationAsOf} : {}),
      ...(value.participationStale !== undefined ? {participationStale:value.participationStale} : {})});
  }
  function create({client, protocol, document, events, storage, locks, now = Date.now, schedule = setTimeout, cancel = clearTimeout}) {
    const listeners = new Set();
    let status = protocol === 'file:' ? 'offline' : 'loading', data = null, pending = null, timer, started = false, lastAttempt = -Infinity;
    let failures = 0, retryAt = 0, errorCode = '', generation = 0, sharedAt = -Infinity, lockRetryAt = 0;
    let sharing = Boolean(storage?.getItem && storage?.setItem);
    const visible = () => document.visibilityState !== 'hidden';
    const nextAttempt = () => Math.max(lastAttempt + interval, retryAt, lockRetryAt);
    const stale = () => data && Date.parse(data.asOf) + data.presenceWindowSeconds * 1000 < now();
    function notify() {for (const fn of listeners) {try {fn({status,data,errorCode});} catch { /* An optional view cannot interrupt the heartbeat. */ }}}
    function markStale() {
      if (status === 'ready' && stale()) {status = 'error'; errorCode = 'stale_stats'; notify();}
    }
    function sharedRecord(raw) {
      if (!raw || raw.length > 4096) return null;
      try {
        const value = JSON.parse(raw), time = now();
        if (value.version !== 1 || !['loading','ready','error'].includes(value.status)
          || !['','database_quota_exceeded','statistics_paused','stale_stats'].includes(value.errorCode)
          || !Number.isSafeInteger(value.writtenAt) || value.writtenAt > time + 5000 || value.writtenAt < time - day
          || !Number.isSafeInteger(value.lastAttempt) || value.lastAttempt < value.writtenAt - day || value.lastAttempt > value.writtenAt
          || !Number.isSafeInteger(value.retryAt) || value.retryAt < 0 || value.retryAt > value.writtenAt + day
          || !Number.isInteger(value.failures) || value.failures < 0 || value.failures > failureDelays.length) return null;
        let publicData = value.data === null ? null : normalize(value.data);
        if ((value.status === 'ready' && !publicData) || (publicData && Date.parse(publicData.asOf) > value.writtenAt + 60000)) return null;
        // Expired counts must not erase a still-valid quota cooldown shared by another tab.
        if (publicData && Date.parse(publicData.asOf) < time - day) publicData = null;
        return {...value,data:publicData,...(value.status === 'ready' && !publicData ? {status:'error',errorCode:'stale_stats'} : {})};
      } catch {return null;}
    }
    function readShared() {
      if (!sharing || status === 'offline') return;
      let raw;
      try {raw = storage.getItem(storageKey);} catch {sharing = false; return;}
      const record = sharedRecord(raw);
      if (!record || record.writtenAt < sharedAt) return;
      sharedAt = record.writtenAt; lastAttempt = Math.max(lastAttempt,record.lastAttempt);
      retryAt = record.retryAt; failures = record.failures; errorCode = record.errorCode;
      data = record.data || data;
      status = record.status === 'loading' && data ? 'ready' : record.status;
      if (status === 'ready' && stale()) {status = 'error'; errorCode = 'stale_stats';}
      notify();
    }
    function publish() {
      if (!sharing || !started) return;
      const writtenAt = now();
      // Explicit fields prevent arbitrary API payloads, credentials or tokens entering localStorage.
      const value = {version:1,writtenAt,lastAttempt,retryAt,failures,errorCode,status,data};
      try {storage.setItem(storageKey,JSON.stringify(value)); sharedAt = writtenAt;} catch {sharing = false;}
    }
    function queue() {
      cancel(timer); timer = null;
      if (started && visible() && !pending && status !== 'offline') timer = schedule(refresh, Math.max(0, nextAttempt() - now()));
    }
    async function heartbeat(active) {
      try {return await client.request('/presence', {}, 'POST');}
      catch (error) {
        if (!active() || !visible()) return null;
        if (error?.status !== 428 || error?.code !== 'visitor_required') throw error;
        // A long-lived tab may outlive its cookie. Recover once, without retry loops.
        await client.config({refresh:true});
        if (!active() || !visible()) return null;
        return client.request('/presence', {}, 'POST');
      }
    }
    function failure(error) {
      const hint = Number(error?.retryAfter ?? error?.data?.retryAfter);
      const reset = error?.resetAt ?? error?.data?.resetAt;
      const resetDelay = timestamp(reset) ? Date.parse(reset) - now() : 0;
      const delay = failureDelays[Math.min(failures,failureDelays.length - 1)];
      failures = Math.min(failures + 1,failureDelays.length);
      errorCode = ['database_quota_exceeded','statistics_paused'].includes(error?.code) ? error.code : '';
      retryAt = now() + Math.ceil(Math.min(day,Math.max(delay, Number.isFinite(hint) ? Math.max(0,hint) * 1000 : 0,
        Math.max(0,resetDelay), errorCode === 'database_quota_exceeded' && resetDelay <= 0 ? 3600000 : 0)));
      status = 'error'; publish(); notify();
    }
    async function attempt(active) {
      if (!active() || !visible()) return;
      readShared(); markStale();
      if (!active() || !visible() || now() < nextAttempt()) return;
      lastAttempt = now(); lockRetryAt = 0;
      if (!data) {status = 'loading'; errorCode = ''; notify();}
      publish();
      try {
        if (!active() || !visible()) return;
        await client.config();
        if (!active() || !visible()) return;
        const value = await heartbeat(active);
        if (!active() || value === null) return;
        data = normalize(value); failures = 0; retryAt = 0;
        // Start the next interval after the response. Otherwise network latency can make
        // the next heartbeat arrive before the server's thirty-minute write gate opens.
        lastAttempt = Math.max(lastAttempt,now());
        status = stale() ? 'error' : 'ready'; errorCode = stale() ? 'stale_stats' : '';
        publish(); notify();
      } catch (error) {if (active()) failure(error);}
    }
    function refresh() {
      if (!started || !visible() || pending || status === 'offline') return pending;
      readShared(); markStale();
      if (!started || !visible()) return null;
      // Focus, manual refresh, new tabs and reconnect all honor the same sending interval.
      if (now() < nextAttempt()) {queue(); return null;}
      cancel(timer); timer = null;
      const ticket = generation, active = () => started && ticket === generation;
      pending = Promise.resolve().then(async () => {
        if (!active() || !visible()) return;
        if (sharing && typeof locks?.request === 'function') {
          let entered = false;
          try {
            await locks.request(lockName,{ifAvailable:true},async lock => {
              if (!active() || !visible()) return;
              entered = true;
              if (lock) await attempt(active);
              else {readShared(); lockRetryAt = now() + interval;}
            });
            return;
          } catch {
            // A denied/unsupported lock API degrades to low-frequency, best-effort sharing.
            if (entered) return;
          }
        }
        await attempt(active);
      }).finally(() => {pending = null; queue();});
      return pending;
    }
    function wake() {
      cancel(timer); timer = null;
      if (started && visible()) refresh();
    }
    function sharedUpdate(event) {
      if (!started || status === 'offline' || (event.key !== storageKey && event.key !== null)) return;
      readShared(); queue();
    }
    const api = {
      subscribe(fn) {listeners.add(fn); fn({status,data,errorCode}); return () => listeners.delete(fn);},
      refresh,
      start() {
        if (started) return; started = true; generation++;
        events.addEventListener('focus',wake); events.addEventListener('online',wake); events.addEventListener('storage',sharedUpdate); document.addEventListener('visibilitychange',wake);
        readShared();
        if (status !== 'offline') refresh();
      },
      stop() {
        started = false; generation++; cancel(timer); timer = null;
        events.removeEventListener('focus',wake); events.removeEventListener('online',wake); events.removeEventListener('storage',sharedUpdate); document.removeEventListener('visibilitychange',wake);
      },
    };
    return api;
  }
  if (typeof module !== 'undefined') module.exports = {create,normalize,storageKey};
  if (!root.WFCommunity?.client || !root.document) return;
  let storage, locks;
  try {storage = root.localStorage; locks = root.navigator?.locks;} catch { /* Private browsing may deny storage access. */ }
  const api = root.WFSiteStats = create({client:root.WFCommunity.client,protocol:root.location.protocol,document:root.document,events:root,storage,locks});
  const host = root.document.getElementById('site-presence');
  if (host) {
    const label = root.document.createElement('span'), count = root.document.createElement('strong'), note = root.document.createElement('small');
    label.textContent = '近30分钟活跃'; host.append(label,count,note);
    api.subscribe(({status,data,errorCode}) => {
      const minutes = (data?.presenceWindowSeconds || 1800) / 60;
      label.textContent = `近${minutes}分钟活跃`;
      count.textContent = data ? `${data.onlineVisitors.toLocaleString('zh-CN')} 人` : '—';
      note.textContent = status === 'offline' ? '离线版不统计访客' : status === 'loading' ? '正在连接统计'
        : status === 'error' ? (errorCode === 'database_quota_exceeded'
          ? (data ? '统计额度已用尽，显示上次统计' : '统计额度已用尽，恢复后自动重试')
          : errorCode === 'stale_stats' ? '显示上次统计，正在更新'
          : errorCode === 'statistics_paused' ? (data ? '统计暂缓，显示上次统计' : '统计暂缓，稍后自动重试')
          : (data ? '连接中断，显示上次统计' : '统计暂不可用'))
          : `最近 ${minutes} 分钟活跃访客 · 每 30 分钟更新${data?.participationStale ? ' · 参与人数更新中' : ''}`;
      host.dataset.status = status;
      host.setAttribute('aria-label', `最近 ${minutes} 分钟活跃访客 ${data ? `${data.onlineVisitors} 人` : '暂无统计'}，${note.textContent}`);
      host.title = `${note.textContent}。按匿名访客去重，同一浏览器多个标签算一人；关闭或转入后台后将在 ${minutes} 分钟内不再计入。不同设备可能重复计数。`;
    });
  }
  api.start();
})(typeof window === 'undefined' ? globalThis : window);
