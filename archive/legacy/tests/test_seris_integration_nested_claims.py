# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_TOOLS = REPO_ROOT / "mod-tools"
if str(MOD_TOOLS) not in sys.path:
    sys.path.insert(0, str(MOD_TOOLS))

import wf_mod_tool as core


BUILD_SCRIPT = REPO_ROOT / "work" / "seris_v2" / "integration" / "build_candidate.py"
SOURCE_PACKAGE = (
    REPO_ROOT
    / ".worktrees"
    / "seris-dual-form"
    / "work"
    / "sfix159"
    / "seris_dragon_king"
    / "package"
)
ROUTE_C_FULL = REPO_ROOT / "work" / "seris_v2" / "authoring" / "pixel_route_c" / "full"
EFFECTS = REPO_ROOT / "work" / "seris_v2" / "authoring" / "effects" / "_containers"
TABLES = (
    ("master/skill/action_skill.orderedmap", "action_nested"),
    ("master/skill/switched_action_skill.orderedmap", "switched_nested"),
)
SERIS = "seris_dragon_king"
STELLA = "stella_summer_goddess"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_table(package: Path, logical_path: str) -> Path:
    return package / "roots" / "common" / Path(*logical_path.split("/"))


def _replace_first_cell(
    table: core.NestedOrderedMap, outer_key: str, inner_key: str, value: str
) -> None:
    inner = table.rows[outer_key]
    index = inner.keys.index(inner_key)
    rows = core.read_csv_lines(inner.rows[index].decode("utf-8"))
    rows[0][0] = value
    inner.rows[index] = core.write_csv_lines(rows).encode("utf-8")


def _append_inner_probe(
    table: core.NestedOrderedMap, outer_key: str, inner_key: str, value: str
) -> None:
    inner = table.rows[outer_key]
    rows = core.read_csv_lines(inner.rows[0].decode("utf-8"))
    rows[0][0] = value
    inner.keys.append(inner_key)
    inner.rows.append(core.write_csv_lines(rows).encode("utf-8"))


def _append_outer_probe(
    table: core.NestedOrderedMap, outer_key: str, value: str
) -> None:
    donor_key = next(key for key in table.rows if key not in (SERIS, STELLA))
    donor = table.rows[donor_key]
    rows = list(donor.rows)
    first = core.read_csv_lines(rows[0].decode("utf-8"))
    first[0][0] = value
    rows[0] = core.write_csv_lines(first).encode("utf-8")
    table.rows[outer_key] = core.OrderedMap(
        f"{table.logical_path}#{outer_key}",
        list(donor.keys),
        rows,
        Path("<test-live>"),
    )


def _inner_rows(table: core.NestedOrderedMap, outer_key: str) -> dict[str, bytes]:
    inner = table.rows[outer_key]
    return dict(zip(inner.keys, inner.rows))


