/* Sponsor drafts stay local until saved; external images load only on explicit preview. */
(() => {
  'use strict';
  const C = window.WFCommunity, keys = ['enabled', 'title', 'description', 'imageUrl', 'targetUrl'];
  const normalize = value => value.replace(/\r\n?/g, '\n').trim().normalize('NFC');
  function invalid(value) {
    if (!value || typeof value.enabled !== 'boolean' || keys.slice(1).some(key => typeof value[key] !== 'string')) return '广告返回格式异常，请重新读取。';
    if ([...value.title].length > 60) return '广告标题不能超过 60 字。';
    if ([...value.description].length > 160) return '简短说明不能超过 160 字。';
    if (/[\u0000-\u001f\u007f]/u.test(value.title + value.description)) return '广告标题和简短说明不能换行或包含控制字符。';
    if (value.targetUrl && !window.WFSponsor?.safeUrl(value.targetUrl)) return '广告跳转链接须为完整 HTTPS 公网地址，不含账号密码。';
    if (value.imageUrl && !window.WFSponsor?.safeUrl(value.imageUrl, true)) return '广告图片地址须为 HTTPS 公网 PNG、JPG、WebP 地址或站内图片地址。';
    if (value.enabled && (!value.title || !value.targetUrl)) return '启用广告前，请填写广告标题和 HTTPS 跳转链接。';
    return '';
  }
  C.sponsorEditor = ({ui, request}) => {
    const {el} = ui, box = el('details', 'sponsor-editor'), form = el('form', 'sponsor-editor-form'), fields = {};
    box.append(el('summary', '', '赞助广告设置')); box.open = false;
    function field(key, label, type, maxLength) {
      const wrapper = el('label', 'admin-field'), input = el(type === 'textarea' ? 'textarea' : 'input');
      input.setAttribute('aria-label', label); if (type !== 'textarea') input.type = type;
      if (maxLength) input.maxLength = maxLength * 2;
      if (type === 'textarea') input.rows = 2;
      input.disabled = true; fields[key] = input;
      wrapper.append(el('span', '', label), input); form.append(wrapper);
      input.addEventListener(type === 'checkbox' ? 'change' : 'input', () => preview.replaceChildren());
      return input;
    }
    field('enabled', '启用赞助广告', 'checkbox'); field('title', '广告标题', 'text', 60);
    field('description', '简短说明', 'text', 160);
    field('imageUrl', '广告图片地址', 'text').placeholder = '可留空；填写完整 HTTPS 图片地址';
    field('targetUrl', '广告跳转链接', 'text').placeholder = 'https://';
    const status = el('p', 'community-status'); status.setAttribute('role', 'status');
    const preview = el('div', 'sponsor-editor-preview'), actions = el('div', 'community-actions');
    function button(label, type, className) {const node = el('button', className, label); node.type = type; actions.append(node); return node;}
    const show = button('预览广告', 'button', 'secondary-button'), save = button('保存广告', 'submit', 'primary-button');
    const reload = button('重新读取', 'button', 'secondary-button');
    form.append(el('p', 'muted sponsor-editor-help', '仅站长、副站长可编辑。不记录广告点击或曝光。访客配置缓存 30 分钟；缓存更新后新开或重新载入页面可查看新广告。'),
      status, actions, preview); box.append(form);
    let revision = null, saved, busy = false, conflict = false, confirmation;
    const draft = () => {
      const value = Object.fromEntries(keys.map(key => [key, key === 'enabled' ? Boolean(fields[key].checked)
        : key.endsWith('Url') ? fields[key].value.trim() : normalize(fields[key].value)]));
      return window.WFSponsor?.normalize(value) || value;
    };
    const fingerprint = value => JSON.stringify(keys.map(key => value[key]));
    const raw = () => JSON.stringify(keys.map(key => key === 'enabled' ? fields[key].checked : fields[key].value));
    box.isDirty = () => revision !== null && fingerprint(draft()) !== fingerprint(saved);
    box.isBusy = () => busy || Boolean(confirmation);
    box.canClose = () => {
      if (busy) {status.textContent = '广告正在读取或保存，请稍候。'; return Promise.resolve(false);}
      if (confirmation) return confirmation;
      if (!box.isDirty()) return Promise.resolve(true);
      if (!window.WFCommunityAdminConfirm) {status.textContent = '广告尚未保存，请先保存再离开。'; return Promise.resolve(false);}
      const snapshot = raw();
      confirmation = Promise.resolve().then(() => window.WFCommunityAdminConfirm.ask('广告还有未保存的修改，是否放弃？',
        {title:'广告尚未保存',confirmLabel:'放弃修改',cancelLabel:'继续编辑'}))
        .then(accepted => Boolean(accepted) && !busy && raw() === snapshot)
        .catch(error => {if (box.isConnected) status.textContent = C.message(error); return false;})
        .finally(() => {confirmation = null; if (box.isConnected) paint();});
      paint(); return confirmation;
    };
    function paint() {
      for (const input of Object.values(fields)) input.disabled = busy || revision === null;
      show.disabled = busy || Boolean(confirmation) || revision === null;
      save.disabled = show.disabled || conflict; reload.disabled = busy || Boolean(confirmation);
    }
    function checked(value) {
      const error = invalid(value);
      if (error || !Number.isSafeInteger(value.revision) || value.revision < 0 ||
          !(value.revision === 0 ? value.updatedAt === null : Number.isSafeInteger(value.updatedAt) && value.updatedAt >= 0)) {
        throw new Error(error || '广告返回格式异常，请重新读取。');
      }
      return Object.fromEntries(keys.map(key => [key, value[key]]));
    }
    function accept(value, next) {
      revision = value.revision; saved = next; conflict = false;
      for (const key of keys) {if (key === 'enabled') fields[key].checked = next[key]; else fields[key].value = next[key];}
      preview.replaceChildren();
    }
    async function load() {
      if (busy || !await box.canClose() || busy || !box.isConnected) return;
      busy = true; paint(); preview.replaceChildren(); status.textContent = '正在读取广告设置…';
      try {
        const value = await request('/admin/sponsorship');
        if (box.isConnected) {accept(value, checked(value)); status.textContent = value.enabled ? '已读取当前广告设置。' : '广告已关闭，填写素材后可预览并启用。';}
      } catch (error) {if (box.isConnected) status.textContent = C.message(error);}
      finally {busy = false; if (box.isConnected) paint();}
    }
    show.addEventListener('click', () => {
      if (busy || confirmation || revision === null) return;
      preview.replaceChildren(); const value = draft(), error = invalid(value);
      if (error) {status.textContent = error; return;}
      try {
        const card = window.WFSponsor?.createCard(document, value, {preview:true});
        if (card) {preview.append(card); status.textContent = '仅预览当前输入；修改需点击“保存广告”后生效。';}
        else status.textContent = '请先填写广告标题和完整 HTTPS 跳转链接，再预览广告。';
      } catch {status.textContent = '广告预览暂不可用，输入仍保留。';}
    });
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (busy || confirmation || revision === null || conflict) return;
      const value = draft(), error = invalid(value);
      if (error) {status.textContent = error; return;}
      const expectedRevision = revision; busy = true; paint(); preview.replaceChildren(); status.textContent = '正在保存广告…';
      try {
        const result = await request('/admin/sponsorship', {...value, expectedRevision}, 'PATCH');
        if (!box.isConnected) return;
        const next = checked(result);
        if (result.revision !== expectedRevision + 1 || fingerprint(next) !== fingerprint(value)) throw new Error('广告保存回执不一致，请重新读取核实。输入仍保留。');
        accept(result, next); status.textContent = value.enabled ? '广告已保存，访客配置缓存最多约 30 分钟更新。' : '广告已关闭，访客配置缓存最多约 30 分钟更新。';
      } catch (error) {
        if (!box.isConnected) return;
        conflict = error.code === 'edit_conflict' || error.status === 409;
        status.textContent = conflict ? '其他管理员已更新广告。你的输入仍保留，请重新读取后核对再保存。' : C.message(error);
      } finally {busy = false; if (box.isConnected) paint();}
    });
    box.addEventListener('toggle', () => {if (!box.open) preview.replaceChildren(); else if (revision === null) return load();});
    reload.addEventListener('click', load); paint(); return box;
  };
})();
