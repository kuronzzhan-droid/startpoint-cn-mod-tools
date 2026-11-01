import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

async function compile(path) {
  const source = await readFile(new URL(`../src/${path}`, import.meta.url), "utf8");
  return ts.transpileModule(source, { compilerOptions: {
    target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
    jsx: ts.JsxEmit.ReactJSX, jsxImportSource: "preact",
  } }).outputText;
}
const [requestSource, timelineSource, behaviorSource] = await Promise.all([
  compile("requests.ts"), compile("timelineApi.ts"), compile("views/boss/BossBehavior.tsx"),
]);

function modules(fetch) {
  const requests = {}, timeline = {};
  const globals = { AbortController, DOMException, URLSearchParams, structuredClone, fetch };
  vm.runInNewContext(requestSource, { ...globals, exports: requests });
  vm.runInNewContext(timelineSource, { ...globals, exports: timeline, require: name => {
    assert.ok(name === "./api" || name === "./requests");
    return requests;
  } });
  return { globals, ...timeline };
}

for (const [name, body] of [
  ["empty response", ""], ["HTML proxy response", "<html>Not found</html>"],
  ["JSON without error", "{}"], ["standard unknown route", '{"error":"未知接口"}'],
]) {
  test(`MovePlayer falls back to DSL on 404 ${name}`, async () => {
    const calls = [], effects = [], states = [], exports = {};
    const parsed = { program: "boss/move", duration: 30, events: [] };
    const { globals, timelineApi } = modules(async url => {
      calls.push(url);
      return url.includes("timeline-summary")
        ? new Response(body, { status: 404 }) : new Response(JSON.stringify(parsed));
    });
    const mocks = {
      "preact/hooks": { useRef: () => ({ current: null }), useEffect: fn => effects.push(fn),
        useState: value => [value, next => states.push(next)] },
      "preact/jsx-runtime": { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
      "../../timelineApi": { timelineApi }, "../common": { Notice: "Notice" },
      "../TimelinePreview": { TimelinePlayer: "TimelinePlayer" }, "../Delivery": {}, "./bossOps": {},
    };
    // Expose the real private component only inside this test's module sandbox.
    vm.runInNewContext(behaviorSource + "\nexports.MovePlayer = MovePlayer;", {
      ...globals, exports, require: name => {
        assert.ok(name in mocks, `unexpected import: ${name}`);
        return mocks[name];
      },
    });
    exports.MovePlayer({ quest: "quest", rev: "1", move: { path: "boss/move", enemy: "boss", slot: 0 }, onClose() {} });
    const cleanups = effects.map(effect => effect());
    await new Promise(setImmediate);
    assert.equal(calls.length, 2);
    assert.match(calls[0], /\/api\/boss\/quest\/timeline-summary\?/);
    assert.equal(calls[1], "/api/studio/timeline?path=boss%2Fmove&kind=subprogram");
    assert.ok(states.some(state => state?.program === parsed.program));
    assert.ok(states.some(state => typeof state === "string" && state.includes("基线视图")));
    assert.ok(!states.some(state => typeof state === "string" && state.includes("HTTP 404")));
    cleanups.forEach(cleanup => cleanup?.());
  });
}

test("cancelled boss summary propagates cancellation instead of starting a fallback read", async () => {
  let calls = 0;
  const { timelineApi } = modules((url, { signal }) => new Promise((resolve, reject) => {
    calls++;
    signal.addEventListener("abort", () => reject(new DOMException("cancelled", "AbortError")), { once: true });
  }));
  const controller = new AbortController();
  const reading = timelineApi.bossMoves("quest", undefined, controller.signal);
  controller.abort();
  await assert.rejects(reading, { name: "AbortError" });
  assert.equal(calls, 1);
});
