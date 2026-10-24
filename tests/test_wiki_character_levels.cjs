const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/character-levels.js'), 'utf8'), context);
const L = context.window.WFCharacterLevels;
const freeze = (value) => {
  if (value && typeof value === 'object') {Object.values(value).forEach(freeze); Object.freeze(value);}
  return value;
};

test('only explicit numeric pairs change; trigger arrows and dynamic formulas remain', () => {
  const value = '技能发动≥1 → 赋予2号位 攻击力 10%→20%，持续 16 + 能力1成长(2.5→5)秒';
  assert.equal(L.projectText(value, 'initial'), '技能发动≥1 → 赋予2号位 攻击力 10%，持续 16 + 能力1成长(2.5)秒');
  assert.equal(L.projectText(value), '技能发动≥1 → 赋予2号位 攻击力 20%，持续 16 + 能力1成长(5)秒');
  assert.equal(L.projectText('85→100% / -20%→-10% / 1.5→3秒', 'initial'), '85% / -20% / 1.5秒');
  assert.equal(L.projectText('1e+06→2e+06% / 1.2e-5→2.4e-5秒', 'initial'), '1e+06% / 1.2e-5秒');
  assert.equal(L.projectText('1→2→3，10秒→20%，(50) × 成长变量1%'), '1→2→3，10秒→20%，(50) × 成长变量1%');
});

test('skill energy follows explicit endpoints without changing forms or inventing missing energy', () => {
  const source = freeze({kind:'switched',level:'2',label:'切换后技能 · 进化技能',description:'技能说明',gauge:450,gaugeMin:500});
  const initial = L.projectEntry(source, 'initial', {kind:'skill'}), maximum = L.projectEntry(source, 'max', {kind:'skill'});
  assert.equal(initial.gauge, 500); assert.equal(maximum.gauge, 450);
  assert.equal(initial.level, '2'); assert.equal(initial.kind, 'switched'); assert.equal(initial.label, source.label);
  assert.match(initial.levelNote, /未提供独立初始文案/); assert.equal(source.gauge,450);
  const absent = L.projectEntry({gauge:450,description:'作者稿'}, 'initial', {kind:'skill'});
  assert.equal(absent.gauge,null); assert.match(absent.levelNote,/初始能量未记录/);
});

test('character projection is immutable, row-local and independent of base stat levels', () => {
  const source = freeze({stats:{levels:[{level:100,hp:5000}]},skills:[],
    leader:{descriptionSource:'数据行自动解析',description:'攻击力 10%→20%',rows:[{description:'攻击力 10%→20%'}]},
    abilities:[{descriptionSource:'游戏面板覆盖文案',description:'作者满级文案 100%',rows:[{description:'攻击力 50%→100%',restrictions:{operator:'AND',items:[{kind:'main'}]}}]}]});
  const before = JSON.stringify(source), initial = L.project(source, 'initial'), maximum = L.project(source);
  assert.equal(initial.leader.description,'攻击力 10%'); assert.equal(maximum.leader.description,'攻击力 20%');
  assert.equal(initial.abilities[0].description,'作者满级文案 100%');
  assert.equal(initial.abilities[0].rows[0].description,'攻击力 50%');
  assert.match(initial.abilities[0].levelNote,/保留为参考/);
  assert.equal(initial.abilities[0].rows[0].restrictions,source.abilities[0].rows[0].restrictions);
  assert.equal(initial.stats,source.stats); assert.equal(JSON.stringify(source),before);
  assert.match(L.projectEntry({descriptionSource:'数据行自动解析',description:'攻击力 50%'},'initial').levelNote,/未记录独立初始端点/);
});

test('numeric details and related programs select endpoints without calculating or summing', () => {
  const numeric = {notes:['箭头表示技能 Lv1→满级；能力成长、叠层成长另列。', '倍率为单次命中。'],rows:[{context:['延迟 1→2秒'],values:[{label:'倍率',value:'5→10倍 + 能力2成长(2→4)倍'}]}]};
  const source = freeze({numericDetails:numeric,relatedPrograms:[{numericDetails:numeric}]});
  const projected = L.projectEntry(source,'initial');
  assert.equal(projected.numericDetails.rows[0].values[0].value,'5倍 + 能力2成长(2)倍');
  assert.equal(projected.relatedPrograms[0].numericDetails.rows[0].context[0],'延迟 1秒');
  assert.equal(projected.numericDetails.notes[0],'当前显示初始技能值；能力成长、叠层成长另列。');
  assert.equal(L.projectEntry(source).numericDetails.notes[0],'当前显示满级技能值；能力成长、叠层成长另列。');
  assert.equal(projected.numericDetails.notes[1],numeric.notes[1]);
  const brief = L.projectEntry(source,'max',{includeNumeric:false});
  assert.equal(brief.numericDetails,numeric); assert.equal(brief.relatedPrograms,source.relatedPrograms);
});
