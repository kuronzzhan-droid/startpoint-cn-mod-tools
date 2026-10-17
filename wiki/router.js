/* Render only the active page; late data must never replace newer navigation. */
window.createWikiRouter = function createWikiRouter(options) {
  'use strict';
  const {data, meta, ui, renderCatalog} = options;
  const {el, text} = ui;
  const catalog = document.getElementById('catalog-view');
  const detail = document.getElementById('detail-view');
  const extra = document.getElementById('extra-view');
  let revision = 0;
  function status(host, message, retry) {
    const box = el('div', 'note-box', message); box.setAttribute('role', 'status');
    if (retry) {
      const button = el('button', 'secondary-button', '重新加载'); button.type = 'button';
      button.addEventListener('click', retry); box.append(button);
    }
    host.replaceChildren(box);
  }
  return async function route() {
    const hash = location.hash.slice(1);
    const allowed = window.WFNavigationGuard?.allow(hash) ?? true;
    if (!(allowed && typeof allowed.then === 'function' ? await allowed : allowed)
        || location.hash.slice(1) !== hash) return;
    const ticket = ++revision;
    if (typeof window.CustomEvent === 'function') window.dispatchEvent(new window.CustomEvent('wf-page-leave', {detail:{to:hash}}));
    const current = () => ticket === revision && location.hash.slice(1) === hash;
    const parts = hash.split('/');
    const isCharacter = parts[0] === 'character' && parts[1];
    const pageTitle = ({team: '队伍编成', community: '配队大全', weapons: '武器图鉴', weapon: '武器详情',
      dungeons: '副本与模式', shops: '兑换商店', 'five-boss': '五重决战', 'tier-list': '从夯到拉',
      battle: hash === 'battle' ? '放置挑战' : ''})[parts[0]];
    document.querySelectorAll('audio').forEach((audio) => audio.pause());
    document.querySelectorAll('.app-navigation a').forEach((link) => {
      const target = link.getAttribute('href').slice(1);
      link.setAttribute('aria-current', (target === hash || (!target && isCharacter)
        || (target === 'community' && parts[0] === 'community') || (target === 'weapons' && parts[0] === 'weapon')
        || (target === 'dungeons' && (['dungeons', 'shops', 'five-boss'].includes(parts[0]) || hash === 'battle'))) ? 'page' : 'false');
      if (link.getAttribute('aria-current') === 'page') window.requestAnimationFrame?.(() => {
        if (link.getAttribute('aria-current') === 'page') link.scrollIntoView?.({block: 'nearest', inline: 'nearest'});
      });
    });
    catalog.hidden = Boolean(pageTitle || isCharacter);
    detail.hidden = !isCharacter;
    extra.hidden = !pageTitle;
    detail.replaceChildren(); extra.replaceChildren();
    if (!catalog.hidden) {
      document.title = '星见图鉴 · MOD 角色 Wiki';
      renderCatalog(); return;
    }
    options.onCatalogLeave?.();
    document.getElementById('character-grid').replaceChildren();
    const host = pageTitle ? extra : detail;
    status(host, '正在载入资料…');
    try {
      if (pageTitle) {
        document.title = `${pageTitle} · 星见图鉴`;
        if (hash === 'battle') {
          if (!window.WFBattleLoader) throw new Error('此份导出未包含放置挑战，请刷新或取得完整版本。');
          await window.WFBattleLoader.load();
        } else if (parts[0] === 'shops') {
          await Promise.all([window.WFWikiData.loadDungeons(), window.WFWikiData.loadEquipment(), window.WFWikiData.loadRewards()]);
        } else if (parts[0] === 'dungeons' || hash === 'five-boss') {
          const directory = await window.WFWikiData.loadDungeons();
          if (!current()) return;
          const item = hash === 'five-boss' ? directory.items.find((entry) => entry.legacyGuide === 'five-boss')
            : directory.items.find((entry) => entry.id === parts[1]);
          const isSeries = directory.items.some((entry) => entry.seriesId && entry.seriesId === parts[1]);
          if (item || isSeries || hash === 'five-boss') {
            await Promise.all([Promise.all([window.WFWikiData.loadEquipment(), window.WFWikiData.loadRewards()]).catch(() => {}),
              ...(hash === 'five-boss' || item?.legacyGuide === 'five-boss' ? [window.WFWikiData.loadBossGuide()] : [])]);
          }
        } else if (parts[0] !== 'tier-list' && !(parts[0] === 'community' && !parts[1])) await window.WFWikiData.loadEquipment();
        if (!current()) return;
        if (!window.renderWikiPage?.(hash, extra, data, ui)) status(extra, '此份导出尚未包含该页面。');
      } else {
        let id = '';
        try { id = decodeURIComponent(parts[1]); } catch { /* invalid links use the missing state */ }
        const character = await window.WFWikiData.loadCharacter(id);
        if (!current()) return;
        if (!character) {
          status(detail, '未找到这位角色，该角色不在本次导出的资料中。');
          const back = el('a', 'back-button', '‹ 返回角色列表'); back.href = '#'; detail.append(back);
        } else {
          document.title = `${text(character.name, '角色详情')} · 星见图鉴`;
          const base = `#character/${encodeURIComponent(id)}`;
          if (parts[2] === 'details') {
            window.renderWikiCharacter(detail, character, meta, ui, {initialTab: parts[3] || 'profile', summaryHref: base});
            if (location.protocol !== 'file:') window.WFCharacterViews?.record(id).catch(() => {});
          } else {
            window.renderWikiCharacterSummary(detail, character, meta, ui, {
              publicOverview:true, characters:data.characters,
              onOpenDetails: (tab) => {location.hash = `${base}/details/${tab || 'profile'}`;},
              onVariantNavigate: (variantId) => window.WFTeamInspector?.rememberVariant(variantId),
            });
            const navigation = el('nav', 'breadcrumbs'); navigation.setAttribute('aria-label', '返回角色列表');
            const back = el('a', 'back-button summary-back-link', '‹ 返回角色图鉴'); back.href = '#';
            navigation.append(back); detail.prepend(navigation);
          }
        }
      }
      if (current()) {
        window.WFTeamInspector?.attachReturn(host, hash, ui);
        window.scrollTo({top: 0});
      }
    } catch (error) {
      if (current()) {
        status(host, error.message || '资料暂时无法载入。', route);
        window.WFTeamInspector?.attachReturn(host, hash, ui);
      }
    }
  };
};
