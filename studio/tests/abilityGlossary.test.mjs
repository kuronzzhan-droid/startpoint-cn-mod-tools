import assert from "node:assert/strict";
import test from "node:test";
import { enumEntries, matches, numericMeaning } from "../src/abilityGlossary.ts";

const entry = { value: "410", official: "施加…迟缓效果", cn: "敌方状态冻结", en: "EnemyConditionFrozen", uses: 12 };
const glossary = {
  groups: { instant_content: { values: [entry] }, character_group: { values: [{ value: "Red" }, { value: "Blue" }] } },
  strengthCountKinds: { instant_content: ["410"] },
  formats: {
    percent: { divisor: 1000, unit: "%" },
    strength: { divisor: 1000, unit: "%", countDivisor: 100000 },
    scaled_frames: { divisor: 100000, unit: "帧", fps: 60 },
    frames: { divisor: 1, unit: "帧", fps: 60 },
    scaled_count: { divisor: 100000, unit: "次" },
    threshold: { divisor: 1000, unit: "%", countDivisor: 100000 },
  },
};

test("search accepts official words, literal names, English and numbers", () => {
  for (const query of ["迟缓", "冻结", "enemycondition", "410", "迟缓 410"]) assert.ok(matches(entry, query));
  assert.equal(matches(entry, "追击"), false);
});

test("scaled frames differ from raw cooltime frames", () => {
  assert.equal(numericMeaning(glossary, { format: "percent" }, "100000", []), "100%");
  assert.equal(numericMeaning(glossary, { format: "scaled_frames" }, "600000", []), "6 帧（0.1 秒）");
  assert.equal(numericMeaning(glossary, { format: "frames" }, "6000", []), "6000 帧（100 秒）");
  assert.equal(numericMeaning(glossary, { format: "scaled_count" }, "600000", []), "6 次");
});

test("zero, empty, None, unknown formats and unknown kinds produce no numeric noise", () => {
  for (const value of ["0", "", "(None)", "abc"]) assert.equal(numericMeaning(glossary, { format: "percent" }, value, []), null);
  assert.equal(numericMeaning(glossary, { format: "unknown" }, "100000", []), null);
  assert.equal(numericMeaning(glossary, { format: "strength", group: "instant_content", kindColumn: 0 }, "100000", ["9999"]), null);
});

test("count-like strength retains the descriptor's two-endpoint guard", () => {
  const rule = { format: "strength", group: "instant_content", kindColumn: 0, endpoints: [1, 2] };
  assert.equal(numericMeaning(glossary, rule, "200000", ["410", "200000", "300000"]), "2（计数 / 层级）");
  assert.equal(numericMeaning(glossary, rule, "200000", ["410", "200000", "150000"]), "200%");
  assert.equal(numericMeaning(glossary, { format: "threshold" }, "600000", []), "6（次 / 层 / 个，依类型）");
  assert.equal(numericMeaning(glossary, { format: "threshold" }, "50000", []), "50%");
});

test("unknown enum values remain distinguishable and group lists accept both delimiters", () => {
  assert.equal(enumEntries(glossary, { enum: "instant_content" }, "9999")[0].entry, undefined);
  assert.deepEqual(enumEntries(glossary, { enum: "character_group", multiple: true }, "Red/Blue,Unknown").map((e) => !!e.entry), [true, true, false]);
});
