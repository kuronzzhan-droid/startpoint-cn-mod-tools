// Exercise actual Preact vnode handlers without a browser or extra DOM dependency.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const studioRequire = createRequire(path.join(root, 'studio/package.json'));
const ts = studioRequire('typescript');
let state = [], cursor = 0;
const hooks = {
  useState(initial) { const i = cursor++; if (!(i in state)) state[i] = initial;
    return [state[i], value => { state[i] = value; }]; },
  useEffect() {},
};
function load(name, mocks = {}) {
  const exports = {};
  const js = ts.transpileModule(fs.readFileSync(path.join(root, name), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'preact' },
  }).outputText;
  vm.runInNewContext(js, { exports, structuredClone,
    require: name => name in mocks ? mocks[name] : name.endsWith('.css') ? {} : studioRequire(name),
  });
  return exports;
}
function flatten(v) {
  if (Array.isArray(v)) return v.flatMap(flatten);
  if (!v || typeof v !== 'object') return [];
  return [v, ...flatten(v.props?.children)];
}
const fields = load('studio/src/views/boss/ModeFields.tsx');
let changes = [];
const numeric = flatten(fields.ModeFields({ value: 2, path: ['budget'], change: (...v) => changes.push(v) }))
  .find(v => v.type === 'input');
numeric.props.onInput({ currentTarget: { value: '3', valueAsNumber: 3 } });
assert.equal(changes[0][1], 3);
const affix = flatten(fields.ModeFields({ value: ['one'], path: ['affixes'], change: (...v) => changes.push(v) }))
  .find(v => v.type === 'input');
affix.props.onInput({ currentTarget: { value: 'two, three' } });
assert.equal(JSON.stringify(changes[1][1]), '["two","three"]');
const workshop = load('studio/src/views/boss/ModeWorkshop.tsx', {
  'preact/hooks': hooks, '../../router': { href: () => '#' },
  '../../modeApi': {}, '../common': { Notice: 'Notice' }, '../Delivery': { DeliveryPanel: 'DeliveryPanel' },
  '../workshopKit': { useWorkshopAction: () => ({ busy: false, run: fn => fn() }) },
  './ModeFields': fields,
});
function reset(baseView = '1.4.10') {
  state = [{ version: '1.4.10', payload: { seed: 7 }, draft: { baseView, payload: { seed: 7 }, revision: 1 } },
    { seed: 7 }, { ok: true, canGenerate: true, blockers: [] }, null, '7', 'generate', 'edit'];
}
function render() { cursor = 0; return flatten(workshop.ModeWorkshop({ mode: 'rogue' })); }
reset();
let input = render().find(v => v.type === 'input');
input.props.onInput({ currentTarget: { value: '' } });
assert.equal(state[2], null, 'input immediately invalidates the old preview');
assert.equal(JSON.stringify(state[1]), '{"seed":7}', 'empty input never stores NaN/null');
let nodes = render();
assert.equal(nodes.find(v => v.type === 'button' && v.props.children === '只读预览与校验').props.disabled, true);
for (const invalid of ['-1', '4294967296', '1.5']) {
  reset(); render().find(v => v.type === 'input').props.onInput({ currentTarget: { value: invalid } });
  assert.equal(render().find(v => v.type === 'button' && v.props.children === '只读预览与校验').props.disabled, true);
}
reset(); render().find(v => v.type === 'input').props.onInput({ currentTarget: { value: '8' } });
assert.equal(state[1].seed, 8); assert.equal(state[2], null);
reset('1.4.9'); state[6] = 'delivery';
nodes = render();
assert.equal(nodes.find(v => v.type === 'DeliveryPanel').props.view.status.state, 'dirty');
assert.equal(nodes.find(v => v.type === 'fieldset').props.disabled, false); // Edit form remains usable.
assert.equal(nodes.filter(v => v.type === 'fieldset').at(-1).props.disabled, true);
reset(); state[6] = 'delivery';
assert.equal(render().filter(v => v.type === 'fieldset').at(-1).props.disabled, false);
console.log('frontend mode handlers: 8 scenarios passed');
