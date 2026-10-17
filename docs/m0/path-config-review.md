# M0.1 路径与配置修复证据

本页覆盖 M1、M2、M4。所有修改和测试写入均位于当前 worktree；外部输入目录只读。

- `project_root()` 现在直接引用 `wf.paths.REPOSITORY`。`wf_publish_guard.ROOT/PACKS`、角色支持层默认 `ROOT`、GUI `ROOT` 和 catalog `ROOT` 均回到工具仓；GUI `CDNDATA` 由显式配置或服务端派生。
- `find_world_upload()` 拒绝仓外根，且跳过解析到仓外的目录链接。正常 store 解析不再调用它，也不扫描 cwd。`wf_quest_lib` 自己的历史目录兜底一并去掉。
- 路径统一由环境变量、`profiles/local.json` 解析。外部命名输入没有推测默认值；仅保留仓内 `output/pathlist` 默认值及 `root_path` 的仓内离线占位根。
- `WF_STORE`、`WF_SERVER` 是规范名称；旧别名使用时警告，同值兼容、不同值报冲突。`WF_PROFILE` 只选版本 ID，`WF_PATHS_PROFILE` 只选 JSON 文件。
- 旧 `profiles.json` 读取时警告；相对路径以本仓为基准；与现代路径、版本元数据冲突时失败。兼容合并独立在 `wf/config/profile_merge.py`，避免继续增加 core 文件体积。
- `null` 视为未配置。空字符串、错误类型、缺失的显式路径档案、无效 store/server/CDN 继续报错。旧示例的可选 `null` 可直接读取，现代示例和迁移规则见 `profiles/README.md`。
- `resolve_server_dir()` 未配置时抛出专用 `ServerDirNotConfiguredError`。离线 catalog 仅捕获这个异常，令可选外根为 `None`；坏配置仍失败，外根迁移命令要求显式 server。未配置 CDN 的 lax 导入占位仍限定在本仓。

验证：

1. 路径、store、CDN、GUI、发布 CDN 与工作目录相关套件：**69 passed、5 subtests passed**（exit 0）。其中旧的自动扫描成功测试已改为拒绝扫描的契约测试。
2. 增补版本冲突测试和 catalog 兼容后，配置、发布、自检及完整 catalog 相关套件：**109 passed、17 subtests passed**（exit 0）。记录在 ignored `work/m0/pytest-path-config.log` / `.xml`。
3. 新增隔离用例覆盖兄弟 WorldFlipper 包（明确报错、不能选中）、缺配服务器、环境优先级、旧别名冲突、新旧档案冲突、版本 ID 与路径文件拆分、可选 null、错误配置和仓内默认路径。所有临时目录位于 `work/t`，设置 `PYTHONDONTWRITEBYTECODE=1`。

首次兼容检查发现旧测试依赖自动探测；扩展发布检查发现 catalog 在 import 阶段强制要求 server。两项均按新契约修正后复验通过，不以失败记录宣称完成。

当前 ignored `profiles/local.json` 仅补入已经只读核实的 kulo、store131、runtimes 显式路径，供配方复验使用；私人配置不会纳入提交。全量 pytest 和配方字节复验由总任务统一记录。


## 末轮实际消费者复核

H1 扫描后逐项复核实际用途，并修复仍在使用父目录的入口：

- analysis 三模块、balance 两模块的日志/marker、reroll 的 builder 路径与子进程工作目录、offline_store 相对归档输入、offline_toolchain 工具扫描/签名配置根均使用当前工具仓。
- character_flow 玛纳板回灌、GUI 的角色/商店/装备/副本/rogue 服务端资产、reroll 的部署表和管理令牌使用 `resolve_server_dir()`。chain_squash、pack_consolidate、enhancement_policy、share_variant 的 `repo_root` 实际表示 active-patch 来源，默认取显式服务端；显式传入的根仍保留离线 API 合同。
- CDN 运行入口统一严格解析，删除宽泛异常吞噬和父目录兜底。新增 `resolve_cdndata_dir()`：显式 cdndata 优先，否则由已配置 server 派生并检查目录；分析与 GUI 共用此解析。
- GUI 只配置 store 时可离线导入，未配 server 的数据库/服务端路径延迟到使用时解析；混合写入在首次写前解析所需根。原有 GUI 启动时要求 store 的契约保留。其余本轮所列模块无 store/server 配置可纯导入。
- story_export 默认 store 与 offline_store 默认三根来源改用统一 store 解析；后者仅在调用方显式提供旧 `profiles_path` 时保留原格式与相对路径合同。enhancement_switch 也复用统一 store，事务目录留在工具仓。
- `WF_FFMPEG` 明确配置为空、相对、缺失或目录时均报错，不再退到 PATH；未配置时仅查询 PATH，不扫描私人 voice-tools。

本轮写入仍仅限当前 worktree，未运行真实服务端、设备或发布动作。针对相关 16 个套件取得 **374 passed、4 skipped、52 subtests passed**，日志 `work/m01/remaining-consumers.log` / `.xml`。独立审阅指出 offline_store 默认旧档案旁路后补齐，并复验受影响的配置消费者、offline_store、voice：**66 passed、1 skipped、15 subtests passed**，日志 `work/m01/remaining-consumers-final.log` / `.xml`。新增合成用例验证缺配在副作用前失败、工具输出根不越界、显式离线根兼容、store-only GUI 导入及配置优先级。全量结果由总报告统一记录。
