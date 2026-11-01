import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/requests.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const requests = await import("data:text/javascript;base64," + Buffer.from(outputText).toString("base64"));
const { get, invalidateReads, readActivity } = requests;

function mockFetch() {
  const calls = [];
  globalThis.fetch = (url, init) => new Promise((resolve, reject) => {
    calls.push({ url, signal: init.signal, resolve: (value) => resolve({ ok: true, json: async () => value }), reject });
    init.signal.addEventListener("abort", () => reject(new DOMException("cancelled", "AbortError")), { once: true });
  });
  return calls;
}

test("concurrent identical reads share one fetch; later reads revalidate", async () => {
  const calls = mockFetch();
  const first = get("/same"), second = get("/same");
  assert.equal(calls.length, 1);
  calls[0].resolve({ revision: 1 });
  assert.deepEqual(await Promise.all([first, second]), [{ revision: 1 }, { revision: 1 }]);
  const later = get("/same");
  assert.equal(calls.length, 2);
  calls[1].resolve({ revision: 2 });
  assert.deepEqual(await later, { revision: 2 });
  assert.equal(readActivity().count, 0);
});

test("leaving one subscriber keeps the other subscriber's request alive", async () => {
  const calls = mockFetch();
  const a = new AbortController(), b = new AbortController();
  const first = get("/shared", a.signal), second = get("/shared", b.signal);
  a.abort();
  await assert.rejects(first, { name: "AbortError" });
  assert.equal(calls[0].signal.aborted, false);
  calls[0].resolve({ ok: true });
  assert.deepEqual(await second, { ok: true });
});

test("last subscriber cancellation aborts the fetch and allows a clean retry", async () => {
  const calls = mockFetch();
  const controller = new AbortController();
  const first = get("/cancel", controller.signal);
  controller.abort();
  await assert.rejects(first, { name: "AbortError" });
  assert.equal(calls[0].signal.aborted, true);
  const retry = get("/cancel");
  assert.equal(calls.length, 2);
  calls[1].resolve("fresh");
  assert.equal(await retry, "fresh");
});

test("draft invalidation prevents joining an older request still in flight", async () => {
  const calls = mockFetch();
  const oldRead = get("/draft");
  invalidateReads();
  const newRead = get("/draft");
  assert.equal(calls.length, 2);
  calls[0].resolve({ revision: 1 });
  await oldRead;
  const other = get("/draft");
  assert.equal(calls.length, 2, "old completion must not delete the newer in-flight entry");
  calls[1].resolve({ revision: 2 });
  assert.deepEqual(await Promise.all([newRead, other]), [{ revision: 2 }, { revision: 2 }]);
});

test("a failed read is never retained", async () => {
  const calls = mockFetch();
  const failed = get("/error");
  calls[0].reject(new Error("broken"));
  await assert.rejects(failed, /broken/);
  const retry = get("/error");
  assert.equal(calls.length, 2);
  calls[1].resolve("recovered");
  assert.equal(await retry, "recovered");
});

test("shared reads give each subscriber independent nested objects and arrays", async () => {
  const calls = mockFetch();
  const reads = [get("/mutable"), get("/mutable"), get("/mutable")];
  calls[0].resolve({ rows: [{ value: 2 }, { value: 1 }] });
  const [first, second, third] = await Promise.all(reads);
  first.rows.sort((a, b) => a.value - b.value);
  first.rows[0].value = 99;
  second.rows.splice(0, 1);
  assert.deepEqual(third, { rows: [{ value: 2 }, { value: 1 }] });
  assert.deepEqual(second, { rows: [{ value: 1 }] });
  assert.equal(calls.length, 1);
});

test("cancelling one of three subscribers preserves isolation for the survivors", async () => {
  const calls = mockFetch();
  const controller = new AbortController();
  const cancelled = get("/mutable-cancel", controller.signal);
  const first = get("/mutable-cancel"), second = get("/mutable-cancel");
  controller.abort();
  await assert.rejects(cancelled, { name: "AbortError" });
  calls[0].resolve({ values: [1, 2] });
  const [a, b] = await Promise.all([first, second]);
  a.values.push(3);
  assert.deepEqual(b, { values: [1, 2] });
  assert.equal(calls.length, 1);
});
