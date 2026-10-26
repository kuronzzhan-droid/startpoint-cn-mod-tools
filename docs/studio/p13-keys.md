# p12b / p13 扩展键与客户端兼容检查

编辑台登记 `p12b`（versionCode `1008033`）和以它为底的 `p13`（`1008050`）。档案复用 `client_profiles.json` 的 `provides`、文件 SHA-256、`evidence` 和 `m2_capabilities` 字段。证据来源为 2026-10-25 的 p12 接口说明、`P13-REPORT.md` 与 `p13-capabilities.json`；仓库只保存中文来源描述与精简声明 JSON，不包含 APK、SWF 或本机路径。

这些档案的 `evidence.verification` 为 `report_declared`，对应 provides 使用既有 `patch-record` 类型。报告声明支持显示「待验证」；没有伪造补丁号、方法哈希或本次设备验收。其余旧能力的继承待核，没有按版本名补齐。旧发布闸门使用的 `capabilities` 留空；编辑台能力列在 `m2_capabilities`，不会凭这些报告绕过旧发布方法证据门禁。

| 能力 ID | p12b | p13 | 数据语法与含义 |
|---|---|---|---|
| `client.summon.cutin_preload@1` | 声明支持 | 声明支持 | multiball 行 c9 配有主动技能时预载球外观的 cutin；无新增键 |
| `client.combo.base@1` | 声明支持 | 声明支持 | unique_condition c0：`wfx:41:0:<base>:0:<label>`；base 为非负 int32，多个来源取最大，层数不放大 |
| `client.pf.dual@1` | 声明支持 | 声明支持 | unique_condition c0：`wfx:42:<level>:<multiball_id>:<flags>:<label>`；level 为 1–3，flags 仅 0/1，bit0 表示无球时仅持有者发动 |
| `client.summon.flip_pf@1` | 降级：弹起 PF 不可用 | 声明支持 | `wfx_summon_flip_pf_<multiball_id>`：`1` 或 `1:<最小间隔帧>` |
| `client.ball.pf_action@1` | 降级：协力球退回原生类型 PF | 声明支持 | `wfx_ball_pf_action_<multiball_id>`：新增 PF 动作键 |

后两种键位于 `master/string/custom_ability_string.orderedmap`，每个值必须为 CSV **单行单列**。编号为规范十进制正 int32；间隔帧为规范十进制非负 int32（0–2147483647）。拒绝负数、前导零、加号、空白、额外字段和溢出。`1:0` 合法，`1:00`、`1:-1`、`1:2147483648`、`1:2:3` 不合法。

动作键必须存在于本次输出或交付使用的基线 `master/skill/power_flip_action.orderedmap`；球必须存在于对应 `master/battle/multiball/multiball.orderedmap`。输出整表替代基线同表，不把输出删除的键从基线补回来。动作键与任一目标 APK 内置表撞名即阻断；APK 内置键通过 [bundle 索引](bundle-keys.md) 读取，不写死 `ranged` 等键。没有目标 APK 时记录「未核对内置键」，该项是警告。

`wf.studio.client_extensions.check_client_extensions(outputs, baseline_view, bundled_keys=...)` 接收逻辑路径到字节的映射。`baseline_view` 支持既有 `read_raw()` 视图或测试用字节映射；`bundled_keys` 是普通 CDN 逻辑路径到键集合的映射，`None` 表示未核对 APK，空映射表示已核对且没有匹配的内置键。返回字段：

```json
{
  "status": "ok",
  "requires": ["client.summon.flip_pf@1"],
  "checks": [],
  "keys": [{"logical": "master/string/custom_ability_string.orderedmap",
            "key": "wfx_summon_flip_pf_7", "capability": "client.summon.flip_pf@1", "value": "1:0"}]
}
```

`status` 为 `ok`、`warning` 或 `error`。`checks` 使用现有 `rule/status/message/blocking` 格式并带 `logical/key`；内置检查还带 `action`。阻断规则为 `CLIENT_EXTENSION_FORMAT`、`CLIENT_EXTENSION_MULTIBALL_MISSING`、`CLIENT_EXTENSION_ACTION_MISSING`、`CLIENT_EXTENSION_ACTION_COLLISION`、`CLIENT_EXTENSION_TABLE_INVALID`；未核对 APK 使用非阻断的 `CLIENT_EXTENSION_BUNDLE_UNCHECKED`。

requires 沿用 `requires.clientCapabilities`；能力推导使用真实表字段，普通文案中提及扩展名不算使用。p12 的 41/42 是独立处理器能力，不套用早期 v35 effect-query 或隐藏图标的方法哈希。五项已知能力缺失时，compat 行为 `rule=capability.degraded`、`status=待验证`、`compatibility=degraded`、`blocking=false`；整体兼容状态为「降级」。声明支持使用 `capability.declared`、`compatibility=declared` 和「待验证」。未知能力、旧能力缺失、未解析依赖及真实 kind 方法证据缺失仍按既有规则阻断。

没有新增独立 p13 CLI；通过编辑台交付入口选择 `--client-profile p12b` 或 `--client-profile p13`，HTTP 使用 `clientProfile`。扩展键校验在交付门禁执行，详细结果写入交付报告。以上检查只证明配置与声明的一致性，不等同于物理碰撞、实际渲染或多设备联机验收。

编辑台 `/api/studio/caps/lookup`、按行查询及 kind 查询共用的 `profiles.<档案>` 结果新增布尔字段 `degraded` 和 `declared`。任一为 true 时 `compatible=false`，该档案不列入 `requiredClientProfiles`；这用于区分「已确认满足」「降级」「仅报告声明」。非阻断说明仍留在 `pending`，`missing` 只含真正的阻断项，交付允许行为保持不变。既有普通「方法待补」提示不会被统一改成阻断或不兼容；前端应按 `degraded/declared` 显示相应状态，不应把它们解释成未登记能力或禁止生成。
