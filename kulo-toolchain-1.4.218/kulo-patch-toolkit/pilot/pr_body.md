<!-- ccr-projects-attribution: {"github_login":"kuronzzhan-droid"} -->
_Requested by **zzh**_

## 目标

主线里有 26 个剧情 boss 没有自己的 boss 战关卡（盘点见项目内《主线boss盘点》）。这条 PR 先做一个试点：以机兵降临讨伐（节点 60）为模板，把第 9 章「歼灭者」做成可单人、可联机的降临讨伐关卡，跑通后其余 boss 按同一生成器批量补。

## 范围与影响层

- [x] server
- [x] cdn
- [ ] client
- [x] 仅文档或工具

## 改动说明

- 候选包 `assets/asset-patch/active/candidates/pinball-1.4.130-1.4.131-2-mainboss-epuration-candidate.zip`（`candidate_only`、`enabled: false`，版本号留给所有者，`cdn_version` 不变），5 个文件：
  - `boss_battle_quest`：新增节点 80，关卡 1080001-1080005，逐列套用节点 60，只改名称/缩略图/开放时间/前置/推荐属性/field/BGM；初级前置 = 主线 9-5-2，之后逐档解锁。
  - `boss_battle_stage_node`：新增「歼灭者讨伐」入口（降临讨伐分组），商店分类沿用 60。
  - `field_data` / `zone`：新增 `mod_mainboss_epuration`，boss 配置原样复制主线 9-5-2（`epuration_boss_single`）。
  - 新地形 `battle/terrain/multi_normal_quest/mod_main_boss/boss_battle_epuration`：主线地形只有 3 个复活位，联机按三人分 9 个，这里补 6 个（坐标取领主战不死王地形）。
- 服务端：`assets/boss_battle_quest_cnmod.json` 加 1080001-1080005（奖励数值复制 1060001-1060005，属性改为 5）。不改任何 `src/` 代码。
- 生成器：`tools/fantasy-gauntlet-mod-tools/build_mainboss_battle_candidate.py`，后续 boss 在 `BOSSES` 加一条即可生成。
- 暂借未换的展示件：节点横幅/背景、领主币商店分类、掉落展示仍是机兵节点 60 的。

## 验证

- 生成器产物与真机测试用的包逐成员 sha256 一致（5/5）。
- 本地服 8001 以本机专用补丁挂载（未提交），MuMu「MuMu安卓设备-1」、账号 dev_mumu1：
  - 客户端拉取约 1MB 增量后进主城无崩溃；降临讨伐列表出现「歼灭者讨伐 NEW 0/5」。
  - 单人「中级」开打、通关、结算正常，「高级」随后解锁。
  - 联机「高级」建房，2 个 NPC 补位后三人开打并通关，结算正常。
  - 服务端日志：`single_battle_quest/start|finish`、`multi_battle_quest/create_room|start|finish` 全部 200，无 body error。
- `bash scripts/check-hygiene.sh --all` 与 `node tests/hygiene-license.test.cjs`（CI 同款两步）本地通过。
- 未测：联机中有人阵亡后的复活位（测试账号太强没人倒下）。

## 风险与回退

- 候选包整表替换 `boss_battle_quest` / `boss_battle_stage_node` / `field_data` / `zone`，基于 1.4.130。若所有者编号前已有其他包改了这几张表，需要用生成器在新基线上重跑。
- 回退：不启用候选包即可；服务端 cnmod 新条目在客户端没有对应关卡时不会被访问。

## 边界检查

- [x] 本 PR 目标分支是 `staging`，没有直接推送 `main` / `staging`
- [x] 没有提交密钥、`.env`、`config/`、APK/IPA/SWF、数据库、日志或签名材料
- [x] 没有在 `.cdn/` 内新增或修改资源包
- [x] 涉及存档、奖励入手来源、CDN 分包或准入配置时，已在上面说明兼容性和回退方式
- [x] 服务端代码改动已同步 `src` 与受版本控制的 `out` 产物（本 PR 无代码改动）
- [x] 一个 PR 只包含一个明确任务，没有无关改动

🤖 Generated with [Claude Code](https://claude.com/claude-code)
