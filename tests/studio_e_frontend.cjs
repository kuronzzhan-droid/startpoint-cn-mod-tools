// Actual Preact handlers, offline and without a DOM or local game inputs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const studioRequire = createRequire(path.join(root, 'studio/package.json'));
const ts = studioRequire('typescript');
let state = [], cursor = 0, effects = [];
const hooks = {
  useState(initial) {
    const i = cursor++;
    if (!(i in state)) state[i] = typeof initial === 'function' ? initial() : initial;
    return [state[i], value => { state[i] = typeof value === 'function' ? value(state[i]) : value; }];
  },
  useEffect(fn) { effects.push(fn); },
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
const route = load('studio/src/router.ts', { 'preact/hooks': hooks });
assert.equal(route.parse('#/opening').work, 'opening');
assert.equal(route.href({ work: 'opening' }), '#/opening');
assert.equal(route.parse('#/content/boss/new').wizard, true, 'simple mode stays reachable');
assert.equal(route.parse('#/content/boss/q/scene-spec/delivery').tab, 'delivery');

const scene = load('studio/src/views/boss/BossSceneWorkshop.tsx', {
  'preact/hooks': hooks, '../../router': route,
  '../../sceneApi': { scenes: { schemaUrl: '/api/scenes/schema' }, sceneDeliveries: {} },
  '../common': { Notice: 'Notice' }, '../Delivery': { DeliveryPanel: 'DeliveryPanel' },
  '../workshopKit': { useWorkshopAction: () => ({ busy: false, run: fn => fn() }) },
  './SceneSpecFields': { SceneSpecFields: 'SceneSpecFields' }, './ScenePreview': { ScenePreview: 'ScenePreview' },
  './SceneCloneForm': { SceneCloneForm: 'SceneCloneForm', SceneCreationSummary: 'SceneCreationSummary' },
});
const spec = { schema: 'scene', id: 'hell-pumpkin', name: 'Synthetic', event: { id: '1', settings: [] },
  tiers: [], phases: [], summons: [], mechanisms: [], trials: [], shops: [], drops: [] };
const approved = { ok: true, canGenerate: true, checks: [], blockers: [] };
function resetScene(baseView = '1.4.10') {
  state = [{ version: '1.4.10', payload: spec, draft: { baseView, payload: spec, revision: 1 } },
    JSON.stringify(spec), approved, null, {}, 'generate'];
}
function renderScene(tab = 'edit') { cursor = 0; effects = []; return flatten(scene.BossSceneWorkshop({ tab })); }
for (const invalid of ['', 'null', '[]', '5', '{']) assert.equal(scene.parseSceneText(invalid).payload, null);
resetScene();
renderScene().find(v => v.type === 'textarea').props.onInput({ currentTarget: { value: '{' } });
assert.equal(state[2], null, 'raw edit invalidates previous preview immediately');
assert.equal(renderScene().find(v => v.type === 'button' && v.props.children === '只读编译与校验').props.disabled, true);
resetScene();
renderScene().find(v => v.type === 'SceneSpecFields').props.change(['tiers', 0, 'value'], undefined, 'invalid number');
assert.equal(state[2], null);
assert.equal(renderScene('delivery').filter(v => v.type === 'fieldset').at(-1).props.disabled, true);
resetScene(); state[1] = JSON.stringify({ ...spec, sourceVersion: {}, event: { ...spec.event, name: {} } });
assert.ok(renderScene().every(v => 'type' in v), 'malformed advanced metadata never becomes an object child');
resetScene('1.4.9');
assert.equal(renderScene('delivery').filter(v => v.type === 'fieldset').at(-1).props.disabled, true, 'stale draft cannot build');
resetScene();
let nodes = renderScene('delivery');
assert.equal(nodes.filter(v => v.type === 'fieldset').at(-1).props.disabled, false);
assert.equal(nodes.find(v => v.type === 'DeliveryPanel').props.allowServerApply, false, 'scene delivery has no server apply UI');
resetScene(); state[2] = { ...approved, canGenerate: false, blockers: ['input unavailable'] };
assert.equal(renderScene('delivery').filter(v => v.type === 'fieldset').at(-1).props.disabled, true);
resetScene(); state[0] = { version: '1.4.10', payload: null, spec: null, draft: null };
state[1] = ''; state[2] = { ok: false, canGenerate: false, blockers: ['template unavailable'], checks: [] };
assert.doesNotThrow(() => renderScene(), 'missing real data stays a visible blocked result');
assert.equal(renderScene('delivery').filter(v => v.type === 'fieldset').at(-1).props.disabled, true);

const preview = load('studio/src/views/boss/ScenePreview.tsx', {
  '../common': { Notice: 'Notice' }, '../rules': { RuleChips: 'RuleChips', ruleCounts: () => ({}) },
  './BossChecks': { BossRuleList: 'BossRuleList' },
});
const previewNodes = flatten(preview.ScenePreview({ result: { ...approved,
  summary: { tables: 2, resources: 3, serverFiles: 1 },
  outputSha256: { 'resource/path': 'sha-client', 'server:event.json': 'sha-server' },
  audit: { aligned: false, differences: [{ logical: 'resource/path', path: ['a', 1], reason: 'different' }] },
} }));
assert.equal(previewNodes.filter(v => v.type === 'td' && v.props.children === 'sha-server').length, 1,
  'actual API hash map is rendered as file rows, never as an object child');

const fields = load('studio/src/views/boss/SceneSpecFields.tsx', { 'preact/hooks': hooks });
const fieldTree = flatten(fields.SceneSpecFields({ spec: { ...spec,
  summons: [{ id: 'count', kind: 'summon', value: 2, bindings: [] }] }, change: () => {} }));
const settingsNode = fieldTree.find(v => typeof v.type === 'function' && v.props.title === '召唤物');
const valueNode = flatten(settingsNode.type(settingsNode.props)).find(v => typeof v.type === 'function');
let changes = [];
cursor = 0; state = ['2', null];
let input = flatten(valueNode.type({ ...valueNode.props, change: (...args) => changes.push(args) })).find(v => v.type === 'input');
input.props.onInput({ currentTarget: { value: '' } });
assert.equal(changes[0][1], undefined);
assert.ok(changes[0][2], 'empty number is an explicit invalid field, never NaN or zero');
input.props.onInput({ currentTarget: { value: '3' } });
assert.equal(changes[1][1], 3);
assert.equal(changes[1][2], null);

const cloneForm = load('studio/src/views/boss/SceneCloneForm.tsx', { 'preact/hooks': hooks });
const clonedNames = [];
const renderClone = () => { cursor = 0; return flatten(cloneForm.SceneCloneForm({ disabled: false,
  onClone: name => clonedNames.push(name) })); };
state = [''];
assert.equal(renderClone().find(v => v.type === 'button').props.disabled, true);
renderClone().find(v => v.type === 'input').props.onInput({ currentTarget: { value: '  Synthetic Event  ' } });
renderClone().find(v => v.type === 'button').props.onClick();
assert.equal(clonedNames[0], 'Synthetic Event', 'new activity name is explicit and trimmed');
cursor = 0;
assert.equal(flatten(cloneForm.SceneCloneForm({ disabled: true, onClone: () => {} }))
  .find(v => v.type === 'button').props.disabled, true, 'invalid spec cannot be cloned');

const requests = [];
const api = load('studio/src/openingApi.ts', { './api': { get: url => { requests.push(url); return Promise.resolve({}); } } });
api.opening.read('test175', 'test client');
assert.equal(requests[0], '/api/studio/opening?server=test175&clientProfile=test%20client');
const cloneRequests = [];
const sceneClient = load('studio/src/sceneApi.ts', { './api': { deliveryApi: () => ({}),
  post: (url, body) => { cloneRequests.push({ url, body }); return Promise.resolve({}); } } });
sceneClient.scenes.clone(spec, 'New Event');
assert.equal(cloneRequests[0].url, '/api/scenes/hell-pumpkin/clone');
assert.deepEqual(Object.keys(cloneRequests[0].body).sort(), ['name', 'payload'], 'IDs are allocated by the read-only backend, not guessed in the UI');
let resolveOld, resolveNew;
const opening = load('studio/src/views/OpeningConsole.tsx', {
  'preact/hooks': hooks, '../clientProfile': { useClientProfile: () => ({ selected: 'test', label: v => v }) },
  '../openingApi': { opening: { read: server => new Promise(resolve => { if (server === 'local') resolveOld = resolve; else resolveNew = resolve; }) } },
  './common': { Notice: 'Notice' }, './rules': { RuleList: 'RuleList' },
});
state = ['local', null, null, 0]; cursor = 0; effects = [];
opening.OpeningConsole(); const cancelOld = effects[0]();
state[0] = 'test175'; cursor = 0; effects = []; opening.OpeningConsole(); cancelOld(); effects[0]();
resolveOld({ server: 'local' }); resolveNew({ server: 'test175' });
setImmediate(async () => {
  assert.equal(state[1].server, 'test175', 'late reply for previous target cannot replace the current target report');
  const report = { status: 'pending', source: { version: '1.4.12', baseVersion: '1.4.10', edgeCount: 2 },
    target: { version: '1.4.10', configured: true }, runtime: '未执行', checks: [], missingEdges: [],
    clientCapabilities: { profile: 'test', available: true, providesCount: 0, status: 'unknown', requires: [], missing: [], unknownEdges: ['1.4.12'], checks: [] },
    manualSteps: ['手工核对'], rollback: '版本只往前，以修正边恢复行为',
    entryLinks: [{ id: 'rehearsal', label: '预演说明', href: '/api/studio/opening/docs/rehearsal' }] };
  const result = flatten(opening.OpeningResult({ report }));
  assert.equal(result.filter(v => v.type === 'button').length, 0, 'checklist contains no execution buttons');
  assert.equal(result.find(v => v.type === 'a').props.href, '/api/studio/opening/docs/rehearsal');
  const savedDraft = { baseView: '1.4.10', revision: 1, payload: spec };
  const cloned = { ...spec, id: 'scene-300098', name: 'New Event', event: { id: '300098', settings: [] },
    creation: { sourceEvent: '300097', tableTargets: [], resourceTargets: [] } };
  const clonePreview = { ...approved, summary: { tiers: 5 } };
  const recovering = load('studio/src/views/boss/BossSceneWorkshop.tsx', {
    'preact/hooks': hooks, '../../router': route,
    '../../sceneApi': { scenes: { schemaUrl: '/api/scenes/schema', save: async () => ({ ...approved, draft: savedDraft }),
      clone: async () => ({ payload: cloned, preview: clonePreview, allocation: { reserved: false } }) },
      sceneDeliveries: { finished: async () => null } },
    '../common': { Notice: 'Notice' }, '../Delivery': { DeliveryPanel: 'DeliveryPanel' },
    '../workshopKit': { useWorkshopAction: () => ({ busy: false, run: fn => fn() }) },
    './SceneSpecFields': { SceneSpecFields: 'SceneSpecFields' }, './ScenePreview': { ScenePreview: 'ScenePreview' },
    './SceneCloneForm': { SceneCloneForm: 'SceneCloneForm', SceneCreationSummary: 'SceneCreationSummary' },
  });
  state = [{ version: '1.4.10', payload: null, spec: null, draft: null }, JSON.stringify(spec), approved, null, {}, 'generate'];
  cursor = 0;
  const savedNodes = flatten(recovering.BossSceneWorkshop({}));
  await savedNodes.find(v => v.type === 'button' && v.props.children === '保存独立草稿').props.onClick();
  assert.equal(state[0].payload, spec, 'saving an imported spec restores a usable saved payload after missing local data');
  assert.equal(state[0].draft, savedDraft);
  cursor = 0;
  await flatten(recovering.BossSceneWorkshop({})).find(v => v.type === 'SceneCloneForm').props.onClone('New Event');
  assert.equal(JSON.parse(state[1]).id, 'scene-300098');
  assert.equal(state[2], clonePreview, 'clone uses its fresh preview rather than retaining parent checks');
  cursor = 0;
  assert.equal(flatten(recovering.BossSceneWorkshop({ tab: 'delivery' })).filter(v => v.type === 'fieldset').at(-1).props.disabled,
    true, 'a cloned spec must be saved before delivery even if the previous draft was saved');
  assert.doesNotThrow(() => cloneForm.SceneCreationSummary({ spec: { creation: true } }), 'invalid advanced JSON does not crash the creation summary');
  sceneClient.scenes.save(cloned, 0);
  assert.equal(cloneRequests[1].url, '/api/scenes/scene-300098/save', 'cloned spec saves to its own spec.id slot');
  const dateTree = flatten(fields.SceneSpecFields({ spec: { ...spec,
    shops: [{ id: '9730001', settings: [{ id: 'c26', kind: 'shop', value: '2000-01-01 00:00:00',
      bindings: [{ table: 'master/shop/event_item_shop.orderedmap', path: ['9730001'], column: 26 }] }] }] }, change: () => {} }));
  const shopGroup = dateTree.find(v => typeof v.type === 'function' && v.props.title === '商店');
  const shopSettings = flatten(shopGroup.type(shopGroup.props)).find(v => typeof v.type === 'function' && v.props?.settings);
  const dateEditor = flatten(shopSettings.type(shopSettings.props)).find(v => typeof v.type === 'function' && v.props?.setting);
  const dateChanges = [];
  cursor = 0; state = ['2000-01-01 00:00:00', null];
  const dateInput = flatten(dateEditor.type({ ...dateEditor.props, change: (...args) => dateChanges.push(args) })).find(v => v.type === 'input');
  dateInput.props.onInput({ currentTarget: { value: 'not-a-date' } });
  assert.equal(dateChanges[0][1], undefined);
  assert.ok(dateChanges[0][2], 'invalid date in shop c26 is blocked immediately in UI');
  dateInput.props.onInput({ currentTarget: { value: '2026-10-31 12:00:00' } });
  assert.equal(dateChanges[1][1], '2026-10-31 12:00:00');
  assert.equal(dateChanges[1][2], null);
  console.log('studio E frontend: 24 scenarios passed');
});
