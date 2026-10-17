# M0 收拢 MOD 工具真源执行报告

日期：2026-10-17。工作分支：`refactor/m0-consolidate`；起点：`fd433b0`。本文中的 `WF_ROOT` 表示本机路径配置的资料根，不是仓库内硬编码。

## 交付结论

以 C 生产工具为基底完成收拢，新增 `wf/view`、`wf/apk`、`wf/deliver`、路径配置和离线历史配方。B 独有 170 个根模块完成导入图审计，只有 `wf_battle_atlas_repack.py` 作为新增 B 模块进入活动层。A 已存在的通用 API 继续作为兼容接口保留；角色、日期、特定交付脚本及备份归档。

两次指定交付均实际重新构建：平衡 223 的 1 个 ZIP / 3 个成员、万圣历史 221 的 11 个 ZIP / 310 个成员全部逐字节一致，每套各重建两次。12 个 ZIP 仅容器 DOS 时间戳不同，原期望 ZIP 的初次与最终 SHA-256 一致。万圣历史 221 使用有证据支持的显式历史分支；当前源的 222 修复保留，两者不能混作当前版本。

本任务的写入、临时依赖、日志、生成物和测试夹具都位于本 worktree。外部源码、store、active、母本及期望产物只读；未 push、未建远端分支或 PR、未调用服务器部署、设备、MuMu 或发布流程。仅作本地提交。临时过程文件在忽略的 `work/m0/`，长期可维护的审计记录位于 `docs/m0/`。

## 合并决策与来源

| 对象 | 本次选择 | 证据与边界 |
|---|---|---|
| A 公共仓起点 | 保留既有通用 API、严格路径与输入检查；固定角色实现归档 | `fd433b0`、`docs/m0/compatibility.json` |
| C 生产源 | 根 528 个 Python 文件作为底本；保留所需资源与静态页面 | `docs/m0/source-decisions.json` 原始 SHA-256、最终归档清单 |
| B 独有 170 项 | 新导入 1 项，169 项不从 B 导入 | `docs/m0/source-decisions.md` 完整 170 行决策表；保留 A 既有模块不等于新增 B 模块 |
| B/C 同名 75 项 | 相同 24、分叉 51；51 项均以 C 算法为底 | 本报告下一节逐项说明；路径适配和必要兼容函数另列 |
| 生产可达性 | AST 解析 1118 文件、32 个近期生产目录，零解析失败 | JSON 的 production_roots/source_imports/dynamic_import_review；排除镜像、tests、旧工具副本 |
| 公共 builder | cursed_abyss 生产逻辑；与 bughunt 比较后提炼 | `docs/m0/recipe-results.md`、`recipes/source-provenance.json` |
| APK / prepush | 10 个通用 APK 库、30 个历史脚本；prepush 拆为 6 模块 | `docs/m0/toolkit-intake.md` 和同名 JSON |
| 静态资源 | 保留 C 工具使用的 assets、art、docs、examples、schemas、server-patch、templates、release-contracts、wiki、wiki-battle 等 | C `wf_wiki.py` 确实消费 wiki；独立 wiki-community/qq_monitor 应用不作为工具源一并迁入 |

可达性审计包含字面 import、动态导入和文件加载检查。没有把 out 内整仓镜像相互引用算作生产依赖，否则会将 115 个 B 独有模块误判为可达。任意运行时环境变量指定的新模块不在静态闭包保证内。

## 51 个分叉文件的取舍

以下是源选择与行为差异记录，不代表把每份 C 原文保持不动。除 `wf_extract_paths.py` 只有文档变化外，其余 50 项都有行为差异。来源原始摘要、符号增删及差异标记见 `docs/m0/source-decisions.json`。

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

## 收编、兼容与归档

五个视图库逐一迁入 `wf/view`。`base149`、`live149`、`layout` 的两个来源仅有路径差异；`stage_all`、`dsltools` 原文件逐字节相同。`stage_all` 的通用函数与特定交付 main 分离，后者保存在 `archive/legacy/tools/stage_all.py`。历史视图改为显式构造，切换视图时清缓存，保持原版本上限与 extra ZIP 覆盖顺序。

