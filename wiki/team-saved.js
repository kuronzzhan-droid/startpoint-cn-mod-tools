/* Visual management for browser saves. No community or game-server writes. */
(() => {
  'use strict';
  let serial = 0;
  window.WFTeamSaved = {create({ui, characters, avatars, getCurrent, onLoad, onChange = () => {}, onStatus = () => {}}) {
    const {el, picture} = ui, store = window.WFTeamSavedStore.create();
    let managerRefresh = null, managerStatus = null;
    const button = (text, action, cls = '') => {
      const node = el('button', `team-saved-button ${cls}`.trim(), text); node.type = 'button';
      node.addEventListener('click', action); return node;
    };
    function preview(team) {
      const grid = el('div', 'team-saved-portraits'); grid.setAttribute('aria-label', '主位与合击角色预览');
      for (const group of ['main', 'unison']) for (let index = 0; index < 3; index++) {
        const id = team?.[group]?.[index], character = characters.get(String(id || ''));
        const slot = el('span', 'team-saved-portrait');
        slot.title = `${index + 1}号${group === 'main' ? '主位' : '合击'}：${character?.name || (id ? '未收录角色' : '空位')}`;
        if (character) slot.append(avatars ? avatars.picture(character, character.name)
          : picture(character.icon, character.name, ''));
        else slot.append(el('span', '', id ? '?' : '—'));
        grid.append(slot);
      }
      return grid;
    }
    function modal(title) {
      const origin = document.activeElement, dialog = el('dialog', 'team-saved-dialog');
      const heading = el('div', 'team-saved-heading'), caption = el('h2', '', title); caption.id = `team-saved-heading-${++serial}`;
      dialog.setAttribute('aria-labelledby', caption.id);
      const close = () => dialog.close();
      heading.append(caption, button('关闭', close, 'team-saved-close'));
      const body = el('div', 'team-saved-body'), status = el('p', 'team-saved-status'); status.setAttribute('role', 'status');
      dialog.append(heading, body, status); document.body.append(dialog);
      const cleanup = () => {window.removeEventListener?.('hashchange', close); dialog.remove(); if (origin?.isConnected) origin.focus();};
      dialog.addEventListener('close', cleanup); window.addEventListener?.('hashchange', close);
      dialog.showModal();
      return {dialog, body, status, close};
    }
    function notice(message) {onStatus(message); if (managerStatus?.isConnected) managerStatus.textContent = message;}
    function committed(message) {onChange(); managerRefresh?.(); notice(message);}
    function load(item) {
      try {
        const current = store.read().records.find(record => record.key === item.key);
        if (!current || JSON.stringify(current) !== JSON.stringify(item)) {
          throw new Error('这支队伍已被其他页面修改或删除，请刷新列表后再装入。当前编成未改动。');
        }
        onLoad(current); return true;
      } catch (error) {onChange(); notice(error.message); return false;}
    }
    function save(record = getCurrent()) {
      const current = {name: String(record.name || '').trim() || '我的队伍', team: window.WFTeamState.copy(record.team)};
      let snapshot;
      try {
        snapshot = store.read();
        if (!snapshot.records.some(item => item.name === current.name)) {
          store.add(snapshot, current); committed(`「${current.name}」已保存到此浏览器。`); return;
        }
      } catch (error) {notice(error.message); return;}
      const box = modal('已有同名队伍'), actions = el('div', 'team-saved-actions');
      box.body.append(el('p', '', `「${current.name}」已有保存记录，请选择覆盖它，或保留原记录另存副本。`), preview(current.team));
      const finish = (operation, text) => {
        try {operation(); box.close(); committed(text);}
        catch (error) {box.status.textContent = error.message;}
      };
      const existing = snapshot.records.filter(item => item.name === current.name);
      if (existing.length === 1) actions.append(button('覆盖同名队伍', () => finish(
        () => store.replace(snapshot, existing[0].key, current), `「${current.name}」已更新。`), 'team-saved-primary'));
      else box.body.append(el('p', '', '旧记录中有多个同名队伍，请先在已保存队伍中重命名，或另存副本。'));
      actions.append(button('另存副本', () => {
        try {
          const name = store.copyName(snapshot, current.name);
          finish(() => store.add(snapshot, {...current, name}), `已另存为「${name}」，原记录保留。`);
        } catch (error) {box.status.textContent = error.message;}
      }), button('取消', box.close));
      box.body.append(actions);
    }
    function open() {
      const box = modal('已保存队伍'), toolbar = el('div', 'team-saved-toolbar');
      const search = el('input', 'team-saved-search'); search.type = 'search'; search.placeholder = '搜索队伍名称';
      search.setAttribute('aria-label', '搜索已保存队伍'); search.maxLength = 60;
      const count = el('p', 'team-saved-count'), list = el('div', 'team-saved-list');
      const readStatus = el('p', 'team-saved-read-status'); readStatus.setAttribute('role', 'status');
      let snapshot = null;
      function refresh() {
        try {snapshot = store.read(); readStatus.textContent = snapshot.skipped ? `有 ${snapshot.skipped} 条旧记录格式异常，已保留原数据。` : ''; render();}
        catch (error) {readStatus.textContent = error.message;}
      }
      function change(operation, success) {
        try {operation(); box.status.textContent = success; committed(success); search.focus();}
        catch (error) {box.status.textContent = error.message;}
      }
      function card(item) {
        const article = el('article', 'team-saved-card'), heading = el('h3', '', item.name || '未命名队伍');
        const actions = el('div', 'team-saved-actions'), rename = el('form', 'team-saved-edit'), remove = el('div', 'team-saved-confirm');
        rename.hidden = true; remove.hidden = true;
        const title = el('input'); title.value = item.name; title.maxLength = 60; title.setAttribute('aria-label', `重命名 ${item.name}`);
        const submit = button('保存名称', () => {}); submit.type = 'submit';
        rename.append(title, submit, button('取消', () => {rename.hidden = true;}));
        rename.addEventListener('submit', event => {event.preventDefault(); change(() => store.rename(snapshot, item.key, title.value), '队伍名称已更新。');});
        remove.append(el('p', '', `删除「${item.name}」的本地保存记录？`),
          button('确认删除', () => change(() => store.remove(snapshot, item.key), `已删除「${item.name}」的保存记录。`), 'team-saved-danger'),
          button('取消', () => {remove.hidden = true;}));
        actions.append(button('装入编成', () => {if (load(item)) box.close();}),
          button('重命名', () => {remove.hidden = true; rename.hidden = false; title.focus();}),
          button('删除', () => {rename.hidden = true; remove.hidden = false;}, 'team-saved-danger'));
        article.append(heading, preview(item.team), actions, rename, remove); return article;
      }
      function render() {
        if (!snapshot) return;
        const value = search.value.trim().toLocaleLowerCase('zh-CN');
        const shown = snapshot.records.filter(item => item.name.toLocaleLowerCase('zh-CN').includes(value));
        count.textContent = `${shown.length} / ${snapshot.records.length} 支队伍`;
        list.replaceChildren(...shown.map(card));
        if (!shown.length) list.append(el('p', 'team-saved-empty', value ? '没有匹配的队伍。' : '还没有保存队伍，先将当前编成保存到这里。'));
      }
      toolbar.append(search, button('保存当前编成', () => save(), 'team-saved-primary'), button('刷新', refresh));
      search.addEventListener('input', render);
      box.body.append(el('p', 'team-saved-note', '保存在此浏览器。删除只移除保存记录，当前编成与云端队伍不变。'), toolbar, readStatus, count, list);
      managerRefresh = refresh; managerStatus = box.status;
      box.dialog.addEventListener('close', () => {if (managerRefresh === refresh) {managerRefresh = null; managerStatus = null;}});
      refresh(); search.focus();
    }
    return {open, save, load, records: () => store.read().records};
  }};
})();
