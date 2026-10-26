import assert from "node:assert/strict";
import test from "node:test";
import { build } from "esbuild";
import { fileURLToPath } from "node:url";

// Exercise the component's real VNode handlers, including dialog bubbling.
// Hooks are inert for this first-render regression; no browser or new DOM
// dependency is required. Native button activation is simulated after keydown.
const compiled = await build({
  entryPoints: [fileURLToPath(new URL("../src/views/Glossary.tsx", import.meta.url))],
  bundle: true, write: false, format: "esm", platform: "node", loader: { ".css": "empty" },
  plugins: [{ name: "render-fixture", setup(builder) {
    builder.onResolve({ filter: /^preact\/hooks$/ }, () => ({ path: "hooks", namespace: "fixture" }));
    builder.onResolve({ filter: /^\.\.\/api$/ }, () => ({ path: "api", namespace: "fixture" }));
    builder.onLoad({ filter: /.*/, namespace: "fixture" }, ({ path }) => ({ contents: path === "hooks"
      ? "export const useEffect = () => {}; export const useRef = () => ({current:null}); export const useState = v => [v, () => {}];"
      : "export const ability = {};", loader: "js" }));
  } }],
});
const { EnumPicker, CellMeaning } = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString("base64")}`);

const entry = { value: "391", en: "EnemyConditionAttackPoint", cn: "敌方状态攻击力", official: "…的攻击力…",
  officialKey: "ability_description_condition_content_attack", officialTemplate: "", officialArguments: {}, evidence: [], mappingStatus: "as3", uses: 1 };
const glossary = { groups: { instant_content: { label: "瞬发效果", values: [entry] } } };
const children = (node) => [node?.props?.children].flat(Infinity).filter(Boolean);
function find(node, predicate) {
  if (predicate(node)) return node;
  for (const child of children(node)) { const match = find(child, predicate); if (match) return match; }
}
function text(node) {
  if (typeof node === "string") return node;
  if (typeof node?.type === "function") return text(node.type(node.props));
  return children(node).map(text).join("");
}
function setup(values = [entry]) {
  const picks = [], closes = [];
  const tree = EnumPicker({ glossary: { groups: { instant_content: { label: "瞬发效果", values } } }, group: "instant_content",
    value: "410", onPick: (v) => picks.push(v), onClose: () => closes.push(true) });
  return { tree, picks, closes, dialog: find(tree, (n) => n?.props?.role === "dialog") };
}
function keydown(fixture, node, key, isComposing = false) {
  const event = { key, isComposing, defaultPrevented: false, stopped: false,
    preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this.stopped = true; } };
  node.props.onKeyDown?.(event);
  if (!event.stopped) fixture.dialog.props.onKeyDown?.(event);
  if (key === "Enter" && node.type === "button" && !event.defaultPrevented) node.props.onClick?.();
  return event;
}

test("Enter on Esc closes without selecting the first result or suppressing native activation", () => {
  const fixture = setup();
  const button = find(fixture.tree, (n) => n?.type === "button");
  assert.equal(keydown(fixture, button, "Enter").defaultPrevented, false);
  assert.deepEqual(fixture.picks, []);
  assert.equal(fixture.closes.length, 1);
});

test("Enter selects only from search or focusable list navigation; IME Enter is ignored", () => {
  for (const type of ["input", "ul"]) {
    const fixture = setup();
    const node = find(fixture.tree, (n) => n?.type === type);
    if (type === "ul") assert.equal(node.props.tabIndex, 0);
    keydown(fixture, node, "Enter", true);
    assert.deepEqual(fixture.picks, []);
    keydown(fixture, node, "Enter");
    assert.deepEqual(fixture.picks, ["391"]);
  }
});

test("empty results do not select; Escape from search still closes once", () => {
  const fixture = setup([]);
  const input = find(fixture.tree, (n) => n?.type === "input");
  keydown(fixture, input, "Enter");
  keydown(fixture, input, "Escape");
  assert.deepEqual(fixture.picks, []);
  assert.equal(fixture.closes.length, 1);
});

test("effect cell keeps 391 neutral for positive and negative strength rows", () => {
  for (const strength of ["-1500", "-3000", "1500", "3000"]) {
    const output = text(CellMeaning({ glossary, rule: { enum: "instant_content" }, value: "391", row: ["391", strength] }));
    assert.ok(output.includes("攻击力"));
    assert.doesNotMatch(output, /提升|降低/);
  }
});
