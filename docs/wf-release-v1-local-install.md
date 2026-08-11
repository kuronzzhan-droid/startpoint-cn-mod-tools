# wf-release-v1 本地受管安装与恢复

本文只描述 `wf-release-v1` v1 的本机受管目标。它不是在线发布器，不会上传 CDN、连接远程主机、
修改源码仓库或清理旧发行物。

## 1. 安全模型

- 所有操作都由宿主本地 `target.json` 指向；Release ZIP 和 receipt 不携带宿主绝对路径。
- `serverUrl` 必须是本地回环 base origin；探针固定访问 `/healthz` 与
  `/api/server/capabilities`，不接受重定向、代理、用户信息或远程地址。
- 受管服务进程用 PID、创建时间、可执行文件路径和 SHA-256 四项共同识别；陌生进程不会按端口或
  进程名终止。
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
  "serverUrl": "http://127.0.0.1:8001"
}
```

Server Bundle 与 Runtime Pack 必须先按各自 manifest 封装并通过 TargetProbe。初次安装前目标服务必须
停止；如果本地没有 `active.json`，安装器可以启动声明的 baseline 做第一次探测，但不会接管已经在
运行却没有受管状态的进程。

## 3. 只读探针

```powershell
python -X utf8 -m wf_release_v1 probe `
  --target D:\wf-target\target.json `
  --json
```

成功输出唯一一行严格 JSON `TargetFacts`。它由 Server Bundle manifest、Runtime Pack manifest 与
运行中 capabilities 三方交叉验证得到。输出不含绝对路径、环境变量或进程命令行。

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
- Mode 只切换完整 active Mode 根；required/allowlist/private resource 由 Release 静态结构和服务端
  Mode loader 双重验收。Mode 变化只有在重启后 capabilities 的 loaded identity 与 `modeDigest`
  达到期望才会提交。
- 验收前任何失败都会尽力恢复原 Content pointer、Overlay 版本目录、Mode 根和 baseline 服务。

命令成功只说明临时受管目标达到了服务端 expected state，不证明客户端已经下载资源、显示角色、
进入战斗或执行玩法。

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
类型不一致时失败关闭。

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

## 8. 验证与性能证据

```powershell
python -X utf8 -m unittest tests.test_release_v1_vertical -v
python -X utf8 -m unittest tests.test_release_v1_mode_switch -v
python -X utf8 -m unittest tests.test_release_v1_install_performance -v
cmd /d /c "python -X utf8 -m tests.test_release_v1_install_performance --benchmark --runs 5 > %TEMP%\wf-release-v1-install-benchmark.json"
```

CI 用 1 GiB 稀疏、未声明 sibling 证明 candidate 物化不会扫描无关组件；人工五次基线使用 10 GiB
稀疏 sentinel，并分别记录 verify、object import、materialize、candidate verify、stop/start、health、
capabilities 和 rollback 的嵌套耗时。相同 environment identity 下，中位数非预期回退超过 20% 时
停止合并并调查；wall time 不写成跨机器的固定 CI 阈值。
