/* Direction is independent of criterion; missing statistics always remain last. */
(() => {
  'use strict';
  window.WFCatalogSort = {create({sort, button, ratings, views, onChange}) {
    let direction = 'desc';
    const stable = (a, b) => window.WFCharacterOrder.compare(a, b);
    function paint() {
      button.textContent = direction === 'asc' ? '↑ 正序' : '↓ 倒序';
      button.setAttribute('aria-label', `当前${direction === 'asc' ? '正序' : '倒序'}，点击切换${direction === 'asc' ? '倒序' : '正序'}`);
      button.setAttribute('aria-pressed', String(direction === 'asc'));
      button.title = '只切换排序方向；未评分、未知查看次数始终排最后，同分票多优先';
    }
    button.addEventListener('click', () => {direction = direction === 'asc' ? 'desc' : 'asc'; paint(); onChange();});
    sort.addEventListener('change', onChange); paint();
    return {getDirection: () => direction, isViewsSort: () => sort.value === 'views',
      compare(a, b) {
        if (ratings.isRatingSort()) return ratings.compare(a, b, direction);
        if (sort.value === 'views') return views.compare(a, b, direction) || stable(a, b);
        const sign = direction === 'asc' ? 1 : -1;
        if (sort.value === 'name') return String(a.name || '').localeCompare(String(b.name || ''), 'zh-CN') * sign || stable(a, b);
        if (sort.value === 'rarity') return (Number(a.rarity) - Number(b.rarity)) * sign || stable(a, b);
        return stable(a, b) * sign;
      },
    };
  }};
})();