APK 的 40 项原始 SHA-256 和去向均在 `docs/m0/toolkit-intake.json`。`wf/apk` 的通用库不在 import 时读取外部 APK 或复制文件；基线文件与摘要显式传入。prepush 保留兼容入口 `wf_prepush_check.py`、原 CLI 和检查算法；逐函数 AST 比较只有 pathlist 定位发生工程变化。未运行历史 APK 签名或设备验收。

将角色脚本中的通用图像、音频和打包函数分别提炼至 `wf/art`、`wf/deliver`，避免活动模块反向导入归档。配方使用的角色实现迁为参数化 `wf/chars` API。A 通用模块通过 `wf/compat` 和模块别名保留旧导入名；`wf_release_v1` 的 v1 是通用协议版本，因此保留其活动包与适用测试。固定角色、固定产品池和日期交付入口仍归档，不用宽泛星号导入重新暴露角色专用函数。

归档清单共 793 条，其中 730 个文件仍归档，63 个通用协议包文件恢复到活动位置，最终路径缺失为 0；752 条有迁入前摘要，其中 255 条因路径、卫生或兼容清理改变。最终路径、迁入前摘要、worktree 最终摘要和 Git blob 标识见 `docs/m0/archive-manifest.json`，统计见 `archive-summary.json`。`final_sha256` 对应本机最终文件字节，Git 提交按 `.gitattributes` 规范化文本换行，提交对象以 `git_blob_sha1` 核对。**不能宣称归档文件全部与迁入前字节相同**；四份 `.bak*` 的来源记录另见 `docs/m0/backup-intake.json`。`pytest.ini` 仅从 tests 收集，明确排除 archive/work；配方运行时还拒绝来自 archive 的模块，无论模块别名是什么。

## 瞬发哨兵与适配修复

C 的 1552 行合法性校验器已经拒绝 `by_each_trigger_puller` 非布尔、`multiply_trigger` 非枚举、声明字段 +14..18 空串。真实缺口是 composer 生成时没有填默认值，以及非空但非法 PF 等级可通过声明检查。本次按我方枚举表独立实现 `wf/rules/instant_content.py`，仅对瞬发且该 kind 声明的字段补 `false`、`0`、`(None)`，保留显式值，并校验 PF 等级。没有复制 GPL 工坊源码。

定向门禁 `tests/test_m0_sentinels.py` + `tests/test_client_legality.py`：119 passed，40 subtests passed。其他适配包括独立仓根定位、共享 store/CDN/server 解析、Windows 长路径夹具、数据库与设备工具显式配置、历史 APK builder 延迟加载。外部数据缺失与纯单元测试分离，避免整模块跳过其中可执行的合成测试。

## 路径配置与清理统计

`wf/paths.py` 提供 `root_path()`、`path()`、`configured()`。环境变量优先于 `profiles/local.json`；`WF_PATHS_PROFILE` 选择路径配置，旧 `WF_PROFILE=cn` 仍是版本档案 ID。store、kulo、runtimes、store131、ASR 模型、下载和签名密钥等可分别指定。路径解析本身不创建目录，默认输出留在本仓。

记录的主批次替换了 177 个文件中的 275 处机器根字面量；323 个文件移除了 337 个路径插入调用。包收编、归档素材和兼容恢复另有独立适配，因此这些是主批次的可核查计数，不是假定所有改动只有这些。明细见 `docs/m0/path-cleanup.json`。

检查脚本 `scripts/check_no_hardcoded_paths.py` 同时扫描 Git 已跟踪和未忽略新增文本，包含 archive；检查盘符根的多种转义形式，并识别变量间接引用、sys/path 别名、insert/append/extend 导入路径。无法解析的 Python 候选也阻断，不再静默跳过；这关闭了异常换行归档脚本造成的漏检。已接入 `tests/test_m0_paths.py` 及 `.github/workflows/hygiene.yml`。本机 profile 和 work 不进入版本控制。

## 公开仓卫生

详细发现及逐条复核在 `docs/m0/hygiene.md` / `.json`。gitleaks 8.24.3 首次完整候选快照 1999 文件，退出 1、24 条原始命中；逐条都是游戏资源键/摘要、测试占位或私钥格式阻断标记，未发现真实密钥/token。这里保留工具非零状态，不把人工复核结果写成工具零命中。

