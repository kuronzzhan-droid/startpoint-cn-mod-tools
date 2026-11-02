import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/clientProfile.ts", import.meta.url), "utf8");
let output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
output = output.replace(/import [^;]+ from "preact\/hooks";/, "const useEffect = () => {}, useRef = () => {}, useState = () => {};");
output = output.replace(/import [^;]+ from "\.\/api";/, "const { drafts, get, post } = globalThis.profileApi;");
globalThis.window = { addEventListener() {} };
const calls = [];
let version = 1;
globalThis.profileApi = {
  drafts: {}, get: async () => ({}),
  post: async (url, body) => {
    calls.push({ url, body });
    return { rows: Object.fromEntries(body.rows.map(row => [row.id, { version, url }])) };
  },
};
const { rowCaps } = await import("data:text/javascript;base64," + Buffer.from(output).toString("base64"));
const row = (id) => ({ id, table: "ability", key: "same", cells: ["422", "shared-reference"] });

test("same rows from simultaneous editors are batched, with each caller's IDs preserved", async () => {
  calls.length = 0;
  const [first, second] = await Promise.all([rowCaps("one", [row("a")]), rowCaps("one", [row("b")])]);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].body.rows.length, 1);
  assert.equal(first.a.version, 1);
  assert.equal(second.b.version, 1);
});

test("later identical cells revalidate referenced content instead of retaining stale capabilities", async () => {
  calls.length = 0;
  version = 2;
  const result = await rowCaps("one", [row("a")]);
  assert.equal(calls.length, 1);
  assert.equal(result.a.version, 2);
});

test("identical rows belonging to different drafts cannot reuse each other's response", async () => {
  calls.length = 0;
  const [first, second] = await Promise.all([rowCaps("one", [row("a")]), rowCaps("two", [row("a")])]);
  assert.equal(calls.length, 2);
  assert.match(first.a.url, /\/one\//);
  assert.match(second.a.url, /\/two\//);
});
