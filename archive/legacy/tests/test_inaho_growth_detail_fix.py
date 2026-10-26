"""C10010 regression, exact cell scope, and native growth arithmetic."""
from copy import deepcopy
import math
from pathlib import Path
import random
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_mod_tool as core
import wf_inaho_growth_detail_data as data

BASE = {
    "1399951": "789cd593cd6ec2300c80ef7b8e1d866489d84d33fa12dc3945a10b5244d6482515f0f6283f2d1ba32040fbf321766227f1e7382bb793ae55b5d55275be7b6f24826f3b0dca7b55afe55e5bebb6c0001810000816a4578be40dee28a73acacbdc357a32780831fa8bd7923108c3a7e887e4697503ce58d21c0030f1653530b0733c2482410184411c7f09086984489437222142393c6e208b5c7feb992ef51817a9c74e9961640db0a8aaaaccf5e3c48ed7fe3416ceaef55f11144f1efe312e9999e4d122e0b7570067e2de7e8d25a04c7d34ce9681b0085bf2c7ec43fff70715548de4a396c61abf975fd37a6b956960a9bcb77aaa6a6f5c33ddac8db5fda4df9a172f1ff47ceda2bbe40001628e0e",
    "1399956": "789cad51bb0ec2300cdcf912906e88933ec84fb033551572a6d048a1053e1fa549ab94a120e82de72867cbbe33eed938df5e2c37edd00fd7aea9d0fb8161f8ce1e021090002a1130d199ad750f808e75900020a5b52e657a0152a19e64149b1201fb93ebf810a52a10c9f14b6445e4b19c274b52a1a55c48b01576e6a315b462c5b4c8ff0b257b3214596d5a7b6314d10a0a5e40bdf9f0c525aba16a1d25e1e21f635ddc30274775ca4e45de2ebc17daeb9e0e",
    "139995": "789cd555c16ec2300cbdef33380dc948b183d5e427b8738a2a48115269a64281cf47491a60a3546843d0f990673576f35e6cc5853b1a57e78bd29abcd9359b0a0480f04bb09f48d2bb28bc2500f89cb9ca8e6350eba734420486b92d4b770020160238263dc73e8a7e01a8b2d647a9b566ba969225627d82826252614b5c9c181bddf39f09a54fe16f212fd37a0fa1a32e1cd35ac5f45ea20afed053189aca2fc31280dddca7fc6fb9337b6c7b653abc96e9662de9fac207dbef77c82b3538f67dcf4a46f4c0896e6feb7abdb4e6e664b36cf2d27c1530422090a34be87657afab554fc63be4522cc344c78a247cd970d3fafce1b7e3ede66d0d132c4b232ce2f3249d00973dd05a",
}


class DetailFixTest(unittest.TestCase):
    def setUp(self):
        self.old = {k: zlib.decompress(bytes.fromhex(v)).decode() for k, v in BASE.items()}
        self.new = data.transform(self.old)
        self.rows = {k: core.read_csv_lines(v) for k, v in self.new.items()}

    def test_frozen_baseline_output_and_idempotence(self):
        self.assertEqual({k: data.sha(v) for k, v in self.old.items()}, data.OLD)
        self.assertEqual({k: data.sha(v) for k, v in self.new.items()}, data.NEW)
        self.assertEqual(data.transform(self.new), self.new)
        bad = dict(self.old, **{"1399951": self.new["1399951"]})
        with self.assertRaises(ValueError):
            data.transform(bad)
        with self.assertRaises(ValueError):
            data.transform(dict(self.old, **{"1399956": self.old["1399956"] + "\n"}))

    def test_only_unsupported_row_and_three_redundant_limits_change(self):
        expected = {"1399951": {(4, c) for c in (39, 40, 42, 43, 44, 45, 47, 48,
                                                    51, 52, 59, 60, 68, 70, 71, 74, 75)} | {(5, 44)},
                    "1399956": {(0, 44)}, "139995": {(1, 42)}}
        for key, text in self.old.items():
            old = core.read_csv_lines(text)
            diff = {(i, c) for i, (a, b) in enumerate(zip(old, self.rows[key]))
                    for c, (x, y) in enumerate(zip(a, b)) if x != y}
            self.assertEqual(diff, expected[key])
        row = self.rows["1399951"][4]
        self.assertEqual((row[1], row[27], row[34], row[35], row[39], row[46], row[47]),
                         ("true", "184", "(None)", "0", "(None)", "0", "629"))
        self.assertEqual(row[40:46], [""] * 6)

    def test_seed_existing_rows_and_state_fields_untouched(self):
        old = core.read_csv_lines(self.old["1399951"])
        for i in (0, 1, 2, 3, 6):
            self.assertEqual(self.rows["1399951"][i], old[i])
        self.assertEqual(self.rows["1399956"][1:], core.read_csv_lines(self.old["1399956"])[1:])

    def test_dsl_uses_same_member_state_local_variable_and_force_apply(self):
        payload, tree = data.asset()
        self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(payload, -15))["tree"], tree)
        expr = tree[11][1][0][1]
        self.assertEqual(expr[:3], ["ConditionalsConditionExist", -17, ["DCUnique", data.STATE]])
        self.assertEqual(expr[4], ["Block", []])
        bind, create = (n[1] for n in expr[3][1])
        self.assertEqual(bind, ["BindConditionAccumulationVariable", -17, data.STATE,
                                ["DCUnique", data.STATE], 4, data.CAP])
        self.assertEqual(create[1], -17)
        self.assertEqual(create[2][0], ["ACUnique", data.STATE, [{"min": 1, "max": 1}]])
        self.assertEqual((create[7], create[10], create[11], create[12]),
                         ("", 1, [{"min": 1, "max": 1, "mul": data.STATE}], True))

    def test_native_floor_and_global_cap_equal_previous_growth(self):
        rng = random.Random(1399952)
        samples = list(range(4200, 4300)) + [data.CAP - i for i in range(8)]
        samples += [rng.randint(4200, data.CAP) for _ in range(2000)]
        for stacks in samples:
            # Native Bind produces exact binary quarters; resolveSLvValueInt floors.
            bound = min(stacks / 4, data.CAP)
            increment = math.floor(bound + 1e-10 + 1e-10)
            self.assertEqual(increment, stacks // 4)
            self.assertEqual(min(data.CAP, stacks + increment), min(data.CAP, stacks * 5 // 4))

    def test_tighter_limits_are_equivalent_and_description_integer_safe(self):
        for divisor in (210, 120, 280):
            limit = data.CAP // divisor
            self.assertLess(10 * limit, 2**31)
            for stacks in (4200, 5250, data.CAP - 1, data.CAP):
                self.assertEqual(min(stacks // divisor, limit), stacks // divisor)


if __name__ == "__main__":
    unittest.main()
