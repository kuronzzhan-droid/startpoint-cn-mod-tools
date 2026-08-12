# wf-release-v1 本地发行物

`wf-release-v1` 是一个纯本地发行物格式。它把已经封印的角色
production workspace 与调用者显式提供的 Patch Overlay 外层 ZIP 绑定成不可变、可分享、
可独立校验的 Release ZIP。

当前实现覆盖角色 Producer、独立 Verifier、本机受管 TargetProbe、Installer 与显式恢复/回退 CLI。
角色 Producer 仍只生成 Content Overlay Release；Verifier/Installer 还可接收经过严格静态验证的
`content+modes` 组合 Release。它不会替代现有角色制作、Overlay 生成、服务端契约或客户端验证流程。

## 1. 输入门禁

`build` 同时要求：

1. 一个由现有角色工具封印的 production workspace；
2. 至少一个显式传入的 Patch Overlay 外层 ZIP；
3. 一个严格的 `requires.json`；
4. 一个当前不存在的显式输出文件。

角色 workspace 必须满足 production 37/37、三层声明一致、`release_ready=true`，且
`package/manifest.json` 中的 workspace digest、角色 ID、code name 与当前只读扫描结果一致。
Producer 只检查已封印输入，不会执行 `seal`、修复缺失资产或写回 workspace。

Patch Overlay 必须由既有 Overlay 生产流程提前生成。Producer：

- 不生成或改写 Overlay；
- 不扫描约 10 GB 的完整 CDN；
- 不读取运行中的服务端；
- 不读取或写入 live store、`CDN_DIR`、`assets`、SQLite、profile 或 `active.json`；
- 不调用旧发布命令，也不启动或停止服务。

每个显式 Overlay 外层 ZIP 会被原样复制到 Release 的 `content/`。Task 4 的 Overlay
结构检查会读取 ZIP 元数据和内部成员；Producer receipt 中的 `bytesRead` 与 `hashCount`
只统计之后的外层文件权威复制/SHA-256，不把结构检查读取量混入统计。

## 2. 发行物结构

```text
<任意新输出名>.zip
`-- wf-release-v1/
    |-- content/
    |   `-- <显式 Patch Overlay 外层 ZIP>
    |-- ownership.json
    |-- requires.json
    `-- release-manifest.json