地址、邮箱、家目录及数字账号启发式扫描共 372 个候选，全部完成上下文复核。旧 APK 源端点、个人下载/密钥路径和审计 literal 中个人目录已改为配置或脱敏；原始源摘要仍保留。未重写历史。

原仓卫生门禁起初只覆盖当时已跟踪文件，不能用那个 0 证明新增文件通过。因此对完整候选补做等价扫描，18 个命中对应 17 条精确文件+整行豁免，均为合法常量/负向测试；修正路径后等价扫描为 0。自测已修为在本仓隔离 Git 夹具内运行，10 项负向/正向测试通过，且保留对豁免文件新增泄漏及篡改豁免行的阻断能力。最终 stage 后原门禁结果列在下节。

此扫描不等于穷尽证明 Git 历史、二进制内部、任意自然语言地址或远端账户安全。

兼容 API 恢复后另做独立快照复核，未覆盖前次证据：2,108 个候选文件，gitleaks 仍为 24 条已审核误报；启发式候选 531 条，其中 525 条映射原归档位置后与前次已审核整行相同，6 条只是精确豁免路径调整。新增候选值、确认新增风险和未复核项均为 0，见 `docs/m0/hygiene-final.md` / `.json`。其后变更仅为路径检查加强、换行/尾空白清理及报告补全；最终原仓门禁再次覆盖全部暂存内容。

## 两次交付的逐字节重跑

| 交付 | 构建轮次 | ZIP 数 | 相同成员 | 不同成员 | 归零 DOS 时间戳后容器相同 |
|---|---:|---:|---:|---:|---:|
| 平衡 1.4.223 | 1 | 1 | 3 | 0 | 1 |
| 平衡 1.4.223 | 2 | 1 | 3 | 0 | 1 |
| 万圣历史 1.4.221 | 1 | 11 | 310 | 0 | 11 |
| 万圣历史 1.4.221 | 2 | 11 | 310 | 0 | 11 |
| 万圣两轮互比 | — | 11 | 310 | 0 | 11 |

平衡入口：`python -B -m recipes.balance1017 --write`。按照原 builder 执行八角色旧值断言与表重编码。原 extra_zips 后来追加了目标 223 自身；本次锁定原截至 222 前缀及每个输入摘要，配合 `WF_TIP=206`，没有把期望输出作为输入，也没有修改外部列表。输出 `work/m0/balance1017/`。

万圣入口：设置 `WF_REPLAY_RUN=historical221-run1`（另一轮 run2），运行 `python -B -m recipes.halloween221`。每轮从原表、母本资产、批准透明图/蒙版/WAV 完整执行四角色 init、tables、kit、assets、pixel、art、voice 和最终分包。输出 `work/m0/halloween-full/historical221-run1/` 与 `historical221-run2/`。八项立绘门禁无问题，87 个 MP3 槽由批准 WAV 重新转码，实际读过的 351 个 viewstore 成员与 105 个历史 ZIP 叠层逐字节一致；56 个运行时 WF/配方模块全部来自本仓。

保留的差异证据：当前 package 重打和当前源两次完整构建都只有 309/310 一致。唯一不同是塞里奥尔 PF3 DSL，当前 463 字节与 222 修复交付一致，历史 221 为 497 字节。没有找到完整旧版 221 源快照；依据现有原树克隆代码、222 修复注释和官方 `knight_lv3.deflate`，恢复“根索引 10 设为 133、原 AMF 编码、raw-deflate level 9”的显式历史分支，独立证明得到历史 SHA-256 `39d0013867105abb217bfc2fdab9308ddcfe1aaa9b9556b6ddc264ee443e85ed`。生成阶段不读期望 ZIP；普通调用仍保留 222 消毒修复。

逐成员真实字节、长度、摘要、原期望前后摘要、容器归零比较及来源记录均在 `docs/m0/recipe-results.json`，解释与运行命令在同名 Markdown。容器仅在内存副本中消除 DOS 时间差来比较，不修改原 ZIP 或伪装原容器。

配方 Python 写入审计限制在当前 checkout，覆盖截断、删除、链接、移动及 UNC/Windows 长路径。ffmpeg 的输出目录、临时目录、cwd 和环境另行校验，清除 FFREPORT 外写通道；子进程不继承 Python audit，**不是 OS 沙箱**。末轮安全和缓存修复只复跑定向测试，未无理由重复全部历史重建。

