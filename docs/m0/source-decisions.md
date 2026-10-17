# M0 源码合并审计

审计日期：2026-10-17。所有外部源只读；本文件的 B/C/out 路径均相对 `source-decisions.json` 的 `source_roots`，本地盘符由 profile 提供。A 基线在任何合并前读取，原始文本与哈希快照暂存于忽略目录 `work/m0/source-snapshot.json`。

## 口径与结论

- 根目录 `*.py`：A 136、B 245、C 528；B/C 同名 75，其中相同 24、分叉 **51**；B 独有 **170**、C 独有 453。任务书数字逐项复现。tests、子包、非 Python 资源不在此计数内。
- C 为基底；B 170 项仅新导入 `wf_battle_atlas_repack.py`，其余 169 项不从 B 导入。A 基线已存在的通用 API 单独保留兼容，不计作新增 B 独有功能；角色、固定活动与日期任务入口继续归档，兼容层不导入归档。A 恢复范围、原始 SHA256 与通用/角色拆分见 `compatibility.md/json`。
- 读取 32 个10月或明确近期生产目录（含角色超限、碧及公共builder）、C 应用源码和 prepush，AST共解析1118文件，0解析失败。完整目录清单、源SHA256、import边、动态调用与文件加载扫描在JSON中。
- 排除了 `out/kulo-sync-1016/baseline` 等整仓镜像、tests、localsrv、node_modules、旧工具副本；这些副本内部互相引用不能证明近期生产使用。未排除时会把115项误判为可达。
- 对非字面动态导入补查：万圣/平衡导入本任务角色配方；seasonal7/midautumn按自己的kit名称导入C模块；灰分享包加载同交付目录的server_apply；Wiki prepare加载其站点文件；offline_release/rogue_validate加载历史builder。全量B独有标识符搜索只多命中gray3的一条“不在我方运行”证据说明，不构成执行边。外部环境变量可以任意指定模块的运行时行为，不属于本次静态闭包保证。

## B 独有模块取舍