```

角色 Producer 输出只有 `content` 组件：

- 不包含 `server/`；server roots 的 bytes 不进入 server payload，但其声明同时参与三层 seal
  与 `ownership.paths` 源语义投影。Archive 内没有 workspace package manifest，Verifier
  不能从发行物重新证明 workspace 来源，也不能证明 logical path 到 Overlay inner bytes 的映射；
- Producer 不自行生成 `modes/`；组合 Release 的 Mode 组件由独立来源封印，包含精确 allowlist、
  required 清单和模块私有资源，且必须要求 `mode.release-contract@1`；
- 服务端运行表仍由目标服务端已有的 Content Sync 从 Overlay 生成；
- 本机安装、恢复和平台生命周期见 `docs/wf-release-v1-local-install.md`。

外层 Release ZIP 使用确定性的 STORE：固定成员顺序、1980-01-01 时间、Unix regular
0644 权限、UTF-8 名称、无 comment/extra。相同输入写到两个不同且不存在的输出路径时，
ZIP bytes、archive SHA-256 与 `releaseId` 必须一致。

## 3. releaseId、ownership 与 replaces

`releaseId` 格式为 `sha256:<64 个小写十六进制字符>`。它是移除自身字段后的完整
`release-manifest.json` canonical bytes 的 SHA-256。名称、发行版本、producer、依赖、
期望状态、payload 路径/大小/SHA-256 或 `replaces` 任一变化都会形成新 ID。

`ownership.json` 由已封印角色 package manifest 单向投影：

- `entities` 表示角色实体，例如 `character:129999`；
- `records` 表示 manifest 声明的表与 key；
- `paths` 是四个 roots 中实际声明的精确逻辑路径，不使用通配符。

ownership 表示“源 manifest 的语义所有权”。它不证明这些逻辑路径与 Overlay 内层
`production/<hash>` 成员存在逐字节映射；Release 对实际 payload 的证明是外层 Overlay ZIP
的精确 size、SHA-256 和 ZIP/Overlay 独立校验。安装器以后必须同时处理 ownership 冲突，
不能把 ownership 当作 Overlay inner mapping。

发行物不可变。替代旧发行物时，调用方必须在 `replaces` 中精确列出旧 `releaseId`；不支持
按名称、模糊版本或“最新版”替代，也不允许新发行物替代自身。当前 Producer 的 `produce`
子命令尚未开放 `--replaces` 参数，默认生成空数组；Installer 会严格消费 Release 中已经封印的
`replaces`，但不会在安装时临时改写它。

## 4. requirements 边界

`requires.json` 必须是 UTF-8 strict JSON，并包含且只包含：

- `schemaVersion`；
- `runtimeApi`；
- `serverCapabilities`；
- `clientVersions`；
- `resourceBaselines`；
- `contentDigests`；
- `patchOverlaySchema`；
- `clientPatchProfile`。

数组必须按 UTF-8 bytes 排序、唯一并满足严格值格式。通用 JSON Schema 只做可表达的结构
预检；严格 Python parser/verifier 才是排序、NFC、跨字段闭包、Python int 与 releaseId 的
权威门禁。接收端不得只跑 JSON Schema 就接受发行物。

第一条纵切的 Producer 与 Verifier 只支持 `patchOverlaySchema=1`。更大的正整数在通用
`requires.json` 格式中仍然合法，但当前构建能力会在创建输出前以
`WFREL_REQUIRE_UNSUPPORTED` 拒绝；这不会收窄 parser 对未来 schema 值的表达能力。

## 5. CLI

以下命令均在工具仓库根目录运行。示例中的输出文件必须尚不存在。

需要图形化串联时可运行 `python -X utf8 wf_release_ui.py --open`。独立工作台的十阶段、导入编辑
边界、CDN 冲突策略与剩余 UX 缺口见 `docs/wf-release-v1-workbench.md`；它不提供 live 安装、回退
或发布入口。

### 构建

```powershell
python -X utf8 -m wf_release_v1 build `
  --workspace D:\path\to\work\character_packs\seris-dragon-king `
  --overlay D:\path\to\worldflipper-overlay-1.4.54-to-1.4.55.zip `
  --requirements D:\path\to\requires.json `
  --name seris-dragon-king `
  --version 1.0.0 `
  --output D:\path\to\out\seris-dragon-king-1.0.0.wf-release.zip
```

多段连续 Overlay 重复传入 `--overlay`。成功时 stdout 只有一行 UTF-8 JSON：

```json
{"archiveSha256":"<64hex>","bytesRead":123,"fileCount":1,"hashCount":1,"releaseId":"sha256:<64hex>"}
```

输出 JSON 不回显绝对 output 路径。构建采用 no-clobber：若输出已存在、并发已有 winner、
输出与 workspace/source 重叠、父链不安全或输入漂移，命令失败且不会覆盖现有文件。构建失败
只关闭本次私有临时句柄，不递归删除用户目录。

### 独立校验

```powershell
python -X utf8 -m wf_release_v1 verify `
  --release D:\path\to\seris-dragon-king-1.0.0.wf-release.zip `
  --json
```

Verifier 从 ZIP bytes 重新开始，不使用 Producer 内存对象或 source inspector。它依次校验
外层 ZIP、strict/canonical metadata、精确成员集合、metadata/payload 摘要、`releaseId`、
Patch Overlay 组件和可从包内判断的 ownership 边界。成功输出：

```json
{"components":["content"],"fileCount":1,"payloadBytes":123,"releaseId":"sha256:<64hex>"}
```

### 检查摘要

```powershell
python -X utf8 -m wf_release_v1 inspect `
  --release D:\path\to\seris-dragon-king-1.0.0.wf-release.zip `
  --json