## 最终检查与本地提交

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 最后一次全量 pytest | **3450 passed、357 skipped、2256 subtests passed、1 failed，exit 1，310.25 秒** | `work/m0/pytest-final.log` / `.xml`；唯一失败见下一行，不能写成整条命令 exit 0 |
| 修复后路径测试 | **5 passed，exit 0，18.28 秒** | `work/m0/pytest-final-paths.log` / `.xml`；包含全仓扫描、配置优先级和负向门禁 |
| 路径脚本 | **1877 个文本文件、0 finding，exit 0** | `python -B scripts/check_no_hardcoded_paths.py`；最终输出记录于 `work/m0/path-final.json` |
| 配方后续顺序回归 | **437 passed、103 skipped、329 subtests passed** | `work/m0/pytest-post-recipe-fix.log`；覆盖环境污染修复后的配方、发布、rogue、武器、WFX 与角色包顺序 |
| 原仓卫生门禁 | **exit 0**，完整 stage 后执行 | `bash scripts/check-hygiene.sh --all` → `提交卫生检查通过。` |
| 卫生门禁自测 | **10 项通过，exit 0** | `bash scripts/tests/test-hygiene.sh` → `卫生门禁自测通过。` |
| 补丁/归档与兼容证据 | 原始输入摘要保留；793 条归档记录和全部兼容目标的本机摘要/Git blob 校验 **0 mismatch** | `docs/m0/archive-manifest.json`、`docs/m0/compatibility.json` |
| 提交卫生 | `git diff --cached --check` 通过 | 仅修尾空白、换行与注释格式时核对可执行 AST 不变 |

全量的唯一失败是 `tests/test_m0_paths.py::test_repository_has_no_machine_paths`，发现历史 PARADOX 归档脚本残留 `sys.path`。已删除残留、修正异常换行，并增加“Python 解析失败必须阻断”的规则；随后上述五项路径测试与独立扫描通过。其余功能代码未变，无未关闭失败。这里复用本轮已通过的功能测试证据，没有把原失败记录删掉或伪造新的全量零退出结果。逐用例跳过、原因分类与闭合记录见 `docs/m0/test-results.json`。

357 项跳过的分类是：外部 client-patch 缺失 190 项及 5 个收集阶段模块、外部游戏数据 127 项、宿主文件系统能力 16 项、外部生产资产 4 项、指定角色包 8 项、显式 truth root 1 项、外部服务端源码 6 项。收集阶段模块中尚未收集的内部测试数量另记，不能把它们算成已执行或已通过。没有为消除失败而伪造这些外部输入。

恢复的发布协议测试会使用短时本机回环 HTTP 合成夹具；这些夹具不是测试服、正式服或设备。没有将本地夹具结果写成实际服务验收。原始日志保留于忽略的 work 目录，长期报告只保留去除机器绝对路径的结论与用例标识。

本地提交按主题拆分如下；未执行 push：

| 提交 | 主题 |
|---|---|
| `e86ca08` | `refactor: consolidate APK patching and prepush libraries` |
| `a4811aa` | `feat: add reproducible historical delivery recipes` |
| `899ffcd` | `build: enforce configurable paths and repository hygiene` |
| `ee261ab` | `refactor: consolidate production tools and archive legacy workflows` |
| `3450bdc` | `fix: preserve generic legacy APIs alongside production tools` |
| `40a1a59` | `fix: reject unparseable Python in the path gate` |
| 本报告所在提交 | `docs: record M0 completion evidence` |

最终交付状态以本报告提交后的 `git status --short` 空输出为准；忽略的本机 profile、测试依赖、构建产物与日志保留供复核，不进入提交。分支保持 `refactor/m0-consolidate`，无 upstream。

