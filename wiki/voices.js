/* Paged, grouped disclosures. Native audio is created only when a row is opened. */
window.renderWikiVoices = function renderWikiVoices(target, entries, character, ui) {
  'use strict';
  const {el, text, safeUrl, safeData} = ui;
  const paragraph = (value, className) => el('p', className, value);
  const note = (value) => el('div', 'note-box', value);
  const categoryOf = (voice) => text(voice.category).trim() || '其他';
  const categoryLabels = new Map([['主页', 'Home · 主页'], ['战斗', '战斗语音'], ['登录', '登录语音']]);
  const categoryLabel = (value) => categoryLabels.get(value) || value;
  const pauseWithin = (node) => node.querySelectorAll('audio').forEach((audio) => audio.pause());
  const caret = () => {const node = el('span', 'voice-toggle', '▸'); node.setAttribute('aria-hidden', 'true'); return node;};
  target.classList.add('voice-section');
  const audioCount = entries.filter((voice) => safeUrl(voice.audio)).length;
  const zhCount = entries.filter((voice) => text(voice.zh).trim()).length;
  target.append(paragraph(`${entries.length} 条语音记录 · ${audioCount} 条可试听 · ${zhCount} 条有中文台词。展开条目查看台词，点击播放时才加载音频，同一时间只播放一条。`, 'voice-summary'));
  if (!entries.length) {target.append(note('本次快照中未找到该角色的可用语音。')); return;}
  target.append(paragraph('按已收录场景分类；现有资料未标注觉醒前后阶段，不作推测。', 'voice-stage-note'));
  const toolbar = el('div', 'voice-toolbar');
  const search = el('input'); search.type = 'search'; search.placeholder = '搜索语音场景、原文或中文台词…';
  search.setAttribute('aria-label', '搜索本角色语音');
  const category = el('select'); category.setAttribute('aria-label', '语音场景筛选');
  category.append(el('option', '', '全部场景')); category.firstChild.value = '';
  [...new Set(entries.map(categoryOf))].forEach((value) => {
    const option = el('option', '', categoryLabel(value)); option.value = value; category.append(option);
  });
  const translation = el('select'); translation.setAttribute('aria-label', '台词完整度筛选');
  [['', '全部台词'], ['translated', '已有中文'], ['missing', '中文待补录']].forEach(([value, label]) => {
    const option = el('option', '', label); option.value = value; translation.append(option);
  });
  toolbar.append(search, category, translation);
  const count = el('div', 'voice-match-count'); count.setAttribute('role', 'status');
  const results = el('div', 'voice-list');
  const more = el('button', 'voice-load-more'); more.type = 'button';
  target.append(toolbar, count, results, more);
  let matching = entries, shown = 0;
  const groups = new Map(), totals = new Map();
  const sourceLabels = {'current-speech': '游戏内字幕', 'package-speech': '独立角色包字幕',
    'hash-matched-script': '音频匹配台词稿', 'hash-matched-original': '音频匹配原版台词', missing: '暂无台词资料'};

  function fillVoice(card, voice) {
    const body = el('div', 'voice-entry-body');
    [['原文', voice.ja, '原文待补录', 'original'], ['中文', voice.zh, '中文台词 / 翻译待补录', 'translated']].forEach(([label, value, missing, style]) => {
      const line = el('dl', `voice-text ${style}`);
      line.append(el('dt', '', label), el('dd', value ? '' : 'muted', text(value, missing))); body.append(line);
    });
    if (safeUrl(voice.audio)) {
      const audio = el('audio'); audio.controls = true; audio.preload = 'none'; audio.src = safeUrl(voice.audio);
      audio.setAttribute('aria-label', `${text(character.name)} ${text(voice.label, '角色')}语音试听`);
      audio.addEventListener('play', () => results.querySelectorAll('audio').forEach((other) => {if (other !== audio) other.pause();}));
      audio.addEventListener('error', () => {
        if (!body.querySelector('.audio-unavailable')) body.append(paragraph('此音频无法读取，请检查媒体文件是否完整。', 'audio-unavailable'));
      });
      body.append(audio);
    } else body.append(paragraph('本次快照未包含音频文件。', 'audio-unavailable'));
    if (voice.textSource) {
      const source = text(safeData(voice.textSource)).split(' + ').map((part) => sourceLabels[part] || part).join(' + ');
      body.append(paragraph(`台词来源：${source}`, 'voice-source'));
    }
    card.append(body);
  }

  function voiceCard(voice) {
    const card = el('details', 'voice-card'), summary = el('summary', 'voice-header');
    summary.append(caret(), el('span', 'voice-entry-label', text(voice.label, '角色语音')),
      el('span', 'voice-entry-state', text(voice.zh).trim() ? '中文' : '待翻译'));
    card.append(summary); let filled = false;
    card.addEventListener('toggle', () => {
      if (!card.open) {pauseWithin(card); return;}
      if (!filled) {fillVoice(card, voice); filled = true;}
    });
    return card;
  }

  function groupFor(key) {
    if (groups.has(key)) return groups.get(key);
    const section = el('details', 'voice-group'); section.open = false;
    const summary = el('summary', 'voice-group-header'), tally = el('span', 'voice-group-count');
    summary.append(caret(), el('span', 'voice-group-label', categoryLabel(key)), tally);
    const body = el('div', 'voice-group-body'); section.append(summary, body);
    section.addEventListener('toggle', () => {if (!section.open) pauseWithin(section);});
    const group = {body, tally, count: 0}; groups.set(key, group); results.append(section); return group;
  }

  function addPage() {
    const next = matching.slice(shown, shown + 24);
    for (const voice of next) {
      const key = categoryOf(voice), group = groupFor(key); group.body.append(voiceCard(voice)); group.count++;
      group.tally.textContent = `${group.count} / ${totals.get(key)} 条`;
      group.tally.title = '当前已显示 / 筛选结果总数；可继续加载剩余语音';
    }
    shown += next.length; count.textContent = `找到 ${matching.length} 条，已显示 ${shown} 条`;
    more.hidden = shown >= matching.length; more.textContent = `继续显示语音（剩余 ${matching.length - shown} 条）`;
  }

  function filter() {
    const query = search.value.trim().toLocaleLowerCase('zh-CN');
    matching = entries.filter((voice) => (!category.value || categoryOf(voice) === category.value)
      && (!translation.value || (translation.value === 'translated' ? text(voice.zh).trim() : !text(voice.zh).trim()))
      && (!query || [voice.label, categoryLabel(categoryOf(voice)), voice.ja, voice.zh].map((value) => text(value)).join(' ').toLocaleLowerCase('zh-CN').includes(query)));
    pauseWithin(results); results.replaceChildren(); groups.clear(); totals.clear(); shown = 0;
    matching.forEach((voice) => {const key = categoryOf(voice); totals.set(key, (totals.get(key) || 0) + 1);});
    addPage();
    if (!matching.length) results.append(note('没有匹配的语音，试试其他关键词或场景。'));
  }
  search.addEventListener('input', filter); category.addEventListener('change', filter);
  translation.addEventListener('change', filter); more.addEventListener('click', addPage); filter();
};