```

`inspect` 不是宽松读取器；它先执行完整 Verifier，再输出同样的已验证摘要。

### 本机受管目标

`probe`、`plan-install`、`install`、`install-legacy` 与 `rollback` 的 target 格式、确认词、恢复语义和
数据降级边界见
`docs/wf-release-v1-local-install.md`。这些命令只作用于调用者显式提供的本机 `target.json`，不上传、
不远程连接，也不访问当前仓库之外未声明的 live store/CDN/assets。

### 旧分享包只读预检

```powershell
python -X utf8 -m wf_release_v1 inspect-share `
  --share D:\path\to\wfshare-example.zip `
  --json
```

`inspect-share` 面向旧 `wfshare` v2 分享 ZIP，明确支持 `wf_share_variant` 的
`variant-report` 方言和早期 `wf_dev_catalog export-pack` 的 `catalog-export` 方言。它先把输入复制到
私有不可变快照，再固定做中央目录/压缩比/CRC、原始路径与 Windows 可移植别名、单根目录、
CDN 层与连续分片、严格 `requires.json` / `report.json` 算术、归档 size/SHA-256/成员数和服务端
数据分类检查；输出是不含源文件绝对路径的迁移计划。旧 catalog 方言没有归档报告，检查器会从
实际字节计算摘要并显式给出 `catalog-export-has-no-archive-report` 警告。

包内 `.py` / `.ps1` / `.bat` / `.vbs` 或未知 `server-data` 可执行形态只被计数并标为人工复核阻断项，
绝不执行；命令也不解包到调用者目录、不写 CDN、服务端仓库或受管目标。

该命令不是宽松安装入口。旧包仍缺少 `wf-release-v1` 的 sealed character workspace、严格
requirements 与受管 server-data 迁移证明，因此当前结果固定是 `migrationStatus=blocked`，供后续
显式转换使用。`full` 且带个人增强的包会另给 `full-variant-includes-enhancements` 警告，不能在
未审查增强差异时伪装成纯角色内容。

### 旧分享包隔离导入

```powershell
python -X utf8 -m wf_release_v1 import-share `
  --share D:\path\to\wfshare-example.zip `
  --output D:\isolated\wfshare-example-import `
  --json
```

`import-share` 只接受一个尚不存在的显式绝对输出目录。它先稳定复制输入，再让同一检查器在同一
已打开快照上完成验证与提取，最后原子提交工作区。工作区保留原始 `source.wfshare.zip`、逐个内层
归档、规范 `legacy-import.json`、元数据副本、最终哈希 payload 和隔离的 `quarantine/`；包内脚本
只作为不可执行字节复制，绝不会被导入器调用。任何失败都不留下半套输出，也不会写入 live CDN、
服务端仓库或受管目标。

旧 CDN payload 只有 SHA-1 存储路径，不能据此反推出逻辑资源名。没有额外证据时它们进入
`opaque/<root>/`，结果明确为 `mappingStatus=opaque`、`clientPayloadEditable=false`。调用者可提供
严格映射文件：

```json
{"legacyPathMapVersion":1,"paths":[{"logicalPath":"character/example/ui/full_shot.png","root":"common"}]}
```

映射的存储路径由工具使用国服固定散列规则重新计算；声明不存在、重复、不可移植或跨 root 的条目
一律失败关闭。已证明的文件进入 `roots/<root>/<logicalPath>`，未证明文件继续留在 `opaque/`。
只有最终 payload 全部有明确映射时 `clientPayloadEditable=true`；这仍不解除 requirements、sealed
workspace、server-data migration 或脚本复核 blocker，也不是安装/发布证明。

### 已映射旧角色采纳

旧包只有在 `import-share` 得到 `mappingStatus=complete` 后，才允许进入角色工作区。采纳配置必须
逐项声明客户端表 codec、outer/inner keys、四张服务端角色表的隔离输入和角色身份；工具不会根据
文件名猜表、不会执行 `quarantine/` 中的脚本，也不会把服务端行混进 Content Overlay：

```powershell
python -X utf8 -m wf_release_v1 adopt-character `
  --imported D:\isolated\rolf-import `
  --config D:\isolated\rolf-import\legacy-character-adoption.json `
  --output D:\isolated\rolf-character-workspace `
  --json
```

