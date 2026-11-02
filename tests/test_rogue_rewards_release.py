"""Repository reward regressions with shared synthetic fixtures."""
from __future__ import annotations

from rogue_rewards_support import *  # noqa: F403

class TestCnProfilePreflight(unittest.TestCase):
    def setUp(self):
        for name, value in (("resolve_server_dir", Path("configured-server")),
                            ("resolve_cdn_root", Path("configured-cdn"))):
            patch = mock.patch.object(core, name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_active_global_fails_before_any_read_write_or_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_global = core.VersionProfile(
                id="global",
                label="Global",
                store=root / "global",
                fallback=None,
            )
            explicit_cn = core.VersionProfile(
                id="cn",
                label="CN",
                store=root / "cn",
                fallback=None,
            )
            active_global.store.mkdir()
            explicit_cn.store.mkdir()

            def resolve_profile(profile_id=None):
                return explicit_cn if profile_id == "cn" else active_global

            with (
                mock.patch.object(rewards.core, "resolve_profile", side_effect=resolve_profile),
                mock.patch.object(rewards.q, "load_table", return_value={}) as load_table,
                mock.patch.object(rewards.q, "save_table") as save_table,
                mock.patch.object(rewards, "load_json", return_value={}) as load_json,
                mock.patch.object(rewards, "save_json") as save_json,
                mock.patch.object(rewards.subprocess, "run") as publish,
                mock.patch.object(sys, "argv", ["wf_rogue_rewards.py"]),
            ):
                result = rewards.main()

            self.assertNotEqual(0, result)
            load_table.assert_not_called()
            save_table.assert_not_called()
            load_json.assert_not_called()
            save_json.assert_not_called()
            publish.assert_not_called()

    def test_profile_is_rechecked_immediately_before_publish(self):
        tables = fake_master_tables(placeholders=True)
        mirrors = fake_server_mirrors()
        cn_profile = core.VersionProfile(
            id="cn", label="CN", store=Path("cn-store"), fallback=None
        )
        stored_tables = {
            rewards.ITEM_T: copy.deepcopy(tables.items),
            rewards.EQUIP_T: copy.deepcopy(tables.equipment),
            rewards.EQUIP_STATUS_T: copy.deepcopy(tables.equipment_status),
            rewards.SOUL_T: copy.deepcopy(tables.ability_soul),
            rewards.RUSH_EVENT_T: copy.deepcopy(tables.rush_event),
        }
        stored_json = {
            "equipment_max_level.json": copy.deepcopy(mirrors.equipment_max_level),
            "equipment_element.json": copy.deepcopy(mirrors.equipment_element),
            "equipment_lookup.json": copy.deepcopy(mirrors.equipment_lookup),
            "equipment_ids.json": copy.deepcopy(mirrors.equipment_ids),
            "item_ids.json": copy.deepcopy(mirrors.item_ids),
        }

        def load_table(logical):
            return copy.deepcopy(stored_tables[logical])

        def save_table(logical, data):
            stored_tables[logical] = copy.deepcopy(data)

        def load_json(name):
            return copy.deepcopy(stored_json[name])

        def save_json(name, data):
            stored_json[name] = copy.deepcopy(data)

        with (
            mock.patch.object(
                rewards,
                "require_cn_profile",
                side_effect=[cn_profile, ValueError("active changed")],
            ) as preflight,
            mock.patch.object(rewards.q, "load_table", side_effect=load_table),
            mock.patch.object(rewards.q, "save_table", side_effect=save_table),
            mock.patch.object(rewards, "load_json", side_effect=load_json),
            mock.patch.object(rewards, "save_json", side_effect=save_json),
            # 写盘/发布机制本身的测试:失败关闭条件由 TestLegacyWriteBlockers 单测
            mock.patch.object(rewards, "legacy_write_blockers", return_value=[]),
            mock.patch.object(
                rewards,
                "validate_source_assets",
                return_value={spec.image_slug: Path(f"{spec.image_slug}.png")
                              for spec in rewards.WEAPONS},
            ),
            mock.patch.object(
                rewards,
                "install_source_assets",
                return_value=[f"hash-{index}" for index in range(15)],
            ),
            mock.patch.object(rewards, "_print_asset_validation"),
            mock.patch.object(rewards, "_print_plan"),
            mock.patch.object(rewards.subprocess, "run") as publish,
            mock.patch.object(
                sys,
                "argv",
                [
                    "wf_rogue_rewards.py",
                    "--write",
                    "--publish",
                    "--client-verification",
                    "client-verification.json",
                    "--ffdec",
                    "client-ffdec.jar",
                    "--java",
                    "client-java.exe",
                ],
            ),
        ):
            result = rewards.main()

        self.assertNotEqual(0, result)
        self.assertEqual(2, preflight.call_count)
        publish.assert_not_called()

    def test_write_validates_and_installs_sources_in_the_cn_store(self):
        tables = fake_master_tables(placeholders=True)
        mirrors = fake_server_mirrors()
        stored_tables = {
            rewards.ITEM_T: copy.deepcopy(tables.items),
            rewards.EQUIP_T: copy.deepcopy(tables.equipment),
            rewards.EQUIP_STATUS_T: copy.deepcopy(tables.equipment_status),
            rewards.SOUL_T: copy.deepcopy(tables.ability_soul),
            rewards.RUSH_EVENT_T: copy.deepcopy(tables.rush_event),
        }
        stored_json = {
            "equipment_max_level.json": copy.deepcopy(mirrors.equipment_max_level),
            "equipment_element.json": copy.deepcopy(mirrors.equipment_element),
            "equipment_lookup.json": copy.deepcopy(mirrors.equipment_lookup),
            "equipment_ids.json": copy.deepcopy(mirrors.equipment_ids),
            "item_ids.json": copy.deepcopy(mirrors.item_ids),
        }

        def load_table(logical):
            return copy.deepcopy(stored_tables[logical])

        def save_table(logical, data):
            stored_tables[logical] = copy.deepcopy(data)

        def load_json(name):
            return copy.deepcopy(stored_json[name])

        def save_json(name, data):
            stored_json[name] = copy.deepcopy(data)

        with tempfile.TemporaryDirectory() as directory:
            profile = core.VersionProfile(
                id="cn", label="CN", store=Path(directory), fallback=None
            )
            sources = {
                spec.image_slug: Path(directory) / f"{spec.image_slug}.png"
                for spec in rewards.WEAPONS
            }
            with (
                mock.patch.object(rewards, "require_cn_profile", return_value=profile),
                mock.patch.object(rewards.q, "load_table", side_effect=load_table),
                mock.patch.object(rewards.q, "save_table", side_effect=save_table),
                mock.patch.object(rewards, "load_json", side_effect=load_json),
                mock.patch.object(rewards, "save_json", side_effect=save_json),
                mock.patch.object(rewards, "legacy_write_blockers", return_value=[]),
                mock.patch.object(
                    rewards, "validate_source_assets", return_value=sources
                ) as validate,
                mock.patch.object(
                    rewards,
                    "install_source_assets",
                    return_value=[f"hash-{index}" for index in range(15)],
                ) as install,
                mock.patch.object(rewards, "_print_asset_validation"),
                mock.patch.object(rewards, "_print_plan"),
                mock.patch.object(sys, "argv", ["wf_rogue_rewards.py", "--write"]),
            ):
                result = rewards.main()

        self.assertEqual(0, result)
        validate.assert_called_once_with(rewards.SOURCE_ASSET_DIR, rewards.WEAPONS)
        install.assert_called_once_with(profile.store, sources, rewards.WEAPONS)

    def test_publish_collects_all_fifteen_installed_asset_paths(self):
        tables = fake_master_tables(placeholders=True)
        mirrors = fake_server_mirrors()
        stored_tables = {
            rewards.ITEM_T: copy.deepcopy(tables.items),
            rewards.EQUIP_T: copy.deepcopy(tables.equipment),
            rewards.EQUIP_STATUS_T: copy.deepcopy(tables.equipment_status),
            rewards.SOUL_T: copy.deepcopy(tables.ability_soul),
            rewards.RUSH_EVENT_T: copy.deepcopy(tables.rush_event),
        }
        stored_json = {
            "equipment_max_level.json": copy.deepcopy(mirrors.equipment_max_level),
            "equipment_element.json": copy.deepcopy(mirrors.equipment_element),
            "equipment_lookup.json": copy.deepcopy(mirrors.equipment_lookup),
            "equipment_ids.json": copy.deepcopy(mirrors.equipment_ids),
            "item_ids.json": copy.deepcopy(mirrors.item_ids),
        }

        def load_table(logical):
            return copy.deepcopy(stored_tables[logical])

        def save_table(logical, data):
            stored_tables[logical] = copy.deepcopy(data)

        def load_json(name):
            return copy.deepcopy(stored_json[name])

        def save_json(name, data):
            stored_json[name] = copy.deepcopy(data)

        with tempfile.TemporaryDirectory() as directory:
            profile = core.VersionProfile(
                id="cn", label="CN", store=Path(directory), fallback=None
            )
            sources = {
                spec.image_slug: Path(directory) / f"{spec.image_slug}.png"
                for spec in rewards.WEAPONS
            }
            expected_asset_paths = {
                rewards.q.hashed_rel(
                    f"{rewards.IMAGE_PREFIX}/{spec.image_slug}.png"
                )
                for spec in rewards.WEAPONS
            }
            snapshot = fake_release_snapshot(profile.store)
            published_manifest: dict[str, object] = {}

            def publish_snapshot(command, **_kwargs):
                manifest_path = Path(command[command.index("--snapshot") + 1])
                published_manifest.update(
                    json.loads(manifest_path.read_text(encoding="utf-8"))
                )
                return mock.Mock(returncode=0)

            with (
                mock.patch.object(rewards, "require_cn_profile", return_value=profile),
                mock.patch.object(rewards.q, "load_table", side_effect=load_table),
                mock.patch.object(rewards.q, "save_table", side_effect=save_table),
                mock.patch.object(rewards, "load_json", side_effect=load_json),
                mock.patch.object(rewards, "save_json", side_effect=save_json),
                mock.patch.object(rewards, "legacy_write_blockers", return_value=[]),
                mock.patch.object(
                    rewards, "validate_source_assets", return_value=sources
                ),
                mock.patch.object(
                    rewards,
                    "install_source_assets",
                    return_value=sorted(expected_asset_paths),
                ),
                mock.patch.object(rewards, "_print_asset_validation"),
                mock.patch.object(rewards, "_print_plan"),
                mock.patch.object(
                    validator,
                    "require_release_ready",
                    return_value=snapshot,
                ),
                mock.patch.object(
                    rewards.subprocess,
                    "run",
                    side_effect=publish_snapshot,
                ) as publish,
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "wf_rogue_rewards.py",
                        "--write",
                        "--publish",
                        "--client-verification",
                        "client-verification.json",
                        "--ffdec",
                        "client-ffdec.jar",
                        "--java",
                        "client-java.exe",
                    ],
                ),
            ):
                result = rewards.main()

        self.assertEqual(0, result)
        publish.assert_called_once()
        command = publish.call_args.args[0]
        publish_argument = command[command.index("--tables") + 1]
        collected = set(wf_publish.collect_files(mock.Mock(tables=publish_argument)))
        published_assets = collected.intersection(expected_asset_paths)
        missing_assets = expected_asset_paths.difference(collected)
        self.assertEqual(
            15,
            len(published_assets),
            f"PUBLISHED_ASSET_PATHS={len(published_assets)}",
        )
        self.assertEqual(set(), missing_assets, f"missing={sorted(missing_assets)}")
        self.assertEqual(1, published_manifest["schema_version"])
        self.assertEqual(
            validator.release_logicals(),
            [entry["logical"] for entry in published_manifest["entries"]],
        )


