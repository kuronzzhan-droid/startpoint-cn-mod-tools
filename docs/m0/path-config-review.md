# M0.1 路径与配置修复证据

本页覆盖 M1、M2、M4。所有修改和测试写入均位于当前 worktree；外部输入目录只读。

- `project_root()` 现在直接引用 `wf.paths.REPOSITORY`。`wf_publish_guard.ROOT/PACKS`、角色支持层默认 `ROOT`、GUI `ROOT/CDNDATA` 和 catalog `ROOT` 均回到工具仓。
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