结构预检 Schema 为 `schemas/wf-release-legacy-character-adoption-v1.schema.json`；罗尔夫的真实 20 表
声明范例为 `docs/examples/legacy-character-adoption.rolf.json`。Schema 只用于编辑器提示和结构预检，
`wf_release_v1.legacy_character` 的严格 parser、表字节回读、37/37 与 seal 才是权威门禁。

罗尔夫范例同时保留 `superFever`、特殊强化弹射三档、unique condition 180000 和四张服务端表的
迁移声明。后两者只是语义和隔离证据：生成 sealed workspace 不等于服务端仓库已合并这些行。

### 从封印角色创建编辑副本

正式 Release 和原封印工作区保持不可变。需要二次调整时，先以显式递增的包版本创建全新目录：

```powershell
python -X utf8 -m wf_release_v1 checkout-character `
  --workspace D:\isolated\rolf-character-workspace `
  --output D:\isolated\rolf-character-edit-1.1.0 `
  --package-version 1.1.0 `
  --json
```

`checkout-character` 只接受通过 37/37、三层一致和 seal 的角色工作区；它逐项验证已声明文件和表/键
所有权，再复制到尚不存在的绝对输出目录。源工作区不变，编辑副本的 `releaseReady` 由内容校验
推导为 `false`，不是用户可切换的状态位。

当前最小闭环允许修改已有声明文件，不允许静默新增、删除或改名。完成表行、图片、声音或 DSL
调整后，运行：

```powershell
python -X utf8 -m wf_release_v1 seal-character `
  --workspace D:\isolated\rolf-character-edit-1.1.0 `
  --json
```

工具会再次解析 flat/raw/nested 表键和四张服务端角色行，拒绝所有权漂移，刷新现有文件的 size 与
SHA-256，再绑定新的 workspace digest。失败会恢复原 manifest，不会写 live CDN、store、服务端
仓库或设备。需要增加/删除文件时仍回到完整角色创作/manifest 审核流程，不能借重新封印绕过声明。

本机工作台也提供“创建角色编辑副本”和“验证并重新封印”两个相同边界的准备动作。这里不引入
项目数据库、手工编辑/分享开关或最近项目同步；一个工作区文件夹就是一个项目，状态始终由校验
结果得出。

### 从封印角色生成标准 Patch Overlay

```powershell
python -X utf8 -m wf_release_v1 build-overlay `
  --workspace D:\isolated\rolf-character-workspace `
  --from-version 1.4.324 `
  --target-version 1.4.347 `
  --output D:\isolated\rolf-1.4.324-to-1.4.347.patch-overlay.zip `
  --json
