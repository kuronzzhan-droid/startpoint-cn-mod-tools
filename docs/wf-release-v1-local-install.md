# wf-release-v1 本地受管安装与恢复

本文描述 `wf-release-v1` 的本机受管现代目标与旧服渐进兼容。它不是在线发布器，不会上传 CDN、连接远程主机、
修改源码仓库或清理旧发行物。

## 1. 安全模型

- 所有操作都由宿主本地 `target.json` 指向；Release ZIP 和 receipt 不携带宿主绝对路径。
- `serverUrl` 必须是本地回环 base origin；探针固定访问 `/healthz` 与
  `/api/server/capabilities`，不接受重定向、代理、用户信息或远程地址。
- `network.publicHost` 必须是本机网卡实际持有的规范 IPv4 回环/RFC1918 地址。受管服务固定把 HTTP
  绑定到 `0.0.0.0:<serverUrl端口>`、TCP 绑定到 `0.0.0.0:8003`，并把该公开地址分别注入
  `CN_PUBLIC_HOST`、`SESSION_PUBLIC_HOST` 和 `CDN_BASE_URL`；控制探针仍只走回环地址。
- 受管服务进程用 PID、创建时间、可执行文件路径和 SHA-256 四项共同识别；陌生进程不会按端口或
  进程名终止。
- `bootstrap`、modern/legacy 安装、modern 恢复/回退与 legacy 回退共享同一个 nofollow 原子 operation
  reservation；任一变更事务存续期间，第二个变更入口必须在读取可变目标状态或停服前失败关闭。
- v1 只安装已经独立验证的 Content Overlay，以及可选的静态 Mode 组件；不执行 Release 中的
  脚本来决定安装路径。
- 安装没有 purge、远程 shell、在线下载或隐式“最新版”选择。

`target.json` 是宿主私有配置，不得打进 Release 或分享包。它包含本机目录布局，可能间接暴露用户
名或磁盘结构。operation receipt、`active.json`、`previous.json` 和 baseline facts 使用无路径的严格
wire shape，可以用于本机审计，但仍应按运维状态文件保护。

## 2. target.json

所有路径必须是规范绝对路径、不能是用户目录根、工具仓根、驱动器根、UNC、符号链接或 reparse
穿越；data、state、活动 CDN、活动 Mode 和三个 candidate root 必须两两不重叠。

```json
{
  "schemaVersion": 1,
  "managedBy": "wf-release-v1",
  "serverBundle": "D:\\wf-target\\server-bundle",
  "runtimePack": "D:\\wf-target\\runtime-pack",
  "dataRoot": "D:\\wf-target\\data",
  "stateRoot": "D:\\wf-target\\state",
  "cdnRoot": "D:\\wf-target\\cdn",
  "modesRoot": "D:\\wf-target\\modes-active",
  "componentRoots": {
    "content": "D:\\wf-target\\candidates-content",
    "server": "D:\\wf-target\\candidates-server",
    "modes": "D:\\wf-target\\candidates-modes"
  },
  "compatibility": {
    "clientVersion": "1.4.54",
    "resourceBaseline": "1.4.53",
    "clientPatchProfile": true
  },
  "network": {
    "publicHost": "10.0.0.130"
  },
  "serverUrl": "http://127.0.0.1:8001"
}
```

可复制的 Windows 起始模板在 `docs/examples/wf-release-target.windows.json`，结构预检 Schema 在
`schemas/wf-release-target-v1.schema.json`。复制后必须把每个路径改成目标机自己的新隔离目录；
Schema 不验证路径互斥、protected root、reparse、ADS 或回环地址的全部语义，`ManagedTarget.load`
仍是唯一权威 parser。模板和生成后的 `target.json` 都不得进入 Release、receipt 或分享包。

Server Bundle 与 Runtime Pack 必须先按各自 manifest 封装并通过 TargetProbe。初次安装前目标服务必须
停止；本地没有 `active.json` 时必须先执行下方显式 bootstrap。工具不会接管已经在运行却没有受管
状态的进程。bootstrap 在任何 Content prepare 前，先持有 operation reservation、证明 publicHost
属于本机接口，并证明 HTTP wildcard 端口与 TCP 8003 都没有监听者。

### 首次受管 baseline bootstrap

