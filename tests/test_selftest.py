import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "wf_selftest.py"


class SelftestStoreResolutionTests(unittest.TestCase):
    def _run_python(self, source: str, *, env: dict[str, str] | None = None):
        clean_env = os.environ.copy()
        clean_env.pop("WF_TARGET_STORE", None)
        if env:
            clean_env.update(env)
        return subprocess.run(
            [sys.executable, "-c", textwrap.dedent(source)],
            cwd=tempfile.gettempdir(),
            env=clean_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_missing_profile_exits_without_traceback_and_explains_setup(self):
        result = self._run_python(
            f"""
            import runpy
            import sys
            import types

            core = types.ModuleType("wf_mod_tool")
            core.env_target_store = lambda: None
            core.resolve_profile = lambda: None
            sys.modules["wf_mod_tool"] = core
            sys.argv = [{str(SCRIPT)!r}]
            runpy.run_path({str(SCRIPT)!r}, run_name="__main__")
            """
        )

        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", output)
        self.assertIn("wf_store_materialize.py", output)
        self.assertIn("--apply", output)
        self.assertIn("--write-profile", output)
        self.assertIn("WF_TARGET_STORE", output)

    def test_existing_profile_keeps_selecting_its_store(self):
        with tempfile.TemporaryDirectory() as td:
            profile_store = Path(td) / "profile-store"
            result = self._run_python(
                f"""
                import runpy
                import types

                module = runpy.run_path({str(SCRIPT)!r})
                profile = types.SimpleNamespace(store={str(profile_store)!r})
                core = types.SimpleNamespace(
                    env_target_store=lambda: None,
                    resolve_profile=lambda: profile,
                    resolve_active_store=lambda **_kwargs: profile.store,
                )
                print(module["_resolve_selftest_store"](core))
                """
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(profile_store))

    def test_target_store_environment_falls_back_when_profile_is_missing(self):
        with tempfile.TemporaryDirectory() as td:
            target_store = Path(td) / "target-store"
            target_store.mkdir()
            result = self._run_python(
                f"""
                import runpy
                import types

                module = runpy.run_path({str(SCRIPT)!r})
                core = types.SimpleNamespace(
                    env_target_store=lambda: {str(target_store)!r},
                    resolve_profile=lambda: None,
                )
                print(module["_resolve_selftest_store"](core))
                """,
                env={"WF_TARGET_STORE": str(target_store)},
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(target_store))

    def test_store_resolution_uses_the_shared_core_environment_validator(self):
        result = self._run_python(
            f"""
            import runpy
            import types

            module = runpy.run_path({str(SCRIPT)!r})
            def reject_environment():
                raise ValueError("WF_TARGET_STORE shared validator sentinel")
            profile = types.SimpleNamespace(store="must-not-win")
            core = types.SimpleNamespace(
                env_target_store=reject_environment,
                resolve_profile=lambda: profile,
            )
            try:
                module["_resolve_selftest_store"](core)
            except ValueError as error:
                print(error)
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "WF_TARGET_STORE shared validator sentinel")


if __name__ == "__main__":
    unittest.main()
