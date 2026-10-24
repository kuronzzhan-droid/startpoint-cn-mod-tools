# M0 原 A 通用 API 兼容保留

A 是本 worktree 的原始基线 `fd433b0`。本文说明 C 为底导入后，如何保留 A 既有通用入口；不从 B 新增缺少生产导入图依据的功能。B 的新增仍为 `wf_battle_atlas_repack.py` 一项，即 **1/170**。逐模块来源、原始 SHA256、目标哈希、公开函数及明确归档符号见 [compatibility.json](compatibility.json)。

## 保留的实现

恢复 **17 个顶层兼容入口**，通过 `sys.modules` alias 指向 `wf/compat/` 的实际模块。公开与私有 API、调用者 monkeypatch 的模块状态使用同一对象；不通过 `star import` 复制名字，不从 `archive/legacy/` 导入实现。原 A 源码从本仓 `git show fd433b0:<path>` 读取并与合并前 SHA256 快照校验。

| 原入口 | 包内实现 | 保留范围 |
|---|---|---|
| `wf_apk_paths` | `wf/compat/apk_paths.py` | 显式 APK 输入解析 |
| `wf_database_paths` | `wf/compat/database_paths.py` | 数据库路径解析 |
| `wf_device_paths` | `wf/compat/device_paths.py` | 可选设备工具路径发现；本任务不执行工具 |
| `wf_flatomo_compile` | `wf/compat/flatomo_compile.py` | 显式效果参数的 `compile_flipbook_effect` |
| `wf_preview_2d` | `wf/compat/preview_2d.py` | 预览 API 与 CLI |
| `wf_preview_2d_core` | `wf/compat/preview_2d_core.py` | 本地素材与预览描述读取 |
| `wf_release_paths` | `wf/compat/release_paths.py` | 显式 profile 和模块根解析 |
| `wf_release_ui` | `wf/compat/release_ui.py` | 发行准备 UI API 与 CLI |
| `wf_release_ui_actions` | `wf/compat/release_ui_actions.py` | 显式准备动作分派 |
| `wf_tool_distribution` | `wf/compat/tool_distribution.py` | 确定性工具源码分发包 |
| `wf_pixelart_compile` | `wf/compat/pixelart_compile.py` | 显式源、目标与 hash 约束的 sprite 编译器 |
| `wf_pixelart_normal_compile` | `wf/compat/pixelart_normal_compile.py` | 完整 normal 动画编译器 |
| `wf_pixelart_special_compile` | `wf/compat/pixelart_special_compile.py` | special 动画编译器 |
| `wf_pixelart_special_compat_compile` | `wf/compat/pixelart_special_compat_compile.py` | normal 像素复用与 special 元数据编译 |
| `wf_character_ui_compile` | `wf/compat/character_ui_compile.py` | 显式裁剪、PNG、atlas 与 ATF 编译 |
| `wf_abyss_gacha_banner_compile` | `wf/compat/abyss_gacha_banner_compile.py` | 显式 banner spec 编译；固定产品锁定包装留归档 |
| `wf_abyss_ticket_compile` | `wf/compat/abyss_ticket_compile.py` | 显式 ticket spec、item 图集与表编译；固定票据产品留归档 |

`wf_release_v1/` 的 **63 个文件**恢复到原顶层包名。这是通用发行协议，`v1` 表示协议版本；没有把它当作一次性版本交付脚本。原 A 包及适配后的文件分别保存源/目标哈希。UI 两个 HTML 和 distribution 默认源码根使用 `wf.paths.REPOSITORY`；release 路径助手也识别 `wf/compat/` 中的实现文件。恢复 API 不代表执行发行、服务或设备操作。

## A 与 C 的接口边界

C 的 `wf_character_pack` 缺少 A 发行协议所依赖的 `logical_path_problem` 与 `windows_logical_path_key`。从原 A AST 提炼这两个通用函数及所需常量到 `wf/deliver/logical_paths.py`，在 C 模块补充 re-export；保持 C 已有实现。此项属于 A 既有 API 的兼容适配，不是选择 B 的完整 `wf_character_pack` 分叉。

恢复测试还揭示 Windows 长路径兼容差异：从 A 恢复 `wf_character_workspace._absolute` 的扩展长度路径处理，并在 `wf_release_v1/materialize.py` 的临时目录清理使用已有 `native_path`；两个长路径 fixture 同步使用扩展路径。没有修改交付 goldens，也没有替换 C 模块的其它行为。逐项来源与修改后哈希在 JSON 的 `api_adaptations` 中。

## 通用与角色边界

- `wf_action_skill_compile.py` 的三个公开函数均是夏龙专用；没有独立通用公开 API，保留原归档。
- pixelart 四模块和 character UI 模块仅提炼显式输入的通用编译器；`SUMMER_THUNDER_*` 与 `compile_summer_thunder_*` 留归档。Flatomo 的固定夏龙 travelling-wave 包装也留归档。
- `compile_special_compatibility` 保留原参数、产物算法和报告键；通用入口不使用固定夏龙哈希授予生产 manifest 资格，`package_manifest_eligible` 与 `locked_summer_thunder_normal_v3` 恒为 false。原角色审批和锁定包装留归档，通用编译成功不构成角色生产验收。
- `wf_canary_skin` 角色入口不恢复；所需通用图片缩放已由 `wf/art/image_fit.py` 承接。固定 gacha 池、票据产品常量、夏龙与 thunder hotfix 工作流保留归档。
- 被提炼模块的完整原文件仍保留在归档，JSON 逐项列出未恢复的角色符号。角色 API 的移除是任务要求的归档边界；不宣称这些角色入口仍兼容。

## 验证范围与证据

恢复六个编译器测试文件，保留合成输入的像素、AMF、hash 锁定和错误输入断言；移除原角色包装专用 case。原完整测试仍在归档，不纳入 pytest。没有修改通用算法期望 hash 来让测试通过。六文件首轮为 **17 passed, 3 subtests passed**，见 `work/m0/compat-compiler-initial.log` 与同名 XML。

新增 `tests/test_m0_compatibility.py` 逐模块验证 alias 与私有状态、显式路径拒绝非法覆盖、UI 资源路径、mock 根解析，以及活跃模块来源不落入 archive。上述七文件最终为 **39 passed, 3 subtests passed**，见 `work/m0/compatibility-final.log/xml`，包含全部 17 个 alias。另有 `tests/test_m0_compatibility_abyss.py` 的显式 banner/ticket spec 回归。

发行协议恢复 **56 个 test/support 文件**，包括 3 个共享 fixture/support 文件，使用合成目录进行协议回归。首轮为 **434 passed、3 skipped、7 failed、1 error、668 subtests passed**；失败共因是 Windows 长路径，见 `work/m0/pytest-release-v1-pass2.log`。修复后相关回归为 **50 passed、9 subtests passed**，见 `work/m0/pytest-release-v1-long-path.log`。这两个结果不是同一次完整运行，不相加或改写为已全量通过；最终完整回归以 `M0-REPORT.md` 的新运行结果为准。

所有临时目录由全局 `tests/conftest.py` 限制到本 worktree 的 `work/t`，保持写审计。兼容七文件组不创建监听；发行协议原测试中的 health、probe、target protocol 和 vertical 测试会创建短时的本机回环随机端口 HTTP fixture，并在测试结束清理。它们使用合成数据，不访问实际测试服、正式服或设备。

路径扫描命令 `python -B scripts/check_no_hardcoded_paths.py` 在本次兼容恢复后返回 **1,873 个文本文件、0 findings**。此数字是扫描时点的文件数，最终全量扫描由总报告记录。
