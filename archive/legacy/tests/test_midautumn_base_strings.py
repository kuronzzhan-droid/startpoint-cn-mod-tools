"""Base-only text must stay unchanged and cannot acquire package ownership."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import wf_seasonal7_common as C
import wf_midautumn_kit_fluffy as F
import wf_midautumn_kitlib as KL
from wf_midautumn_base_strings import validate_base_strings


class BaseStringTests(unittest.TestCase):
    def context(self, live=None, candidate=None):
        key = F.SLOT_OVERRIDE[5]
        default = {key: C.csv_join([[F.CAS_TEXTS[key]]])}
        return SimpleNamespace(live_flat=lambda _: default if live is None else live,
                               pkg_flat=lambda _: default if candidate is None else candidate,
                               csv_split=C.csv_split)

    def test_equal_dependency_is_read_only(self):
        data = {k: C.csv_join([[F.CAS_TEXTS[k]]]) for k in F.BASE_STRING_KEYS}
        before = copy.deepcopy(data)
        validate_base_strings(self.context(data, data), {k: F.CAS_TEXTS[k] for k in F.BASE_STRING_KEYS})
        self.assertEqual(data, before)

    def test_missing_or_changed_dependency_is_rejected_before_write(self):
        key = F.SLOT_OVERRIDE[5]
        for side in ('live', 'candidate'):
            for value in ({}, {key: C.csv_join([['different']])}):
                with self.subTest(side=side, value=value):
                    ctx = self.context(**{side: value})
                    ctx.write_flat = Mock()
                    with self.assertRaises(KL.KitError):
                        F.write_strings(ctx)
                    ctx.write_flat.assert_not_called()

    def test_writer_excludes_base_key_but_retains_all_owned_strings(self):
        ctx = self.context()
        ctx.spec = SimpleNamespace(extra_keys=F.SPEC['extra_keys'])
        ctx.official_flat = lambda _: {}
        ctx.write_flat, ctx.unclaim = Mock(), Mock()
        result = F.write_strings(ctx)
        logical, rows = ctx.write_flat.call_args.args
        self.assertEqual(logical, KL.CAS)
        self.assertEqual(set(rows), set(F.CAS_TEXTS) - F.BASE_STRING_KEYS)
        ctx.unclaim.assert_called_once_with(KL.CAS, F.BASE_STRING_KEYS)
        self.assertEqual(result, F.CAS_TEXTS)


if __name__ == '__main__':
    unittest.main()
