/* Editing a saved plate stays inside its revision-protected administrator form. */
(() => {
  'use strict';
  window.WFCommunityTeamPicker = {create({team:initial, data, ui, onChange = () => {}}) {
    const S = window.WFTeamState, {el} = ui, root = el('fieldset', 'community-team-picker');
    const labels = {main:'主位', unison:'合击', weapon:'装备', soul:'魂珠'};
    const characters = new Map(data.characters.map(item => [String(item.id),item]));
    const equipment = new Map((data.equipment || []).map(item => [String(item.id),item]));
    let team = S.copy(initial), selected = null, disabled = false, candidates, characterFilters, equipmentFilters;
    let characterItems, equipmentItems, matchedCharacters, matchedEquipment, slotButtons = [];
    const artUi = {...ui, picture:ui.picture || ((_url,name,cls) => el('span',cls,name)),
      elementBadge:ui.elementBadge || (value => el('span','element-badge',value)), safeUrl:ui.safeUrl || (value => value || '')};
    const board = el('div', 'community-picker-board'), picker = el('div', 'community-picker-library'); picker.hidden = true;
    const controls = el('div', 'community-picker-controls'), heading = el('strong'), avatarHost = el('div');
    const avatars = window.WFCatalogAvatars?.create?.({host:avatarHost,catalog:root,characters:data.characters,ui:artUi,label:'编辑队伍头像'});
    const button = (label, action, cls = 'secondary-button') => {
      const node = el('button',cls,label); node.type = 'button'; node.addEventListener('click',() => {if (!disabled) action();}); return node;
    };
    const clear = button('清空此位',() => assign(''));
    root.addEventListener('keydown',event => {if (event.key === 'Enter' && event.target.type === 'search') event.preventDefault();});
    controls.append(heading,clear); picker.append(controls,avatarHost); root.append(el('legend','','队伍编成'),board,picker);
    function apply(next) {
      if (JSON.stringify(next) === JSON.stringify(team)) return;
      team = next; paintBoard(); paintLibrary(); onChange();
    }
    function assign(id,kind) {
      if (disabled || !selected || (kind && kind !== (S.isCharacter(selected.group) ? 'character' : 'equipment'))) return;
      apply(S.place(team,selected.group,selected.index,id,characters,equipment));
    }
    function choose(group,index) {
      if (disabled) return;
      selected = {group,index}; picker.hidden = false;
      slotButtons.forEach(entry => entry.slot.setAttribute('aria-pressed',String(entry.group===group && entry.index===index)));
      paintLibrary();
    }
    function paintBoard() {
      board.replaceChildren(); slotButtons = [];
      for (let index=0;index<3;index++) {
        const column = el('div','community-picker-column'); column.append(el('strong','community-picker-position',index ? `${index+1}号位` : '队长'));
        for (const group of ['main','unison','weapon','soul']) {
          const character = S.isCharacter(group), id = team[group][index], item = (character ? characters : equipment).get(id);
          const slot = button('',() => choose(group,index),'community-picker-slot');
          slot.setAttribute('aria-label',`调整${index+1}号${labels[group]}：${item?.name || (id ? '未收录' : '空位')}`);
          slot.setAttribute('aria-pressed',String(selected?.group===group && selected?.index===index));
          slot.title = item?.name || (id ? '原条目未收录，点击更换' : '点击选择');
          const portrait = el('span','community-picker-portrait');
          if (item) {
            portrait.append(character && avatars ? avatars.picture(item,item.name,'community-picker-image')
              : artUi.picture(item.avatars?.[window.WFCatalogAvatars?.getForm?.()] || item.icon,item.name,'community-picker-image'));
            if (character) {window.WFCharacterFrame?.apply(portrait,item);window.WFCharacterBadges?.append(portrait,item,artUi);}
          } else portrait.append(el('span','',id ? '?' : '+'));
          slot.append(portrait,el('span','community-picker-label',labels[group]));
          slot.addEventListener('dragover',event => {if (!disabled) event.preventDefault();});
          slot.addEventListener('drop',event => {
            event.preventDefault(); if (disabled) return;
            try {
              const value = JSON.parse(event.dataTransfer.getData('application/x-wf-wiki'));
              if (value.kind !== (character ? 'character' : 'equipment')) return;
              choose(group,index); assign(value.id,value.kind);
            } catch { /* Ignore drags from other pages. */ }
          });
          slotButtons.push({group,index,slot}); column.append(slot);
        }
        board.append(column);
      }
    }
    function mountLibrary() {
      if (candidates) return;
      characterItems = [...characters.values()].sort(window.WFCharacterOrder.compareTeam);
      equipmentItems = [...equipment.values()].sort(window.WFEquipmentOrder.createCompare(data.equipment || []));
      characterFilters = window.WFCharacterFilters.create({characters:data.characters,ui:artUi,idPrefix:'admin-team-character',collapsible:false,
        onChange:() => {matchedCharacters=null;paintLibrary();}});
      equipmentFilters = window.WFTeamEquipmentFilters.create({equipment:data.equipment || [],ui:artUi,
        onChange:() => {matchedEquipment=null;paintLibrary();}});
      candidates = window.WFTeamCandidates.create({ui:artUi,avatars,onAssign:assign,scrollRail:false});
      picker.append(characterFilters.element,equipmentFilters.element,candidates.element);
    }
    function paintLibrary() {
      if (!selected) return;
      mountLibrary();
      const character = S.isCharacter(selected.group);
      heading.textContent = `替换 ${selected.index+1}号${labels[selected.group]}`;
      characterFilters.element.hidden = !character; equipmentFilters.element.hidden = character; avatarHost.hidden = !character;
      if (!character) equipmentFilters.setMode(selected.group);
      const items = character ? (matchedCharacters ||= characterItems.filter(characterFilters.matches))
        : (matchedEquipment ||= equipmentItems.filter(equipmentFilters.matches));
      candidates.show(character ? 'character' : 'equipment',items,selected.group,team[selected.group][selected.index]);
      clear.disabled = !team[selected.group][selected.index];
    }
    paintBoard();
    return {element:root, getTeam:() => S.copy(team), setDisabled(value) {disabled=Boolean(value);root.disabled=disabled;root.setAttribute('aria-disabled',String(disabled));}};
  }};
})();
