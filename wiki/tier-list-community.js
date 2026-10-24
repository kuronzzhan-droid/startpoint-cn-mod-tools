/* Public tiers are server-owned; editing a local board never submits a vote. */
(() => {
  'use strict';
  const rowKeys = ['tier0', 'between0', 'tier1', 'between1', 'tier2', 'between2', 'tier3', 'between3', 'tier4'];
  const publicRowKeys = [...rowKeys, 'provisional'];
  const labels = ['夯', '夯 ↔ 顶级', '顶级', '顶级 ↔ 人上人', '人上人', '人上人 ↔ NPC', 'NPC', 'NPC ↔ 拉完了', '拉完了'];
  const score = (value) => Number.isFinite(value) && value >= 0 && value <= 5;
  const votes = (value) => Number.isSafeInteger(value) && value >= 0;
  const ranking = window.WFRatingScore, sources = {placement: '手动排行', rating: '角色评分'};
  const beijingTime = value => new Date(value).toLocaleString('zh-CN', {
    timeZone:'Asia/Shanghai', month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit', hour12:false,
  });
  const publishedTime = value => value?.asOf && value?.nextRefreshAt
    ? `${value.stale ? '上次汇总' : '今日汇总'}：北京时间 ${beijingTime(value.asOf)}；${value.stale ? '今日数据更新中' : `下次 ${beijingTime(value.nextRefreshAt)}`}。`
    : '公共榜每日汇总（北京时间换日），新投票立即保存，次日计入。';
  function publicRecord(value) {
    const invalid = () => {throw new Error('排行资料异常，请重新载入。');};
    if (!value || Object.entries(ranking.FORMULA).some(([key, entry]) => value.formula?.[key] !== entry)) invalid();
    if (value.asOf !== undefined && (!Number.isFinite(Date.parse(value.asOf))
      || !Number.isFinite(Date.parse(value.nextRefreshAt)) || Date.parse(value.nextRefreshAt) <= Date.parse(value.asOf)
      || typeof value.stale !== 'boolean')) invalid();
    for (const source of Object.keys(sources)) {
      if (!Array.isArray(value.rankings?.[source])) invalid();
      const seen = new Set();
      for (const item of value.rankings[source]) {
        // The server tiers unrounded averages; the displayed two-decimal mean can cross a boundary.
        if (!item || typeof item.id !== 'string' || seen.has(item.id) || !publicRowKeys.includes(item.row) || !score(item.rankScore)
          || !votes(item.voters) || !item.voters || !score(item.average) || (source === 'placement' && item.average < 1)
          || (item.row === 'provisional') !== (item.voters < ranking.MINIMUM_TIER_VOTERS)) invalid();
        seen.add(item.id);
      }
    }
    return value;
  }
  function personalRecord(value) {
    if (!value || typeof value.submittedToday !== 'boolean' || !Number.isFinite(value.nextVoteAt) || value.nextVoteAt <= 0
      || !votes(value.rankedCharacters) || value.challengeAction !== 'submit_tier_ranking'
      || !value.rows || rowKeys.some(row => !Array.isArray(value.rows[row]) || value.rows[row].some(id => typeof id !== 'string')))
      throw new Error('无法确认今天的提交状态，请重新连接。');
    return value;
  }
  const nextTime = (value) => `北京时间 ${new Date(value.nextVoteAt).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  })} 后可再次提交。`;
  function create({host, data, ui, state, initialView = 'community', onViewChange = () => {}}) {
    const {el, nativeIcon} = ui, C = window.WFCommunity;
    const characters = data.characters || [], byId = new Map(characters.map(character => [String(character.id), character]));
    const element = el('section', 'tier-community'), tabs = el('div', 'tier-community-tabs');
    tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', '选择个人或大家排行');
    const mineHost = el('div', 'tier-personal-view'), dynamicHost = el('div', 'tier-public-view');
    mineHost.id = 'tier-personal-view'; dynamicHost.id = 'tier-public-view';
    mineHost.setAttribute('role', 'tabpanel'); dynamicHost.setAttribute('role', 'tabpanel');
    const mineTab = el('button', '', '我的排行'), publicTab = el('button', '', '大家排行');
    [mineTab, publicTab].forEach((button, index) => {
      button.type = 'button'; button.id = index ? 'tier-public-tab' : 'tier-personal-tab'; button.setAttribute('role', 'tab');
      button.setAttribute('aria-controls', index ? dynamicHost.id : mineHost.id); tabs.append(button);
      button.addEventListener('click', () => setView(index ? 'community' : 'mine'));
      button.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const next = event.key === 'Home' ? 0 : event.key === 'End' ? 1 : 1 - index;
        setView(next ? 'community' : 'mine'); [mineTab, publicTab][next].focus();
      });
    });
    mineHost.setAttribute('aria-labelledby', mineTab.id); dynamicHost.setAttribute('aria-labelledby', publicTab.id);
    const submitBar = el('div', 'tier-submit-bar'), submit = el('button', 'primary-button', '提交我的排行'); submit.type = 'button';
    const mineStatus = el('span', 'tier-submit-status'); mineStatus.setAttribute('role', 'status');
    submitBar.append(submit, mineStatus);
    const publicToolbar = el('div', 'tier-public-toolbar'), avatarHost = el('div');
    const refresh = el('button', 'secondary-button', '刷新'); refresh.type = 'button';
    refresh.setAttribute('aria-label', '刷新大家排行');
    const detailToggle = el('button', 'tier-detail-toggle'); detailToggle.type = 'button';
    detailToggle.setAttribute('role', 'switch'); detailToggle.setAttribute('aria-label', '显示全部评分详情');
    detailToggle.setAttribute('aria-checked', 'false');
    const track = el('span', 'tier-detail-track'); track.setAttribute('aria-hidden', 'true'); track.append(el('span', 'tier-detail-thumb'));
    detailToggle.append(track, el('span', '', '详情'));
    const help = el('details', 'tier-help tier-public-help'), helpSummary = el('summary', '', '说明');
    const helpBody = el('div', 'tier-help-body'); helpSummary.setAttribute('aria-label', '查看排行说明');
    helpBody.id = 'tier-public-help-body'; helpBody.hidden = true;
    helpSummary.setAttribute('aria-controls', helpBody.id); help.append(helpSummary);
    help.addEventListener('toggle', () => {helpBody.hidden = help.hidden || !help.open;});
    const participation = el('div', 'tier-public-participation'); participation.setAttribute('aria-label', '全站参与人数');
    const totalCount = el('strong', '', '—'), ratingCount = el('strong', '', '—'), tierCount = el('strong', '', '—');
    const participationStatus = el('small', 'tier-participation-status'); participationStatus.setAttribute('role', 'status');
    [['参与', totalCount, '角色评分和手动排行合并去重的全站人数'], ['评分', ratingCount, '全站角色评分人数'], ['手排', tierCount, '全站手动排行人数']].forEach(([label, value, title]) => {
      const item = el('span', 'tier-participation-count'); item.append(el('span', '', label), value, el('span', '', '人'));
      item.title = `${title}，不随属性筛选变化。`;
      participation.append(item);
    });
    participation.append(participationStatus);
    const sourceTabs = el('div', 'tier-ranking-sources'), sourceButtons = [];
    sourceTabs.setAttribute('role', 'group'); sourceTabs.setAttribute('aria-label', '排行投票来源');
    publicToolbar.append(sourceTabs, avatarHost);
    const description = el('p', 'tier-public-formula'), publicSummary = el('p', 'tier-public-summary');
    const updated = el('p', 'tier-public-updated');
    helpBody.append(description, publicSummary, updated, refresh);
    const publicStatus = el('p', 'tier-public-status'); publicStatus.setAttribute('role', 'status');
    const elementFilters = el('div', 'tier-public-elements'); elementFilters.setAttribute('role', 'group'); elementFilters.setAttribute('aria-label', '排行属性');
    const results = el('div', 'tier-public-results'), elementButtons = [], boardHeading = el('div', 'tier-public-heading');
    boardHeading.append(elementFilters, participation);
    dynamicHost.append(publicToolbar, boardHeading, publicStatus, results);
    // Keep the disclosure in its toolbar slot; only its separate full-width panel expands below.
    const navigation = el('div', 'tier-community-nav'); navigation.append(tabs, detailToggle, help, helpBody);
    element.append(navigation, submitBar, mineHost, dynamicHost); host.append(element);
    let view = 'mine', revision = 0, portraits, dialogOpen = false, submitted, cached, elementFilter = '', source = 'placement', showDetails = false, publicCards = [];
    let stopStats, statsDisposed = false, statsAttached = element.isConnected, lastStats;
    function destroy() {
      if (statsDisposed) return;
      statsDisposed = true; revision++; stopStats?.(); stopStats = undefined;
      window.removeEventListener?.('wf-page-leave', destroy);
    }
    function paintParticipation(snapshot = {}) {
      if (statsDisposed) return;
      if (!element.isConnected && statsAttached) {destroy(); return;}
      statsAttached ||= element.isConnected;
      const valid = votes(snapshot.data?.totalVoters) && votes(snapshot.data?.ratingVoters) && votes(snapshot.data?.tierVoters);
      if (valid) lastStats = snapshot.data;
      const text = (node, value) => {if (node.textContent !== value) node.textContent = value;};
      text(totalCount, lastStats ? String(lastStats.totalVoters) : '—');
      text(ratingCount, lastStats ? String(lastStats.ratingVoters) : '—');
      text(tierCount, lastStats ? String(lastStats.tierVoters) : '—');
      participationStatus.title = lastStats?.participationAsOf ? `参与人数统计于 ${new Date(lastStats.participationAsOf).toLocaleString('zh-CN')}；投票变化后按请求定时汇总。` : '';
      text(participationStatus, snapshot.status === 'ready' && valid ? (lastStats.participationStale ? '参与人数更新中' : '定时更新')
        : snapshot.status === 'offline' ? (lastStats ? '离线 · 上次统计' : '离线，暂无统计')
        : snapshot.status === 'loading' ? (lastStats ? '更新中…' : '正在统计…')
        : lastStats ? '更新失败 · 上次统计' : '统计暂不可用');
      participationStatus.hidden = snapshot.status === 'ready' && valid && !lastStats.participationStale;
      participation.title = `全站参与人数，不随属性筛选变化。${participationStatus.title || '定时更新。'}${participationStatus.textContent}`;
    }
    window.addEventListener?.('wf-page-leave', destroy);
    paintParticipation({status: /^https?:$/.test(window.location?.protocol) ? 'loading' : 'offline'});
    if (window.WFSiteStats?.subscribe) {
      stopStats = window.WFSiteStats.subscribe(paintParticipation);
      if (statsDisposed) {stopStats?.(); stopStats = undefined;}
    } else if (/^https?:$/.test(window.location?.protocol)) paintParticipation({status: 'error'});
    detailToggle.addEventListener('click', () => {
      showDetails = !showDetails; detailToggle.setAttribute('aria-checked', String(showDetails));
      publicCards.forEach(({card, text}) => {text.hidden = !showDetails; card.className = `tier-public-card${showDetails ? '' : ' is-compact'}`;});
    });
    function describeSource() {
      description.textContent = `${sources[source]}独立计票，每日汇总（北京时间换日）。满 ${ranking.MINIMUM_TIER_VOTERS} 票按真实均分分档，不足则暂定，无票不入榜。档内排序参考 ${ranking.PRIOR_VOTERS} 份中立分（每份 ${ranking.PRIORS[source]} 分），不增加玩家票数。`;
    }
    Object.entries(sources).forEach(([value, label]) => {
      const button = el('button', 'tier-ranking-source', label); button.type = 'button';
      button.setAttribute('aria-pressed', String(value === source));
      button.addEventListener('click', () => {
        source = value; sourceButtons.forEach(entry => entry.button.setAttribute('aria-pressed', String(entry.value === source)));
        describeSource(); if (cached) renderPublic(cached);
      });
      sourceButtons.push({button, value}); sourceTabs.append(button);
    });
    describeSource();
    ['', '火', '水', '雷', '风', '光', '暗'].forEach(value => {
      const button = el('button', 'tier-public-element'); button.type = 'button';
      button.setAttribute('aria-label', value ? `${value}属性排行` : '全体角色总榜');
      if (value) button.append(nativeIcon('elements', value, value)); button.append(el('span', '', value || '总榜'));
      button.setAttribute('aria-pressed', String(value === elementFilter));
      button.addEventListener('click', () => {
        elementFilter = value; elementButtons.forEach(entry => entry.button.setAttribute('aria-pressed', String(entry.value === value)));
        if (cached) renderPublic(cached);
      });
      elementButtons.push({button, value}); elementFilters.append(button);
    });
    const online = () => Boolean(C?.client && C?.dialog && C?.challenge && /^https?:$/.test(window.location?.protocol));
    const message = error => error?.status === 401 ? '无法确认访客身份，请刷新页面后重试。'
      : C?.message?.(error) || error?.message || '排行服务暂时不可用，请重试。';
    function refreshState() {
      const count = Object.values(state.getRows()).reduce((total, ids) => total + ids.length, 0);
      submit.disabled = dialogOpen || !online();
      mineStatus.textContent = !online() ? '离线模式，无法提交'
        : submitted?.submittedToday ? `今天已提交 ${submitted.rankedCharacters} 位角色`
        : count ? `本地已排 ${count} 位角色` : '尚未放置角色';
      mineStatus.title = submitted?.submittedToday ? nextTime(submitted) : '本地自动保存，点击提交才计入大家排行；提交空榜可撤回旧票。';
    }
    function renderPublic(value) {
      const items = value.rankings[source].filter(item => byId.has(item.id) && (!elementFilter || byId.get(item.id).element === elementFilter));
      const sourceLabel = sources[source], currentSource = source;
      const board = el('div', 'tier-board tier-public-board');
      const provisionalCount = items.filter(item => item.row === 'provisional').length;
      let provisionalSection;
      publicCards = [];
      publicRowKeys.forEach((key, index) => {
        const provisional = key === 'provisional', between = key.startsWith('between');
        const row = el('section', provisional ? 'tier-public-provisional' : `tier-zone ${between ? 'tier-boundary' : `tier-row tier-row-${index / 2}`}`);
        row.setAttribute('data-row', key);
        const slots = el('div', 'tier-slots');
        if (provisional) {
          const heading = el('div', 'tier-provisional-heading');
          heading.append(el('h2', '', '暂定'), el('span', 'tier-provisional-count', `${provisionalCount} 位角色`));
          heading.title = `不足 ${ranking.MINIMUM_TIER_VOTERS} 票，尚未定级；满票后按真实均分分档。`;
          row.append(heading, slots);
          provisionalSection = row;
        } else row.append(el(between ? 'span' : 'h2', 'tier-label', labels[index]), slots);
        items.filter(item => item.row === key).forEach(item => {
          const character = byId.get(item.id), card = el('button', `tier-public-card${showDetails ? '' : ' is-compact'}`); card.type = 'button';
          card.setAttribute('data-character-id', item.id);
          const portrait = el('span', 'tier-avatar'); portrait.append(portraits.picture(character, '', ''), nativeIcon('elements', character.element, character.element, 'tier-avatar-element'));
          window.WFCharacterFrame?.apply(portrait, character);
          const title = `${character.name}${character.theme ? `（${character.theme}）` : ''}`;
          const counts = `${item.voters} 人 · ${provisional ? '暂定排序' : '档内排序'} ${item.rankScore.toFixed(2)}`;
          card.title = title; card.setAttribute('aria-label', `查看${title}的排行详情`);
          card.setAttribute('aria-haspopup', 'dialog');
          card.addEventListener('click', () => {
            const modal = C.dialog(`${title} · ${sourceLabel}`, ui), body = el('div', 'tier-score-detail');
            const headline = el('div', 'tier-score-headline');
            headline.append(el('span', '', '真实均分'), el('strong', '', item.average.toFixed(2)), el('span', '', `/ 5 · ${provisional ? '暂定，尚未定级' : labels[rowKeys.indexOf(item.row)]}`));
            body.append(headline);
            const stat = el('div', 'tier-score-stat');
            stat.append(el('span', '', provisional ? '暂定排序分' : '档内排序分'), el('strong', '', item.rankScore.toFixed(2)), el('span', '', `${item.voters} 位玩家`)); body.append(stat);
            body.append(el('p', 'tier-score-placement', provisional
              ? `当前 ${item.voters} 票，未满 ${ranking.MINIMUM_TIER_VOTERS} 票，仅作暂定；满票后按真实均分分档。`
              : `已满 ${ranking.MINIMUM_TIER_VOTERS} 票，按真实均分分档；排序分仅决定档内顺序。`));
            body.append(el('p', 'tier-score-explanation', `参考 ${ranking.PRIOR_VOTERS} 份中立分、每份 ${ranking.PRIORS[currentSource]} 分，不增加玩家票数。排序分 =（真实均分 × 票数 + ${ranking.PRIOR_VOTERS} × ${ranking.PRIORS[currentSource]}）÷（票数 + ${ranking.PRIOR_VOTERS}）。仅使用${sourceLabel}，不混合另一类投票。`));
            const link = el('a', 'primary-button', '查看角色完整资料'); link.href = `#character/${encodeURIComponent(item.id)}`;
            body.append(link); modal.element.append(body);
          });
          const text = el('span', 'tier-public-card-text'); text.append(el('strong', 'tier-public-score', `均分 ${item.average.toFixed(2)}`),
            el('span', 'tier-public-name', title), el('small', 'tier-public-counts', counts));
          text.hidden = !showDetails;
          publicCards.push({card, text}); card.append(portrait, text); slots.append(card);
        });
        if (!slots.children.length) slots.append(el('span', 'tier-placeholder', provisional ? '暂无暂定角色' : '暂无角色'));
        if (!provisional) board.append(row);
      });
      results.replaceChildren(board, provisionalSection);
      publicSummary.textContent = items.length ? `${sourceLabel} · ${elementFilter ? `${elementFilter}属性榜` : '总榜'} · ${items.length} 位角色（已定级 ${items.length - provisionalCount} · 暂定 ${provisionalCount}）；点击头像查看均分与人数。`
        : `${sourceLabel} · ${elementFilter ? `${elementFilter}属性` : '目前'}还没有已汇总的玩家投票；未评分角色不入此榜。`;
      updated.textContent = publishedTime(value);
      publicStatus.textContent = items.length ? '' : '暂无已汇总投票'; publicStatus.hidden = Boolean(items.length);
    }
    async function loadPublic() {
      const ticket = ++revision; cached = undefined; refresh.disabled = true; results.replaceChildren();
      publicSummary.textContent = ''; updated.textContent = '';
      publicStatus.hidden = false; publicStatus.textContent = '正在载入大家排行…';
      if (!C?.client || !/^https?:$/.test(window.location?.protocol)) {
        publicStatus.textContent = '离线版无法读取大家排行，请前往在线网站查看。'; refresh.disabled = true; return;
      }
      try {
        const value = publicRecord(await C.client.request('/tier-rankings'));
        if (ticket === revision && view === 'community' && element.isConnected) {cached = value; renderPublic(value);}
      } catch (error) {
        if (ticket === revision && view === 'community' && element.isConnected) publicStatus.textContent = `${message(error)} 可在“说明”中点击“刷新”重试。`;
      } finally {if (ticket === revision) refresh.disabled = false;}
    }
    function setView(next) {
      const changed = view !== next; view = next === 'community' ? 'community' : 'mine';
      const mine = view === 'mine'; mineHost.hidden = !mine; submitBar.hidden = !mine; dynamicHost.hidden = mine;
      detailToggle.hidden = mine; help.hidden = mine; helpBody.hidden = mine || !help.open;
      [mineTab, publicTab].forEach((tab, index) => {tab.setAttribute('aria-selected', String(mine === !index)); tab.tabIndex = mine === !index ? 0 : -1;});
      onViewChange(view);
      if (mine) {revision++; refreshState(); return;}
      if (!portraits) portraits = window.WFCatalogAvatars.create({host: avatarHost, catalog: dynamicHost, characters, ui, label: '大家排行角色头像'});
      if (cached && !cached.stale && Date.parse(cached.nextRefreshAt) > Date.now()) renderPublic(cached);
      else if (changed || !results.children.length) loadPublic();
    }
    async function openSubmit() {
      if (dialogOpen || !online()) return;
      const rows = state.getRows(), count = Object.values(rows).reduce((total, ids) => total + ids.length, 0);
      const modal = C.dialog(count ? '提交我的排行' : '撤回自己的手排票', ui), dialog = modal.element;
      dialogOpen = true; refreshState();
      dialog.append(el('p', 'tier-submit-preview', count ? `将提交当前 ${count} 位角色的位置。未摆放的角色不计票。` : '当前排行为空，提交后会撤回你之前全部手排票。'),
        el('p', 'tier-submit-policy', '每天可提交一次（北京时间换日）。本次提交会替换自己的整份旧排行，每位玩家对每个角色只占一票。提交立即保存，公共榜每日汇总，次日显示。'));
      const notice = el('p', 'tier-submit-notice', '正在确认今日提交状态…'); notice.setAttribute('role', 'status');
      const verification = el('div', 'community-verification'), confirm = el('button', 'primary-button', count ? '验证后确认提交' : '验证后确认撤回'); confirm.type = 'button';
      const retry = el('button', 'secondary-button', '重新连接排行服务'); retry.type = 'button'; retry.hidden = true;
      dialog.append(notice, verification, confirm, retry);
      let closed = false, busy = false, completed = false, ready = false, challenge, personal;
      const sync = () => {confirm.disabled = !ready || busy || completed || Boolean(personal?.submittedToday);};
      sync(); modal.cleanup(() => {closed = true; challenge?.destroy(); dialogOpen = false; refreshState();});
      async function connect() {
        challenge?.destroy(); challenge = undefined; verification.replaceChildren();
        ready = false; sync(); retry.hidden = true; notice.textContent = '正在确认今日提交状态…';
        try {
          personal = personalRecord(await C.client.request('/tier-rankings/me')); if (closed) return;
          submitted = personal; refreshState();
          if (personal.submittedToday) {notice.textContent = `今天已提交过排行。${nextTime(personal)}`; completed = true; sync(); return;}
          const config = await C.client.config(); if (closed) return;
          challenge?.destroy(); verification.replaceChildren();
          challenge = C.challenge(verification, config, personal.challengeAction, ui, valid => {ready = valid; sync();});
          notice.textContent = '请完成验证，再确认提交。';
        } catch (error) {if (!closed) {notice.textContent = message(error); retry.hidden = false;}}
      }
      retry.addEventListener('click', connect);
      confirm.addEventListener('click', async () => {
        if (closed || busy || completed || personal?.submittedToday) return;
        const turnstileToken = challenge?.take(); if (!turnstileToken) return;
        busy = true; sync(); notice.textContent = '正在提交排行…';
        try {
          const value = personalRecord(await C.client.request('/tier-rankings', {rows, turnstileToken}));
          if (!value.submittedToday || value.rankedCharacters !== count) throw new Error('服务端尚未确认本次排行，请重新连接核实。');
          submitted = value; completed = true;
          if (!closed) {notice.textContent = `${count ? '排行已保存，次日计入大家排行。' : '已撤回之前的手排票，公共榜次日更新。'}${nextTime(value)}`; verification.hidden = true;}
        } catch (error) {
          if (error?.code === 'already_ranked' || error?.code === 'daily_limit') {
            completed = true;
            try {submitted = personalRecord(error.data);} catch { /* Reopening checks the authoritative daily state. */ }
            if (!closed) {notice.textContent = `今天已提交过排行。${submitted ? nextTime(submitted) : '请明天（北京时间）再试。'}`; verification.hidden = true;}
          } else if (!closed) {notice.textContent = message(error); retry.hidden = false;}
        } finally {busy = false; refreshState(); if (!closed) {challenge?.reset(); ready = false; sync();}}
      });
      connect();
    }
    submit.addEventListener('click', openSubmit); refresh.addEventListener('click', loadPublic); setView(initialView === 'mine' ? 'mine' : 'community');
    return {element, mineHost, refreshState, setView, destroy};
  }
  window.WFTierListCommunity = {create};
})();