复验命令（本任务 pytest 安装在忽略的本仓目录，未安装到外部）：

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'work/m0/test-deps'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
python -B -m pytest
python -B scripts/check_no_hardcoded_paths.py
# TEMP/TMP 指向本仓 work/t 后运行仓内卫生脚本
bash scripts/tests/test-hygiene.sh
bash scripts/check-hygiene.sh --all
```

## 已知限制与 M1 建议

1. 外部 client-patch、特定服务端资产、完整 store 等不随工具仓分发；相关集成测试的跳过原因必须与纯单元测试成功分开阅读。本次未验证设备、运行中的服务或发布。
2. B 的 iOS/live-CDN/独立发布语义与 C 不同，未因为文件更新或更长就合并。M1 如需这些能力，按 51 项差异表选择独立回归样本后逐项纳入。
3. 源 C 的若干巨型历史模块继续存在；本次新公共库已按职责拆分。M1 优先拆 GUI、rogue_build、character_pack 的稳定接口，不以大规模重写替代本次已确认的字节基线。
4. 归档保留历史依赖与上下文，不保证直接运行；兼容层不能反向导入 archive。没有选入的 B 169 项不表示代码不正确，只是本次没有生产可达证据。
5. 万圣 221 复现证明的是历史字节可重建，不表示该旧 PF3 行为适合再次发布；保持历史分支与 222 修复隔离。
6. M1 建议把输入 ZIP、view 上限、extra 顺序、资产母本和算法版本统一做成版本锁，将本次 313 个成员比较作为真实回归，并继续补外部集成环境的可选门禁。

## M0.1 修复

本节记录 2026-10-17 按 M0.1 任务书对上述初版结论的修正。前文保留为 M0 当时的执行记录，最新状态以本节和链接的专项报告为准。写入仍只发生在当前 worktree；外部源码、资料、store、active、期望包只读，未操作其它 worktree、服务器或设备，未 push。

### 修正源选择的依据（H1、L4）

撤回“因为 C 是完整生产依赖基底，所以所有同名分叉都选 C”的推断。原 builder 的 `fw.py` 从 `oldrepo_modtools` 读取合法性与描述器，`base149` 从 kulo 工具副本读取 `wf_quest_lib`；这不是单一 C 来源。配方逐字节一致只证明该调用路径上的重建等价，不能证明 C 已包含 B 的其它安全修复。

本轮按 B/C 实际共同祖先 `4eef6915c49f5705fad0c619679c92d74101688b`（2026-07-16）审计之后的工具提交，覆盖任务书指定的 17 项及更早的另外 36 项。适用于当前调用路径的修复回收后增加行为回归；B 独有引擎、平台能力和内容策略不因文件同名就整体覆盖。逐提交的状态、具体符号、理由和负向验证结果见本节后续 H1 验收及 `docs/m0/b-lineage-review.md`。

回收包括计分鲨鱼候选/身份/深层锚排除、三来源伤害抗性相加和写前门禁、CreateCondition p8 可空及 Option<SLvValue> 精确类型、Standard Funnel 反向引用、混搭的闭包/地形/实际等级校验、能力词条与 GUI 枚举语义、发布根和 Windows 子目录权限，以及禁止自定义 codec 替换内建校验器。DSL 与 rogue 通用规则拆进 `wf/rules/`，没有整体覆盖 C 的角色内容、运行模式或发布协议。

H1 五个专属测试文件 **61 passed，exit 0**；加上最终语音回归为 **71 passed、5 subtests passed**。在独立进程和源码副本中逐项撤回修复，**17 项变异全部得到真实断言失败、exit 1**；活动源码 SHA-256 前后不变。初始 C 在新核心测试上为 27 failed / 4 passed，描述器为 8 failed / 2 passed，这些旧失败与最终通过分开记录。逐变异行为和日志位置见 [`b-lineage-review.md`](docs/m0/b-lineage-review.md)。

### 路径与配置（M1、M2、M4）

`project_root()` 改为本工具仓根；发布保护的 `PACKS`、角色支持层的默认 `ROOT`、GUI 的 `ROOT/CDNDATA` 和 catalog 根同步修正。store 不再扫描 cwd、父目录、兄弟 WorldFlipper 包或旧目录；`find_world_upload()` 拒绝仓外搜索。服务器缺配由 `resolve_server_dir()` 明确抛出专用异常，不返回上一级目录。纯离线 catalog 只捕获“确实未配置”，错误配置仍报错。

现代外部输入统一为 **环境变量 > `profiles/local.json` > 未配置报错**。规范变量为 `WF_STORE`、`WF_SERVER`；旧别名继续兼容但警告，同值可兼容、不同值报冲突。`WF_PROFILE` 只选版本 ID，`WF_PATHS_PROFILE` 只选路径文件。旧 `profiles.json` 读取就警告，与现代配置冲突即报错。JSON `null` 表示未配置，空字符串、错误类型、显式缺失配置文件或无效目录仍报错。

保留的默认值限于仓内输出/路径表和安全离线占位路径，不把 `wf_root` 当作外部数据目录存在的证明。完整规则见 [`profiles/README.md`](profiles/README.md)，实现和测试汇总见 [`path-config-review.md`](docs/m0/path-config-review.md)。配置与消费者扩展定向回归为 **109 passed、17 subtests passed，exit 0**。全量收集还发现 ASR 在 import 时解析外部模型；已延迟到实际转录，既有音频/文本比较 4 项测试通过。

后续逐消费者复查覆盖 B/C 历史同名集合的 75 个模块：70 个仍在活动根目录，5 个已归档；归档项不冒充活动入口。实际修复继续落实到分析/平衡日志与 marker、rogue 资源/镜像/数据库/发布、角色流程、链整合、装备策略、离线工具链和 GUI 调用点。工具资源与输出留在本仓，服务端 assets、认证和事务从显式配置解析；只有实际需要的操作才要求 server。`WF_CDNDATA` / profile 镜像覆盖优先，缺省时必须从已配置 server 的 `assets/cdndata` 取得。GUI 的数据库和镜像改为使用时解析，避免只配置 store 的离线导入被未使用的服务端配置阻断。

末轮 16 个消费者套件 **374 passed、4 skipped、52 subtests passed**；独立审阅发现 `offline_store` 默认旧档案旁路后修正，受影响子集 **66 passed、1 skipped、15 subtests passed**。另一组六个 rogue/平衡消费者关联验证 **361 passed、25 skipped、167 subtests passed**，待 GUI 修正后又将它与新隔离用例和存档路径合测，**34 passed、8 subtests passed**。这些数字来自不同范围的重叠检查，不能相加当成全量测试总数。具体消费者、配置合同及记录见专项报告。

### 配方、底座与 pathlist（M3、L3、L5）

平衡底座锁记录实际 `tip=206` 的 **85 个 active ZIP** 名称、叠加顺序和 SHA-256，范围为 `131→132` 至 `205→206`；保留现有 **32 个 extra ZIP** 摘要，截止 222，不输入 223。运行开始和出包前都重新验证 active 列表及摘要，漂移拒绝出包。

本次八角色构建实际读取的 3 个成员全部来自 ZIP 覆盖层，**使用 store131 的成员数为 0**。锁中的 `store_members: {}` 是禁止任何未锁回退，而非关闭校验；未来新增回退读取必须补锁。针对 active 增删/内容变化和 store 摘要/未锁回退均有负向用例。

| 验收对象 | 最终成员比较 | 容器与边界 |
|---|---|---|
| 平衡 223 对原交付 | **3/3 相同** | 容器仅 DOS 时间戳不同 |
| 万圣历史 221 对原交付 | **310/310 相同** | 11 个 ZIP 均仅 DOS 时间戳不同 |
| 万圣当前源对原 221 叠加 222 | **310/310 相同** | 当前完整入口保持 222 修复 |
| 当前源对原 221 | 309 相同、1 不同 | 唯一差异为塞里奥尔 PF3 |
| 当前源 PF3 对原 222 | **463 字节及 SHA-256 相同** | 原 222 只是修复包，不能称两个完整容器相同 |

`python -B -m recipes.halloween_full` 现在执行当前源完整构建；`recipes.halloween221` 显式选择历史分支，两模式不得共用 run 目录。本轮均完整执行四角色素材与语音构建；H1 描述器修复后，再执行受影响的全部 kit 和分包，最终结果仍如上。蒙版只读取原 NPZ/JSON 缓存，**没有重算**；缺失时直接拒绝，不触发仓外缓存生成。

最终源码冻结后，对平衡配方再次在内存重算得到 **3/3**，并重新读取全部 **23 个输出 ZIP** 做 CRC 和成员核对，223、历史 221、当前源对 222 叠层的结果保持上表。万圣记录的 57 个运行模块中，后续变更交集仅 describe、core、character_pack：describe 与已复验版本一致，另外两者只改了配方未调用的函数/方法。函数级 AST 与模块摘要证据见 [`recipe-final-impact.json`](docs/m0/recipe-final-impact.json)，因此没有无理由重复素材重编码或蒙版计算；既有完整构建和受影响 kit 重跑证据继续有效。

原 prepush 目录的 `WF_PATHLIST_recovered.txt` 本次核查时不存在，不能称两份相同，也不能推断原交付时是否存在。当前缺失文件时原脚本有效路径为内建 58 条，仓内为 100,089 条，增加 100,031 条、减少 0 条。新增 `--pathlist` 参数可显式指定，显式缺失文件返回 exit 2。说明、执行命令与逐成员证据见 [`recipe-repair-review.md`](docs/m0/recipe-repair-review.md)。配方定向验收 **22 passed，exit 0**。

### 可读性与公开仓准备（L1、L6）

恢复了 67 个被压平的多行模块 docstring，包括审查点名的活动文件和归档文件。转换前后逐文件完整 AST 相同，保留 `${WF_ROOT}` 替换；既有 `pass  # Imports resolve...` 未改。