```

该命令从 sealed workspace 的客户端 roots 生成确定性 classic STORE 内外层 ZIP，并使用国服固定
散列路径重建 `production/<hash>`。它不会读取当前 CDN、不会覆盖已存在输出，也不会把四张
server rows 或隔离脚本塞进 Overlay。输出仍须交给 `build` 与独立 Verifier 形成最终 Release。

### 可复用配置边界

- `legacy-character-adoption.rolf.json`：角色/表/技能声明模板，可复制后逐键替换；
- `wf-release-target.windows.json`：宿主本地受管目标模板，绝不能打进分享包；
- `capture-requirements`：从当前目标事实生成严格 requirements，不是手写“兼容所有版本”；
- `plan-install`：只读给出兼容性、冲突、no-op 与 retained previous 回退可用性。

这些模板不会复制角色资产，也不会把一个角色的 ID、技能树或服务端行自动套给另一个角色。
模板是显式声明的起点，不是绕过映射、表闭包、seal、TargetProbe 或真机验收的快捷方式。

## 6. 错误与退出码

失败时 stdout 为空，stderr 只有一行 UTF-8 JSON，包含稳定 `code` 和中文 `message`；默认不
显示绝对路径、traceback、底层英文异常或私有 token。

| 退出码 | 含义 | 常见稳定错误族 |
|---:|---|---|
| 0 | 成功 | — |
| 2 | CLI 参数错误 | `WFREL_CLI_ARGUMENTS` |
| 10 | schema、路径、ZIP 或摘要格式错误 | `WFREL_SCHEMA_*`、`WFREL_PATH_*`、`WFREL_HASH_*`、`WFREL_ARCHIVE_*` |
| 20 | 发布源、组件或依赖不兼容 | `WFREL_CHARACTER_SOURCE_*`、`WFREL_CHARACTER_EDIT_*`、`WFREL_OVERLAY_GRAPH`、`WFREL_REQUIRE_*`、`WFREL_OWNERSHIP_*`、`WFREL_COMPONENT_*` |
| 30 | 本地 I/O、输出或未分类执行失败 | `WFREL_BUILD_IO`、`WFREL_BUILD_OUTPUT_*`、`WFREL_CLI_IO` |

调用者应同时判断退出码和 `code`，不要解析中文提示文本。

## 7. 证据边界

`verify` 通过只证明：收到的发行 ZIP 结构、metadata、payload identity、内嵌 Overlay 和当前
组件接收约束一致。它不证明：

- 发行物已经安装或激活；
- receiver/Content Sync 已经接受并切换；
- 服务端已启动或 capabilities 已达到期望状态；
- 客户端完成资源下载、解包或缓存切换；
- 安卓/其他平台壳已经完成安装事务；
- 角色显示、战斗或玩法在真机上正确。

当前 Windows 验收覆盖 Windows 发布路径。Linux 的无权限 `linkat(AT_EMPTY_PATH)` →
`/proc/self/fd` fallback 已有真实 Linux-only procfd 子进程 gate，但本次 Windows 设备不会执行该 gate，
因此不能把 Windows skip 当作 Linux 运行证明。

## 8. 性能基线

CI 单测只锁定读取次数、SHA 次数、外层字节不变、稀疏哨兵不读取及重复 verify 的状态独立性，
不使用易抖动的绝对秒数阈值：

```powershell
python -X utf8 -m unittest tests.test_release_v1_performance -v
```

同一机器做人工基线时运行 5 次：

```powershell
python -X utf8 -m tests.test_release_v1_performance --benchmark --runs 5 > wf-release-v1-benchmark.json
```

输出是单个机器可读 JSON object，保留每次运行及 `median`，分别记录 cold build、相同输入的
第二次 build、一个 manifest 已声明 workspace 文件变化并更新 claim、重新封印后的 build、
verify 的 `wallTimeSeconds`、
`peakTracemallocBytes`、`bytesRead` 和 `hashCount`。其中 build 的读/hash 仅指 Producer 外层
Overlay 权威复制，verify 的读/hash 仅指 Release payload 权威 SHA；metadata 与 Overlay
结构读取在 `metricScope` 中明确排除，不能把这些数字冒充总物理 I/O。

顶层 `environment` 固定记录 Python implementation/version、OS/architecture，以及临时目录的
存储身份：Windows 为 volume kind、drive 和 device ID，POSIX 为 filesystem kind 和 device ID；
不调用外部命令，也不输出临时目录绝对路径。只有 `environment` 中所有字段和值完全一致时，
两份结果才允许直接做性能回退比较；任一字段不同都必须建立新基线，不能套用旧基线的比例。

后续变更必须在同一机器、同一 Python/文件系统条件下与该分支基线比较。5 次中位数出现超过
20% 的非预期回退时停止合并并调查；这是人工比较规则，不把随机 wall time 写成 CI 断言，
也不得通过跳过完整 SHA-256 来换取更好数字。

Installer 使用独立的临时目标基线：

```powershell
python -X utf8 -m unittest tests.test_release_v1_install_performance -v
cmd /d /c "python -X utf8 -m tests.test_release_v1_install_performance --benchmark --runs 5 > %TEMP%\wf-release-v1-install-benchmark.json"
```

该基线记录成功安装和验收前恢复两条链，并用未声明稀疏 sentinel 证明 component root 不被全量扫描；
阶段耗时互相嵌套，不能相加冒充总耗时。
