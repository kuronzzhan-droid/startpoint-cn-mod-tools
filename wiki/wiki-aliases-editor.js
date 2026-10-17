/* Local draft only: the parent keeps authentication, revision checks and saving. */
(() => {
  'use strict';
  window.WFWikiAliasEditor = {create(aliases, ui) {
    const {el} = ui, draft = [...aliases];
    const element = el('div', 'wiki-aliases-editor'), tags = el('div', 'wiki-aliases-editor-tags');
    tags.setAttribute('role', 'list'); tags.setAttribute('aria-label', '待保存的黑话');
    const field = el('label', 'wiki-aliases-add-field'); field.append(el('span', '', '添加黑话'));
    const row = el('div', 'wiki-aliases-add-row'), input = el('input'); input.type = 'text'; input.maxLength = 500;
    input.placeholder = '输入后按回车或逗号'; input.setAttribute('aria-label', '新增黑话');
    const add = el('button', 'secondary-button', '添加'); add.type = 'button';
    row.append(input, add); field.append(row);
    const footer = el('div', 'wiki-aliases-editor-footer'), count = el('small');
    const clear = el('button', 'text-button', '清空标签'); clear.type = 'button'; footer.append(count, clear);
    const status = el('p', 'wiki-aliases-status'); status.setAttribute('role', 'status');
    element.append(tags, field, footer, status);
    let locked = false, removeButtons = [];
    function sync() {
      input.disabled = add.disabled = locked; clear.disabled = locked || !draft.length;
      removeButtons.forEach(button => {button.disabled = locked;});
    }
    function paint() {
      tags.replaceChildren(); removeButtons = [];
      draft.forEach((alias, index) => {
        const tag = el('span', 'wiki-alias-chip wiki-alias-chip-editable'); tag.setAttribute('role', 'listitem');
        const remove = el('button', 'wiki-alias-remove', '×'); remove.type = 'button';
        remove.setAttribute('aria-label', `删除黑话：${alias}`); remove.title = `删除 ${alias}`;
        remove.addEventListener('click', () => {
          if (locked) return; draft.splice(index, 1); status.textContent = `已移除「${alias}」，保存后生效。`; paint();
          (removeButtons[Math.min(index, removeButtons.length - 1)] || input).focus();
        });
        removeButtons.push(remove); tag.append(el('span', '', alias), remove); tags.append(tag);
      });
      count.textContent = `${draft.length} / 12 条；每条最多 32 字。删除全部后保存可清除。`; sync();
    }
    function addPending() {
      if (locked) return false;
      const parts = input.value.split(/[\n,，、]/).map(value => value.trim().normalize('NFC')).filter(Boolean);
      if (!parts.length) {input.value = ''; return true;}
      if (parts.some(value => [...value].length > 32 || /[\u0000-\u001F\u007F]/u.test(value))) {
        status.textContent = '每条黑话最多 32 字，且不能包含控制字符。'; input.focus(); return false;
      }
      const seen = new Set(draft.map(value => value.toLowerCase())), added = [];
      for (const alias of parts) if (!seen.has(alias.toLowerCase())) {seen.add(alias.toLowerCase()); added.push(alias);}
      if (draft.length + added.length > 12) {status.textContent = '最多添加 12 条黑话，请先删除不需要的标签。'; input.focus(); return false;}
      draft.push(...added); input.value = ''; paint();
      status.textContent = added.length ? `已添加 ${added.length} 条，保存后生效。` : '这条黑话已存在，未重复添加。';
      return true;
    }
    add.addEventListener('click', () => {if (addPending()) input.focus();});
    input.addEventListener('keydown', event => {
      if (!event.isComposing && ['Enter', ',', '，', '、'].includes(event.key)) {event.preventDefault(); addPending();}
    });
    const addSeparated = event => {if (!event.isComposing && /[\n,，、]/.test(input.value)) addPending();};
    input.addEventListener('input', addSeparated); input.addEventListener('compositionend', addSeparated);
    clear.addEventListener('click', () => {if (!locked) {draft.splice(0); input.value = ''; status.textContent = '标签已清空，保存后生效。'; paint(); input.focus();}});
    paint();
    return {element, read: () => addPending() ? [...draft] : null, focus: () => input.focus(),
      lock(value) {locked = Boolean(value); sync();}};
  }};
})();