86 个仅供归档使用的整行 JSON 夹具已移到忽略的 `private-assets/tests/fixtures/`，共 **8,049,592 字节**；其中 `balance_2026092*` 为 75 个、7,931,475 字节。84 个归档测试文件的路径同步修正，原文件与迁移后文件 SHA-256 全部相同。获取与离线恢复方法、逐项摘要见 [`private-fixtures.md`](docs/m0/private-fixtures.md) 和同名 JSON。活动测试依赖的模板和 gz 保留待审，没有改写 Git 历史。

当前跟踪树实际二进制清单为 **237 个、11,882,858 字节**：233 PNG、2 JPG、2 gz，分属 20 个直接目录，按完整资源包归为 17 个可勾选目录。相对 `fd433b0` 新增 PNG 实测为 213，和原审查“230 张”的估算不同；本轮逐文件清单包含全部实际文件，未据估算漏项。作者审查表为 [`public-assets-review.md`](docs/m0/public-assets-review.md)，逐文件摘要在同名 inventory JSON。按任务书末尾“作者裁决（10-17 03:39）”，17 行全部勾选“可公开”，全部保留原位；这是作者决定的记录，不是工具自行认定素材权利来源。

`scripts/split_private_assets.py` 已准备，默认只预览，只有审查表中勾选“移出”并运行 `--apply` 才移动到忽略目录并修改可证明的静态引用。当前全“可公开”时实际预览为 **0 个目录、0 个移动、0 个引用修改**。本轮未对真实资源执行迁移。22 项合成测试及独立 5 项实证复核通过，覆盖路径链接、直接 CLI、未知根不误改、输出路径、JS 相对路径和完整回滚。

