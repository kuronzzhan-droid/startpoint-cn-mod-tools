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

归档的 111 项补丁不等同 111 个自动检测器。角色专用 #1/#5/#6/#7/#15/#32/#55/#65 与晒伤语义能力归 C 层（需要 APK），按注册表 `character_ids` 和角色的实际引用闭包识别。涉及能力、技能、固有、PF、覆盖文案或 DSL 等角色内容但缺少归属基线时保留 `partial`，不会漏掉角色专用补丁后宣称 resolved。纯性能、UI、原生平台等没有内容触发信号的条目仍需显式声明 `capabilities`。

注册表通过 `allowed_tables` 与 `kind_bindings` 中明确的 `(block, kind)` 选择依赖；`kinds`、`allowed_blocks` 是受校验的目录索引。instant 419/422/423/424 不产生 PF 或补丁依赖；during 422/424 分别要求 #3/#20；during 423 在角色能力表要求 #31，在两张武器表要求独立 R3，不要求 #30；instant 724 要求 #4。PF 只有 instant 722 / during 419 会跟进 override 引用。五张能力表包含 `ex_ability`。

具体位置是否支持，统一由 `wf apk kinds` 的真实 SWF 分支证据决定。两个编号相同但块不同的效果各自核对，不能因另一块登记了补丁而拒绝官方效果。`requires.kindSites` 记录表、块、kind、叶键与行号；交付在出 ZIP 前复用 `check_kind_sites`，编辑台也以完整位置作为缓存键的一部分。旧证据缺表或块时保留阻断的待验证，不再按编号补猜。缺少候选表基线时，`inferenceNotes` 明示按整张候选表保守扫描。

`requires.capabilityEvidence` 包含每项命中的逻辑路径、叶键、信号和值；`clientPatches` 是所需归档补丁号的并集。注册表以外的显式能力 ID、损坏表和损坏 DSL 会报问题。查不到所需引用时保留 `unresolved` 并标 `partial`，不能用空列表宣称没有依赖。有效但本仓尚未登记的未来玩法不在这份注册表的证明范围内。

`wf check` 回读交付时还比较 requires 的版本、ZIP 链和扫描成员摘要与实际交付字节，防止拿另一批内容的扫描结果充当本批证据。此回读检查不重复证明全部 DSL 语义；复现需要原变更集和基线。

`declared` 同样必须提供非空且完整的 `scannedMembers`。兼容命令会从 requires 所在目录只读打开 `pack.archives` 并逐成员核对摘要；缺归档、成员缺漏、重复或摘要不符均判问题。直接调用 `check_compat` 时须传入 `delivery_dir` 才能验证 declared 输入，单凭手写声明不能放行。

## 匹配结果

- 所需能力不存在、缺少其任一必需补丁、方法哈希不一致：`问题`，blocking=true，命令非零退出。
- 内容推导为 `partial` 或旧 `pending-m2`：`待验证`，blocking=true，不能确认兼容。
- 注册表已有 SHA-256，但输入缺少该方法或摘要：`问题`，阻断；包括全部方法缺失和只缺部分方法的情况。`wf apk provides` 不会提供这些补丁及依赖它们的能力。
- 只有注册表本身明确为 `null / 待补` 的方法可以保留 `待验证`，不伪造 hash。命令可能退出 0，调用方必须读状态。输入中多出的未登记方法列入 `warnings`，不会用它们证明能力。
- 所需能力、补丁与已有方法摘要全部吻合：`满足`。这是静态证据匹配，不能外推设备运行或服务端功能已部署。

真实反例固定在 `tests/test_m2_seris_history.py`：读取 1.4.208→209 实际战斗表和引用的 DSL，推导赛瑞斯 PF Lv4；完整 v34 记录匹配，移除 #87–89 后必须报“缺 PF Lv4”。测试不根据“v34”字符串决定结果。

机制矩阵入口及历史对比见 [矩阵说明](matrix.md)，文案规则与两镜像范围见 [文案规范说明](text-standard.md)。