```powershell
python -X utf8 -m wf_release_v1 bootstrap `
  --target D:\wf-target\target.json `
  --confirm BOOTSTRAP_WF_TARGET
```

该命令只接受没有 `active.json`、没有 `previous.json`、也没有受管进程记录的停止目标。固定顺序是
`Content Sync prepare -> 启动 Server Bundle -> /healthz ready -> capabilities 与本地 Bundle/Runtime
一致 -> live cdnTargetVersion 与 target.resourceBaseline 一致 -> 提交空 active/previous`。健康响应
必须精确回显本操作 ID、PID、HTTP/TCP 监听和公开地址、CDN URL，并报告 HTTP/TCP 都 ready；工具不会
按端口或进程名接管陌生进程。

bootstrap 会写 Data Volume 的 Content 状态，服务启动还可能迁移数据库 schema；因此执行前必须完成
项目专用的停服一致性备份。health、capabilities、版本校验或 state commit 失败时，只停止本事务启动且
身份仍匹配的进程，不回滚数据库或 Data Volume。若停止失败则返回 `WFREL_RECOVERY_FAILED` 并保留现场；
不得删除半状态后盲目重试。

### 恢复已受管但停止的服务

已存在合法 `active.json` 与 `previous.json`、但受管服务停止时，先显式恢复服务，再执行
`capture-requirements` 或 `plan-install`：

```powershell
python -X utf8 -m wf_release_v1 resume `
  --target D:\wf-target\target.json `
  --confirm RESUME_WF_TARGET
```

`resume` 从读取 active/previous、进程或网络开始全程持有 operation reservation。若受管进程已经运行，
命令只按 process state 精确验证 `/healthz` 的操作 ID、PID、HTTP/TCP bindings 和 modern capabilities，
随后返回 `outcome=noop`，不会重启。若服务停止，则先证明 publicHost 属于本机且 `target.serverUrl`
对应的 HTTP 端口与 target session 端口均未被占用，再按 target 的 launch/environment 启动；它不会运行
Content prepare，也不会改写 active、previous 或 Content。`CN_ADMIN_TOKEN` 只继承到子进程环境，不进入
state 或输出。

成功输出为不含路径的单行 JSON，包括 `outcome`、本次 `operationId`、`targetProtocol=capabilities-v1`
与完整 `TargetFacts` 顶层字段。启动后验证失败只会停止本次启动且身份仍精确匹配的进程；进程已退出视为
已停止，process state 缺失或身份漂移则返回 `WFREL_RECOVERY_FAILED` 且不终止无法证明归属的进程。
若 running-noop 验证完成后 reservation 释放失败，命令保留原 state/lock 错误且不停止既有进程；若本次
启动已验收后才发生该失败，则返回 `WFREL_RECOVERY_FAILED` 并保留进程与现场，不在失去 reservation
所有权后盲目停服。

## 3. 只读探针

```powershell
python -X utf8 -m wf_release_v1 probe `
  --target D:\wf-target\target.json `
  --json
```

成功输出唯一一行 `probeVersion=2` 的严格 JSON，并给出：

- `modern`：`targetProtocol=capabilities-v1`，保留原有 14 个 `TargetFacts` 顶层字段；
- `transition`：capabilities 精确 404、三层旧 CDN 闭包有效且工具持有运行进程，可自动安装 content-only；
- `legacy`：旧服本地事实或进程所有权不足，只能 preparation-only。

输出不含绝对路径、环境变量或进程命令行。401/403/5xx、重定向、超时、坏 JSON、错误 MIME 或不受支持的
现代 contract 都不会被当成旧服；只有 capabilities 精确 404 才进入旧服本地事实检查。

### 只读捕获 requirements

服务端、Runtime Pack 和角色 workspace 都已准备好后，用当前目标事实生成单目标 requirements：

```powershell
python -X utf8 -m wf_release_v1 capture-requirements `
  --target D:\wf-target\target.json `
  --workspace D:\isolated\rolf-character-workspace `
  --output D:\isolated\rolf-requires.json `
  --json
```

输出采用 no-clobber，只写调用者给出的新文件；不写目标目录。它把 workspace 的 required
capabilities 与 TargetProbe 的 runtimeApi、服务端 capabilities、contentDigest、Overlay schema
以及 `target.json` 的客户端版本/资源基线绑定。服务端缺少角色所需 capability 时失败关闭。