| 模块 | 决定 | 可达证据 / 排除依据 |
|---|---|---|
| `adjust_abyss_swap_thunder_pf_local_test.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `apply_balance_20260810.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `apply_gerald_balance_20260829.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `apply_lion_balance_20260829.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `apply_siete_active_skill_balance_20260829.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `apply_simoun_balance_20260829.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `apply_simoun_skill_text_correction_20260829.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `apply_vaseraga_skill_text_correction_20260829.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `audit_awakened_balance_migration_20260830.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `build_abyss_sponsor_laite_candidate.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `build_fantasy_weapon_candidates.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `build_greyupd0902_abyss_icon_closure.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `build_greyupd0902_cdn_recovery.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `build_integrated_cloud_1_4_88_20260825.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `finalize_abyss_element_tower.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `fix_rogue_floor24.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `fold_swimex_leader_into_1_4_81_20260817.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `import_thunder_dragon_abyss_gacha.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `install_mode15_token_icon.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `merge_abyss_reroll_1_4_87_20260823.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `merge_general_shop_1_4_87_20260823.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `package_floor24_cloud_overlay.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `prepare_sponsor_title_wide.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `prepare_swimex_20260817.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_abyss_details_rewards_local_test.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_abyss_exchange_shop_1_4_100.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_abyss_laite_exchange.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_abyss_weapon_token_cost_1_4_98.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_awakened_balance_migration_1_4_94_20260830.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_battle_atlas_repack_in_1_4_91_20260827.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_claude_abyss_1_4_82_20260818.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_complete_1_4_78_patch.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_fantasy_icon_trim_patch.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_fantasy_two_icon_refresh_in_1_4_80_20260817.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_gacha_pool_cleanup_client_1_4_99.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_gauntlet_final_art_1_4_84_20260818.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_gauntlet_hub_1_4_83_20260818.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_greyupd0902_client_cdn_1_4_96.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_home_load_rank_p5b_1_4_92_20260829.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_lion_balance_1_4_87_20260823.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_mana_node_awake_board2_1_4_95_20260831.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_mod_balance_fold_1_4_92_20260829.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_mosiyike_balance_1_4_85_20260821.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_orochi_ex_high_1_4_88_20260823.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_orochi_native_trial_1_4_120_20260925.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_rank_title_conditions_1_4_100.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_rogue_floor24_patch.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_season_rank_titles_1_4_97.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_shop_banner_png_encoding_1_4_101.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_siete_balance_visual_restore_1_4_99.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_simoun_abyss_stability_1_4_93_20260830.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_sponsor_special_thanks.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_sponsor_title_wide_local_test.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_swimex_active_1_4_80_20260817.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_thunder_dragon_fantasy_v4_1_4_81_20260817.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `publish_twochar_1_4_86_20260822.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `reconcile_integrated_candidate_rogue_audit_20260826.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `repair_abyss_ex20_exchange_115.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `repair_abyss_pre_action_local_test.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `repair_abyss_standard_links_local_test.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `repair_cursed_weapon_awaken_icon_preload_1_4_128.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `restore_weapon_caps_practice_hp_1_4_107.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `revise_practice_clones_1_4_107.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `sync_abyss_element_local_test.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `test_sponsor_special_thanks.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_ability_composer.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_abyss_custom_position_fix.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_abyss_ex.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_abyss_gacha_banner_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_contract.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_drop_source.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_package_audit.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_package_cli.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_package_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_package_components.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_package_contract.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_package_sources.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_package_workspace.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_gacha_pool.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_mode_sources.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_abyss_modes.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_abyss_quest_details.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_abyss_ticket_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_ticket_drop.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_abyss_tower_adjustments.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_action_skill_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_apk_paths.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_battle_atlas_repack.py` | 导入 B | `out/kulo-patch-toolkit/cursed_abyss/build/fb_ring_probe.py:5`；`out/kulo-patch-toolkit/cursed_abyss/build/fb_slim196_build.py:9`；`out/kulo-patch-toolkit/cursed_abyss/build/fb_slim196_repack.py:19`；`out/kulo-patch-toolkit/cursed_abyss/build/soul_icon_atlas.py:21` |
| `wf_boss_hp_audit.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_boss_trial.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_character_gates.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_character_reference_export.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_character_storage.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_character_studio.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_character_ui_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_database_paths.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_device_paths.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_dsl_subjects.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_effect_cell_reskin.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_equipment_enhancement_shop.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_fantasy_shop.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_final_state_guard.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_flatomo_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_flatomo_layer_retarget.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_flatomo_preview_render.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_general_exchange.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_general_exchange_client.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_gerald_balance.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_ginovi_balance.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_lion_balance.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_live_cdn.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_mode15_banner.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_mode15_build.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_orochi_ex.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_pixelart_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_pixelart_normal_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_pixelart_special_compat_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_pixelart_special_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_pixelart_split_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_preview_2d.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_preview_2d_core.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_quest_time_revision.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_race_character_nerf.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_release_paths.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_release_ui.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_release_ui_actions.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_rogue_audit_diff.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_rogue_canary.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_rogue_element_channel.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_rogue_reward_schedule.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_rogue_token_result.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_siete_balance.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_simoun_balance.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_spgirl_balance.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_spgirl_effect.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_standard_enemy_links.py` | 不导入 B | 无生产/C/prepush可执行导入边 |
| `wf_summer_thunder_ability_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_core_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_flatomo_gate.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_master_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_acceptance.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_assemble.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_base.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_cli.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_contract.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_evidence.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_image.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_paths.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_rebase.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_skill_gate.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_sources.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_workspace.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_workspace_commit.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_package_workspace_state.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_server_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_skill_action_gate.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_skill_preview_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_summer_thunder_voice_compile.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_thunder_hotfix_character.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_thunder_hotfix_gacha.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_thunder_hotfix_package.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_thunder_hotfix_package_audit.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_thunder_hotfix_package_cli.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_thunder_hotfix_package_sources.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_thunder_hotfix_package_workspace.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_thunder_hotfix_payloads.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_tool_distribution.py` | 不导入 B | 无生产/C/prepush可执行导入边；A已有副本归档 |
| `wf_vaseraga_balance.py` | 不导入 B | 无生产/C/prepush可执行导入边 |

选入 atlas 仅依赖 C 已有的 `wf_assets.png_decode/png_encode` 与 `wf_dsl.parse_dsl/encode_amf3`，无进一步 B 独有依赖。逐文件完整 SHA256 和全部排除记录均在 JSON。

## 51 个同名分叉逐一决策

以下均先选 C；路径配置化、公共函数提炼及本次哨兵修复不改变其来源判定。B的独立发布器或更大文件不自动覆盖生产行为。表中的新增/删除符号清单是顶层 AST 定义比较，完整符号名在 JSON。

| 文件 | B / C 行数 | 行为差异与取舍理由 |
|---|---|---|
| `wf_all_analysis.py` | 561 / 562 | C 从 active profile 取 store；B 用 require_active_store 的强制存在校验。保留 C 分析结果口径，路径入口由配置层统一。 |
| `wf_asset_archive.py` | 293 / 282 | C 的 7-Zip 查找依赖 Windows 默认目录；B 支持 WF_7ZIP、可注入查找器并对无效显式路径报错。M0 保留 C 解包行为，配置化另行处理。 |
| `wf_asset_maintenance.py` | 1070 / 1067 | C 从项目内 mod-tools 发现工具资源；B 显式传 tool_root。保留 C 维护计划逻辑，修复布局定位。 |
| `wf_asset_policy.py` | 488 / 482 | ReferenceIndex 的 profiles、生成目录、pending、changelog 归属不同；B 可指定独立工具根，C 按项目内 mod-tools 查。保留 C 策略和证据规则，路径另迁。 |
| `wf_assets.py` | 597 / 423 | B 多 live-CDN 当前视图、iOS 根、MP3 ID3 padding/voice dump 解析；C 是生产 builder 使用的本地 store 和 PNG/MP3 读写。保留 C，避免叠层和编码行为同时变化。 |
| `wf_atf.py` | 772 / 459 | B 额外实现 ETC2/EAC alpha 和 iOS cutin 成对输出；C 是已交付生产素材的 ATF 行为。选 C；新增平台能力留待有独立回归样本时合并。 |
| `wf_balance_patch.py` | 354 / 357 | 主要差异是 store/profile 缺失处理，B 强制 active store，C 显式读取 profile。保留 C 数值修改逻辑。 |
| `wf_balance_patch_v2.py` | 583 / 584 | 主要差异是 store 定位，C 直接取 profile.store。保留 C 通用改表 API，store 解析统一为显式校验；v2 接口名本身不作为归档依据。 |
| `wf_balance_suite.py` | 1487 / 1488 | 除 store 获取方式外有技能槽文字注释差异；保留 C 原备份选择和批处理数值口径，统一 store 校验；日期专项平衡脚本另归档。 |
| `wf_boss.py` | 300 / 295 | B 用 live-CDN revision 缓存及 exists_current；C 用 store 文件 mtime 与实际文件存在性。生产视图由 wf.view 负责，选 C。 |
| `wf_chain_squash.py` | 698 / 697 | B 认识 ios 根并经 core 解析 CDN；C 只合 common/medium/android/patch，接受 WF_CDN_DIR。选 C，避免给现有包改变归档根排序。 |
| `wf_character_flow.py` | 1072 / 1022 | C 有客户端 capability 门禁、服务端 mana board 同步、Windows 清理重试；B 有声明/生产边界/实时store漂移与键并集门禁。不能按行数判新；以 C 编排为底，未自动拼接两套发布授权语义。 |
| `wf_character_pack.py` | 3528 / 3501 | C 增加 client legality、素材形状与 mana-board服务端镜像；B 增加若干 JSON codec、accepted replacement 和 Windows逻辑路径约束。选 C 保持生产包预检；B独立发布器不激活。 |
| `wf_character_requirements.py` | 413 / 475 | C 识别 ResolveByElement 并按属性派生真实特效路径，避免把基目录误当文件；B 无此解析。选 C。 |
| `wf_character_rollback.py` | 653 / 651 | C 使用 release._repo_paths 三元组和仓内快照；B 用路径对象分离 tool/server/CDN。选 C 与 C release 配套。 |
| `wf_character_workspace.py` | 579 / 591 | C 检测把哈希分片路径误写为 logical_path 的错误；B 的 _absolute 有 Windows 扩展长度前缀。选 C，保留防二次哈希门禁。 |
| `wf_client_legality.py` | 217 / 1552 | C 1552行包含补丁作用域、声明字段、元素/DSL/装备/像素等完整门禁，已拒绝 Bool、multiply 和+14..18空值；B 217行包含独立Option规则。选 C并以自有枚举表补非空非法PF等级检查，生成默认另放 wf.rules。 |
| `wf_decrypt_all.py` | 701 / 694 | B 将命令行构造抽出 build_parser，要求明确输入/输出；C 保留自动定位与旧默认路径。保留 C 解密恢复算法，路径统一配置。 |
| `wf_describe.py` | 473 / 406 | B 额外处理六属性角色组、来源字段和若干描述分支；C 是生产文本校验链使用版本。选 C，未把文字输出差异混入逐字节验收。 |
| `wf_dev_catalog.py` | 3622 / 3618 | CDN/server根以及视图物化、回填输出定位存在差异；选 C 的开发目录与覆盖规则，根目录转为配置。 |
| `wf_dsl.py` | 380 / 492 | C 额外有迭代命令、光束方向、坐标来源和玩家侧DSL校验；B 读取当前live-CDN raw。选 C 保留生产编码/校验，视图由 wf.view 提供。 |
| `wf_dsl_sig.py` | 1980 / 1819 | B 额外新增 DslSignatureError、参数编辑断言和 validate_action_dsl；C保留1819行签名真源。选 C，B新增API无当前可达消费方。 |
| `wf_enhancement_policy.py` | 854 / 887 | 两版 OfficialBaseline 的基线查找/可用性校验不同；C保留生产官方基线索引语义，避免把当前store混作官方源。 |
| `wf_enhancement_switch.py` | 1513 / 1508 | resolve_context 的 active store/path 推导不同；选 C 批次语义，路径配置化，历史增强开关风险在原工具中保留。 |
| `wf_export_assets.py` | 275 / 266 | B 抽出 CLI parser 并要求显式路径；C有旧目录自动查找。保留 C 导出算法并清除绝对默认。 |
| `wf_extract_paths.py` | 214 / 214 | 仅模块文档示例发生变化，函数定义及可执行语句相同；选 C后清理示例路径，无业务行为差异。 |
| `wf_field_catalog.py` | 506 / 506 | B 通过 q.read_raw 可读实时叠层；C 通过 q.store_path 读取物化store文件。选 C，避免隐式跨视图。 |
| `wf_fire_analysis.py` | 448 / 449 | 主要差异为 require_active_store 与 resolve_profile().store；选 C分析逻辑，配置入口统一。 |
| `wf_gui.py` | 8874 / 8904 | C 内嵌 composer，支持C版发布/赛季/API；B外置composer和studio、live revision、pending路径新布局。选 C与其HTML配套；补生成默认值而不导入不可达的B composer。 |
| `wf_kyle_canary.py` | 1407 / 1408 | B 处理iOS/Android双端cutin并读当前视图；C避免重复处理已规划ATF。特定角色脚本选 C后归档；抽出的通用工具另记迁移清单。 |
| `wf_mod_tool.py` | 1844 / 1707 | B 新增live-CDN读取、严格store校验、路径显式解析及orderedmap helper；C保留生产核心表读写和profile规则。选 C并统一路径，不改编码语义。 |
| `wf_night_pack.py` | 162 / 162 | C直接locate/read_bytes；B用read_current叠层读取。角色固定包选 C后归档。 |
| `wf_pack_consolidate.py` | 527 / 526 | B经core解析CDN；C取显式参数/WF_CDN_DIR/旧默认。选 C合包规则并替换路径配置。 |
| `wf_publish.py` | 1062 / 667 | B新增active manifest登记、iOS cutin闭包和required keys；C发布链保留client profile/WFX门禁。选 C，仅收源不执行发布；不混合外部写入模型。 |
| `wf_publish_guard.py` | 376 / 346 | B将assets/asset-patch/active叠入最新键索引；C检查旧CDN archive且从GUI取store。选 C源，M0验收走收编prepush，不声称两套发布门禁等价。 |
| `wf_quest_lib.py` | 329 / 283 | B新增fallback/live-CDN read_raw和exists_current；C按确定store物化路径读表。生产builder依赖C，选 C。 |
| `wf_recover_pathlist.py` | 235 / 237 | B要求base/pathlist/out显式参数；C自动发现base且带旧默认。选 C路径恢复逻辑，路径配置化。 |
| `wf_release.py` | 2054 / 2034 | C有client capability预检和Windows长路径清理；B有新JSON集合codec与独立路径对象。选 C与character_flow/pack同步；不主动执行发布。 |
| `wf_rogue_banner.py` | 137 / 136 | pending路径与store取得方式不同；选 C横幅编码逻辑，路径配置化。 |
| `wf_rogue_build.py` | 17842 / 7777 | B17842行较C7777行多HP审计、Sphere/OrochiEx/特殊boss克隆与全场景闭包；C是当前生产依赖基底。选 C；不能因B更大就覆盖已交付数值与关卡语义。 |
| `wf_rogue_bundle.py` | 1958 / 1878 | B新增动作身份闭包审计并改bundle读取/地形加载；C保留既有native bundle目录和store读取。选 C。 |
| `wf_rogue_reroll.py` | 225 / 530 | C530行有服务端赛季查询/切换、baseline记录、fingerprint；B225行较少。选 C保持赛季行为；M0不运行服务端路径。 |
| `wf_rogue_rewards.py` | 1416 / 1560 | C增加legacy写入阻断、效果强度和魂珠合法性规则；B编码/读取路径有分歧。选 C，保护当前奖励数据与门禁。 |
| `wf_rogue_save.py` | 396 / 353 | B支持可配置数据库/MuMu与缩略图门禁；C使用旧默认路径。选 C存档操作语义并配置路径，本任务不调用设备/数据库写入。 |
| `wf_rogue_shop.py` | 682 / 568 | B增加票据价格/资源根推导，客户端和服务端shop构建有变化；C保持已交付商店结构。选 C。 |
| `wf_rogue_validate.py` | 1263 / 1225 | B有可配置client patch目录并增加离线轮次/PNG相关差异；C动态加载历史task builder。选 C并审计文件加载，历史脚本不自动成为兼容API。 |
| `wf_selftest.py` | 369 / 370 | B通过core.resolve_active_store验证路径；C检查WF_TARGET_STORE然后profile.store。选 C自检项，配置入口统一。 |
| `wf_seris_release_pack.py` | 532 / 578 | C新增Windows扩展长度路径与失败清理提示，避免长目录静默漏文件；B无这些处理。选 C；公共打包API需保留，固定角色入口归档。 |
| `wf_share_variant.py` | 648 / 853 | C新增unique context门禁、pending overlay加载/合并及requires生成变化；B没有这些覆层语义。选 C维护分享包闭包。 |
| `wf_unique_mech.py` | 219 / 220 | 主要差异为store/profile取得方式；选 C机制分析逻辑，路径配置化。 |
| `wf_voice.py` | 260 / 255 | B严格WF_FFMPEG/PATH且无个人目录fallback；C可继续fallback旧目录。选 C转码语义，工具路径交给配置层。 |

## 哨兵缺口与修复

C 已经用专门规则拒绝 `by_each_trigger_puller` 非布尔和 `multiply_trigger` 非枚举，且 `declared_block_field_problems` 已拒绝声明字段 +14..18 空串。任务书“C可能缺这些修复”经核对不能直接成立；不能再整段替换1552行验证器。

真实缺口是 `wf_gui.composer_generate` 未填默认值，以及非空但非法的 `end_power_flip_accepted_levels`（如0、4）仍可通过已有声明必填规则。本次按 C 枚举表独立实现 `wf/rules/instant_content.py`：仅瞬发行、仅该kind声明的字段填 false/0/(None)，保留显式值，校验PF等级为(None)/1/2/3/11/12。没有读取或复制GPL工坊代码；当前我方B也已具备这些规则，任务书对B落后的描述已过时。

定向验证：`python -B -m pytest -q tests/test_m0_sentinels.py tests/test_client_legality.py` → **119 passed, 40 subtests passed**。测试覆盖4类表布局、未激活块、未声明字段、显式值保留、非法/合法PF等级，并隔离GUI安装环境调用实际composer函数。

## 资源和归档建议

- 保留 C 根枚举/配置JSON、词条手册、GUI HTML，以及 assets/docs/examples/schemas/server-patch/templates/release-contracts/rolf_tools 中活跃工具实际读取资源；不能只复制py。
- `C/wf_wiki.py:184` 明确读取 `wiki/` 静态资源。若保留导出器，应保留必要静态资源；wiki-community/qq_monitor是独立应用，不能因同仓存在就当作MOD工具依赖。
- 带日期/版本、固定角色脚本与.bak归档时，测试同步退出收集；公共工具若调用角色文件中的通用函数，应先提炼，再归档原入口，不能让活跃兼容层反向import archive。
- 已识别需提炼的公共消费者：art_voice_audio→gerald_voice_audio；featured_face_crops→campus_art_images；ui_derive→canary_skin；cursed_weapons→balance_20260927d_ginovi；release→seris_release_pack；seasonal7/midautumn/campus/nephtim被本次万圣配方复用。迁移落点与实际归档数量以M0总报告及迁移清单为准。
- A 自带的 `wf_release_v1/` 是通用发行协议包，`v1` 表示协议版本，不属于一次性交付脚本；保留原 A 包及其离线测试，并明确适配与 C 的 API 边界。A 既有顶层通用模块恢复为 `wf/compat/` 实现和 module alias；相应纯编译测试恢复，角色专用包装测试留归档。该兼容保留不改变 B 新导入 **1/170** 的静态审计口径，详见 `compatibility.md/json`。

## A/C 通用 API 适配

从原 A `wf_character_pack.py` 原样提炼 `logical_path_problem`、`windows_logical_path_key` 和3个常量至 `wf/deliver/logical_paths.py`，由 C pack re-export；恢复 A workspace `_absolute` 的 Windows 扩展长度路径语义。C的清单与角色逻辑保留。发行协议包的失败清理复用其既有 `native_path`，长路径测试保留完整资源名与断言。来源与实现位置记录在 JSON 的 `A_compatibility` 和 `post_merge_compatibility` 字段。

## 证据与限制

`source-decisions.json`逐项保存 A/B/C 原始SHA256、51项函数差异、170项B独有决策、1118个源码的导入边、动态导入及文件加载搜索。临时审计脚本为 `work/m0/source-audit-scan.py`，原始完整差异摘要为 `work/m0/source-diff-summary.json`。审计不执行任何外部源码，不访问服务或设备，不证明设备兼容或发布安全；生产逐字节验收由recipes重跑结果单独证明。
