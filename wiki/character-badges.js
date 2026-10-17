/* Availability is explicit source data; MOD identity never implies limited. */
(() => {
  'use strict';
  window.WFCharacterBadges = {
    append(host, character, ui, inline = false) {
      const entries = [];
      if (character.limited === true) entries.push(['limited', '限定', [character.availabilitySource, character.availabilityNote].filter(Boolean).join('；')]);
      if (['新增MOD', '灰服独立角色资料'].includes(character.origin)) entries.push(['mod', 'MOD', 'MOD 角色']);
      if (character.origin === '改版官方') entries.push(['modified', 'MOD改', '在官方角色基础上修改；详情中可查看与原版的区别']);
      if (!entries.length) return;
      const labels = ui.el('span', `character-labels${inline ? ' character-labels-inline' : ''}`);
      for (const [kind, label, description] of entries) {
        const badge = ui.el('span', `character-label character-label-${kind}`, label);
        badge.title = description;
        labels.append(badge);
      }
      host.append(labels);
    },
  };
})();