### 安装前只读预览

```powershell
python -X utf8 -m wf_release_v1 plan-install `
  --target D:\wf-target\target.json `
  --release D:\releases\rolf-1.0.0.wf-release.zip `
  --json
```

该命令完整验证 Release，再按探测到的目标能力读取 modern TargetProbe 或 legacy 三层 CDN、本机
active/previous 状态，输出兼容性错误码、版本、no-op、ownership 冲突和恢复边界。成功或不兼容都不创建
operation receipt、不物化 candidate、不停服、不切换指针；响应固定包含 `"writesLive":false`。
modern 只有 `compatible=true` 才允许进入下一节；transition 只有 `installable=true` 才允许进入旧服安装。
纯 legacy 会保留 `previewOnly=true` 与阻断码，不能自动写入。

## 4. 安装

```powershell
python -X utf8 -m wf_release_v1 install `
  --target D:\wf-target\target.json `
  --release D:\releases\seris-1.0.0.wf-release.zip `
  --confirm INSTALL_WF_RELEASE
```

一次安装按固定顺序执行：独立验证、不可变 object import、baseline probe、requirements/ownership
门禁、停止受管进程、候选物化与复验、保存 Content pointer 和 baseline facts、切换 Overlay/Mode、
prepare、启动、`/healthz` ready、capabilities expected state、最后提交 active/previous。

- 同一 `releaseId` 已 active 时是显式 no-op，不重启、不创建 operation receipt。
- entity/record 冲突必须由精确 `replaces` 解决；共享表的 source path 不是独占键。
- Content 只切换 `cdnRoot/patches/<targetVersion>`，永不覆盖官方 `cdnRoot/cn`。
- Content candidate 会把已独立验证的单边 Overlay 外层 ZIP 解包成 Content Sync 实际接收的
  `patch-manifest.json`、`README.md`、`requires.json` 与 `archive-*-diff/*.zip`，同时保留外层 ZIP
  作为逐字节审计锚；candidate 复验覆盖全部文件并证明解包成员与该外层 ZIP 完全一致。当前事务只能
  原子切换一个版本目录，因此多边 Overlay Release 在任何 candidate 写入前失败关闭。
- Mode 只切换完整 active Mode 根；required/allowlist/private resource 由 Release 静态结构和服务端
  Mode loader 双重验收。Mode 变化只有在重启后 capabilities 的 loaded identity 与 `modeDigest`
  达到期望才会提交。
- 验收前任何失败都会尽力恢复原 Content pointer、Overlay 版本目录、Mode 根和 baseline 服务。

命令成功只说明临时受管目标达到了服务端 expected state，不证明客户端已经下载资源、显示角色、
进入战斗或执行玩法。

### transition 旧服的 content-only 安装

```powershell
python -X utf8 -m wf_release_v1 install-legacy `
  --target D:\wf-target\target.json `
  --release D:\releases\rolf-1.0.0.wf-release.zip `
  --confirm INSTALL_LEGACY_RELEASE
```

该入口只接受 `transition`，且 Release 必须只有 Content/Patch Overlay、唯一要求 `content.sync@1`、没有
Mode、server-data 或数据库迁移。工具先证明旧服进程所有权，再停服，把三层归档写入同卷私有 staging，
逐项 no-clobber 提交和 readback，重启同一 LaunchSpec，并验证旧只读健康 JSON、capabilities 仍精确 404、
进程身份和链尾。任一步失败都恢复本次新增文件和原运行状态；恢复失败则保持停止并保留证据。

已成功提交至少两条 Release 后，可以把 transition 目标精确回到 `previous.json` 记录的前一条链尾：

```powershell
python -X utf8 -m wf_release_v1 rollback-legacy `
  --target D:\wf-target\target.json `
  --to-release sha256:<previous-release-id> `
  --confirm ROLLBACK_LEGACY_RELEASE
```