class TestReleaseGate(unittest.TestCase):
    def setUp(self):
        for name, value in (("resolve_server_dir", Path("configured-server")),
                            ("resolve_cdn_root", Path("configured-cdn"))):
            patch = mock.patch.object(core, name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_publish_without_write_is_rejected_before_reads_writes_or_subprocess(self):
        with (
            mock.patch.object(rewards, "validate_source_assets") as validate_assets,
            mock.patch.object(rewards, "require_cn_profile") as profile,
            mock.patch.object(rewards.q, "load_table") as load_table,
            mock.patch.object(rewards.q, "save_table") as save_table,
            mock.patch.object(rewards.subprocess, "run") as publish,
            mock.patch.object(
                sys,
                "argv",
                [
                    "wf_rogue_rewards.py",
                    "--publish",
                    "--client-verification",
                    "client-verification.json",
                ],
            ),
        ):
            result = rewards.main()

        self.assertNotEqual(0, result)
        validate_assets.assert_not_called()
        profile.assert_not_called()
        load_table.assert_not_called()
        save_table.assert_not_called()
        publish.assert_not_called()

    def test_publish_without_client_verification_is_rejected_before_any_write(self):
        with (
            mock.patch.object(rewards, "validate_source_assets") as validate_assets,
            mock.patch.object(rewards, "require_cn_profile") as profile,
            mock.patch.object(rewards.q, "save_table") as save_table,
            mock.patch.object(rewards.subprocess, "run") as publish,
            mock.patch.object(
                sys, "argv", ["wf_rogue_rewards.py", "--write", "--publish"]
            ),
        ):
            result = rewards.main()

        self.assertNotEqual(0, result)
        validate_assets.assert_not_called()
        profile.assert_not_called()
        save_table.assert_not_called()
        publish.assert_not_called()

    def test_publish_without_client_toolchain_is_rejected_before_any_write(self):
        with (
            mock.patch.object(rewards, "validate_source_assets") as validate_assets,
            mock.patch.object(rewards, "require_cn_profile") as profile,
            mock.patch.object(rewards.q, "save_table") as save_table,
            mock.patch.object(rewards.subprocess, "run") as publish,
            mock.patch.object(
                sys,
                "argv",
                [
                    "wf_rogue_rewards.py",
                    "--write",
                    "--publish",
                    "--client-verification",
                    "client-verification.json",
                ],
            ),
        ):
            result = rewards.main()

        self.assertNotEqual(0, result)
        validate_assets.assert_not_called()
        profile.assert_not_called()
        save_table.assert_not_called()
        publish.assert_not_called()

    def _run_write_publish(self, *, gate_error=None, publisher_error=None):
        tables = fake_master_tables(placeholders=True)
        mirrors = fake_server_mirrors()
        stored_tables = {
            rewards.ITEM_T: copy.deepcopy(tables.items),
            rewards.EQUIP_T: copy.deepcopy(tables.equipment),
            rewards.EQUIP_STATUS_T: copy.deepcopy(tables.equipment_status),
            rewards.SOUL_T: copy.deepcopy(tables.ability_soul),
            rewards.RUSH_EVENT_T: copy.deepcopy(tables.rush_event),
        }
        stored_json = {
            "equipment_max_level.json": copy.deepcopy(mirrors.equipment_max_level),
            "equipment_element.json": copy.deepcopy(mirrors.equipment_element),
            "equipment_lookup.json": copy.deepcopy(mirrors.equipment_lookup),
            "equipment_ids.json": copy.deepcopy(mirrors.equipment_ids),
            "item_ids.json": copy.deepcopy(mirrors.item_ids),
        }
        events: list[str] = []

        def load_table(logical):
            events.append(f"load:{logical}")
            return copy.deepcopy(stored_tables[logical])

        def save_table(logical, data):
            events.append(f"save:{logical}")
            stored_tables[logical] = copy.deepcopy(data)

        def load_json(name):
            events.append(f"load_json:{name}")
            return copy.deepcopy(stored_json[name])

        def save_json(name, data):
            events.append(f"save_json:{name}")
            stored_json[name] = copy.deepcopy(data)

        profile = core.VersionProfile(
            id="cn", label="CN", store=Path("cn-store"), fallback=None
        )
        sources = {
            spec.image_slug: Path(f"{spec.image_slug}.png")
            for spec in rewards.WEAPONS
        }
        snapshot = fake_release_snapshot(profile.store)
        published_manifest: dict[str, object] = {}

        def install(*_args):
            events.append("install_pngs")
            return [f"hash-{index}" for index in range(15)]

        def gate(*_args, **_kwargs):
            events.append("release_gate")
            if gate_error is not None:
                raise gate_error
            return snapshot

        def publish(command, **_kwargs):
            events.append("publisher")
            if publisher_error is not None:
                raise publisher_error
            manifest_path = Path(command[command.index("--snapshot") + 1])
            published_manifest.update(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
            return mock.Mock(returncode=0)

        with (
            mock.patch.object(rewards, "require_cn_profile", return_value=profile) as preflight,
            mock.patch.object(rewards.q, "load_table", side_effect=load_table),
            mock.patch.object(rewards.q, "save_table", side_effect=save_table),
            mock.patch.object(rewards, "load_json", side_effect=load_json),
            mock.patch.object(rewards, "save_json", side_effect=save_json),
            mock.patch.object(rewards, "legacy_write_blockers", return_value=[]),
            mock.patch.object(rewards, "validate_source_assets", return_value=sources),
            mock.patch.object(rewards, "install_source_assets", side_effect=install),
            mock.patch.object(rewards, "_print_asset_validation"),
            mock.patch.object(rewards, "_print_plan"),
            mock.patch.object(validator, "require_release_ready", side_effect=gate) as gate_mock,
            mock.patch.object(rewards.subprocess, "run", side_effect=publish) as publish_mock,
            mock.patch.object(
                sys,
                "argv",
                [
                    "wf_rogue_rewards.py",
                    "--write",
                    "--publish",
                    "--client-verification",
                    "client-verification.json",
                    "--ffdec",
                    "client-ffdec.jar",
                    "--java",
                    "client-java.exe",
                ],
            ),
        ):
            result = rewards.main()

        return (
            result,
            events,
            profile,
            preflight,
            gate_mock,
            publish_mock,
            published_manifest,
        )

    def test_release_validation_failure_never_invokes_publisher(self):
        (
            result,
            events,
            _profile,
            preflight,
            gate,
            publish,
            _manifest,
        ) = self._run_write_publish(
            gate_error=RuntimeError("invalid release")
        )

        self.assertNotEqual(0, result)
        self.assertEqual(2, preflight.call_count)
        gate.assert_called_once()
        publish.assert_not_called()
        self.assertNotIn("publisher", events)
        self.assertGreater(events.index("release_gate"), events.index("install_pngs"))

    def test_valid_release_invokes_publisher_once_with_exact_allowlist_and_check(self):
        (
            result,
            events,
            profile,
            preflight,
            gate,
            publish,
            manifest,
        ) = self._run_write_publish()

        self.assertEqual(0, result)
        self.assertEqual(2, preflight.call_count)
        gate.assert_called_once_with(
            profile.store,
            Path("configured-server") / "assets",
            Path("client-verification.json"),
            ffdec=Path("client-ffdec.jar"),
            java=Path("client-java.exe"),
        )
        publish.assert_called_once()
        command = publish.call_args.args[0]
        self.assertEqual(
            [
                sys.executable,
                str(rewards.MOD_DIR / "wf_publish.py"),
                "--tables",
                ",".join(validator.release_logicals()),
            ],
            command[:4],
        )
        self.assertEqual("--snapshot", command[4])
        self.assertEqual(Path("configured-server"), publish.call_args.kwargs["cwd"])
        self.assertIs(True, publish.call_args.kwargs["check"])
        self.assertEqual(1, manifest["schema_version"])
        self.assertEqual(
            validator.release_logicals(),
            [entry["logical"] for entry in manifest["entries"]],
        )
        self.assertEqual("release_gate", events[-2])
        self.assertEqual("publisher", events[-1])
        self.assertNotIn("pending", " ".join(command).lower())

    def test_publisher_nonzero_exit_is_propagated(self):
        failure = subprocess.CalledProcessError(9, ["wf_publish.py"])
        (
            result,
            events,
            _profile,
            _preflight,
            gate,
            publish,
            _manifest,
        ) = self._run_write_publish(
            publisher_error=failure
        )

        self.assertEqual(9, result)
        gate.assert_called_once()
        publish.assert_called_once()
        self.assertEqual(1, events.count("publisher"))
