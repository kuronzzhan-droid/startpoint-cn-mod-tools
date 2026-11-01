# 应用到本地服与撤销

本功能仅向机器配置明确授权的本地服务端写一条交付边，不启停服务，不连接远端、不安装客户端、不操作数据库或模拟器。正式发布和测试服 175 不在此接口开放范围内。不要为远端快照或正式环境设置应用开关。

机器配置 `servers.<name>.apply_enabled` 必须严格为 JSON `true`，缺省、`false`、字符串或数字均拒绝。根目录仅从同条目的 `root` 解析，遵循 `wf_root` 相对路径规则；HTTP 和 CLI 都不接受目标路径。配置示例见 [profiles/README.md](../../profiles/README.md)。

```text
python -m wf.studio.draft apply --delivery-dir <构建根或交付目录> --server local --dry-run
python -m wf.studio.draft apply --delivery-dir <构建根或交付目录> --server local
python -m wf.studio.draft unapply --delivery-dir <构建根或交付目录> --server local
```

`server` 缺省为 `local`。dry-run 执行完整预演、交付检查证据及合并冲突检查，不写服务端、不生成备份；会短暂持有工作区内的事务锁。

## 门禁和写入

每次应用重新调用 `rehearse(..., write=False)`，任何 blocking 均拒绝。交付 `check.json.results` 必须存在且非空，各条明确 `blocking:false`；清单声明的 compat、draft-checks、safety-checks 必须存在，且不得有阻断或 error。draft-checks 接受编译器的 `state=满足` / `code` / `message` 格式，不要求通过项携带 blocking；state/status 为“问题”仍阻断。构建失败、prepush 失败或未豁免的未知兼容性同样拒绝。应用读取既有交付检查证据，不冒充重新执行构建、客户端能力或设备检查；rehearsal 会重新读取 ZIP、摘要及服务端状态。缺检查证据的历史裸 ZIP 不能直接应用。

交付 from 必须等于当前启用链尾。复用该次 rehearsal 的 `manifestEntry`，不重新构造。`local_test_only` 用于防止本地候选被当作正式发布。目标严格配置 `apply_enabled=true` 时，apply 和 dry-run 均允许交付携带该字段（包括值为 false 的历史标记）；只读预演显示“可应用到本地服，不可直接推 175”。复用的 manifest 条目及其 archive_integrity 均不写入这个字段，符合 HOWTO 的要求。原交付、标记、ZIP 与校验文件不修改；这不授予正式发布权限。非 apply_enabled 目标的预演仍按原规则阻断带标记交付，apply 则在入口拒绝。

1. 对所有涉及文件复核摘要，在 `work/studio-applied/<server>/<交付名>-<服务端与交付规范路径摘要>/` 写原始字节备份及 `receipt.json`。备份和锁均禁止落入任一命名服务端、全局 server 或配置的 CDN 根。备份先在同级临时目录完整写入，再原子发布；准备失败清理半成品。不同服务端及角色/BOSS/武器目录互不撞名。
2. 将 ZIP 放入 `assets/asset-patch/active/`。已有同名同内容跳过，同名不同内容拒绝。
3. 服务端 JSON 递归按对象键合并，保留未出现的旧键；已有叶子值不同拒绝。仅允许 assets/ 下业务 JSON，不允许 out/、数据库或 asset-patch/ 业务候选。根数组和服务端代码需要人工流程。拒绝重复键、NaN/Infinity 和溢出浮点值；保留未修改顶层键的原始值字节及原换行风格。
4. 每次写前复核读取过的服务端文件，manifest 写入前再检查链尾。末尾追加条目并更新 `cdn_version`，UTF-8 无 BOM、CRLF、2 空格缩进、末尾 CRLF，通过同目录临时文件和原子替换写回。
5. 完成后记录前后 SHA-256、各文件备份名、新放入文件、重启标志和步骤。失败撤销已做部分，原字节恢复；遇外部并发改动不覆盖对方内容。完整回滚记录 rolled-back；回滚未完成记录 rollback-failed 并保留服务端锁，阻止后续自动写入。错误回执本身也无法落盘时，保留旧回执与锁，并在响应 steps 中记录写回错误，不能视为完整恢复。

工具进程之间通过服务端根摘要命名的工作区锁串行化。外部编辑器并不遵循该锁，摘要复核是乐观并发检测，不能提供跨多个文件的系统级原子事务。进程崩溃或断电后须先检查 prepared 回执和锁，不自动猜测恢复。正常捕获到的中途错误会执行回滚。

applied/prepared/rollback-failed 回执禁止覆盖；unapplied 或 rolled-back 回执先移入同级 `.history/`，再允许新一次应用。旧版扁平回执不自动迁移：已有事务须先人工核对，不能凭新目录缺失推断已撤销。

## 撤销约束

只接受状态为 `applied`、对应同一服务端和交付的回执；交付必须仍是 manifest 最后一条、启用链尾。当前所有文件摘要（包括跳过的同内容 ZIP）与回执 afterSnapshot 一致，备份摘要也一致，才可恢复原文件并删除本次新增文件。未修改的既有 ZIP 保留。撤销失败同样恢复已撤销部分。

**客户端版本回退风险：** 已下载过这条边的客户端不会随服务端回滚自动恢复，可能无法继续更新。需要操作者人工处理客户端版本和资源，或制作更高版本修复边。本工具不会操作客户端。

## 前端接口

两个 POST 均经过现有 WriteGuard：JSON Content-Type、`X-WF-Studio-Token`、Host、Origin、Sec-Fetch-Site 检查。同一交付生成、预演、应用或导出中拒绝重复操作。

| 接口 | 请求体 |
| --- | --- |
| `POST /api/deliveries/<name>/apply` | `{"server":"local","dryRun":false}`；两个字段均可省略 |
| `POST /api/deliveries/<name>/unapply` | `{"server":"local"}`；可省略 server |

JSON 请求体必须为对象；数组、字符串、布尔、数字和 null 返回 400，不降级为默认真实应用。未知字段（尤其 root/path）、非布尔 dryRun 拒绝。HTTP 参数错误为 400、鉴权错误为 403；Content-Type 错误按 WriteGuard 返回 415。完成的应用尝试为 HTTP 200，必须检查 `ok`；业务拒绝并不等同 HTTP 失败。

| 响应字段 | 含义 |
| --- | --- |
| name / server | HTTP 交付名 / 命名目标 |
| ok / status | 布尔；`blocked`、`failed`、`dry-run`、`applied` 或 `unapplied` |
| error | 失败原因；失败时存在 |
| steps[] | `step/status`；write 有 path，rehearse 有 checks，rollback 有 errors |
| from / to | apply 计划的版本边；尚未完成输入检查时缺省 |
| dryRun | apply 是否仅检查 |
| files[] | apply 成功时 path/beforeSha256/afterSha256/backup；dry-run 为计划路径列表 |
| receipt | 成功写入的本地回执路径 |
| restartRequired / restartReason | 是否需要人工重启及原因；只有资源无需重启，服务端 JSON 需要 |
| clientRisk | unapply 始终返回客户端回退风险说明，前端应显示 |

CLI 包装为 `{"ok":true或false,"result":<上述结果>}`，失败退出码 1，成功为 0。结果不是运行态或设备验证证据。