该命令只接受与上一笔已提交 legacy install receipt 对应的 retained Release。它在停服后逐项证明当前三层
归档仍与该 Release 完全一致，只删除这笔安装拥有的归档；更早的链边和无关文件不会被枚举删除。重启后链尾
必须精确回到 Overlay 的 `fromVersion`，才会提交 previous active state 和 schema-v2 legacy receipt。删除、启动、
readiness 或 readback 任一失败都会恢复已删除的精确字节和原运行状态；恢复本身失败则保持服务停止并保留
staging/receipt 证据。`rollback-legacy` 不回滚数据库、server-data、存档或客户端状态，
`dataCompatibilityGuaranteed` 固定为 `false`。

纯 `legacy` 没有自动安装入口：分享包检查、隔离导入、角色采纳、编辑、重新封印、2D 预览和 Overlay/部署包
导出仍可闭环，部署到旧服务端必须人工执行其既有流程。工具不会执行包内脚本或替用户合并 server-data。

## 5. recovery_failed

如果自动恢复本身失败，安装结果是 `recovery_failed`，服务保持停止，operation staging、candidate、
receipt 与原 object 都保留。不要删除这些证据，也不要手工拼接 active state。

排除磁盘/权限/运行时故障并确认目标停止后，按原 operation 精确重试：

```powershell
python -X utf8 -m wf_release_v1 rollback `
  --target D:\wf-target\target.json `
  --operation 20260812T010203.000000Z-0123456789abcdef0123456789abcdef `
  --confirm RECOVER_FAILED_INSTALL
```

该操作只恢复原 operation 留存的 baseline，不更改 active commit point；marker、Release 对象与组件
类型不一致时失败关闭。当前 `rollback` 是 modern Content/Mode 恢复器；传入 legacy operation receipt 会以
`WFREL_TARGET_PROTOCOL` 拒绝，不会把旧 CDN 文件误交给 modern 指针恢复逻辑。

## 6. 成功安装后的显式回退

只有精确保留的 `previous.json` 允许成为回退目标：

```powershell
python -X utf8 -m wf_release_v1 rollback `
  --target D:\wf-target\target.json `
  --to-release sha256:<64-hex> `
  --confirm I_UNDERSTAND_DATA_DOWNGRADE_RISK
```

这会在目标停止时恢复对应 install receipt 留存的 Content/Mode 根，启动并重新验收，然后提交新的
active/previous。`dataCompatibilityGuaranteed` 固定为 `false`：服务端或 Mode 可能已经写入新存档
字段，工具无法证明玩家数据可以安全降级。需要数据库迁移或真实存档回退时必须使用项目专用流程，
不能把此命令当作数据回滚。

## 7. 运维边界

- 不删除 `stateRoot/objects`、`staging`、`receipts` 或 candidate root；v1 没有 purge。
- 不把 `target.json`、Server Bundle、Runtime Pack 或 active roots 放入分享 ZIP。
- 不在真实服运行时直接替换 active CDN/Mode；所有变更先停服并由 phase receipt 记录。
- `probe` 通过不等于 `install` 通过；`install` 通过不等于客户端/设备/玩法验收通过。
- 任何 `WFREL_RECOVERY_FAILED` 先保持停止并保存证据，不要反复盲重试。
- 新 operation receipt 使用 schema v2 并写明 `targetProtocol=capabilities-v1|legacy`；历史 v1 receipt 只按
  隐式 `capabilities-v1` 读取，更新或恢复时协议不可切换。

## 8. 验证与性能证据

```powershell
python -X utf8 -m unittest tests.test_release_v1_vertical -v
python -X utf8 -m unittest tests.test_release_v1_mode_switch -v
python -X utf8 -m unittest tests.test_release_v1_legacy_transaction tests.test_release_v1_legacy_rollback -v
python -X utf8 -m unittest tests.test_release_v1_install_performance -v
cmd /d /c "python -X utf8 -m tests.test_release_v1_install_performance --benchmark --runs 5 > %TEMP%\wf-release-v1-install-benchmark.json"
```

CI 用 1 GiB 稀疏、未声明 sibling 证明 candidate 物化不会扫描无关组件；人工五次基线使用 10 GiB
稀疏 sentinel，并分别记录 verify、object import、materialize、candidate verify、stop/start、health、
capabilities 和 rollback 的嵌套耗时。相同 environment identity 下，中位数非预期回退超过 20% 时
停止合并并调查；wall time 不写成跨机器的固定 CI 阈值。