另外在 `work/m01/asset-rehearsal-d2y4w81j` 独立副本试迁全部 17 目录，真实资源不动；237 项资产 SHA-256 完全相同，Python 消费者子集 **342 passed、101 skipped、184 subtests passed**，Node 两套资源测试 **14 passed**，移动后的图标 builder 可直接运行。跳过分类与日志在 [`private-assets-rehearsal.md`](docs/m0/private-assets-rehearsal.md)。这个演练验证后续改变选择时的工具，不改变当前作者裁决，也不构成发布或 push 授权。

### 最终全量验收

生产源码冻结在 `ec6779d`；最后两项旧测试的严格 CDN 合同适配在 `063c385` 完成后重新执行整轮 pytest，最终 **exit 0**。不是只把失败项重跑通过后推定全量成功。

| 检查 | 最终实际结果 | 证据 |
|---|---|---|
| 完整 pytest | **3613 passed、357 skipped、2263 subtests passed，0 failed / 0 errors，exit 0；334.57 秒** | `work/m01/pytest-acceptance-run2.log` / `.xml` / `-exit.json` |
| 全仓路径扫描 | **1827 个文本文件、0 finding，exit 0** | `work/m01/path-acceptance.json` |
| 原仓卫生门禁 | **exit 0**，已将新验收 JSON 和报告纳入跟踪候选后执行 | `work/m01/hygiene-acceptance.log` |
| 保留资源与本地夹具 | **237 + 86 项 SHA-256 全部相同，0 mismatch** | `work/m01/final-asset-hashes.json` |
| 资源拆分默认预览 | 作者裁决全部可公开，**0 目录 / 0 移动 / 0 引用修改** | 当前审查表与 `python -B scripts/split_private_assets.py` |

