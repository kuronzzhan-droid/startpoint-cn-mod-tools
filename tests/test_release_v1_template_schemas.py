"""Executable schema locks for reusable release-v1 configuration templates."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tests.release_v1_schema_support import Draft202012Subset
from wf_release_v1.legacy_character import _load_config


ROOT = Path(__file__).resolve().parents[1]


class ReleaseTemplateSchemaTests(unittest.TestCase):
    def _document(self, relative: str) -> dict[str, object]:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_rolf_adoption_example_is_executable_and_schema_valid(self) -> None:
        schema = self._document(
            "schemas/wf-release-legacy-character-adoption-v1.schema.json"
        )
        example_path = ROOT / "docs/examples/legacy-character-adoption.rolf.json"
        example = self._document("docs/examples/legacy-character-adoption.rolf.json")

        self.assertTrue(Draft202012Subset(schema).accepts(example))
        self.assertEqual(example, dict(_load_config(example_path)))
        self.assertEqual(179999, example["targetCharacterId"])
        self.assertEqual(20, len(example["clientTables"]))
        self.assertEqual(
            "quarantine/server-data/rolf_179999_rows.json",
            example["serverRows"]["path"],
        )

    def test_adoption_schema_rejects_shape_and_identity_mutations(self) -> None:
        schema = Draft202012Subset(
            self._document(
                "schemas/wf-release-legacy-character-adoption-v1.schema.json"
            )
        )
        example = self._document("docs/examples/legacy-character-adoption.rolf.json")
        cases: list[dict[str, object]] = []

        missing = deepcopy(example)
        del missing["serverRows"]
        cases.append(missing)
        unknown = deepcopy(example)
        unknown["unknown"] = True
        cases.append(unknown)
        bad_version = deepcopy(example)
        bad_version["legacyCharacterAdoptionVersion"] = 2
        cases.append(bad_version)
        bad_root = deepcopy(example)
        bad_root["clientTables"][0]["root"] = "server"  # type: ignore[index]
        cases.append(bad_root)
        bad_codec = deepcopy(example)
        bad_codec["clientTables"][0]["codecId"] = "guessed"  # type: ignore[index]
        cases.append(bad_codec)
        bad_sha = deepcopy(example)
        bad_sha["serverRows"]["sha256"] = "0" * 63  # type: ignore[index]
        cases.append(bad_sha)

        for value in cases:
            with self.subTest(value=value):
                self.assertFalse(schema.accepts(value))

    def test_managed_target_example_matches_closed_schema(self) -> None:
        schema_document = self._document("schemas/wf-release-target-v1.schema.json")
        schema = Draft202012Subset(schema_document)
        example = self._document("docs/examples/wf-release-target.windows.json")

        self.assertTrue(schema.accepts(example))
        self.assertEqual(set(example), set(schema_document["required"]))
        self.assertEqual(set(example), set(schema_document["properties"]))

        missing = deepcopy(example)
        del missing["stateRoot"]
        unknown = deepcopy(example)
        unknown["profile"] = "active"
        bad_manager = deepcopy(example)
        bad_manager["managedBy"] = "legacy-tool"
        bad_capability_url = deepcopy(example)
        bad_capability_url["serverUrl"] = "http://127.0.0.1:8001/api/server/capabilities"
        bad_compatibility = deepcopy(example)
        bad_compatibility["compatibility"]["clientPatchProfile"] = 1  # type: ignore[index]

        for value in (
            missing,
            unknown,
            bad_manager,
            bad_capability_url,
            bad_compatibility,
        ):
            with self.subTest(value=value):
                self.assertFalse(schema.accepts(value))

    def test_templates_do_not_contain_host_secrets_or_live_profiles(self) -> None:
        for relative in (
            "docs/examples/legacy-character-adoption.rolf.json",
            "docs/examples/wf-release-target.windows.json",
        ):
            raw = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("profiles.json", raw)
            self.assertNotIn("WF_PROFILE", raw)
            self.assertNotIn("Authorization", raw)
            self.assertNotIn("Bearer ", raw)
            self.assertNotIn("C:\\Users\\", raw)

    def test_user_guides_expose_the_full_preparation_and_preview_flow(self) -> None:
        release_guide = (ROOT / "docs/wf-release-v1.md").read_text(encoding="utf-8")
        install_guide = (ROOT / "docs/wf-release-v1-local-install.md").read_text(
            encoding="utf-8"
        )
        for token in (
            "adopt-character",
            "checkout-character",
            "seal-character",
            "build-overlay",
            "legacy-character-adoption.rolf.json",
            "wf-release-legacy-character-adoption-v1.schema.json",
        ):
            self.assertIn(token, release_guide)
        for token in (
            "capture-requirements",
            "plan-install",
            "wf-release-target.windows.json",
            "wf-release-target-v1.schema.json",
            '"writesLive":false',
        ):
            self.assertIn(token, install_guide)


if __name__ == "__main__":
    unittest.main()
