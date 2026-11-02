import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const sources = new Map(await Promise.all([
  "requests", "api", "clientProfile", "modeApi", "craftApi", "batchApi", "bossApi", "weaponApi", "studioApi",
].map(async name => {
  const source = await readFile(new URL(`../src/${name}.ts`, import.meta.url), "utf8");
  return ["./" + name, ts.transpileModule(source, { compilerOptions: {
    target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
  } }).outputText];
})));

function harness() {
  const modules = new Map(), calls = [];
  function load(name) {
    if (name === "preact/hooks") return {};
    if (modules.has(name)) return modules.get(name);
    assert.ok(sources.has(name), `unexpected import: ${name}`);
    const exports = {};
    modules.set(name, exports);
    vm.runInNewContext(sources.get(name), {
      exports, require: load, AbortController, DOMException, structuredClone, setTimeout,
      document: { querySelector: () => ({ content: "test-token" }) },
      window: { addEventListener() {} },
      fetch: (url, init) => {
        const call = { url, init };
        calls.push(call);
        if (init.method !== "POST") return new Promise(resolve => { call.resolve = resolve; });
        const body = JSON.parse(init.body);
        return Promise.resolve(new Response(JSON.stringify({
          ok: true, questId: "1", weaponId: "1", characterId: "1", checks: [],
          rows: Object.fromEntries((body.rows ?? []).map(row => [row.id, { compatible: true }])),
        })));
      },
    });
    return exports;
  }
  return { calls, api: load("./api"), profile: load("./clientProfile"),
    ...load("./modeApi"), ...load("./craftApi"), ...load("./batchApi"),
    ...load("./bossApi"), ...load("./weaponApi"), ...load("./studioApi") };
}

const readonly = {
  "ability check": h => h.api.ability.check("1", {}),
  "text lint": h => h.api.ability.lint("1", {}),
  "pixel check": h => h.api.drafts.checkPixel("1", {}),
  "pixel remap dry run": h => h.api.workshop.remap("1", { dryRun: true }),
  "pixel generation preview": h => h.api.workshop.generate("1", { save: false }),
  "pixel import dry run": h => h.api.scratchApi.importSet("1", { dryRun: true }),
  "scratch bind dry run": h => h.api.scratchApi.bind("scratch-one", { dryRun: true }),
  "pixel precheck": h => h.craft.precheck("1", {}),
  "mode preview": h => h.modes.preview("five", {}),
  "batch parsing": h => h.batch.parse("value"),
  "balance preview": h => h.batch.balance({}),
  "variants preview": h => h.batch.variants({}),
  "row capabilities": h => h.profile.rowCaps("1", [{ id: "r", table: "ability", key: "1", cells: ["422"] }]),
  "delivery apply dry run": h => h.api.deliveryApi("/api").apply("candidate", "local", true),
  "boss preview": h => h.boss.preview("1", {}),
  "weapon preview": h => h.weapons.preview({ operation: "weapon_clone", weapon: {} }),
  "weapon icon preview": h => h.weaponIcons.preview("1", {}),
  "weapon set preview": h => h.weaponSet.preview("1", {}),
  "character clone preview": h => h.studio.previewClone({}),
};

const mutations = {
  "default POST": h => h.api.post("/api/mutation", {}),
  "ability apply": h => h.api.ability.apply("1", {}),
  "pixel save": h => h.api.drafts.savePixel("1", {}),
  "portrait source upload": h => h.api.drafts.uploadPortrait("1", "normal", "png"),
  "portrait save": h => h.api.drafts.savePortrait("1", {}),
  "speech save": h => h.api.drafts.addSpeech("1", []),
  "voice save": h => h.api.drafts.saveVoice("1", {}),
  "draft save": h => h.api.drafts.save("1"),
  "draft revert": h => h.api.drafts.revert("1", "change"),
  "pixel remap save": h => h.api.workshop.remap("1", {}),
  "pixel generation save": h => h.api.workshop.generate("1", { save: true }),
  "pixel import save": h => h.api.scratchApi.importSet("1", {}),
  "scratch bind save": h => h.api.scratchApi.bind("scratch-one", {}),
  "scratch create": h => h.api.scratchApi.create({}),
  "scratch rename": h => h.api.scratchApi.rename("scratch-one", {}),
  "scratch remove": h => h.api.scratchApi.remove("scratch-one"),
  "pixel precheck apply": h => h.craft.precheck("1", { apply: true }),
  "atlas repack": h => h.craft.applyRepack("1", "pixelart"),
  "handoff notes": h => h.craft.saveNotes("1", {}),
  "mode save": h => h.modes.save("five", {}, 0),
  "remember balance mapping": h => h.batch.remember({}),
  "balance apply": h => h.batch.apply("balance", {}, "review", [1]),
  "variants apply": h => h.batch.apply("variants", {}, "review", [1]),
  "delivery build": h => h.api.deliveryApi("/api").start("1", {}),
  "delivery cancel": h => h.api.deliveryApi("/api").cancel("1"),
  "rehearsal report": h => h.api.deliveryApi("/api").rehearse("candidate", "local"),
  "delivery apply": h => h.api.deliveryApi("/api").apply("candidate", "local", false),
  "delivery unapply": h => h.api.deliveryApi("/api").unapply("candidate", "local"),
  "overlay export": h => h.api.deliveryApi("/api").overlay("candidate", "client"),
  "device result": h => h.api.deliveryApi("/api").writeDevice("1", "candidate", {}),
  "device result import": h => h.api.deliveryApi("/api").importDevice("1", "candidate", "record"),
  "boss apply": h => h.boss.apply("1", {}),
  "boss save": h => h.boss.save("1"),
  "boss revert": h => h.boss.revert("1", "change"),
  "weapon apply": h => h.weapons.apply({ operation: "weapon_clone", weapon: {} }),
  "weapon save": h => h.weapons.save("1"),
  "weapon revert": h => h.weapons.revert("1", "change"),
  "weapon icon apply": h => h.weaponIcons.apply("1", {}),
  "weapon set apply": h => h.weaponSet.apply("1", {}),
  "character clone": h => h.studio.cloneCharacter({}),
  "scratch promote": h => h.studio.promoteScratch("scratch-one", {}),
  "view export": h => h.studio.exportStore("work/export", false),
};

for (const [kind, cases] of [["readonly", readonly], ["mutation", mutations]]) {
  for (const [name, operation] of Object.entries(cases)) {
    test(`${kind}: ${name} ${kind === "readonly" ? "preserves" : "invalidates"} pending GET sharing`, async () => {
      const h = harness();
      const first = h.api.get("/api/pending");
      await operation(h);
      const second = h.api.get("/api/pending");
      const reads = h.calls.filter(call => call.init.method !== "POST");
      assert.equal(reads.length, kind === "readonly" ? 1 : 2);
      assert.equal(h.calls.filter(call => call.init.method === "POST").length, 1);
      reads.forEach((call, revision) => call.resolve(new Response(JSON.stringify({ revision }))));
      const [oldRead, newRead] = await Promise.all([first, second]);
      assert.equal(oldRead.revision, 0);
      assert.equal(newRead.revision, kind === "readonly" ? 0 : 1);
    });
  }
}
