/* Management uses verified server identity and revision checks, never a user-entered email. */
(() => {
  'use strict';
  function createApi(fetcher, protocol) {
    return async function request(path, body, method = body ? 'PATCH' : 'GET') {
      if (!/^https?:$/.test(protocol)) throw new Error('离线版不能登录管理员；请在已启用社区的公开网站管理推荐盘。');
      const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 15000);
      try {
        const response = await fetcher(`/api/community${path}`, {method, credentials:'same-origin', signal:controller.signal,
          headers:{Accept:'application/json', ...(body ? {'Content-Type':'application/json'} : {})},
          ...(body ? {body:JSON.stringify(body)} : {})});
        let result;
        try {result = await response.json();} catch {throw new Error('此站尚未提供管理员服务，请确认社区已配置。');}
        if (!response.ok) throw Object.assign(new Error(result.message || '管理员操作暂时失败。'),
          {status:response.status, code:result.error});
        return result;
      } catch (error) {
        if (error.name === 'AbortError') throw new Error('连接超时，请重试；表单内容仍保留。');
        if (error instanceof TypeError) throw new Error('网络连接失败，请重试；表单内容仍保留。');
        throw error;
      } finally {clearTimeout(timer);}
    };
  }
  window.WFCommunityAdmin = {createApi};
  window.renderWikiCommunityAdmin = async function renderWikiCommunityAdmin(host, data, ui) {
    const {el} = ui, C = window.WFCommunity, initialTarget = C.adminTarget; delete C.adminTarget;
    const fallback = createApi(window.fetch.bind(window), window.location.protocol);
    const request = (path, body, method = body ? 'PATCH' : 'GET') => C.client ? C.client.request(path, body, method) : fallback(path, body, method);
    const page = el('section', 'community-admin'), header = el('header', 'admin-header');
    const home = el('a', 'back-button', '‹ 返回配队社区'); home.href = '#community';
    home.setAttribute('data-navigation-guard','custom');
    home.addEventListener('click', (event) => {event.preventDefault(); return navigate('#community');});
    const create = el('a', 'primary-button', '＋ 新建队伍'); create.href = '#team';
    create.setAttribute('data-navigation-guard','custom');
    create.addEventListener('click', (event) => {
      event.preventDefault(); return navigate('#team', () => window.WFTeamImport?.load(C.teamCopy(), '新队伍'));
    });
    header.append(el('h1', '', '队伍管理'), home, create);
    const notice = el('p', 'admin-notice', '正在验证管理员身份…'); notice.setAttribute('role', 'status');
    const account = el('p', 'admin-account'), authHost = el('div', 'admin-auth'), controls = el('div', 'admin-controls');
    const layout = el('div', 'admin-layout'), listHost = el('div', 'admin-list'), editorHost = el('div', 'admin-editor');
    const announcementHost = el('div'), sponsorHost = el('div');
    editorHost.hidden = true; layout.append(listHost, editorHost); page.append(header, account, authHost, notice, announcementHost, sponsorHost, controls, layout);
    host.replaceChildren(page);
    let config, identity, serial = 0, nextCursor = '', statusFilter, categoryFilter, sectionFilter, scopeFilter, codeFilter, search, more;
    let currentForm, announcementEditor, sponsorEditor, loading = false, mutating = false, authBusy = false, debounce, avatars;
    const tabs = [];
    window.WFNavigationGuard?.register({isActive:() => page.isConnected, canLeave:() => allowLeave(true),
      needsProtection:() => mutating || authBusy || [currentForm,announcementEditor,sponsorEditor].some(form => form?.isConnected && (form.isDirty?.() || form.isBusy?.()))});
    async function navigate(hash, before) {
      if (window.WFNavigationGuard) return window.WFNavigationGuard.navigate(hash,before);
      if (await allowLeave(true)) {before?.(); window.location.hash = hash;}
    }
    function canSwitch() {
      if (mutating || authBusy) notice.textContent = `正在处理${authBusy ? '账号' : '队伍'}操作，请稍候再切换。`;
      return !mutating && !authBusy;
    }
    async function allowLeave(protectAnnouncement = false) {
      if (!canSwitch()) return false;
      const form = currentForm;
      const allowed = !form || !form.isConnected || !form.canClose || await form.canClose();
      const announcementAllowed = allowed && (!protectAnnouncement || !announcementEditor?.isConnected || await announcementEditor.canClose());
      const sponsorAllowed = announcementAllowed && (!protectAnnouncement || !sponsorEditor?.isConnected || await sponsorEditor.canClose());
      return sponsorAllowed && canSwitch() && currentForm === form && page.isConnected;
    }
    function closeEditor() {currentForm = null; editorHost.replaceChildren(); editorHost.hidden = true; controls.hidden = false;}
    function button(label, action, cls = 'secondary-button') {
      const node = el('button', cls, label); node.type = 'button'; node.addEventListener('click', action); return node;
    }
    function field(label, input) {
      input.setAttribute('aria-label', label);
      const node = el('label', 'admin-field'); node.append(el('span', '', label), input); return node;
    }
    function select(values, current) {
      const node = el('select');
      values.forEach(([value, label]) => {const option = el('option', '', label); option.value = value; node.append(option);});
      node.value = current; return node;
    }
    async function edit(item, bypass = false) {
      if (!canSwitch()) return;
      if (!bypass && !await allowLeave()) return;
      if (!canSwitch()) return;
      if (!window.WFCommunityAdminEditor) {notice.textContent = '编辑模块未加载，请刷新页面。'; return;}
      const form = window.WFCommunityAdminEditor.create({item, identity, config, data, ui, request,
        onClose: () => {if (canSwitch()) closeEditor();}, onReload: () => load(false),
        onSaved: async (saved) => {await load(false, true); if (!page.isConnected) return;
          await edit(saved, true); notice.textContent = `已保存「${saved.title}」，当前版本 ${saved.revision}。`;}});
      currentForm = form;
      editorHost.replaceChildren(form); editorHost.hidden = false; controls.hidden = true;
      editorHost.scrollIntoView?.({block:'start'});
    }
    function row(item) {
      return window.WFCommunityAdminCards.create(item, {data, ui, avatars, onEdit:edit,
        onDelete: item => mutate(item, false), onRestore: item => mutate(item, true)});
    }
    async function mutate(item, restore) {
      if (mutating || loading || !await allowLeave() || mutating || loading) return;
      const question = restore ? `恢复「${item.title}」？\n${item.visibility === 'private' ? '恢复到创建者的个人空间。' : '恢复后会重新显示在配队大全。'}旧队伍码不会恢复，需要重新公开。`
        : `删除「${item.title}」？\n队伍会移到回收站，可随时恢复；大全和副本推荐中不再展示，已公开的队伍码立即失效。`;
      const previousNotice = notice.textContent;
      mutating = true; page.setAttribute('aria-busy','true');
      try {
        if (!window.WFCommunityAdminConfirm) throw new Error('确认模块未加载，请刷新页面后重试。');
        const confirmed = await window.WFCommunityAdminConfirm.ask(question,{restore});
        if (!page.isConnected) return;
        if (!confirmed) {notice.textContent = previousNotice; return;}
        page.inert = true;
        notice.textContent = restore ? '正在恢复…' : '正在移到回收站…';
        const result = await request(`/admin/teams/${encodeURIComponent(item.id)}`,
          {expectedRevision:Number(item.revision), ...(restore ? {status:'approved'} : {})}, restore ? 'PATCH' : 'DELETE');
        if (result.team?.id !== item.id || !Number.isSafeInteger(Number(result.team.revision)) || Number(result.team.revision) <= Number(item.revision)) {
          throw new Error('服务端未返回新版本，请刷新列表核实。');
        }
        if (!page.isConnected) return;
        await load(false, true);
        notice.textContent = restore ? `已恢复「${item.title}」，如需游戏队伍码请重新公开。` : `已将「${item.title}」移到回收站，原队伍码已停用。`;
      } catch (error) {
        if (page.isConnected) notice.textContent = error.code === 'edit_conflict' ? '队伍已被其他管理员修改，请刷新后核对再操作。' : C.message(error);
      } finally {mutating = false; page.inert = false; page.setAttribute('aria-busy','false');}
    }
    function updateTabs() {
      tabs.forEach(({node,scope,status}) => node.setAttribute('aria-pressed', String(statusFilter.value === status && (status === 'hidden' || scopeFilter.value === scope))));
    }
    async function load(append, bypass = false) {
      if (!bypass && !canSwitch()) return;
      if (!append && !bypass && !await allowLeave()) return;
      if (!bypass && !canSwitch()) return;
      clearTimeout(debounce);
      const ticket = ++serial; more.disabled = true;
      loading = true;
      if (!append) {closeEditor(); listHost.replaceChildren(); nextCursor = '';}
      updateTabs();
      notice.textContent = '正在载入推荐盘…';
      const params = new URLSearchParams({status:statusFilter.value, sort:'latest'});
      if (categoryFilter.value) params.set('category', categoryFilter.value);
      if (sectionFilter.value) params.set('section', sectionFilter.value);
      params.set('scope', scopeFilter.value);
      if (codeFilter.value) params.set('code', codeFilter.value);
      if (search.value.trim()) params.set('q', search.value.trim());
      if (append && nextCursor) params.set('cursor', nextCursor);
      try {
        const result = await request(`/admin/teams?${params}`);
        if (!page.isConnected || ticket !== serial) return;
        if (!Array.isArray(result.items)) throw new Error('管理员列表格式无效，请重试。');
        result.items.forEach((item) => listHost.append(row(item)));
        nextCursor = result.nextCursor || ''; more.hidden = !nextCursor;
        notice.textContent = listHost.childElementCount ? `已显示 ${listHost.childElementCount} 支队伍${nextCursor ? '，还有更多可加载' : ''}。${statusFilter.value === 'hidden' ? '回收站包含以前停用的队伍；恢复不会启用旧码。' : '点击头像或“编辑队伍”修改，删除后可在回收站恢复。'}` : '当前筛选下没有队伍。';
      } catch (error) {
        if (page.isConnected && ticket === serial) {notice.textContent = C.message(error); more.hidden = false;}
      } finally {if (ticket === serial) {more.disabled = false; loading = false;}}
    }
    async function start() {
      clearTimeout(debounce); more?.remove?.(); currentForm = null;
      announcementEditor = null; announcementHost.replaceChildren();
      sponsorEditor = null; sponsorHost.replaceChildren();
      serial++; account.textContent = ''; controls.replaceChildren(); listHost.replaceChildren(); editorHost.replaceChildren();
      create.hidden = true; controls.hidden = true; layout.hidden = true; notice.textContent = '正在验证管理员身份…';
      try {
        config = await request('/config');
        if (!config.enabled) throw new Error('此站暂未启用社区，管理员功能不可用。');
        if (!page.isConnected) return;
        if (config.authMode === 'password' && !window.WFCommunityAuth) throw new Error('登录模块未加载，请刷新页面后重试。');
        identity = config.authMode === 'password' ? await window.WFCommunityAuth.ensure(authHost, config, ui, start) : await request('/admin/me');
        if (!page.isConnected) return;
        if (!identity) {notice.textContent = ''; return;}
        if (!identity.id || !identity.email) throw new Error('未取得有效管理员身份，请重新登录。');
        const prefix = config.authMode === 'password' ? (config.development ? '本机账号' : '已登录') : (config.development ? '本机测试身份' : '已验证管理员');
        account.textContent = `${prefix} · ${identity.email}${identity.role === 'owner' ? ' · 站长' : identity.role === 'deputy' ? ' · 副站长' : ''}`;
        if (config.authMode === 'password') window.WFCommunityAuth.controls(authHost, identity, ui, start, {
          beforeAction:async () => {if (!await allowLeave(true)) return false; closeEditor(); return true;},
          onBusyChange:value => {authBusy = value;},
        });
        await window.WFWikiData?.loadEquipment();
        if (!page.isConnected) return;
        create.hidden = false; controls.hidden = false; layout.hidden = false;
        if (C.announcementEditor) {announcementEditor = C.announcementEditor({ui, request}); announcementHost.append(announcementEditor);}
        if (C.sponsorEditor && ['owner','deputy'].includes(identity.role)) {sponsorEditor = C.sponsorEditor({ui,request}); sponsorHost.append(sponsorEditor);}
        statusFilter = select([['approved','使用中'],['hidden','回收站 / 已停用'],['','全部状态']], 'approved');
        statusFilter.addEventListener('change', () => load(false));
        categoryFilter = select([['','全部分类'], ...C.teamCategories.map((value) => [value,value]), ['uncategorized','未分类']], '');
        categoryFilter.addEventListener('change', () => load(false));
        sectionFilter = select([['','全部玩法'], ...Object.entries(C.teamSections).filter(([value]) => value), ['general',C.sectionLabel('')]], '');
        sectionFilter.addEventListener('change', () => load(false));
        scopeFilter = select([['all','全部可见队伍'],['public','配队大全'],['mine','我的空间'],
          ...(['owner','deputy'].includes(identity.role) ? [['private','全部私有队伍']] : [])], initialTarget?.scope === 'mine' ? 'mine' : 'all');
        scopeFilter.addEventListener('change', () => load(false));
        codeFilter = select([['','全部队伍码状态'],['has','已有队伍码'],['none','暂无队伍码']], '');
        codeFilter.addEventListener('change', () => load(false));
        more = button('继续加载 / 重试', () => load(true), 'secondary-button community-more'); more.hidden = true;
        const spaces = el('div', 'admin-space-tabs'); spaces.setAttribute('role','group'); spaces.setAttribute('aria-label','队伍保存位置'); tabs.length = 0;
        [['all','approved','全部队伍'],['public','approved','配队大全'],['mine','approved','我的空间'],['all','hidden','回收站']].forEach(([scope,status,label]) => {
          const node = button(label, async () => {if (!await allowLeave() || !canSwitch()) return; scopeFilter.value = scope; statusFilter.value = status; return load(false, true);}, 'admin-space-tab');
          tabs.push({node,scope,status}); spaces.append(node);
        });
        search = el('input'); search.type = 'search'; search.maxLength = 80; search.placeholder = '搜索队伍名称、作者或队伍码'; search.setAttribute('aria-label','搜索已保存队伍');
        search.addEventListener('input', () => {clearTimeout(debounce); debounce = setTimeout(() => {if (page.isConnected) load(false);}, 250);});
        const searchRow = el('div','admin-search-row'); searchRow.append(search, field('队伍码状态', codeFilter), button('刷新列表', () => load(false)));
        const advanced = el('details', 'admin-filter-details'); advanced.append(el('summary','','更多筛选'));
        const filterBody = el('div','admin-filter-body'); filterBody.append(field('查看空间',scopeFilter),field('查看状态',statusFilter),field('查看玩法分区',sectionFilter),field('查看配队分类',categoryFilter)); advanced.append(filterBody);
        const avatarHost = el('div','admin-avatar-controls');
        avatars = ui.picture && ui.safeUrl ? window.WFCatalogAvatars?.create({host:avatarHost,catalog:page,characters:data.characters || [],ui,label:'管理队伍角色头像'}) : null;
        controls.replaceChildren(spaces, searchRow, advanced, avatarHost);
        layout.after?.(more);
        if (!more.parentNode) controls.append(more);
        await load(false);
        if (initialTarget?.id && page.isConnected) {
          const result = await request(`/admin/teams/${encodeURIComponent(initialTarget.id)}`);
          if (page.isConnected && result.team) await edit(result.team);
        }
      } catch (error) {
        if (!page.isConnected) return;
        notice.textContent = error.code === 'admin_auth_required' ? '请使用获授权的管理员账号登录。' : C.message(error);
        controls.replaceChildren(); controls.hidden = false;
        if (error.code === 'admin_auth_required' && config?.authMode !== 'password') {
          const login = el('a', 'primary-button', '登录管理员'); login.href = '/api/community/admin/login'; controls.append(login);
          if (config?.development === true && ['localhost','127.0.0.1','[::1]'].includes(window.location.hostname)) {
            const dev = button('本机测试：登录测试管理员', async () => {
              dev.disabled = true;
              try {await request('/development-admin-login', {}, 'POST'); await start();}
              catch (failure) {notice.textContent = C.message(failure); dev.disabled = false;}
            }); controls.append(dev);
          }
        } else controls.append(button('重新检查服务', start));
      }
    }
    await start();
  };
})();
