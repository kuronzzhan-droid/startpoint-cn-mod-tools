/* A weapon card keeps enhancement, effect level and soul preview as separate choices. */
(() => {
  'use strict';
  window.WFEquipmentCard = {
    create(entry, ui, {enhancedStates = new Map()} = {}) {
      const {el, picture} = ui, {lazyDetails, renderReadable} = window.WFWikiReadable;
      const e = entry.enhancement, stateKey = entry.id || entry.name;
      const forms = Array.isArray(e?.forms) ? e.forms.filter((form) => form && Number.isFinite(Number(form.level)) && Number(form.level) > 0)
        .map((form) => ({...form, level:Number(form.level)})).sort((a, b) => a.level - b.level) : [];
      const stages = forms.length ? forms : e && Number.isFinite(Number(e.maxLevel)) && Number(e.maxLevel) > 0
        ? [{...e, level:Number(e.maxLevel), label:`强化后 Lv${e.maxLevel}`}] : [];
      const originalLabel = forms.length ? '原始形态' : '强化前';
      const partyNotes = entry.partyRule ? entry.notes || [] : [];
      const card = el('details', `equipment-card game-panel${e ? ' equipment-enhanceable' : ''}`);
      const summary = el('summary'), title = el('div', 'equipment-card-title'), name = el('strong', '', entry.name);
      title.append(name, el('span', 'muted', [entry.category, entry.element, `${entry.rarity}★`].filter(Boolean).join(' · ')));
      const stateLabel = el('span', 'equipment-current-state');
      const enhanceBadge = el('span', `equipment-enhance-badge${forms.length ? ' equipment-forms-badge' : ''}`,
        e ? `可强化 · ${forms.length ? `${forms.length + 1} 种形态 · ` : ''}最高 Lv${e.maxLevel}` : '');
      if (e) title.append(enhanceBadge, stateLabel);
      let icon = el('span'); summary.append(icon, title);
      const panelStats = el('div', 'equipment-final-stats'); title.append(panelStats);
      let body, effectControls, active, selectedLevel = 0, effectLevel = 'max', mode = 'weapon', renderedKey;
      const buttons = [], effectButtons = [];
      const enhancementControls = el('div', `team-controls equipment-toggle${forms.length ? ' equipment-toggle-forms' : ''}`);
      const emphasizeValues = (node, text) => {
        String(text).split(/([-+＋－]?\d+(?:\.\d+)?(?:%|％|倍|秒|次|层)?)/g).forEach((part, i) => {
          if (part) node.append(el(i % 2 ? 'b' : 'span', i % 2 ? 'equipment-effect-value' : '', part));
        });
        return node;
      };
      const effects = (parent, label, values, emphasize = false) => {
        if (!values?.length) return;
        if (label) parent.append(el('h4', '', label));
        const ul = el('ul', 'equipment-effects');
        (Array.isArray(values) ? values : [values]).forEach((value) => {
          const text = typeof value === 'string' ? value : value.description || value.text || '';
          ul.append(emphasize ? emphasizeValues(el('li'), text) : el('li', '', text));
        });
        parent.append(ul);
      };
      const stats = (value) => value ? `HP ${value.hp} / 攻击力 ${value.atk}` : '暂无数值';
      function renderHeader(level) {
        active = stages.find((stage) => stage.level === Number(level)); selectedLevel = active?.level || 0;
        const soul = mode === 'soul', shownName = !soul && active ? active.name || entry.name : entry.name;
        name.textContent = soul ? `${shownName} · 魂珠` : shownName;
        summary.setAttribute('aria-label', `${name.textContent}，${soul ? '魂珠效果' : active?.label || (active ? `强化 Lv${selectedLevel}` : e ? originalLabel : '武器资料')}，展开或收起资料`);
        summary.title = `${name.textContent} · ${entry.element || '通用'} · ${entry.rarity || ''}★`;
        card.setAttribute('data-enhanced', String(Boolean(active) && !soul));
        card.setAttribute('data-enhancement-level', String(selectedLevel)); card.setAttribute('data-equipment-mode', mode);
        stateLabel.textContent = `当前：${active ? active.label || `强化后 Lv${selectedLevel}` : originalLabel}`;
        enhanceBadge.hidden = stateLabel.hidden = enhancementControls.hidden = soul;
        panelStats.hidden = soul;
        panelStats.replaceChildren(el('span', 'equipment-final-stats-label', active ? '强化最终面板' : '满觉醒面板'),
          el('b', '', stats(active ? active.stats?.total : entry.stats?.awakened)));
        let nextIcon = picture(!soul && active ? active.icon || entry.icon : entry.icon, shownName, 'equipment-icon');
        if (!soul && active?.frame) {
          const framed = el('span', 'equipment-framed-icon');
          framed.append(picture(active.frame, '', 'equipment-frame-image'), nextIcon); nextIcon = framed;
        }
        icon.replaceWith(nextIcon); icon = nextIcon;
        buttons.forEach(({button, value, label}) => {
          button.setAttribute('aria-pressed', String(value === selectedLevel)); button.textContent = `${value === selectedLevel ? '● ' : ''}${label}`;
        });
        modeSwitch.setAttribute('aria-checked', String(soul));
        modeLabel.textContent = modeSwitch.disabled ? '无魂珠' : soul ? '魂珠' : '武器';
        if (!modeSwitch.disabled) modeSwitch.title = `当前：${soul ? '魂珠' : '武器'}，点击切换为${soul ? '武器' : '魂珠'}`;
      }
      function breakdown(fullEffects, baseEffects) {
        const details = el('details', 'equipment-calculation'); details.open = false;
        details.append(el('summary', '', '本体、强化追加与计算明细'));
        const content = el('div'); details.append(content);
        if (active?.description || entry.description) content.append(el('p', '', active?.description || entry.description));
        content.append(el('p', 'muted', `初始 ${stats(entry.stats?.base)}；满觉醒 ${stats(entry.stats?.awakened)}`));
        if (active?.stats?.additional) content.append(el('p', 'muted', `强化追加 ${stats(active.stats.additional)}`));
        effects(content, fullEffects ? '本体满级效果' : '本体初始效果', baseEffects);
        if (active) {
          effects(content, `强化 Lv${selectedLevel} 追加效果`, active.effects);
          if (active.panelDescription) content.append(el('p', '', active.panelDescription));
          if (active.note) content.append(el('p', 'muted', active.note));
        }
        if (entry.panelDescription) content.append(el('p', '', entry.panelDescription));
        if (e?.costs) content.append(lazyDetails(ui, '强化材料', '', (cost) => renderReadable(cost, e.costs, ui)));
        if (!entry.partyRule) (entry.notes || []).forEach((note) => content.append(el('p', 'weapon-note', note)));
        return details;
      }
      function renderBody() {
        const key = `${selectedLevel}:${effectLevel}:${mode}`;
        if (!card.open || renderedKey === key) return;
        if (!body) {
          effectControls = el('div', 'team-controls equipment-toggle');
          effectControls.setAttribute('role', 'group'); effectControls.setAttribute('aria-label', `${entry.name}本体效果等级`);
          [['initial', '初始效果'], ['max', '满级效果']].forEach(([value, label]) => {
            const button = el('button', 'secondary-button', label); button.type = 'button'; button.setAttribute('data-effect-level', value);
            button.addEventListener('click', () => {if (value !== effectLevel) {effectLevel = value; renderBody();}});
            effectButtons.push({button, value}); effectControls.append(button);
          });
          body = el('div', 'equipment-state'); card.append(effectControls, body);
        }
        effectControls.hidden = mode === 'soul'; body.replaceChildren();
        if (mode === 'soul') {
          effects(body, '魂珠效果', entry.soul.effects, true);
          body.append(el('p', 'muted', entry.soul.note || '魂珠效果独立于武器强化，不附带武器 HP / 攻击力。'));
          if (!entry.soul.effects?.length) body.append(el('p', 'muted', '暂无魂珠效果资料。'));
          partyNotes.forEach((note) => body.append(el('p', 'weapon-note', note)));
        } else {
          const fullEffects = effectLevel === 'max', baseEffects = fullEffects ? entry.awakenedEffects : entry.baseEffects;
          effectButtons.forEach(({button, value}) => button.setAttribute('aria-pressed', String(value === effectLevel)));
          const finalEffects = fullEffects ? active?.finalEffects : active?.initialFinalEffects;
          const finalDescription = fullEffects ? active?.finalDescription : active?.initialFinalDescription;
          if (active && finalDescription) body.append(el('h4', '', '最终加成'), emphasizeValues(el('p', 'equipment-final-effects'), finalDescription));
          else if (active && finalEffects?.length) effects(body, '最终效果', finalEffects, true);
          else if (active) {
            effects(body, '当前效果', [...(baseEffects || []), ...(active.effects || [])], true);
            body.append(el('p', 'muted', '当前数据尚未汇总，以上按各条原有效果列出。'));
          } else effects(body, fullEffects ? '满级效果' : '初始效果', baseEffects, true);
          if (active && !fullEffects) body.append(el('p', 'muted', '本体采用初始效果；强化追加仍按所选等级计算。'));
          if (forms.length && selectedLevel === 200) body.append(el('p', 'equipment-highest-marker', '最高强化 · Lv200'));
          partyNotes.forEach((note) => body.append(el('p', 'weapon-note', note)));
          body.append(breakdown(fullEffects, baseEffects));
        }
        renderedKey = key;
      }
      const modeControls = el('div', 'equipment-mode-controls');
      modeControls.setAttribute('role', 'group'); modeControls.setAttribute('aria-label', `${entry.name}效果类型`);
      const modeSwitch = el('button', 'secondary-button equipment-mode-switch'); modeSwitch.type = 'button';
      modeSwitch.setAttribute('role', 'switch'); modeSwitch.disabled = !entry.soul?.available;
      modeSwitch.setAttribute('aria-label', `${entry.name}魂珠预览${modeSwitch.disabled ? '（无可用魂珠）' : ''}`);
      modeSwitch.title = modeSwitch.disabled ? entry.soul?.note || '暂无可用魂珠' : '点击切换武器或魂珠效果';
      const modeTrack = el('span', 'equipment-mode-track'), modeLabel = el('span', 'equipment-mode-label');
      modeTrack.setAttribute('aria-hidden', 'true'); modeTrack.append(el('span', 'equipment-mode-thumb'));
      modeSwitch.append(modeTrack, modeLabel); modeControls.append(modeSwitch);
      modeSwitch.addEventListener('click', (event) => {
        event.preventDefault(); event.stopPropagation(); if (modeSwitch.disabled) return;
        mode = mode === 'weapon' ? 'soul' : 'weapon'; card.open = true; renderHeader(selectedLevel); renderBody();
      });
      const actions = el('div', 'equipment-card-actions');
      actions.append(modeControls); summary.append(actions);
      if (e) {
        enhancementControls.setAttribute('role', 'group'); enhancementControls.setAttribute('aria-label', `${entry.name}强化状态`);
        [[0, originalLabel], ...stages.map((stage) => [stage.level, stage.label || `强化后 Lv${stage.level}`])].forEach(([value, label]) => {
          const button = el('button', 'secondary-button', label); button.type = 'button'; button.setAttribute('data-level', String(value));
          button.addEventListener('click', (event) => {
            event.preventDefault(); event.stopPropagation(); if (value === selectedLevel) return;
            enhancedStates.set(stateKey, value); renderHeader(value); renderBody();
          });
          buttons.push({button, value, label}); enhancementControls.append(button);
        });
        title.append(enhancementControls);
      }
      const defaultLevel = Math.max(0, ...stages.map((stage) => stage.level));
      card.append(summary); renderHeader(enhancedStates.has(stateKey) ? enhancedStates.get(stateKey) : defaultLevel);
      card.addEventListener('toggle', renderBody);
      return card;
    },
  };
})();
