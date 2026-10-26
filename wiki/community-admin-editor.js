/* An editor owns its saved snapshot; game codes never publish unsaved form data. */
(() => {
  'use strict';
  window.WFCommunityAdminEditor = {create({item, identity, config, data, ui, request, onSaved, onClose, onReload}) {
    const C = window.WFCommunity, {el} = ui, form = el('form', 'admin-edit-form');
    const revision = Number(item.revision), editable = [];
    const warning = el('p', 'admin-edit-status'); warning.setAttribute('role', 'status');
    const dirtyStatus = el('p', 'admin-dirty-status'); dirtyStatus.setAttribute('role', 'status');
    const button = (label, action) => {const node = el('button', 'secondary-button', label); node.type = 'button'; node.addEventListener('click', action); return node;};
    const field = (label, input) => {input.setAttribute('aria-label', label); const node = el('label', 'admin-field'); node.append(el('span', '', label), input); return node;};
    function input(value, limit, multiline = false) {
      const node = el(multiline ? 'textarea' : 'input'); node.value = String(value || ''); node.maxLength = limit;
      if (multiline) node.rows = 2; else node.type = 'text'; editable.push(node); return node;
    }
    function select(values, value) {
      const node = el('select'); values.forEach(([key,label]) => {const option = el('option', '', label); option.value = key; node.append(option);});
      node.value = value; editable.push(node); return node;
    }
    const title = input(item.title,80), author = input(item.author,40), notes = input(item.notes,2000,true); title.required = true;
    const element = select([['auto','根据队长属性自动判断'],['universal','宇宙'],
      ...(config.elements || ['火','水','雷','风','光','暗','无']).filter((value) => value !== 'universal').map((value) => [value,value])], item.element || 'auto');
    const status = select([['approved','使用中'],['hidden','回收站 / 已停用']], item.status === 'hidden' ? 'hidden' : 'approved');
    const category = select([...(item.category ? [] : [['','未分类（历史队伍）']]), ...C.teamCategories.map((value) => [value,value])], item.category || '');
    const section = select(Object.entries(C.teamSections), item.section || '');
    const canPrivatize = ['owner','deputy'].includes(identity?.role) || Boolean(item.createdBy && item.createdBy === identity?.id);
    const privateLabel = item.createdBy === identity?.id ? '我的空间（私有）' : item.createdBy ? '创建者的私有空间' : '私有（仅站长及副站长）';
    const visibility = select([['public','配队大全（公开）'], ...(canPrivatize || item.visibility === 'private' ? [['private',privateLabel]] : [])], item.visibility || 'public');
    const heading = el('div', 'admin-edit-heading'); heading.append(el('h2', '', `编辑：${item.title}`), button('关闭编辑', async () => {if (await form.canClose() && form.isConnected) onClose();}));
    const teamPicker = window.WFCommunityTeamPicker.create({team:C.teamCopy(item.team),data,ui,onChange:() => update()});
    const names = el('div', 'admin-edit-names'); names.append(field('队伍标题', title), field('投稿者署名', author));
    form.append(heading, el('p', 'admin-version', `当前版本 ${revision} · 保存时自动检查版本`), teamPicker.element, names);
    const meta = el('div', 'admin-edit-meta'); meta.append(field('属性分类', element), field('展示状态', status),
      field('配队分类', category), field('玩法分区', section), field('保存位置', visibility)); form.append(meta);
    if (!canPrivatize && item.visibility !== 'private') form.append(el('p', 'muted', '只有创建者、站长或副站长可以将这支队伍移入私有空间。'));
    const damages = el('fieldset', 'admin-damage'); damages.append(el('legend', '', '伤害分类（至少一项）'));
    const checks = Object.entries(C.damageTypes).map(([value,label]) => {
      const check = el('input'); check.type = 'checkbox'; check.value = value; check.checked = (item.damageTypes || []).includes(value);
      editable.push(check); damages.append(field(label,check)); return check;
    });
    form.append(damages, field('队伍说明', notes));
    function values() {
      const currentTeam = teamPicker.getTeam();
      return {title:title.value.trim(),author:author.value.trim(),notes:notes.value.trim(),team:currentTeam,element:element.value,
        category:category.value,section:section.value,visibility:visibility.value,status:status.value,
        damageTypes:checks.filter((check) => check.checked).map((check) => check.value)};
    }
    let saved = JSON.stringify(values()), busy = false, conflict = false, closeRequest;
    form.isDirty = () => JSON.stringify(values()) !== saved;
    form.isBusy = () => busy || Boolean(closeRequest) || Boolean(manager?.isBusy?.());
    form.canClose = () => {
      if (closeRequest) return closeRequest;
      if (form.isBusy()) {warning.textContent = '正在保存或处理队伍码，请稍候再关闭编辑。'; return Promise.resolve(false);}
      if (!form.isDirty()) return Promise.resolve(true);
      if (!window.WFCommunityAdminConfirm) {warning.textContent = '确认模块未加载，修改仍保留，请稍后重试。'; return Promise.resolve(false);}
      const snapshot = JSON.stringify(values());
      closeRequest = Promise.resolve(window.WFCommunityAdminConfirm.ask('还有未保存的修改，放弃后将无法恢复。',
        {title:'放弃未保存的修改？',confirmLabel:'放弃修改',cancelLabel:'继续编辑'}))
        .then(accepted => Boolean(accepted) && !busy && snapshot === JSON.stringify(values()))
        .finally(() => {closeRequest = null;});
      return closeRequest;
    };
    const blocked = () => conflict ? '版本冲突，请重新加载队伍后再公开队伍码。' : busy ? '正在保存，请稍候。'
      : form.isDirty() ? '还有未保存的修改，请先保存后再公开队伍码。' : '';
    const manager = window.WFCommunityGameCodes?.controls(item,ui,request,{mutationBlocked:blocked,
      onBusyChange:() => {save.disabled = busy || conflict || Boolean(manager?.isBusy?.());}});
    function update() {
      dirtyStatus.textContent = blocked(); manager?.refreshAvailability();
    }
    form.addEventListener('input', update); form.addEventListener('change', update);
    form.append(dirtyStatus,warning);
    const save = el('button', 'primary-button', '保存修改'); save.type = 'submit';
    const reload = button('重新加载列表', onReload); reload.hidden = true;
    const actions = el('div','admin-edit-actions'); actions.append(save,reload); form.append(actions);
    if (manager) form.append(manager);
    update();
    form.addEventListener('submit', async (event) => {
      event.preventDefault(); if (busy || conflict) return;
      if (closeRequest || manager?.isBusy?.()) {warning.textContent = '请先完成当前确认或队伍码操作，再保存修改。'; return;}
      const next = values(), invalid = !next.title ? '请填写队伍标题。' : !next.damageTypes.length ? '请至少选择一种伤害分类。'
        : (!C.teamCategories.includes(next.category) && (item.category || next.category)) ? '请选择有效的配队分类。'
        : !Object.hasOwn(C.teamSections,next.section) ? '请选择有效的玩法分区。'
        : !['public','private'].includes(next.visibility) ? '请选择有效的保存位置。'
        : next.visibility === 'private' && item.visibility !== 'private' && !canPrivatize ? '只有创建者、站长或副站长可以设为私有。' : C.teamError(next.team,data);
      if (invalid) {warning.textContent = invalid; return;}
      busy = true; save.disabled = true; teamPicker.setDisabled(true); editable.forEach((node) => {node.disabled = true;}); update(); warning.textContent = '正在保存…';
      try {
        const result = await request(`/admin/teams/${encodeURIComponent(item.id)}`, {expectedRevision:revision,...next});
        if (result.team?.id !== item.id || !Number.isSafeInteger(Number(result.team.revision)) || Number(result.team.revision) <= revision) {
          throw new Error('服务端未返回更新版本，请重新加载列表核实。');
        }
        saved = JSON.stringify(next);
        if (form.isConnected) await onSaved(result.team);
      } catch (error) {
        if (!form.isConnected) return;
        if (error.code === 'edit_conflict') {
          conflict = true; reload.hidden = false;
          warning.textContent = '这张盘已被其他管理员修改。你的输入仍保留，保存已暂停；请重新加载列表后再编辑，避免覆盖他人的修改。';
        } else warning.textContent = C.message(error);
      } finally {busy = false; save.disabled = conflict; teamPicker.setDisabled(false); editable.forEach((node) => {node.disabled = false;}); update();}
    });
    return form;
  }};
})();