26 条 pytest 警告来自专门覆盖旧配置别名的兼容用例。完整命令、终端统计、JUnit 两种计数口径、357 条跳过的用例标识与原因在 [`m01-validation.json`](docs/m0/m01-validation.json)。其中 JUnit 套件累计 `tests=6233`，实际 `testcase` 节点为 3967；本报告的主测试与子测试数量取终端摘要，未将 XML 节点数混用为执行数量。

| 跳过分类 | 数量 |
|---|---:|
| 外部 client-patch 集成源码 | 190 |
| 外部 client-patch 缺失导致收集阶段模块跳过 | 5 |
| 外部 live store / 游戏数据 | 127 |
| 宿主文件系统能力（POSIX / symlink 等） | 16 |
| 外部生产资产 | 4 |
| 指定角色包 | 8 |
| 显式 truth root | 1 |
| 外部服务端源码 | 6 |
| 合计 | **357** |

5 个收集阶段模块的静态测试函数数量单独记录，不能算成已收集、已运行或已通过。发布协议测试使用的短时本机回环 HTTP 夹具不是真实游戏服务；本轮不宣称设备或外部集成层通过。

前几轮失败日志均保留：ASR import 提前读取模型已延迟，GUI 提前解析 server/DB 与旧存档常量测试已修正；第一次冻结验收余下的两项失败是旧测试仍 mock `resolve_cdn_root_lax`。`063c385` 改用严格解析接口，并在有效兼容 CDN 存在时验证错误环境配置仍被拒绝，相关 41 项回归及最终 4 项入口测试通过，再取得上述完整零退出结果。没有通过恢复宽松回退来消除失败。

### 本地提交与交付边界

所有提交均在 `refactor/m0-consolidate`，从本任务起点 `c67d90f` 之后按主题拆分：

| 提交 | 主题 |
|---|---|
| `334cc81` | 恢复多行 docstring，逐文件 AST 不变 |
| `23ac313` | 归档游戏数据夹具移到忽略目录 |
| `c5e8cd6` | prepush 显式 pathlist 参数与差异证据 |
| `f55a254` | 平衡配方 active 链与 store 回退锁 |
| `6f2c810` | 外部路径统一配置、旧档案冲突与 null 兼容 |
| `0a0b335` | 区分当前万圣完整构建和历史 221 |
| `840b7f3` | ASR 模型延迟到实际转录解析 |
| `2615c0b` | 资源清单、审查表及私有迁移工具 |
| `c98e6c2` | rogue 安全门禁与 DSL 签名回收 |
| `4be4106` | 描述器、中文枚举及 GUI 语义回收 |
| `ff54e7c` | 发布根与 Windows 子目录最小权限 |
| `967db40` | 隔离副本资源迁移实证 |
| `d90cc3a` | JS/CJS 相对资源引用迁移 |
| `b0054ee` | 六个 rogue/平衡消费者的显式路径 |
| `29ae936` | 禁止覆盖内建表 codec 校验器 |
| `1ff63c5` | 记录作者全部资源可公开的裁决 |
| `ec6779d` | 末轮工具输出与服务端消费者分离；源码冻结点 |
| `16c7999` | 53 提交、75 路径与 17 项变异审计 |
| `0656044` | 冻结源码的配方影响和产物复核 |
| `063c385` | 链整理/整包测试改用严格 CDN 合同，补错误配置拒绝用例 |
| 本节及验收 JSON 所在提交 | M0.1 最终报告和全量验收证据 |

未 push，未操作 `m3-studio`；其他源码、资料和期望交付均只读。忽略的本机 profile、依赖、产物、源码副本与日志保留在当前 worktree，供复核使用；临时任务材料没有放入版本控制。没有安装到仓外、真实设备验证、服务端部署、历史改写或外部发布。最终提交后的 `git status --short` 应为空；本地忽略资料不属于待提交改动。
