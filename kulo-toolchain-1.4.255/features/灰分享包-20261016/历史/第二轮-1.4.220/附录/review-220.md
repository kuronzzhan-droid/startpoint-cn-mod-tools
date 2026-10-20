# 1.4.220 最终分包独立复核

复核对象：灰 `1.4.136 → 1.4.220` 最终重建13个分包及其sidecar；源为锁定灰136与我方219。本记录已刷新最终sidecar、规则和脚本SHA。

- 13包、890成员；逐包SHA、大小≤5MiB、ZIP CRC、成员清单和成员SHA全部通过。
- 13个ZIP的SHA与上一次独立复核全部相同；sidecar以本次读回的最终SHA为准。
- 五处缺陷修复从最终ZIP读回均严格等于我方219：凉月三行、碧PNG与atlas两成员。
- 碧其余18项灰行继续保持灰136：character/text/status/speech/full_shot属性/generated character_image/leader、六条ability、action_skill及四条trimmed_image键。
- 当前五重精确清单2074条均已逐键检查最终视图，全部等于我方219且等于规则ours值。
- 五处客户端冲突均明确记录为ours_defect，碧PNG的逻辑路径已恢复。
- 已重新审阅priority_overrides.py、build_client.py：新增的源值断言和资源路径映射正确；当前输入下未发现规则应用遗漏。
- 最终priority-applied元数据计数：{'defect': 5, 'five': 819}。它只记录进入merge/override的行，不等于最终视图保护范围；全部2074条已独立验证。
- 三个evil/49行c109的fb3_buff$entrance首轮已是我方值，本轮继续保持；历史/我方/当前三者一致。

## 最终证据绑定

- manifest-entry SHA256：`239f31e6391987489aad306fbe5744d70f2da0c3b85edc430ca29750d52627a2`
- 五重规则SHA256：`bd87d984e38c529994cff13f061638ec2cd567d6ff6588d9c7ac8d496fb20fb8`
- 缺陷规则SHA256：`ee2513b14bbc8b9dc84a671c96269db2cdd4052191b624e95ff0db4099271b62`

review-220.json逐一记录最终13包SHA、sidecar SHA、受审脚本SHA及各行核对结果。审阅只写本记录，未修改业务数据、ZIP或构建器。客户端、服务端和联机运行表现仍为未核实。
