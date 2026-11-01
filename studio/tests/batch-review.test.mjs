import { test } from "node:test";
import assert from "node:assert/strict";
import { pruneMapping, canSaveBatchRow, duplicateTarget, startingId } from "../src/batchReviewState.ts";

test("changing tables clears missing optional columns in submitted state", () => {
  const old = { character: "角色", entry: "词条", before: "前", after: "后", row: "行号", column: "原始列" };
  assert.deepEqual(pruneMapping(old, ["角色", "词条", "前", "后"]), { ...old, row: "", column: "" });
  assert.equal(old.row, "行号");
});

test("manual imports cannot be selected; blocked variants are explicitly draft only", () => {
  assert.equal(canSaveBatchRow("需人工"), false);
  assert.equal(canSaveBatchRow("可写草稿"), true);
  assert.equal(canSaveBatchRow("含需人工（仅存草稿，阻断交付）"), true);
  assert.equal(canSaveBatchRow("unknown"), false);
});

test("duplicate target IDs are marked on both rows", () => {
  const targets = [{ to: "199000" }, { to: "199000" }, { to: "199001" }];
  assert.equal(duplicateTarget(targets, targets[0].to), true);
  assert.equal(duplicateTarget(targets, targets[1].to), true);
  assert.equal(duplicateTarget(targets, targets[2].to), false);
  assert.equal(duplicateTarget([{ to: "" }, { to: "" }], ""), false);
});

test("allocation starts from the first supplied ID", () => {
  assert.equal(startingId([{ to: "151801" }, { to: "199000" }]), "151801");
  assert.equal(startingId([{ to: "" }]), undefined);
});
