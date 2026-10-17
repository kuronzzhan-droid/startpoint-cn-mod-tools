/* Shared announcement editor with revision checks and the existing navigation guard. */
(() => {
  'use strict';
  const C = window.WFCommunity;
  C.announcementEditor = ({ui, request}) => {
    const {el} = ui, box = el('details', 'community-announcement-editor');
    box.append(el('summary', '', '编辑配队公告'));
    const form = el('form'), field = el('label', 'admin-field'); field.append(el('span', '', '公告内容'));
    const input = el('textarea'); input.rows = 3; input.maxLength = 1000;
    input.placeholder = '最多 500 字，支持换行；留空保存可撤下公告'; input.setAttribute('aria-label', '公告内容');
    input.disabled = true; field.append(input);
    const status = el('p', 'community-status'); status.setAttribute('role', 'status');
    const save = el('button', 'primary-button', '保存公告'); save.type = 'submit'; save.disabled = true;
    const reload = el('button', 'secondary-button', '重新读取'); reload.type = 'button';
    const actions = el('div', 'community-actions'); actions.append(save, reload);
    form.append(field, el('p', 'muted community-announcement-help', '所有管理员均可编辑。保存后公开展示，最多约 30 秒更新。'), status, actions); box.append(form);
    let revision = null, saved = '', busy = false, conflict = false, confirmation;
    const normalized = () => input.value.replace(/\r\n?/g, '\n').trim().normalize('NFC');
    box.isDirty = () => revision !== null && normalized() !== saved;
    box.isBusy = () => busy || Boolean(confirmation);
    box.canClose = () => {
      if (busy) {status.textContent = '公告正在读取或保存，请稍候。'; return Promise.resolve(false);}
      if (confirmation) return confirmation;
      if (!box.isDirty()) return Promise.resolve(true);
      const snapshot = input.value;
      if (!window.WFCommunityAdminConfirm) {status.textContent = '公告尚未保存，请先保存再离开。'; return Promise.resolve(false);}
      confirmation = Promise.resolve(window.WFCommunityAdminConfirm.ask('公告还有未保存的修改，是否放弃？',
        {title:'公告尚未保存',confirmLabel:'放弃修改',cancelLabel:'继续编辑'}))
        .then(accepted => Boolean(accepted) && !busy && input.value === snapshot).finally(() => {confirmation = null;});
      return confirmation;
    };
    function paint() {input.disabled = busy || revision === null; save.disabled = busy || revision === null || conflict; reload.disabled = busy;}
    function accept(value) {
      if (typeof value?.text !== 'string' || !Number.isSafeInteger(value.revision) || value.revision < 0) throw new Error('公告返回格式异常，请重新读取。');
      revision = value.revision; saved = value.text; input.value = saved; conflict = false;
    }
    async function load() {
      if (busy || !await box.canClose() || busy || !box.isConnected) return;
      busy = true; paint(); status.textContent = '正在读取公告…';
      try {const value = await request('/admin/announcement'); if (box.isConnected) {accept(value); status.textContent = value.text ? '已读取当前公告。' : '暂无公告，填写后保存即可公开。';}}
      catch (error) {if (box.isConnected) status.textContent = C.message(error);}
      finally {busy = false; if (box.isConnected) paint();}
    }
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (busy || confirmation || revision === null || conflict) return;
      const text = normalized();
      if ([...text].length > 500) {status.textContent = '公告不能超过 500 字。'; return;}
      const expectedRevision = revision; busy = true; paint(); status.textContent = '正在保存公告…';
      try {
        const value = await request('/admin/announcement', {text, expectedRevision}, 'PATCH');
        if (!box.isConnected) return;
        if (value?.revision !== expectedRevision + 1 || value.text !== text) throw new Error('公告保存回执不一致，请重新读取核实。输入仍保留。');
        accept(value); status.textContent = text ? '公告已保存，最多约 30 秒后公开更新。' : '公告已撤下，最多约 30 秒后生效。';
      } catch (error) {
        if (!box.isConnected) return;
        conflict = error.code === 'edit_conflict';
        status.textContent = conflict ? '其他管理员已更新公告。你的输入仍保留，请重新读取后核对再保存。' : C.message(error);
      } finally {busy = false; if (box.isConnected) paint();}
    });
    box.addEventListener('toggle', () => {if (box.open && revision === null) load();});
    reload.addEventListener('click', load); return box;
  };
})();
