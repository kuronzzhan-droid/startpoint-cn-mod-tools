"""Behavior tests for the standalone WF mod-tools distribution builder."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from wf_tool_distribution import DistributionError, build_tool_distribution


class ToolDistributionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "docs").mkdir()
        (self.source / "README.md").write_text("# portable tools\n", encoding="utf-8")
        (self.source / "wf_demo.py").write_text("print('ok')\n", encoding="utf-8")
        (self.source / "docs" / "guide.md").write_text("portable\n", encoding="utf-8")
        self.config = self.source / "tool-distribution-v1.json"
        self._write_config(
            files=["README.md", "tool-distribution-v1.json", "wf_demo.py"],
            trees=["docs"],
        )
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "Distribution Test")
        self._git("add", "-A")
        self._git("commit", "-qm", "fixture")

    def _git(self, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.source,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.strip()

    def _write_config(
        self,
        *,
        files: list[str],
        trees: list[str],
        excluded: list[str] | None = None,
    ) -> None:
        value = {
            "schemaVersion": 1,
            "toolVersion": "1.0.0",
            "archiveRoot": "wf-mod-tools",
            "files": files,
            "trees": trees,
            "excludedTracked": excluded or [],
        }
        self.config.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def test_repeated_builds_are_byte_identical_and_self_describing(self) -> None:
        first = self.root / "first.zip"
        second = self.root / "second.zip"
        first_receipt = build_tool_distribution(self.source, first, self.config)
        second_receipt = build_tool_distribution(self.source, second, self.config)

        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(), first_receipt.sha256)
        self.assertEqual(first_receipt, second_receipt)
        with zipfile.ZipFile(first) as archive:
            self.assertEqual(
                [
                    "wf-mod-tools/MANIFEST.json",
                    "wf-mod-tools/README.md",
                    "wf-mod-tools/docs/guide.md",
                    "wf-mod-tools/tool-distribution-v1.json",
                    "wf-mod-tools/wf_demo.py",
                ],
                archive.namelist(),
            )
            manifest = json.loads(archive.read("wf-mod-tools/MANIFEST.json"))
            self.assertEqual(
                {
                    "schemaVersion",
                    "toolVersion",
                    "sourceCommit",
                    "files",
                },
                set(manifest),
            )
            self.assertEqual(self._git("rev-parse", "HEAD"), manifest["sourceCommit"])
            self.assertEqual(
                [
                    "README.md",
                    "docs/guide.md",
                    "tool-distribution-v1.json",
                    "wf_demo.py",
                ],
                [entry["path"] for entry in manifest["files"]],
            )
            self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()))

    def test_dirty_or_unclassified_sources_are_rejected(self) -> None:
        (self.source / "scratch.txt").write_text("untracked\n", encoding="utf-8")
        with self.assertRaisesRegex(DistributionError, "clean Git checkout"):
            build_tool_distribution(self.source, self.root / "dirty.zip", self.config)
        (self.source / "scratch.txt").unlink()

        (self.source / "extra.py").write_text("print('unclassified')\n", encoding="utf-8")
        self._git("add", "extra.py")
        self._git("commit", "-qm", "add unclassified file")
        with self.assertRaisesRegex(DistributionError, "unclassified tracked file"):
            build_tool_distribution(self.source, self.root / "unclassified.zip", self.config)

    def test_sensitive_or_unsafe_members_are_rejected_before_reading(self) -> None:
        secret = self.source / ".env"
        secret.write_text("TOKEN=do-not-package\n", encoding="utf-8")
        self._write_config(
            files=[".env", "README.md", "tool-distribution-v1.json", "wf_demo.py"],
            trees=["docs"],
        )
        self._git("add", ".env", "tool-distribution-v1.json")
        self._git("commit", "-qm", "attempt sensitive include")
        with self.assertRaisesRegex(DistributionError, "sensitive distribution member"):
            build_tool_distribution(self.source, self.root / "secret.zip", self.config)

        self._write_config(
            files=["../escape.txt", "README.md", "tool-distribution-v1.json", "wf_demo.py"],
            trees=["docs"],
        )
        self._git("add", "tool-distribution-v1.json")
        self._git("commit", "-qm", "attempt traversal")
        with self.assertRaisesRegex(DistributionError, "portable relative path"):
            build_tool_distribution(self.source, self.root / "escape.zip", self.config)

    def test_case_aliases_and_symlinks_cannot_enter_the_archive(self) -> None:
        self._write_config(
            files=[
                "README.md",
                "readme.md",
                "tool-distribution-v1.json",
                "wf_demo.py",
            ],
            trees=["docs"],
        )
        self._git("add", "tool-distribution-v1.json")
        self._git("commit", "-qm", "attempt case alias")
        with self.assertRaisesRegex(DistributionError, "case-insensitive path alias"):
            build_tool_distribution(self.source, self.root / "alias.zip", self.config)

    def test_logical_home_segments_are_not_mistaken_for_local_absolute_paths(self) -> None:
        paths = self.source / "paths.txt"
        paths.write_text("character/hero/voice/home/greeting.mp3\n", encoding="utf-8")
        self._write_config(
            files=[
                "README.md",
                "paths.txt",
                "tool-distribution-v1.json",
                "wf_demo.py",
            ],
            trees=["docs"],
        )
        self._git("add", "paths.txt", "tool-distribution-v1.json")
        self._git("commit", "-qm", "add logical path list")
        build_tool_distribution(self.source, self.root / "logical-paths.zip", self.config)

        paths.write_text("/home/alice/private.txt\n", encoding="utf-8")
        self._git("add", "paths.txt")
        self._git("commit", "-qm", "add local path")
        with self.assertRaisesRegex(DistributionError, "local absolute path"):
            build_tool_distribution(self.source, self.root / "local-path.zip", self.config)


if __name__ == "__main__":
    unittest.main()
