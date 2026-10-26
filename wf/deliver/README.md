# 本地变更集交付

`python -m wf deliver changeset.json --baseline-manifest <manifest.json> --base-store <store> --out work/m1/deliver/candidate` 从已暂存的变更集生成交付，不安装、部署或发布。输出必须在当前工具 checkout 内且为空；不会覆盖已有交付。

变更集采用 `schemas/change-set.schema.json`。客户端每个成员声明 `root`、逻辑路径、相对暂存文件、前后 SHA-256；`before_sha256: null` 表示前置视图不存在该成员。`server_changes` 以服务端相对路径表示 JSON 等镜像文件，只生成 `server/` 下的暂存副本。`changes` 可保留逐键、逐行、逐格的审阅记录。路径逃逸、摘要漂移、重复目标和版本回退直接拒绝。

交付包含：

- 历史 `pinball-<from>-<to>-<seq>-<slug>.zip`、每包 integrity、汇总 integrity 和旧 manifest 条目。
- `patches/<to>/patch-manifest.json` 及 common、medium、android 三层 inner ZIP；空层使用 `.empty`。每个 ZIP 实际压缩后的容器不超过 5 MiB，单成员无法容纳时失败。
- `delivery-manifest.json`、`requires.json`、`SHA256SUMS` 和独立 `assert_box.py` / `assert-box.json`。`installed_size` 是本批变更成员解压写入的总字节数，不是整个客户端资源视图的 `totalSize`。
- 自动执行 `prepush --since <from>` 的 JSON 和日志，以及 `dsl-629.json`。`validation/` 只暂存检查所需 JSON；基线 ZIP 按 manifest 选取后直接只读引用，不复制 active。

默认必须提供 `--baseline-manifest`，由 `wf view` 的依赖链解析器绑定 `from_version`，并写出 `baseline.lock.json`。重复的 `--baseline-manifest-extra` 和 `--baseline-zip-dir` 补充清单与搜索目录；`--view-lock` 可强制已有输入锁，`--base-version` 默认 `1.4.131`。`--baseline-active` 兼容入口从其父目录的 `manifest.json` 推导；`--baseline-zip` 只允许已被清单选中的归档，不能用手工 ZIP 清单代替版本证明。manifest 中已有目标版本（包括禁用条目）时禁止同版本重铸，已有更新启用边时拒绝过期 from。

确实缺少客户端基线时，仅显式 `--no-baseline-i-know` 可以放弃这项检查，交付清单与 prepush 报告会保留该决定。已提供但矛盾的基线不能因此放行。此开关也不能豁免 629 门禁或服务端前置摘要。`--server-dir` 只读取 prepush 所需 JSON，不加载服务程序、不向该目录写入；涉及 `server_changes` 必须提供，并逐文件检查前置摘要，包括原文件不存在的断言。

继承 prepush 的 ERROR 会使命令返回非零。缺少必需基线或服务端前置输入属于问题；未加载 kulo #35 服务模块等剩余限制仍标为待验证。本模块另行检查本地版本边、seq 连续性、重复、分叉、断链和前后摘要；这些结果保存在 `prepush.json` 的 `local_contract`。打 ZIP 前从候选能力表推导受影响的 629 树并递归检查 `path$program`，问题会留下报告并阻止出包。能力表与 DSL 必须位于 common 层，不能用其他层跳过门禁。

M2.1 新增 `delivery.reward-keys`：本次 `server_changes` 中的 score_reward、rare_score_reward 及各自 `_cnmod` 文件按服务端实际覆盖语义合并，与候选客户端对应表核对组键和子位置。score 行引用的 rare 组及可能返回的 rare 子索引一并检查。新增行缺键为 ERROR；存量行（含本次修改的存量行）为 WARN。删除 `_cnmod` 覆盖后重新露出的基础行也会检查。`prepush.json` 的 `companion_reward_keys` 记录执行状态、服务端目标、检查行数和基线完整性；`wf check` 回读同一结果，未执行和缺基线不会写成满足。

M2 起 `requires.json` 从变更叶子及其引用闭包推导已登记能力：角色引用、真实 kind 列、PF 等级、固有 ID/字符串、技能 DSL、超限表和语音路径。保留各能力命中位置、成员 SHA-256 与必需补丁号；不把未改叶子一并算作本次新增依赖。引用完整时为 `resolved`，缺少引用数据时为 `partial` 并列明缺项。结构损坏出包前失败。旧 `pending-m2` 文件仍可读，但不能通过兼容匹配。显式 `capabilities` 只能追加已登记的依赖，不能掩盖自动推导结果。

用 `python -m wf check compat --requires <交付/requires.json> --provides <客户端/provides.json>` 匹配目标客户端。缺能力会列出中文名称和必需补丁；同时核对能力与补丁两处方法哈希。`resolved` 表示本次内容的注册能力扫描完成，不代表所有客户端都兼容、所有游戏语义已知或设备已实测；服务端配合项仍单独列在 `serverFeatures`。完整格式与边界见 [M2 能力依赖说明](../../docs/m2/capabilities.md)。

断言脚本只读，可在交付目录单独使用：

```powershell
python assert_box.py --phase pre --manifest <旧manifest.json> --active <旧active> --store <production> --server-dir <服务端目录>
python assert_box.py --phase post --manifest <新manifest.json> --active <新active> --store <production> --server-dir <服务端目录>
```

版本和摘要来自生成的 `assert-box.json`，不用手改脚本版本号。运行断言本身不会部署文件。

上游结构沿启动器 `docs/在线更新协议.md` 引用的固定提交核对：[官方 patch manifest schema](https://github.com/DontBeAlarmed/startpoint-cn/blob/b2e40c3f1b24b704e5881fbefa12be101ea78134/docs/cdn/patch-manifest.schema.json)、[Overlay 契约](https://github.com/DontBeAlarmed/startpoint-cn/blob/b2e40c3f1b24b704e5881fbefa12be101ea78134/docs/cdn/patch-overlay.md)。`compatibleClient: CN 1.8.1` 是该容器协议要求的标识，不替代本批 MOD 内容的能力匹配或客户端实测。

历史 221 变更集由 `python -m recipes.halloween221_changeset --package-root <完整historical221重建的pkgroot> --out <本仓输出>` 产生。此入口只消费完整重建 package；期望交付 ZIP 只用于后续独立逐成员比较。Windows 读深层 DSL 文件时保留扩展长度路径，避免普通 `is_file()` 把长路径漏当成不存在。

M1.1 起历史 221 的 PF3 树必须被公开 deliver 阻断。历史 310 成员字节回归单独核对归档算法，不生成通过门禁的交付清单，也不构成对旧包的放行。
