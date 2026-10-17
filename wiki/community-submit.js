/* Administrator-maintained recommendations; visitors can browse and like. */
(() => {
  'use strict';
  const C = window.WFCommunity;
  C.openSubmit = async ({team: input, title: initialTitle = '', data, ui}) => {
    const {el} = ui, team = C.teamCopy(input);
    const modal = C.dialog('管理员保存队伍', ui), host = modal.element;
    let closed = false;
    modal.cleanup(() => {closed = true;});
    const gate = el('p', 'community-status', '正在检查管理员登录…'); gate.setAttribute('role', 'status'); host.append(gate);
    const loginLink = (target) => {const link = el('a', 'text-button', '前往管理员登录'); link.href = '#community/admin'; target.append(link);};
    try {
      const me = await C.client.request('/admin/me');
      if (closed) return;
      if (!me.id) {gate.textContent = '配队大全由管理员维护，登录后可以收录和修改队伍。'; loginLink(gate); return;}
    } catch (error) {if (!closed) {gate.textContent = C.message(error); loginLink(gate);} return;}
    gate.remove();
    if (C.board) host.append(C.board(team, data, ui));
    const form = el('form', 'community-form'), status = el('p', 'community-status'); status.setAttribute('role', 'status');
    const field = (label, tag, maxLength, value = '') => {
      const wrap = el('label', 'community-field', label), control = el(tag);
      control.maxLength = maxLength; control.value = value; wrap.append(control); form.append(wrap); return control;
    };
    const title = field('队伍名称', 'input', 80, initialTitle.slice(0, 80)); title.required = true;
    const author = field('作者署名', 'input', 40); author.required = true;
    const visibility = field('保存位置', 'select', 0); visibility.setAttribute('aria-label', '保存位置');
    [['private','我的空间（私有）'],['public','配队大全（公开）']].forEach(([value,label]) => {
      const option = el('option', '', label); option.value = value; visibility.append(option);
    });
    visibility.value = 'private';
    const notes = field('用途、操作要点与替换建议（选填）', 'textarea', 2000); notes.rows = 4;
    const category = field('配队分类', 'select', 0); category.required = true; category.setAttribute('aria-label', '配队分类');
    const categoryPrompt = el('option', '', '请选择配队分类'); categoryPrompt.value = ''; category.append(categoryPrompt);
    C.teamCategories.forEach((value) => {const option = el('option', '', value); option.value = value; category.append(option);});
    const section = field('玩法分区', 'select', 0); section.setAttribute('aria-label', '玩法分区');
    Object.entries(C.teamSections).forEach(([value,label]) => {const option = el('option', '', label); option.value = value; section.append(option);});
    section.value = '';
    const leader = (data.characters || []).find((item) => item.id === team.main[0]);
    const element = field('队伍属性', 'select', 0);
    const auto = el('option', '', `自动：队长${leader ? ` ${leader.name} · ${leader.element}` : '尚未选择'}`); auto.value = 'auto'; element.append(auto);
    const damage = el('fieldset', 'community-damage-options'); damage.append(el('legend', '', '伤害类型（至少选一项，可多选）'));
    const checks = Object.entries(C.damageTypes).map(([value, label]) => {
      const wrap = el('label', 'community-check'), input = el('input'); input.type = 'checkbox'; input.value = value;
      wrap.append(input, el('span', '', label)); damage.append(wrap); return input;
    });
    const submit = el('button', 'primary-button', '保存队伍'); submit.type = 'submit'; submit.disabled = true;
    const retry = el('button', 'secondary-button', '重新连接社区'); retry.type = 'button'; retry.hidden = true;
    form.append(damage, el('p', 'community-save-help', '我的空间仅本人及站长、副站长可见；选择配队大全则公开展示。保存后可单独公开游戏队伍码。'), status, submit, retry);
    host.append(form);
    let busy = false, ready = false, saved = false;
    const update = (valid) => {ready = valid; submit.disabled = !ready || busy || saved;};
    const lockFields = (locked) => {for (const tag of ['input','select','textarea']) form.querySelectorAll(tag).forEach((node) => {node.disabled = locked;});};
    const adminLink = (label, item) => {
      const link = el('a', 'text-button', label); link.href = '#community/admin';
      link.addEventListener('click', () => {C.adminTarget = {id:item.id,scope:item.visibility === 'private' ? 'mine' : 'all'};}); return link;
    };
    async function connect() {
      retry.hidden = true; status.textContent = '正在连接配队社区…';
      try {
        const config = await C.client.config(); if (closed) return;
        element.replaceChildren(auto);
        (config.elements || []).forEach((value) => {const option = el('option', '', C.elementLabel(value)); option.value = value; element.append(option);});
        status.textContent = C.teamError(team, data);
        update(true);
      } catch (error) {if (!closed) {status.textContent = C.message(error); retry.hidden = false;}}
    }
    retry.addEventListener('click', connect);
    form.addEventListener('submit', async (event) => {
      event.preventDefault(); if (busy || saved) return;
      const damageTypes = checks.filter((check) => check.checked).map((check) => check.value);
      const invalid = C.teamError(team, data) || (!title.value.trim() ? '请填写队伍名称。' : '')
        || (!author.value.trim() ? '请填写作者署名。' : '') || (!C.teamCategories.includes(category.value) ? '请选择配队分类。' : '')
        || (!Object.hasOwn(C.teamSections, section.value) ? '请选择有效的玩法分区。' : '')
        || (!['public','private'].includes(visibility.value) ? '请选择有效的保存位置。' : '')
        || (!damageTypes.length ? '请至少选择一种伤害类型。' : '');
      if (invalid) {status.textContent = invalid; return;}
      if (!ready) {status.textContent = '请先连接配队社区。'; return;}
      busy = true; lockFields(true); update(false); status.textContent = '正在保存…';
      try {
        const result = await C.client.request('/admin/teams', {team, title: title.value.trim(), author: author.value.trim(),
          notes: notes.value.trim(), category: category.value, section: section.value, visibility:visibility.value, element: element.value, damageTypes});
        if (closed) return;
        const item = result.team;
        if (!item?.id || !Number.isSafeInteger(Number(item.revision)) || Number(item.revision) < 1 || !['public','private'].includes(item.visibility)) {
          throw new Error('服务端未返回完整的保存结果，请到管理后台核实，避免重复保存。');
        }
        saved = true;
        if (item.visibility === 'private') {
          status.replaceChildren(el('span', '', '已保存到我的空间，仅本人及站长、副站长可见。 '), adminLink('查看我的队伍',item));
        } else if (item.status === 'approved') {
          status.replaceChildren(el('span', '', '收录成功，已公开。 '));
          const link = el('a', 'text-button', '查看推荐盘'); link.href = `#community/${encodeURIComponent(item.id)}`; status.append(link);
        } else status.textContent = '队伍已保存，公开后可在配队大全查看。';
        const actions = el('div', 'community-saved-actions'); actions.append(adminLink('继续编辑 / 管理',item));
        const codes = window.WFCommunityGameCodes?.controls(item,ui,(...args) => C.client.request(...args));
        if (codes) {codes.open = true; actions.append(codes);} host.append(actions);
      } catch (error) {
        if (closed) return;
        status.textContent = C.message(error);
        if (error.code === 'duplicate' && error.data?.existingId) {
          if (error.data.status === 'hidden') status.textContent = '相同阵容已保存，暂不公开；不需要重复保存。';
          status.append(adminLink(' 在后台查看已保存的队伍',{id:error.data.existingId}));
        } else if (error.code === 'duplicate') status.textContent = '相同阵容已保存，暂不公开；不需要重复收录。';
        if (error.status === 401 || error.status === 403) loginLink(status);
      } finally {busy = false; if (!closed) {lockFields(saved); update(true);}}
    });
    connect();
  };
  C.openLike = async (item, ui, onLiked) => {
    const {el} = ui, modal = C.dialog(`为「${item.title}」点赞`, ui), host = modal.element;
    const notice = el('p', 'community-status', '同一盘、同一访客每天可点赞一次，以北京时间换日。'); notice.setAttribute('role', 'status');
    const verification = el('div', 'community-verification');
    const button = el('button', 'primary-button', '确认点赞'); button.type = 'button'; button.disabled = true;
    const retry = el('button', 'secondary-button', '重新连接社区'); retry.type = 'button'; retry.hidden = true;
    host.append(notice, verification, button, retry);
    let challenge, busy = false, closed = false, completed = false;
    modal.cleanup(() => {closed = true; challenge?.destroy();});
    async function connect() {
      retry.hidden = true;
      try {
        const config = await C.client.config(); if (closed) return;
        challenge?.destroy(); verification.replaceChildren();
        challenge = C.challenge(verification, config, 'like_team', ui, (valid) => {button.disabled = !valid || busy || completed;});
      } catch (error) {if (!closed) {notice.textContent = C.message(error); retry.hidden = false;}}
    }
    retry.addEventListener('click', connect);
    button.addEventListener('click', async () => {
      if (busy || completed) return;
      const turnstileToken = challenge?.take(); if (!turnstileToken) return;
      busy = true; button.disabled = true;
      try {
        const result = await C.client.request(`/teams/${encodeURIComponent(item.id)}/like`, {turnstileToken});
        completed = true; onLiked(result); if (!closed) notice.textContent = '点赞成功，谢谢你的推荐。';
      } catch (error) {
        if (error.code === 'already_liked') {completed = true; onLiked(error.data);}
        if (!closed) notice.textContent = C.message(error);
      } finally {
        busy = false; if (!closed) {challenge?.reset(); button.disabled = true; if (completed) verification.hidden = true;}
      }
    });
    connect();
  };
})();