class TestSerisIntegrationNestedClaims(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("seris_integration_step4", BUILD_SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load build script: {BUILD_SCRIPT}")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

        cls.temp = tempfile.TemporaryDirectory(prefix="seris-phase2-step4-test-")
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / "source-package"
        shutil.copytree(SOURCE_PACKAGE, cls.source)
        cls.live_store = cls.root / "live-store"
        cls.live_store.mkdir()

        # Build a deterministic live baseline before changing the candidate claims.
        for logical_path, _ in TABLES:
            source_path = _package_table(cls.source, logical_path)
            live = core.load_nested_table_bytes(source_path.read_bytes(), logical_path)
            if STELLA in live.rows:
                _replace_first_cell(live, STELLA, "1", "STEP4_STELLA_LIVE")
            _append_inner_probe(live, SERIS, "99", f"STEP4_INNER_LIVE:{logical_path}")
            _append_outer_probe(
                live, "phase2_step4_unclaimed_probe", f"STEP4_OUTER_LIVE:{logical_path}"
            )
            live_path = core.table_path(cls.live_store, logical_path)
            live_path.parent.mkdir(parents=True, exist_ok=True)
            live_path.write_bytes(core.build_nested_table(live, logical_path))

        # Candidate-only changes prove that exactly the declared Seris inner rows win.
        action_path = _package_table(cls.source, TABLES[0][0])
        action = core.load_nested_table_bytes(action_path.read_bytes(), TABLES[0][0])
        _replace_first_cell(action, SERIS, "1", "STEP4_SERIS_ACTION_CANDIDATE")
        action_path.write_bytes(core.build_nested_table(action, TABLES[0][0]))
        switched_path = _package_table(cls.source, TABLES[1][0])
        switched = core.load_nested_table_bytes(switched_path.read_bytes(), TABLES[1][0])
        _replace_first_cell(switched, SERIS, "2", "STEP4_SERIS_SWITCHED_CANDIDATE")
        switched_path.write_bytes(core.build_nested_table(switched, TABLES[1][0]))

        cls.source_before = cls.module._snapshot(cls.source)
        cls.live_before = {
            logical: _sha256(core.table_path(cls.live_store, logical))
            for logical, _ in TABLES
        }
        cls.integration = cls.root / "integration"
        cls.output = cls.integration / "seris_dragon_king"
        cls.evidence = cls.integration / "evidence" / "phase2_step4.json"
        cls.report = cls.module.build_candidate(
            cls.source,
            cls.output,
            cls.evidence,
            allowed_output_root=cls.integration,
            route_c_full=ROUTE_C_FULL,
            effects_source=EFFECTS,
            live_store=cls.live_store,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_codecs_roundtrip_live_candidate_and_final(self) -> None:
        audit = self.report["nested_claims_audit"]
        self.assertEqual("phase2_step4", self.report["phase"])
        self.assertEqual({"action_nested", "switched_nested"}, {
            item["codec_id"] for item in audit["tables"].values()
        })
        for item in audit["tables"].values():
            self.assertTrue(item["live_codec_roundtrip"])
            self.assertTrue(item["candidate_codec_roundtrip"])
            self.assertTrue(item["final_codec_roundtrip"])

    def test_only_declared_seris_inner_rows_take_candidate_values(self) -> None:
        manifest = json.loads((self.source / "manifest.json").read_text(encoding="utf-8"))
        by_path = {item["logical_path"]: item for item in manifest["tables"]}
        for logical_path, _ in TABLES:
            final = core.load_nested_table_bytes(
                _package_table(self.output, logical_path).read_bytes(), logical_path
            )
            candidate = core.load_nested_table_bytes(
                _package_table(self.source, logical_path).read_bytes(), logical_path
            )
            claims = next(
                item["keys"]
                for item in by_path[logical_path]["inner_keys"]
                if item["outer_key"] == SERIS
            )
            final_rows = _inner_rows(final, SERIS)
            candidate_rows = _inner_rows(candidate, SERIS)
            for key in claims:
                self.assertEqual(candidate_rows[key], final_rows[key])
            changed = self.report["nested_claims_audit"]["tables"][logical_path][
                "changed_inner_rows"
            ]
            self.assertTrue(set(changed).issubset({f"{SERIS}/{key}" for key in claims}))

    def test_stella_and_every_nonclaimed_row_are_live_byte_exact(self) -> None:
        for logical_path, _ in TABLES:
            live = core.load_nested_table_bytes(
                core.table_path(self.live_store, logical_path).read_bytes(), logical_path
            )
            final = core.load_nested_table_bytes(
                _package_table(self.output, logical_path).read_bytes(), logical_path
            )
            self.assertEqual(tuple(live.rows), tuple(final.rows))
            for outer_key in live.rows:
                if outer_key != SERIS:
                    self.assertEqual(live.raw_rows[outer_key], final.raw_rows[outer_key])
            if STELLA in live.rows:
                self.assertEqual(live.raw_rows[STELLA], final.raw_rows[STELLA])
            final_seris = _inner_rows(final, SERIS)
            live_seris = _inner_rows(live, SERIS)
            self.assertEqual(live_seris["99"], final_seris["99"])
            audit = self.report["nested_claims_audit"]["tables"][logical_path]
            self.assertTrue(audit["stella_byte_exact"])
            self.assertTrue(audit["all_nonclaimed_outer_rows_byte_exact"])
            self.assertTrue(audit["all_nonclaimed_inner_rows_byte_exact"])
            self.assertEqual([], audit["changed_nonclaimed_rows"])

    def test_manifest_hashes_match_and_transaction_claims_are_unchanged(self) -> None:
        source_manifest = json.loads((self.source / "manifest.json").read_text(encoding="utf-8"))
        final_manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        source_tables = {
            item["logical_path"]: item for item in source_manifest["tables"]
            if item["logical_path"] in {logical for logical, _ in TABLES}
        }
        final_tables = {
            item["logical_path"]: item for item in final_manifest["tables"]
            if item["logical_path"] in source_tables
        }
        self.assertEqual(source_tables, final_tables)
        common = {item["logical_path"]: item for item in final_manifest["roots"]["common"]}
        for logical_path, _ in TABLES:
            path = _package_table(self.output, logical_path)
            self.assertEqual(_sha256(path), common[logical_path]["sha256"])
            self.assertEqual(path.stat().st_size, common[logical_path]["size"])
        manifest_audit = self.report["nested_claims_audit"]["manifest"]
        self.assertEqual(2, manifest_audit["updated_entries"])
        self.assertTrue(manifest_audit["all_match"])

    def test_two_clean_builds_match_and_inputs_are_read_only(self) -> None:
        self.assertTrue(self.report["reproducible"])
        self.assertTrue(self.report["source_unchanged"])
        self.assertTrue(self.report["route_c_source_unchanged"])
        self.assertTrue(self.report["effects_source_unchanged"])
        self.assertTrue(self.report["live_nested_source_unchanged"])
        self.assertEqual(self.source_before, self.module._snapshot(self.source))
        self.assertEqual(
            self.live_before,
            {logical: _sha256(core.table_path(self.live_store, logical)) for logical, _ in TABLES},
        )
        self.assertEqual(self.report["build_a"], self.report["build_b"])
        self.assertEqual(self.report["build_b"], self.report["final"])
        self.assertEqual(
            self.report,
            json.loads(self.evidence.read_text(encoding="utf-8")),
        )


if __name__ == "__main__":
    unittest.main()
