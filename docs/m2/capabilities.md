# M2 能力声明、推导与兼容匹配

三个入口分别回答登记了什么、内容需要什么、指定客户端是否有这些能力。它们均为本地文件操作，不连接设备或运行服务。

```powershell
python -m wf check caps --json work/m2/capabilities-check.json
python -m wf apk provides <构建记录或APK或SWF> --output work/m2/provides.json
python -m wf deliver <changeset.json> --out <本仓空目录> --baseline-manifest <manifest.json> --base-store <store>
python -m wf check compat --requires <交付目录/requires.json> --provides work/m2/provides.json --json work/m2/compat.json
```

注册表格式和 v34 证据来源见 [注册表说明](../../wf/caps/README.md)。`wf check <能力.yml>` 校验 schema 与补丁归属，`wf check caps` 校验全部声明。只读输入可以在仓外，所有输出必须在当前 checkout。

## 内容推导

`infer_requirements(members, read_raw=...)` 读取候选成员原始字节，`read_raw` 提供只读基线。完整表按叶子与基线比较，只扫描变更叶子；没有基线时扫描所提交全表，报告中的 `scannedMembers` 逐项绑定原始 SHA-256 和 common/medium/android 层。

能力表依据本仓枚举布局读取真实 kind、固有 ID、PF override 和觉醒字段，124/126 列分别定位。角色行继续追踪技能、切换技能、队长技和六个能力槽；能力引用的固有字符串、PF 表、技能档和 DSL 递归跟进。`desc_override_` 只认键，PF Lv4 只认等级声明，文案中出现数字 424 或文字 `hidden_` 不会产生对应能力。DSL 识别 ACUnique/DCUnique、伤害类型转换标志及程序引用。语音轮换识别实际 `skill_ready_alt_1` 至 `_5`、`matched_skill_ready_alt_1` 至 `_5` 路径，以及角色的 `_voice_ready` 切换技能标记。

归档的 111 项补丁不等同 111 个自动检测器。性能、UI、原生平台补丁，以及仍按文档映射的角色专用补丁（如九尾连击快照、特定角色旧准备语音和私有视觉预载），没有通用数据触发信号的条目需在变更集中显式声明 `capabilities`。矩阵把这些文档映射单独标明来源；不能据矩阵徽章推定任意内容片段都能自动识别该补丁。

`requires.capabilityEvidence` 包含每项命中的逻辑路径、叶键、信号和值；`clientPatches` 是所需归档补丁号的并集。注册表以外的显式能力 ID、损坏表和损坏 DSL 会报问题。查不到所需引用时保留 `unresolved` 并标 `partial`，不能用空列表宣称没有依赖。有效但本仓尚未登记的未来玩法不在这份注册表的证明范围内。

`wf check` 回读交付时还比较 requires 的版本、ZIP 链和扫描成员摘要与实际交付字节，防止拿另一批内容的扫描结果充当本批证据。此回读检查不重复证明全部 DSL 语义；复现需要原变更集和基线。

## 匹配结果

- 所需能力不存在、缺少其任一必需补丁、方法哈希不一致：`问题`，blocking=true，命令非零退出。
- 内容推导为 `partial` 或旧 `pending-m2`：`待验证`，blocking=true，不能确认兼容。
- 能力和补丁存在，但方法哈希为 `null / 待补`：保留 `待验证`，不伪造 hash。遵循既有检查约定，不把证据不足改写成确定错误；命令可能退出 0，调用方必须读状态。
- 所需能力、补丁与已有方法摘要全部吻合：`满足`。这是静态证据匹配，不能外推设备运行或服务端功能已部署。

真实反例固定在 `tests/test_m2_seris_history.py`：读取 1.4.208→209 实际战斗表和引用的 DSL，推导赛瑞斯 PF Lv4；完整 v34 记录匹配，移除 #87–89 后必须报“缺 PF Lv4”。测试不根据“v34”字符串决定结果。

机制矩阵入口及历史对比见 [矩阵说明](matrix.md)，文案规则与两镜像范围见 [文案规范说明](text-standard.md)。
