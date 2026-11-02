import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const require = createRequire(import.meta.url);
const source = await readFile(new URL("../src/views/boss/ModeWorkshop.tsx", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
  jsx: ts.JsxEmit.ReactJSX, jsxImportSource: "preact",
} });

test("changing the mode aborts the previous read and discards a late response", async () => {
  const states = [], effects = [], calls = [];
  let cursor = 0;
  const hooks = {
    useState(initial) {
      const i = cursor++;
      if (!(i in states)) states[i] = initial;
      return [states[i], value => { states[i] = value; }];
    },
    useEffect(effect) { effects.push(effect); },
  };
  const mocks = {
    "preact/hooks": hooks,
    "../../modeApi": { modes: { read(mode, signal) {
      return new Promise(resolve => calls.push({ mode, signal, resolve }));
    } } },
    "../../router": { href: () => "#" },
    "../common": { Notice: "Notice" }, "../Loading": { Loading: "Loading" },
    "../Delivery": { DeliveryPanel: "DeliveryPanel" },
    "../workshopKit": { useWorkshopAction: () => ({ busy: false }) },
    "./ModeFields": { ModeFields: "ModeFields" },
  };
  const exports = {};
  vm.runInNewContext(outputText, { exports, AbortController, structuredClone,
    require: name => name in mocks ? mocks[name] : name.endsWith(".css") ? {} : require(name),
  });
  exports.ModeWorkshop({ mode: "five" });
  const leaveFirst = effects.pop()();
  assert.equal(calls[0].signal.aborted, false);
  leaveFirst();
  assert.equal(calls[0].signal.aborted, true);
  cursor = 0;
  exports.ModeWorkshop({ mode: "rogue" });
  const leaveSecond = effects.pop()();
  const latest = { payload: { seed: 42 }, version: "fresh" };
  calls[1].resolve(latest);
  await Promise.resolve();
  assert.equal(states[0], latest);
  calls[0].resolve({ payload: { rounds: [] }, version: "old" });
  await Promise.resolve();
  assert.equal(states[0], latest, "old mode response must not overwrite the new mode");
  leaveSecond();
});
