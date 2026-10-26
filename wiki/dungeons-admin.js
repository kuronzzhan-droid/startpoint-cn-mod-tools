/* Guide edits are staged locally; only authenticated, revision-checked saves publish them. */
(() => {
  'use strict';
  const maxImages = 12, maxTeams = 30, maxBytes = 512 * 1024, maxText = 30000;
  const request = (...args) => window.WFCommunity.client.request(...args);
  const isConflict = (error) => error?.status === 409 && error?.code === 'edit_conflict';
  const errorText = (error) => isConflict(error) ? '内容已被其他管理员修改，你的草稿已保留。请读取最新版本后合并。'
    : error?.status === 401 || error?.status === 403 ? '管理员登录已失效或没有权限，请重新登录；草稿仍保留。'
    : window.WFCommunity?.message(error) || '操作失败，请重试；草稿仍保留。';
  async function shrink(file) {
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file?.type)) throw new Error('请选择 PNG、JPEG 或 WebP 图片。');
    if (!file.size || file.size > 20 * 1024 * 1024) throw new Error('原图需小于 20 MB。');
    const url = URL.createObjectURL(file), img = new Image();
    try {
      await new Promise((resolve, reject) => {img.onload = resolve; img.onerror = () => reject(new Error('图片无法解码，请换一张图片。')); img.src = url;});
      if (!img.naturalWidth || !img.naturalHeight || img.naturalWidth * img.naturalHeight > 40000000) throw new Error('图片尺寸过大，请先裁剪或缩小。');
      const scale = Math.min(1, 1600 / Math.max(img.naturalWidth, img.naturalHeight));
      const canvas = document.createElement('canvas'), context = canvas.getContext('2d');
      if (!context) throw new Error('当前浏览器不支持图片压缩，请更换浏览器重试。');
      canvas.width = Math.max(1, Math.round(img.naturalWidth * scale)); canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
      for (let pass = 0; pass < 5; pass++) {
        context.clearRect(0, 0, canvas.width, canvas.height); context.drawImage(img, 0, 0, canvas.width, canvas.height);
        for (const quality of [0.86, 0.7, 0.5]) {
          const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/webp', quality));
          if (blob && ['image/png','image/jpeg','image/webp'].includes(blob.type) && blob.size <= maxBytes) return blob;
        }
        canvas.width = Math.max(1, Math.round(canvas.width * 0.75)); canvas.height = Math.max(1, Math.round(canvas.height * 0.75));
      }
      throw new Error('图片仍超过 512 KB，请裁剪后再试。');
    } finally {URL.revokeObjectURL(url);}
  }
  async function upload(id, blob) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await window.fetch(`/api/community/admin/dungeons/${encodeURIComponent(id)}/images`, {
        method:'POST', credentials:'same-origin', signal:controller.signal,
        headers:{Accept:'application/json', 'Content-Type':blob.type}, body:blob,
      });
      const value = await response.json();
      if (!response.ok) throw Object.assign(new Error(value.message || '图片上传失败。'), {status:response.status, code:value.error, retryAfter:value.retryAfter});
      if (!value.image?.id || !value.image.previewUrl) throw new Error('未返回有效的图片信息，请重新检查。');
      return value.image;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('图片上传超时，请稍后重试。');
      throw error;
    } finally {clearTimeout(timer);}
  }
  function editor(host, item, result, data, ui, settings) {
    const {el} = ui, D = window.WFDungeons, base = `/admin/dungeons/${encodeURIComponent(item.id)}`;
    const form = el('form', 'dungeon-editor'), guide = result.guide || {};
    let revision = Number(guide.revision) || 0, busy = false, teamCursor = '', teamSerial = 0, teamsLoaded = false;
    const selectedTeams = new Set(guide.teamIds || []), selectedImages = new Set(guide.imageIds || []);
    const teams = new Map((result.teams || []).map((team) => [team.id, team]));
    const images = new Map([...(guide.images || []), ...(result.availableImages || [])].map((image) => [image.id, image]));
    const heading = el('div', 'dungeon-editor-heading'); heading.append(el('h2', '', '编辑攻略与推荐队伍'));
    if (item.scopeLabel) heading.append(el('p', 'muted', `${item.title}${item.scopeLabel === '通用攻略' ? ' · 通用攻略' : ''}；切换层数会保留此处未保存的草稿。`));
    const status = el('p', 'dungeon-status'); status.setAttribute('role', 'status');
    const text = el('textarea', 'dungeon-guide-input'); text.rows = 12; text.maxLength = maxText; text.value = guide.text || '';
    text.setAttribute('aria-label', '详细攻略'); text.placeholder = '写下适用难度、机制、操作顺序及注意事项…';
    const textField = el('label', 'dungeon-field'); textField.append(el('span', '', '详细攻略'), text);
    const count = el('span', 'muted dungeon-text-count');
    const updateCount = () => {count.textContent = `${text.value.length} / ${maxText} 字`;}; text.addEventListener('input', updateCount); updateCount();
    const teamSection = el('section', 'dungeon-edit-section'), chosenTeams = el('div', 'dungeon-selected-teams');
    const teamLibrary = el('details', 'dungeon-fold'), candidateList = el('div', 'dungeon-team-candidates');
    teamLibrary.append(el('summary', '', '从配队大全添加队伍'));
    const search = el('input'); search.type = 'search'; search.placeholder = '搜索已加载的公开队伍…'; search.setAttribute('aria-label', '查找可添加的队伍');
    const libraryStatus = el('p', 'muted'); libraryStatus.setAttribute('role', 'status');
    const more = D.button(ui, '加载队伍', () => loadTeams());
    teamLibrary.append(search, libraryStatus, candidateList, more);
    teamSection.append(el('h3', '', '推荐队伍'), el('p', 'muted', '最多 30 盘。移除只取消该副本的推荐，不删除原队伍。'), chosenTeams, teamLibrary);
    const imageSection = el('section', 'dungeon-edit-section'), imageList = el('div', 'dungeon-edit-images');
    const input = el('input'); input.type = 'file'; input.accept = 'image/png,image/jpeg,image/webp'; input.multiple = true;
    input.setAttribute('aria-label', '上传攻略图片');
    imageSection.append(el('h3', '', '攻略图片'), el('p', 'muted', '最多 12 张；上传时自动压缩。图片加入攻略并保存后才公开。'), input, imageList);
    const draftImages = el('details', 'dungeon-fold'), draftList = el('div', 'dungeon-draft-images');
    draftImages.append(el('summary', '', '未使用的已上传图片'), draftList); imageSection.append(draftImages);
    const conflict = el('div', 'dungeon-conflict'); conflict.hidden = true;
    const reload = D.button(ui, '读取最新版本供合并', async () => {
      reload.disabled = true;
      try {
        const latest = await request(base); if (!active()) return;
        const other = el('div', 'dungeon-latest-version');
        other.append(el('h3', '', `当前已保存版本 ${latest.guide.revision}`), el('p', 'dungeon-guide-text', latest.guide.text || '暂无攻略正文'),
          el('p', '', `推荐盘：${(latest.teams || []).map((team) => team.title).join(' / ') || '无'} · 图片 ${(latest.guide.imageIds || []).length} 张`));
        const accept = D.button(ui, '以最新版本继续编辑', () => {
          revision = latest.guide.revision; conflict.hidden = true; status.textContent = '已更新版本基准；请合并上方差异后再保存。你的草稿保持不变。';
        });
        other.append(el('p', 'muted', '下面的按钮保留你的草稿，不会自动覆盖或保存服务器内容。'), accept);
        conflict.replaceChildren(other); conflict.hidden = false;
      } catch (error) {if (active()) status.textContent = errorText(error);}
      finally {reload.disabled = false;}
    });
    const actions = el('div', 'dungeon-editor-actions'), save = el('button', 'primary-button', '保存攻略与推荐'); save.type = 'submit';
    actions.append(save, D.button(ui, '收起编辑（保留草稿）', () => {host.hidden = true; settings.onFold?.();}));
    form.append(heading, textField, count, teamSection, imageSection, conflict, status, actions); host.replaceChildren(form);
    const active = () => settings.current() && form.isConnected;
    function lock(value) {
      busy = value; form.querySelectorAll('input, textarea, button').forEach((node) => {node.disabled = value;});
      if (!value) {renderTeams(); renderImages();}
    }
    function renderTeams() {
      chosenTeams.replaceChildren();
      for (const id of selectedTeams) {
        const row = el('div', 'dungeon-choice-row'), team = teams.get(id);
        const title = el('a', '', team?.title || '已关联队伍（可能已隐藏）'); title.href = `#community/${encodeURIComponent(id)}`;
        const remove = D.button(ui, '移除', () => {if (!busy) {selectedTeams.delete(id); renderTeams();}}); remove.disabled = busy;
        row.append(title, remove); chosenTeams.append(row);
      }
      if (!selectedTeams.size) chosenTeams.append(el('p', 'muted', '尚未关联推荐盘。'));
      renderCandidates();
    }
    function renderCandidates() {
      const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean); candidateList.replaceChildren();
      for (const team of teams.values()) {
        if (selectedTeams.has(team.id) || !team._candidate) continue;
        if (!words.every((word) => `${team.title || ''} ${team.element || ''} ${team.category || ''}`.toLowerCase().includes(word))) continue;
        const row = el('div', 'dungeon-choice-row'), add = D.button(ui, '添加', () => {
          if (busy) return;
          if (selectedTeams.size >= maxTeams) {status.textContent = '每个副本最多推荐 30 盘。'; return;}
          selectedTeams.add(team.id); renderTeams();
        });
        add.disabled = busy || selectedTeams.size >= maxTeams;
        row.append(el('span', '', [team.title, team.element, team.category].filter(Boolean).join(' · ')), add); candidateList.append(row);
      }
    }
    async function loadTeams() {
      const ticket = ++teamSerial; more.disabled = true; libraryStatus.textContent = '正在读取公开队伍…';
      try {
        const params = new URLSearchParams({sort:'latest'}); if (teamCursor) params.set('cursor', teamCursor);
        const page = await request(`/teams?${params}`); if (!active() || teamSerial !== ticket) return;
        if (!Array.isArray(page.items)) throw new Error('队伍列表暂不可用，请重试。');
        page.items.forEach((team) => teams.set(team.id, {...team, _candidate:true}));
        teamsLoaded = true; teamCursor = page.nextCursor || ''; more.hidden = !teamCursor; more.textContent = '继续加载队伍';
        libraryStatus.textContent = teamCursor ? '可继续加载更多公开队伍。' : '已加载全部公开队伍。'; renderTeams();
      } catch (error) {if (active() && teamSerial === ticket) {libraryStatus.textContent = errorText(error); more.hidden = false; more.textContent = '重试加载队伍';}}
      finally {if (ticket === teamSerial) more.disabled = busy;}
    }
    function renderImages() {
      imageList.replaceChildren(); draftList.replaceChildren();
      for (const [id, entry] of images) {
        const included = selectedImages.has(id), row = el('figure', 'dungeon-edit-image');
        const img = D.image(ui, entry.previewUrl || entry.url, '攻略图片预览'); if (img) row.append(img);
        if (included) {
          const remove = D.button(ui, '从攻略移除', () => {if (!busy) {selectedImages.delete(id); renderImages();}}); remove.disabled = busy; row.append(remove);
        }
        else {
          const add = D.button(ui, '加入攻略', () => {if (!busy && selectedImages.size < maxImages) {selectedImages.add(id); renderImages();}});
          add.disabled = busy || selectedImages.size >= maxImages; row.append(add);
          row.append(D.button(ui, '删除未使用图片', async () => {
            if (busy) return; lock(true);
            try {await request(`${base}/images/${encodeURIComponent(id)}`, undefined, 'DELETE'); if (active()) {images.delete(id); status.textContent = '已删除未使用图片。';}}
            catch (error) {if (active()) status.textContent = errorText(error);}
            finally {if (active()) lock(false);}
          }));
        }
        (included ? imageList : draftList).append(row);
      }
      draftImages.hidden = !draftList.children.length; input.disabled = busy || selectedImages.size >= maxImages;
    }
    search.addEventListener('input', renderCandidates);
    search.addEventListener('keydown', (event) => {if (event.key === 'Enter') event.preventDefault();});
    teamLibrary.addEventListener('toggle', () => {if (teamLibrary.open && !teamsLoaded && !more.disabled) loadTeams();});
    input.addEventListener('change', async () => {
      const files = Array.from(input.files || []); if (!files.length || busy) return;
      if (selectedImages.size + files.length > maxImages) {status.textContent = '每个副本最多 12 张图片，请减少本次选择的数量。'; input.value = ''; return;}
      lock(true); let done = 0;
      try {
        for (const file of files) {
          status.textContent = `正在压缩并上传图片 ${done + 1} / ${files.length}…`;
          const blob = await shrink(file); if (!active()) break;
          const entry = await upload(item.id, blob); if (!active()) break;
          images.set(entry.id, entry); selectedImages.add(entry.id); done++;
        }
        if (active()) status.textContent = `已上传 ${done} 张，保存攻略后公开。`;
      } catch (error) {if (active()) status.textContent = `${done ? `已有 ${done} 张上传成功。` : ''}${errorText(error)}`;}
      finally {input.value = ''; if (active()) lock(false);}
    });
    form.addEventListener('submit', async (event) => {
      event.preventDefault(); if (busy) return;
      if (text.value.length > maxText || selectedTeams.size > maxTeams || selectedImages.size > maxImages) {status.textContent = '内容超过上限，请缩减后再保存。'; return;}
      lock(true); status.textContent = '正在保存…';
      try {
        const saved = await request(base, {expectedRevision:revision, text:text.value, teamIds:[...selectedTeams], imageIds:[...selectedImages]}, 'PATCH');
        if (!active()) return;
        if (!saved.guide || !Number.isSafeInteger(saved.guide.revision)) throw new Error('保存结果无法确认，请读取最新版本核对。');
        revision = saved.guide.revision; conflict.hidden = true; status.textContent = '已保存，攻略与推荐队伍已更新。'; settings.onSaved(saved);
      } catch (error) {
        if (!active()) return; status.textContent = errorText(error);
        if (isConflict(error)) {conflict.replaceChildren(el('p', '', '你的文字、队伍和图片草稿都已保留。'), reload); conflict.hidden = false;}
      } finally {if (active()) lock(false);}
    });
    renderTeams(); renderImages(); return form;
  }
  async function attach(host, item, data, ui, settings) {
    if (!window.WFCommunity?.client) return;
    let identity;
    try {identity = await (settings.identity || request('/admin/me'));} catch {return;}
    // Legacy Access identities have no role; /admin/me has already verified their email allowlist.
    if (!settings.current() || !identity?.id || !identity.email ||
        (identity.role !== undefined && !['owner','deputy','editor'].includes(identity.role)) || identity.mustChangePassword) return;
    const D = window.WFDungeons, box = ui.el('div'), notice = ui.el('p', 'dungeon-status'); notice.setAttribute('role', 'status'); box.hidden = true;
    let loaded = false, loading = false;
    const edit = D.button(ui, '编辑攻略与推荐队伍', async () => {
      if (loading || !settings.current()) return;
      if (loaded) {box.hidden = !box.hidden; edit.setAttribute('aria-expanded', String(!box.hidden)); return;}
      loading = true; edit.disabled = true; notice.textContent = '正在读取可编辑版本…';
      try {
        const result = await request(`/admin/dungeons/${encodeURIComponent(item.id)}`); if (!settings.current()) return;
        editor(box, item, result, data, ui, {...settings, onFold: () => edit.setAttribute('aria-expanded', 'false')});
        loaded = true; box.hidden = false; edit.setAttribute('aria-expanded', 'true'); notice.textContent = '';
      } catch (error) {if (settings.current()) notice.textContent = errorText(error);}
      finally {loading = false; edit.disabled = false;}
    });
    edit.setAttribute('aria-expanded', 'false'); host.replaceChildren(edit, notice, box);
  }
  window.WFDungeonsAdmin = {attach, editor, shrink, upload};
})();
