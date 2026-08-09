# wf-release-v1 本地发行物

`wf-release-v1` 是一个纯本地、content-only 的发行物格式。它把已经封印的角色
production workspace 与调用者显式提供的 Patch Overlay 外层 ZIP 绑定成不可变、可分享、
可独立校验的 Release ZIP。

当前实现只覆盖 Producer、Verifier 与只读 CLI。它不会安装发行物，也不会替代现有角色制作、
Overlay 生成或客户端验证流程。

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

第一条纵切只有 `content` 组件：

- 不包含 `server/`；角色 workspace 的 server roots 只参与三层 seal 复核；
- 不包含 `modes/`，也不要求 Mode；
- 服务端运行表仍由目标服务端已有的 Content Sync 从 Overlay 生成；
- 尚不存在 `install`、`rollback`、`probe` 或平台套壳安装命令。

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
按名称、模糊版本或“最新版”替代，也不允许新发行物替代自身。当前 CLI 尚未开放
`--replaces` 参数；默认生成空数组，替代工作流留给后续 installer 计划。

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

## 5. CLI

以下命令均在工具仓库根目录运行。示例中的输出文件必须尚不存在。

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

## 6. 错误与退出码

失败时 stdout 为空，stderr 只有一行 UTF-8 JSON，包含稳定 `code` 和中文 `message`；默认不
显示绝对路径、traceback、底层英文异常或私有 token。

| 退出码 | 含义 | 常见稳定错误族 |
|---:|---|---|
| 0 | 成功 | — |
| 2 | CLI 参数错误 | `WFREL_CLI_ARGUMENTS` |
| 10 | schema、路径、ZIP 或摘要格式错误 | `WFREL_SCHEMA_*`、`WFREL_PATH_*`、`WFREL_HASH_*`、`WFREL_ARCHIVE_*` |
| 20 | 发布源、组件或依赖不兼容 | `WFREL_CHARACTER_SOURCE_*`、`WFREL_OVERLAY_GRAPH`、`WFREL_REQUIRE_*`、`WFREL_OWNERSHIP_*`、`WFREL_COMPONENT_*` |
| 30 | 本地 I/O、输出或未分类执行失败 | `WFREL_BUILD_IO`、`WFREL_BUILD_OUTPUT_*`、`WFREL_CLI_IO` |

调用者应同时判断退出码和 `code`，不要解析中文提示文本。

## 7. 证据边界

`verify` 通过只证明：收到的发行 ZIP 结构、metadata、payload identity、内嵌 Overlay 和当前
content-only 约束一致。它不证明：

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
第二次 build、一个 Overlay 文件变化后的 build、verify 的 `wallTimeSeconds`、
`peakTracemallocBytes`、`bytesRead` 和 `hashCount`。其中 build 的读/hash 仅指 Producer 外层
Overlay 权威复制，verify 的读/hash 仅指 Release payload 权威 SHA；metadata 与 Overlay
结构读取在 `metricScope` 中明确排除，不能把这些数字冒充总物理 I/O。

后续变更必须在同一机器、同一 Python/文件系统条件下与该分支基线比较。5 次中位数出现超过
20% 的非预期回退时停止合并并调查；这是人工比较规则，不把随机 wall time 写成 CI 断言，
也不得通过跳过完整 SHA-256 来换取更好数字。
