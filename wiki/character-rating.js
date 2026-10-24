/* Ratings are server-owned; verification is created only after choosing a score. */
(() => {
  'use strict';
  const states = new Map();
  function record(value) {
    const validScore = (score) => Number.isInteger(score) && score >= 0 && score <= 5;
    if (!value || !Number.isSafeInteger(value.voters) || value.voters < 0 || typeof value.ratedToday !== 'boolean'
      || !(value.myScore === null || validScore(value.myScore))
      || !Number.isFinite(value.nextVoteAt) || value.nextVoteAt <= 0
      || (value.voters === 0 ? value.average !== null : !Number.isFinite(value.average) || value.average < 0 || value.average > 5)
      || (value.rankScore !== undefined && (value.voters === 0 ? value.rankScore !== null : !Number.isFinite(value.rankScore) || value.rankScore < 0 || value.rankScore > 5))) {
      throw new Error('评分数据暂时不可用，请重试。');
    }
    return {average:value.average,voters:value.voters,myScore:value.myScore,ratedToday:value.ratedToday,nextVoteAt:value.nextVoteAt,
      ...(value.rankScore === undefined ? {} : {rankScore:value.rankScore})};
  }
  function message(error) {
    if (error?.status === 401) return '无法确认访客身份，请刷新页面后重试。';
    if (error?.status === 429) return `操作较频繁，请等待 ${Math.max(1, Math.ceil(Number(error.retryAfter || error.data?.retryAfter) || 60))} 秒后再试。`;
    return error?.message || '暂时无法连接评分服务，请稍后重试。';
  }
  function nextTime(value) {
    if (!value?.nextVoteAt) return '北京时间次日 00:00 后可再评。';
    const time = new Date(value.nextVoteAt).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
    return `北京时间 ${time} 后可再评。`;
  }
  function notify(state) {
    for (const view of state.views) {
      if (!view.element.isConnected && view.attached) {state.views.delete(view); continue;}
      view.attached ||= view.element.isConnected;
      view.paint();
    }
  }
  function accept(state, value) {
    state.value = record(value); state.version++; state.error = ''; state.dailyBlocked = false; notify(state);
    window.WFCatalogRatings?.update(state.id, state.value);
  }
  async function load(state, C) {
    const ticket = ++state.loadRevision, version = state.version;
    state.loading = true; state.error = ''; notify(state);
    try {
      const value = await C.client.request(state.path);
      if (ticket === state.loadRevision && version === state.version) accept(state,value);
    } catch (error) {
      if (ticket === state.loadRevision && version === state.version) state.error = message(error);
    } finally {if (ticket === state.loadRevision) {state.loading = false; notify(state);}}
  }
  function refreshExpired(state) {
    const boundary = state.value?.nextVoteAt, C = window.WFCommunity;
    if (!boundary || Date.now() < boundary || state.checkedBoundary === boundary || state.loading || state.voting || state.dialogOpen
      || !C?.client || window.location?.protocol === 'file:' || ![...state.views].some((view) => view.element.isConnected)) return;
    // One automatic attempt per boundary; a failed request or a skewed device clock must not create a request loop.
    state.checkedBoundary = boundary; load(state,C);
  }
  function refreshVisible() {
    if (!window.document?.hidden) for (const state of states.values()) refreshExpired(state);
  }
  window.addEventListener?.('focus',refreshVisible);
  window.document?.addEventListener('visibilitychange',refreshVisible);
  function open(state, character, ui, score, C) {
    if (state.loading || state.dialogOpen || state.voting || !state.value || state.value.ratedToday || state.dailyBlocked) return;
    const {el} = ui, modal = C.dialog(`为「${character.name || '角色'}」评分`,ui), host = modal.element;
    state.dialogOpen = true; notify(state);
    const selection = el('p', 'character-rating-selection', `你的评分：${score} / 5`);
    const notice = el('p', 'character-rating-dialog-status', '正在准备人机验证…'); notice.setAttribute('role','status');
    const verification = el('div', 'community-verification');
    const submit = el('button', 'primary-button', `确认提交 ${score} 分`); submit.type = 'button'; submit.disabled = true;
    const retry = el('button', 'secondary-button', '重新连接评分服务'); retry.type = 'button'; retry.hidden = true;
    host.append(selection,el('p','character-rating-policy','同一角色每天限评一次，以北京时间换日；次日修改会替换旧分，不增加投票人数。'),notice,verification,submit,retry);
    let challenge, closed = false, busy = false, completed = false, ready = false;
    const sync = () => {submit.disabled = !ready || busy || completed || Boolean(state.value?.ratedToday) || state.dailyBlocked;};
    modal.cleanup(() => {closed = true; challenge?.destroy(); state.dialogOpen = false; notify(state);});
    async function connect() {
      ready = false; sync(); retry.hidden = true;
      try {
        const config = await C.client.config(); if (closed) return;
        challenge?.destroy(); verification.replaceChildren();
        challenge = C.challenge(verification,config,'rate_character',ui,(valid) => {ready = valid; sync();});
        notice.textContent = '请完成验证，再确认提交。';
      } catch (error) {if (!closed) {notice.textContent = message(error); retry.hidden = false;}}
    }
    retry.addEventListener('click',connect);
    submit.addEventListener('click',async () => {
      if (closed || busy || completed || state.value?.ratedToday || state.dailyBlocked) {sync(); return;}
      const turnstileToken = challenge?.take(); if (!turnstileToken) return;
      busy = true; state.voting = true; sync(); notify(state); notice.textContent = '正在提交评分…';
      try {
        const result = await C.client.request(state.path,{score,turnstileToken});
        const confirmed = record(result);
        if (!confirmed.ratedToday || confirmed.myScore !== score) throw new Error('服务端未确认本次评分，请刷新评分后核实。');
        accept(state,confirmed); completed = true;
        if (!closed) {notice.textContent = `已提交 ${score} 分；公共榜每日汇总，次日计入。${nextTime(confirmed)}`; verification.hidden = true;}
      } catch (error) {
        if (error?.code === 'already_rated' || error?.code === 'daily_limit') {
          completed = true; state.dailyBlocked = true;
          try {accept(state,error.data); state.dailyBlocked = true;} catch {await load(state,C);}
          if (!closed) {notice.textContent = `今天已为这个角色评分。${nextTime(state.value)}`; verification.hidden = true;}
        } else if (!closed) notice.textContent = message(error);
      } finally {
        busy = false; state.voting = false; notify(state);
        if (!closed) {challenge?.reset(); ready = false; sync();}
      }
    });
    connect();
  }
  window.WFCharacterRating = {mount(host,character,ui) {
    const {el} = ui, C = window.WFCommunity, id = String(character?.id || '');
    const root = el('section','character-rating'); root.setAttribute('aria-label','玩家评分');
    const summary = el('div','character-rating-summary'), result = el('div','character-rating-result');
    const average = el('strong','character-rating-average','—'), voters = el('small','character-rating-voters','');
    result.append(average,el('span','character-rating-out-of','/ 5'));
    summary.append(el('span','character-rating-label','玩家评分'),result,voters);
    const meter = el('meter','character-rating-meter'); meter.min = 0; meter.max = 5; meter.value = 0;
    meter.setAttribute('aria-label','当前平均评分'); meter.hidden = true;
    const choices = el('div','character-rating-choices'); choices.setAttribute('role','group'); choices.setAttribute('aria-label','选择评分，0 至 5 分');
    const status = el('p','character-rating-status'); status.setAttribute('role','status');
    const retry = el('button','text-button character-rating-retry','刷新评分'); retry.type = 'button'; retry.hidden = true;
    root.append(summary,meter,choices,status,retry); host.append(root);
    for (const state of states.values()) for (const view of state.views) if (!view.element.isConnected) state.views.delete(view);
    if (!states.has(id)) states.set(id,{id,path:`/ratings/characters/${encodeURIComponent(id)}`,value:null,version:0,loadRevision:0,views:new Set()});
    const state = states.get(id), buttons = Array.from({length:6},(_,score) => {
      const button = el('button','character-rating-score',String(score)); button.type = 'button'; button.disabled = true;
      button.setAttribute('aria-label',`为${character.name || '角色'}评 ${score} 分`);
      button.addEventListener('click',() => {if (C?.dialog && C?.challenge) open(state,character,ui,score,C);}); choices.append(button); return button;
    });
    function paint() {
      const value = state.value, locked = value?.ratedToday || state.dailyBlocked;
      average.textContent = value?.average == null ? '—' : value.average.toFixed(1);
      meter.hidden = value?.average == null; meter.value = value?.average ?? 0;
      voters.textContent = value ? `${value.voters} 位玩家` : '';
      buttons.forEach((button,score) => {
        button.disabled = Boolean(!value || state.loading || state.error || locked || state.dialogOpen || state.voting || !C?.dialog || !C?.challenge);
        button.setAttribute('aria-pressed',String(value?.myScore === score));
      });
      status.textContent = state.error || (state.loading ? '正在载入评分…' : locked
        ? `${value?.myScore == null ? '今天已评分。' : `今天已评 ${value.myScore} 分。`}${nextTime(value)}`
        : '选择 0–5 分，每位访客每天限评一次（北京时间）。');
      retry.hidden = false; retry.disabled = Boolean(state.loading || state.dialogOpen || state.voting);
    }
    state.views.add({element:root,paint,attached:root.isConnected}); paint();
    if (!id || !C?.client || window.location?.protocol === 'file:') {
      state.error = window.location?.protocol === 'file:' ? '离线版无法读取或提交玩家评分。' : '评分服务尚未准备好，请刷新页面重试。'; paint(); retry.hidden = true;
    } else {
      retry.addEventListener('click',() => load(state,C));
      root.addEventListener('pointerdown',() => refreshExpired(state));
      root.addEventListener('focusin',() => refreshExpired(state));
      load(state,C);
    }
    return root;
  }};
})();
