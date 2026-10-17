"""候选表审查不允许静默丢键或重编码无关数据。"""
import sys
import unittest
import zlib
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core
from wf_miniboss_verify import changed_keys


def table(rows):
    data = core.OrderedMap("test", list(rows),
                           [zlib.compress(text.encode()) for text in rows.values()], Path("."))
    return core.build_orderedmap_raw_rows(data)


class MinibossPackageTests(unittest.TestCase):
    def test_only_changed_character_is_reported(self):
        before = table({"129998": "old", "169989": "campus"})
        after = table({"129998": "new", "169989": "campus"})
        self.assertEqual(changed_keys(before, after), {"129998"})

    def test_foreign_change_cannot_hide_in_full_table(self):
        before = table({"129998": "old", "169989": "campus"})
        after = table({"129998": "new", "169989": "wrong"})
        self.assertEqual(changed_keys(before, after), {"129998", "169989"})

    def test_missing_old_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "removed"):
            changed_keys(table({"a": "a", "b": "b"}), table({"a": "a"}))


if __name__ == "__main__":
    unittest.main()
