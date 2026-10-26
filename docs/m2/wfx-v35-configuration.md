# v35 配置扫描与证据边界

`wfx_registry.json` 的发布事实、参数约束与 `wf/caps` 的客户端方法证据是不同层次。登记为 `shipped` 不会自动产生方法摘要；缺少方法证据的 v35f–v35l 能力在新版依赖推导中继续返回 `partial` 和明确原因。

## 角色标签的实际位置

`character_tag_patterns` 登记的是标签格式，不是独立 master 表。发布门禁和依赖推导读取：

- `master/character/character.orderedmap` 的 c5。
- 五张词条表当前触发模式实际解析的块中，已声明的 `character_groups`、`*.character_groups` 列。列位来自 `ability_enum_map.json`，组内按逗号和斜线分词。

`wfx_cid_129989` 要求 `character-identity-tag-v1`；空后缀、零、前导零和非数字后缀被拒绝。普通文案中的相同字样和当前触发模式不读取的块不会产生该依赖。

原有 `ModDualForm` 登记保留。无参数标签沿用旧版行为；`ModDualForm:<正整数uid>` 要求 `dual-form-uid-v1`，其默认 UID 登记仍为 22。

## 码 30–36 的已知约束

所有这些效果均依赖 `wfx-effect-query-v1`。只声明效果本身、未声明查询底座的客户端档案不能通过门禁。

| 码 | 参数约束 | 尚未确认的部分 |
| --- | --- | --- |
| 30 | arg 保守限于 0..4；0 跟随队长 `concepts[0]`，concept 已登记类型为 1 技能、2 PF、3 直击、4 能力 | 非 0 分支的完整实现、value/flags 单位及运行时边界 |
| 31/32/33 | 当前只确认整数载体，不据效果名称猜测参数 | arg、value、flags 的完整语义；门禁保留 TODO 警告 |
| 34/35 | `类型 + 10 × 档位百分数 + 1000 × CT秒`；保守接受个位 0..4、非零两位档位 | 100% 档位会与 CT 进位重叠，零档编码被拒绝；CT 运行时边界及 value/flags 含义待核实 |
| 36 | bit0 表示只用类型 PF；仅接受 arg 0/1。value 是 Fever 倍率万分比，flags 是平时倍率 | 平时倍率缩放单位、数值运行时边界尚未确认 |

码 36 按持有者成员 PF 后，同帧执行其合击角色自身 PF；419/722 的合击覆盖优先，否则使用类型 PF。它不接受“队员槽位”解释。依据是随任务事实卡 `wf-v35-generic-patches.md` 的 v35l/TASK12 记录。

码 30–36 的叠层规则未获得实现证据，因此 `stack_scaled` 显式登记为 `null`，门禁提示未知叠层规则。不能把未知值改成 `false` 或 `true`，也不能把普通整数载体校验当成战斗运行时验收。

## 文案表配置

`wfx_unlock_<队长技编号>` 的编号必须为规范正整数，不接受前导零。位掩码只允许已登记的 1/2/4/8/16；8/16 另外要求 `leader-unlock-v2`。

`wfx_pf4_<角色编号>` 的值为正整数门槛，可附六位 RGB 十六进制颜色。大小写均接受，例如 `100:FF4040`、`100:ff4040`；门槛 0 被拒绝。

v35e 的 17 项语义能力仍由相同 SWF 哈希的累计方法证据覆盖。任务事实明确登记的 PF4 与队长解锁为 `shipped`，其余 15 项继续保留原 `local_candidate` 状态；仅在本地 APK 中发现某能力，不足以扩大其发布状态。

武器专属觉醒素材键 `awakening_material_<装备编号>` 也必须进入客户端依赖扫描。该键在旧注册表 `string_keys` 中对应 `equipment-awakening-material-v1`，尚无新版方法能力映射时返回 `partial`，阻止无证据的交付绿灯。现有 `client.apk.patch029@1` 只登记 5900101 专用限制，不能用相同方法名替代通用素材键的实现证据。
