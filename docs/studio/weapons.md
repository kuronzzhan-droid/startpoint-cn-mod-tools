# 独立武器工坊后端接口

武器接口以 `/api/studio/weapons` 为前缀，不需要 quest。读取使用编辑台当前视图和显式配置的本机服务端输入；编辑写入 `work/studio-drafts/weapons/<武器ID>/changeset.json`，保存、生成和导出复用现有编辑台机制。`WF_STUDIO_DRAFTS` 或启动时的草稿根覆盖同样生效。

所有 ID 都用十进制字符串。所有 POST 都要求 `Content-Type: application/json` 和当前会话的 `X-WF-Studio-Token`；Host、Origin、Sec-Fetch-Site 沿用编辑台守卫。克隆和材料编辑的预检、正式写入失败返回 HTTP 400、`ok: false`、兼容字段 `error` 及五态 `checks`，详见第 3 节；其他输入错误沿用 `{"error":"原因"}`。鉴权失败为 403，详情不存在为 404。写入错误不会留下部分草稿。这里的 `runtime: "未执行"` 表示未做设备实测。

## 1. 全局列表

`GET /api/studio/weapons?q=剑&element=1&rarity=5&limit=200`

| 参数 | 语义 |
| --- | --- |
| `q` | ID、名称、内部代码包含匹配，不区分大小写 |
| `element` | 服务端装备分类，整数 -1..5；不是魂珠可装备属性限制 |
| `rarity` | 整数 1..5 |
| `limit` | 默认 200，范围 1..2000；筛选后截断 |

每个参数最多出现一次。省略属性或稀有度表示不过滤，响应示例：

```json
{
  "schema": "wf-studio-weapons/1",
  "version": "1.4.254",
  "items": [{
    "id": "5010005", "name": "示例武器", "rarity": 5,
    "element": 1, "icon": "item/example_weapon", "soulId": "5010005",
    "isMod": false, "hasEnhancement": true, "hasAwakening": true
  }],
  "total": 1, "count": 1, "limit": 200,
  "notes": ["属性来自服务端 equipment_element 分类，不推导能力的属性限制。"]
}
```

`total` 是筛选后的总数，`count` 是返回条数。图标是逻辑路径，可使用现有 `/api/boss/icon.png?path=<URL编码后的逻辑路径>` 读取，该图标接口不依赖副本。

`isMod` 由官方装备基线判断是否新增键：新增 true，官方已有 false，基线不可用 null。修改官方武器不会变成“新增 MOD”。`element` 在本机服务端输入缺失时为 null。`hasEnhancement` 表示存在强化本体，`hasAwakening` 取装备原生最大觉醒等级；这些字段不代表实际运行验证。

列表读取当前基线；尚未生成交付的武器通过第 5 节的草稿列表发现，再用详情接口读取候选状态。

## 2. 武器详情

`GET /api/studio/weapons/5010005`

返回列表卡片字段以及以下详情字段；如果该武器有独立草稿，返回校验输入哈希后的重放候选。示例展示摘要字段（实际响应还含完整原生行）：

```json
{
  "schema": "wf-studio-weapon/1", "version": "1.4.254",
  "id": "5010005", "weaponId": "5010005", "subjectKind": "weapon",
  "curves": {
    "base": {"count": 2, "first": {"level": 1, "hp": 100, "attack": 20},
             "last": {"level": 5, "hp": 200, "attack": 40}},
    "enhancement": {"count": 0, "first": null, "last": null}
  },
  "awakening": {
    "maxLevel": 5, "serverInputAvailable": true,
    "materialId": null, "material": null, "clientMaterial": null,
    "rarityOverride": null, "standardMaterials": []
  },
  "references": {"shops": [], "gacha": []},
  "changeset": null, "status": {"state": "clean", "label": "无草稿改动", "changes": 0},
  "draft_status": {"state": "clean", "label": "无草稿改动", "changes": 0},
  "checks": [], "runtime": "未执行"
}
```

| 字段 | 内容 |
| --- | --- |
| `equipment` | 本体记录，包含 `row`、表路径及来源 |
| `soul_item` / `ability_soul` | 通过本体 c10 关联魂珠 item 与能力魂记录，二者 ID 不假定与武器相同 |
| `equipment_enhancement` / `equipment_enhancement_ability` | 强化本体与强化能力记录 |
| `base_status` / `enhancement_status` | 完整基础曲线和强化曲线；字段含义、类型保持兼容 |
| `curves` | 两类曲线的点数及首尾 HP/攻击 |
| `enhancement_chain` | 强化商品阶段、原生行、材料、普通货币、等级范围；`costs[]` 含材料 `itemId`、`amount`、`name`、`icon` |
| `materials_to_120` / `user_costs_to_120` | 沿用现有模型的到 120 级材料/普通货币累计；材料条目同样含 `name`、`icon` |
| `awakening` | 本机专用材料限制、稀有度覆盖、客户端材料文案和原生通用材料行；缺少输入时显式标注 |
| `references` / `referenceCoverage` | 商店及客户端/服务端装备卡池引用及扫描范围；权重 0 的条目仍是引用，不等于开放获取 |
| `changeset` / `draft_status` / `checks` | 草稿、保存状态及规则结果；未设置魂珠属性时包含继承提醒 |
| `status` | `draft_status` 的兼容别名，仍是草稿保存状态对象 |

记录类型字段包含 `table`、`path`、`row`、`source`；找不到关联行时为 null。前端须处理 null，不推断其已经通过验证。

本接口与 BOSS `WeaponDoc` 的命名有历史差异：BOSS `status` 是基础曲线数组，独立武器详情的 `status` 是草稿保存状态对象。新增的 `draft_status` 与本接口 `status` 始终相同，建议新调用方显式读取 `draft_status`；基础曲线继续从 `base_status` 读取。复用 BOSS 武器组件时，仍应把 `base_status` 映射到其 `status` 字段，不能直接把整份详情当作 BOSS `WeaponDoc`。

`enhancement_chain[].costs[]` 与 `materials_to_120[]` 的 `name`、`icon` 从当前候选视图的材料 item 行读取，分别对应 c2 名称和 c3 图标逻辑路径。关联材料不存在或字段为空、`(None)` 时，对应字段为 null；仍保留 `itemId` 和数量，不把图集成员名 c4 当作 PNG 路径。图标可用第 1 节的 `/api/boss/icon.png` 接口读取，路径存在不代表已经验证图像文件可用。阶段的 `amount` 保持原生字符串，累计的 `amount` 保持整数，例如：

```json
{
  "enhancement_chain": [{"costs": [
    {"itemId": "1", "amount": "2", "name": "强化矿石", "icon": "item/ore"}
  ]}],
  "materials_to_120": [
    {"itemId": "1", "amount": 240, "name": "强化矿石", "icon": "item/ore"}
  ]
}
```

商店引用扫描客户端的领主币商店、活动道具商店和强化商店，以及本机服务端的 `boss_coin_shop`、`event_item_shop`、`event_item_shop_rank_p5b`、`general_shop`、`star_grain_shop`、`treasure_shop`、`equipment_enhancement_shop` JSON。服务端来源是否可用逐个列在 `referenceCoverage.serverShops`；false 表示缺少输入，不代表没有该类商店。羁绊兑换通过已核实的 `general_shop.json` 奖励关系关联，不猜其他客户端商店列位。

引用中的 `scope` 区分 client/server；服务端记录还带 `source`、`path`、`product`、`matches`，活动商店带 eventType/eventId。一个商品的客户端记录、服务端镜像和附加表各自返回证据，不可直接用引用条数作为去重后的商品数。

## 3. 克隆武器

`POST /api/studio/weapons/clone`，请求体直接传 BOSS 版的 `weapon` spec，不再包裹 operation/weapon：

```json
{
  "sourceWeapon": "5010005",
  "name": "工坊新武器", "description": "新武器说明",
  "soulDescription": "魂珠说明", "soul_elements": "all",
  "hpMultiplier": 1.2, "attackMultiplier": 1.1
}
```

支持原有 `id`、`icon`、`enhancedIcon`、`abilities`、`enhancementProducts`。图标沿用既有武器/魂珠配对和加载资源检查，能力编辑沿用武器专用列位及客户端能力检查。`id` 省略时按既有 5950001..5999999 分配；显式指定时接受无前导零的 1..21474835，以保证 `id * 100 + 99` 不超过有符号 32 位整数。会检查客户端表、本机服务端镜像、BOSS 草稿和独立武器草稿的占用，包括仅修改材料的草稿以及强化商品号所占的武器号段。

P0 新增 `code`、`exclusive_character`、`soul_template`。`code` 必须匹配 `[a-z][a-z0-9_]{0,79}`，写入 equipment c0；派生魂珠 item c0 为 `<code>_soul`。两者同时检查当前 equipment/item 表和 BOSS、独立武器草稿预留，冲突拒绝。未传 `code` 时仍使用 `boss_workshop_<id>` / `boss_workshop_soul_<id>`，兼容原 BOSS 页面。草稿命名空间的 `code: weapon_<id>` 保持原契约，和游戏内部代码名是两个字段。

`enhancementProducts` 通常省略；克隆后的阶段号固定为 `武器ID * 100 + 阶段序号`，序号从 1 开始、最多 99。显式传入的阶段号必须与此一致；冲突不会通过跳号规避。旧草稿若保存了错位阶段号，重放会拒绝，须以当前基线重新创建。

克隆专用觉醒材料时，同步生成客户端 `awakening_material_<新ID>` 与服务端 `materialByEquipment` 条目。需要修改觉醒配置时必须提供实际的完整 `equipment_awakening_material.json` 基线；专用材料还要求现有客户端 `custom_ability_string` 表。缺少这些输入会拒绝操作，不生成空基线配置。稀有度与装备 ID 百万位不一致时同步写 `rarityOverrides`，保留其他键与通用材料。

`soul_elements` 可传 `"all"`、`"auto"` 或 1..6 个不重复的整数 0..5，例如 `[0,3]`。它们分别写 item[12] 为 `0,3,2,1,4,5`、`30`、逗号分隔列表。省略时继承母本；母本已明确包含全部六属性时不报限制告警，其他情况返回 `weapon.soul-elements-inherited` 非阻断提醒。`soulDescription` 写 item[5]，可选；未给时继承母本。`description` 是武器及强化武器说明。

预检、保存和交付重放都会拦截 `blocking: true` 或 `level: "error"` 的规则结果。非阻断检查写进草稿时保留原有 `info`/`warn` 等级，未指定等级才默认 `warn`。

响应摘要示例：

```json
{
  "ok": true, "weaponId": "5950001", "subjectKind": "weapon",
  "allocation": {
    "sourceWeapon": "5010005", "id": "5950001",
    "enhancementProducts": ["595000101"], "soul_elements": "all"
  },
  "status": {"state": "dirty", "label": "草稿 1 项 · 未保存", "changes": 1, "savedAt": null},
  "checks": [], "runtime": "未执行"
}
```

实际响应还含 `change`、`changeset`、逐叶 `changes` 和 `serverTargets`。`allocation` 保留原请求字段并补齐 ID。追加 `?preview=true` 可预检，不写草稿、不占用 ID；预检响应包含候选 allocation/changes/checks，但不含 change/changeset/status，正式提交可能获得不同 ID。

克隆和材料编辑在预检或正式写入被拒绝时，HTTP 状态为 400。返回 `ok: false`、`subjectKind: "weapon"`、`runtime: "未执行"`，并保留 `error` 字符串方便旧调用方显示。`checks` 第一项是阻断摘要 `weapon.inputs`；如果规则检查阻断候选，后面保留已经生成的所有规则结果及附加证据，包括通过、提醒和阻断项。各项 `status` 沿用 BOSS 五态：`满足`、`问题`、`待验证`、`不适用`、`未执行`；不是每次都生成五个检查项。

失败响应中的 `weaponId` 是已知的候选 ID 或材料接口路径 ID，尚未确定时为 null；`allocation` 在规则阻断且已经完成克隆分配时返回候选 spec，其他情况为 null。失败不会保存草稿、修改已有草稿或占用候选 ID。例如材料请求的 `id` 与 URL 不同：

```json
{
  "ok": false, "error": "请求中的武器 ID 与路径不一致",
  "weaponId": "5010005", "subjectKind": "weapon", "allocation": null,
  "checks": [{
    "rule": "weapon.inputs", "status": "问题", "blocking": true,
    "message": "请求中的武器 ID 与路径不一致"
  }],
  "runtime": "未执行"
}
```

## 4. 编辑强化材料

`POST /api/studio/weapons/5950001/materials`

```json
{
  "stages": [{
    "productId": "595000101",
    "costs": [{"itemId": "2370099", "amount": 10}],
    "userCost": {"type": 2, "amount": 100}
  }]
}
```

路径给出武器 ID；请求中可省略 `id`，如传入必须相同。`productId` 必须属于该武器，材料必须在当前视图存在；商品阶段 ID 使用详情或克隆 allocation 返回值。`userCost` 缺省保留、null 删除，type 只接受 1/2。客户端行和服务端强化商品镜像同步编译。可以直接编辑基线武器，也可以继续编辑同 ID 的克隆草稿，不要求所属 BOSS。支持 `?preview=true`。

响应结构同克隆，`allocation` 为 null。一个武器的全部操作保存为同一个可重放 change；后续操作 revision 递增，重放会重新检查原输入哈希。

## 5. 本次修改、保存、生成交付

| 方法及路径（相对前缀） | 用途 |
| --- | --- |
| `GET /drafts` | 返回 `{"subjectKind":"weapon","drafts":[...]}`；条目新增 `weaponId`、`name`、`isNew`，保留 `characterId` 等原有字段 |
| `GET /drafts/<id>` | 返回 weaponId、兼容字段 characterId、subjectKind、changeset、status、actions |
| `POST /drafts/<id>/save`，body `{}` | 校验并保存，返回 `{"status":{...}}` |
| `POST /drafts/<id>/changes/<changeId>/revert`，body `{}` | 撤销整组可重放武器操作，返回 status |
| `GET /deliveries/defaults` | 当前视图版本、候选目标版本、客户端档案及输出目录 |
| `POST /drafts/<id>/build` | 复用 `build_draft`，同步返回 build-report；`{"background":true}` 返回后台任务 |
| `POST /drafts/<id>/build/cancel` | 取消后台生成 |
| `GET /deliveries`、`GET /deliveries/jobs/<name>` | 交付列表、生成进度 |
| `GET /deliveries/<name>`、`GET /deliveries/<name>/file?path=...` | 交付详情和导出文件 |

草稿列表条目示例：

```json
{
  "characterId": "5950001", "weaponId": "5950001", "code": "weapon_5950001",
  "name": "工坊新武器", "isNew": true, "changes": 1,
  "updatedAt": "2026-10-25T12:00:00+00:00", "savedAt": null
}
```

`isNew` 表示草稿当前包含 `weapon_clone` 操作：克隆草稿为 true，仅编辑已有武器材料为 false，撤销克隆后为 false。它与列表中的 `isMod` 含义不同，不依赖官方基线。`name` 优先取克隆请求中的名称；未指定时取当前视图的母本名称，已有武器则取本体名称。关联本体不存在或名称字段为空时为 null。列表只描述草稿操作，不要求成功重放或验证客户端能力；因此仍可找到需要修复或撤销的草稿，列表可见不代表该草稿可生成交付。

生成示例请求（版本和 clientProfile 应从 defaults 取值）：

```json
{"from":"1.4.254","to":"1.4.255","background":true}
```

生成重新验证 schema、命名空间、基线版本、输入 SHA-256、能力与材料规则，并通过现有本地交付流程生成客户端补丁、服务端镜像及断言、能力检查和清单。输出在 `work/studio-deliveries/weapons/`；变更集 ID 为 `studio-weapon-<id>-<版本>`，与同号角色和 BOSS 隔离。缺少所需本机服务端输入会拒绝写入或生成。

共享表从完整基线逐键编译：客户端保留未修改外层键及其全部记录，服务端 JSON 仅合并本次修改的装备/商品键，觉醒文件保留其他装备材料、稀有度覆盖和官方素材配置。客户端协议及服务端镜像的交付单位仍是整文件；交付包不等于可随意覆盖的增量键补丁。打包前与 `run_prepush` 均以本次 manifest 选中的基线检查外层键、角色包已在该基线存在的 claims、键内记录条数、武器 JSON 映射键和 ID 列表；缺少完整共享表基线、丢键、记录缩水或无法解析会阻断，结果写入 `prepush.json` 的 `shared_table_preservation`。商品内部的价格、材料与可选 `userCost` 仍按本次请求变更。

武器嵌套曲线表的已有等级键同样受保护。BOSS 原有 `shop_delete` 仅在变更集明确记录该商店单键删除、从基线逐步重放该键的修改后与删除前值一致时豁免该键；支持同草稿先修改再删除，任何旧值断链都会拒绝，角色包 claims 不豁免。这不开放任意表的删除开关。底层 `wf deliver --no-baseline-i-know` 保留原有无基线本地审阅合同并明确记录“键保留未验证”；Studio 武器生成始终绑定 manifest，不使用此逃生口。

同一 `from -> to` 边生成的两份草稿包是候选方案，各自包含完整基线和本草稿的修改，不能按顺序复制两包的整表来累加。第一份进入新的基线后，另一份必须重新建立草稿；当前没有 rebase API。manifest 已占用目标版本、来源落后或客户端/服务端输入 SHA-256 漂移都会拒绝旧草稿；随包断言也会拒绝在第一份已改变的服务端文件上套用第二份旧包。

能力检查不能用合成测试客户端证明真实可用。当前 `awakening_material_` 对应的 `equipment-awakening-material-v1` 尚缺 M2 能力目录/方法证据时，受限武器仍可生成供审阅的本地文件和键保留报告，但依赖推导会列出 TODO、兼容检查阻断且 `ok: false`；须补齐与所选实际 SWF 绑定的能力证据后才能宣称兼容。真实交付回归使用可解析的合成 SWF，仅验证 native kind 分支扫描和构建链，不代表已安装客户端或设备结果。

原有 device-result 读取、写入及导入接口同样挂在上述交付前缀下，绑定 `kind: "weapon"`。生成成功与设备实测分别报告；本次接口不会执行发布或部署。前端可将 `/drafts` 的武器条目加入“本次修改”，对对应武器调用 build，再使用交付列表和文件接口导出。

## 6. 专属角色的证据边界

克隆 spec 可包含 `"exclusive_character": "139988"`。该字段保留在草稿请求和 allocation 内，返回 `weapon.exclusive-character-metadata`、`enforcement: "metadata_only"` 的非阻断提醒。它只记录设计归属；本次不限制武器装备、魂珠装配或能力生效，也不承诺客户端已有专属限制。

本次核对的客户端源码是反编译客户端 `scripts/pinball/master/generated/` 下的 `EquipmentValues.as` 与 `ItemValues.as`：前者构造函数只读取 c0..c15，未提供专属角色 ID；后者 `ItemEffectKind.AbilitySoul` 的参数是 `parseAt12(element)`，c12 是属性列表。没有发现可据此写入的角色独占列或已登记补丁。因此没有将角色 ID 写进属性、装备类型或其他列。需要真正限制装备时，应先补充对应客户端及服务端规则的证据和需求。

旧引擎笔记曾以官方样本 c67/c68 为空推断魂珠表无 InvokeSkill 落点；本次直接核对同目录 `AbilitySoulValues.as:11494`，确认 629 分支读取 `parseAt67` / `parseAt68`。实现采用源码实证列位，不沿用那条旧推断。

## 7. 魂珠能力伤害模板

模板随 `POST /api/studio/weapons/clone` 的 `soul_template` 对象提交，**替换母本全部 ability_soul 行**，不会和母本能力叠加；强化能力仍按原克隆规则保留。不能同时提交 `abilities` 中针对 `ability_soul` 的手动修改，以避免覆盖顺序歧义。

```json
{
  "sourceWeapon": "5100017", "id": "5950001", "code": "duet_example",
  "exclusive_character": "139988",
  "soul_template": {
    "template": "pf_hit_ability_damage", "element": 2,
    "multiplier": 1, "max_multiplier": 2,
    "trigger_limit": 10, "cooldown_frames": 120
  }
}
```

| 模板 | 触发 | 默认伤害对象与 kind |
| --- | --- | --- |
| `pf_hit_ability_damage` | PF 命中 183 | 命中的敌人，316..321 |
| `pf_use_ability_damage` | PF 发动 2 | 全体敌人，251..256 |
| `pf_hit_invoke_damage` | PF 命中 183 | 全体敌人，629 + 生成的 DSL |
| `pf_use_invoke_damage` | PF 发动 2 | 全体敌人，629 + 生成的 DSL |

原生模板完全使用现有能力伤害族，不生成 DSL。`damage_target` 可改为 `all_enemies`（251..256）、`trigger_enemy`（316..321）或 `nearest_enemy`（352..357）；PF 发动模板没有命中敌人上下文，不能选择 `trigger_enemy`。元素由 kind 决定，未向无效元素列塞值。其余 251..387 家族中的 HP 基准及不计连击变体不在本次模板选项内。

| 字段 | 约束及含义 |
| --- | --- |
| `element` | 必填整数 0..5：火、水、雷、风、光、暗 |
| `multiplier` | 必填攻击倍率，0.00001..21474；1 表示攻击力 1 倍，写 c48=`100000` |
| `max_multiplier` | 可选满觉醒倍率，默认等于 multiplier，不能更小；写 c49。魂珠取最低档，武器按觉醒等级插值 |
| `trigger_limit` | 可选正整数触发次数上限，写 c31；null/省略写 `(None)` 表示不限制。本字段不是单次伤害封顶 |
| `cooldown_frames` | 可选非负整数，默认 0；写 c32，60 帧为 1 秒 |
| `damage_target` | 原生模板支持上述三个对象；629 只支持 `all_enemies` |

629 版本还必须显式提供 `dsl_element`（1..6，严格等于 element + 1）及 `hit_effect`（字符串 `Explosion` 或 `None`）。拒绝元素继承 255、空元素和按属性查图的其他命中特效，防止装备主体预载触发 C10013。DSL 使用根头 `buffTargetAs=2`，明确按能力伤害乘区结算；不是默认 InvokeSkill 的技能伤害归属。倍率固定，`max_multiplier` 如给出必须与 multiplier 相同；本模板不声称实现 DSL 觉醒倍率插值。

629 必须通过明确的目标 provides 或 client_profile 选择，并要求 provides 含 `official.kind629.invoke_skill@1` 与 `client.kind424.damage_convert@1`（登记的 patch 20 伤害归属相关方法证据），再检查与 provides 哈希绑定的实际 SWF 在 ability_soul 的 instant_content 中支持 629。缺少证据拒绝。HTTP 使用服务启动时的 `default_provides`；CLI 通过 `--provides` 或 `--client-profile` 传入。它不会把任意机器上的补丁、旧反编译快照或技能表分支当作目标客户端支持。

provides 中还必须有编号 20、状态 `recorded` 的补丁条目，且伤害归属 capability 明确列出补丁 20；仅写 capability 名称不通过。该检查是静态输入证据检查，不代表设备运行通过。

魂珠固定为 123 列，629 的 string_id/action_path 必须位于 c67/c68；要求完整的 `custom_ability_string` 基线，生成其新键和 `battle/action/skill/action/ability_skill/studio_weapon/<code>_pf_damage.action.dsl.amf3.deflate`。文件名冲突或当前布局不符均拒绝。模板、文本和 DSL 随同一草稿重放、快照及交付，不改只读基线。实现参考 `bt_weapon.py` 的原生 183→318 行与诅咒武器 w27/w28 的 CT/触发上限编码，未复制角色 ID 或武器专用常量。

## 8. 上传武器、魂珠及材料图标

`POST /api/studio/weapons/<id>/icon`，JSON 请求，不使用文件选择窗或 multipart：

```json
{"kind":"weapon","png":"<原始 PNG 的 base64>"}
```

`kind=weapon` 必须为 20×20 单帧 PNG，写新的独立逻辑 PNG 并更新 equipment c6。`kind=soul` 必须为 40×40，自动选当前武器 equipment c10 指向的魂珠。`kind=material` 必须为 40×40，另外传 `item_id`，例如 `{"kind":"material","item_id":"10000145","png":"..."}`；该 ID 必须为已有 item 行。材料是共享 item，此草稿中的该 item 图标引用会影响使用它的所有消费者。

魂珠/材料 40×40 像素写入 `item_icon/sprite_sheet` 的空位；同时按最近邻派生独立 20×20 PNG，分别更新 item c4 与 c3。复用 `weapon_awaken.find_slot`，保留边距并要求空位及 1px 外圈原本全透明。不扩画布、不移动旧条目，追加后逐像素比较所有旧区域；无空位直接拒绝。图像名包含像素摘要，同图重复导入复用既有槽，换图追加新槽。旧 PNG、旧 atlas 条目和其他 item 行不会被覆盖。

`png` 是原始 PNG 字节的标准 base64，不带 data URL 前缀；上限 2,000,000 字符。尺寸不符、非 PNG、多帧、无效 base64、关联 item 缺失或旧槽同名不同像素均拒绝。可加 `?preview=true`，只编译候选不写草稿。成功响应沿用武器修改结构，新增 `icons`，含 `kind/logical/size`；魂珠/材料还含 `itemId/thumbnail/atlasSize/preservedEntries`。失败使用现有 400 与 `checks` 合同，不改变已保存草稿。

上传写成 `weapon_icon` 可重放请求，图像随请求保存在本地草稿。所有输入图集、表与新增资源的存在状态都进入快照；构建沿用 `build_draft`，服务端文件不因单纯换图而产生修改。HTTP Origin/Token/Host 守卫沿用现有 server.Handler。

## 9. 一行 JSON CLI

无需启动服务器或拼接 Origin/Token。全局视图参数与其他 draft 命令相同，`--drafts` 指普通草稿根，命令自动进入其 `weapons/` 子目录。`--server-dir` 可写在全局或操作子命令后面。

```powershell
python -m wf.studio.draft --manifest manifest.json --store store131 --zip-dir archives --tip 282 --server-dir server weapon list --q 雷 --limit 100
python -m wf.studio.draft --tip 282 --server-dir server weapon show 5950001
python -m wf.studio.draft --tip 282 --server-dir server weapon clone --from 5100017 --to 5950001 --code duet_example --name 二重奏 --exclusive-character 139988 --soul-template template.json
python -m wf.studio.draft --tip 282 --server-dir server weapon materials 5950001 --request materials.json
python -m wf.studio.draft --tip 282 --server-dir server weapon icon 5950001 --kind weapon --png weapon20.png
python -m wf.studio.draft --tip 282 --server-dir server weapon icon 5950001 --kind soul --png soul40.png
```

`clone/materials/icon --request` 接受对应 HTTP body；clone 的 `--from/--to/--code/--name/--exclusive-character/--soul-template` 和 icon 的 `--kind/--png/--item-id` 可覆盖文件中的同名参数。`--preview` 不落草稿。所有五个子命令支持 `--provides PATH`、`--client-profile NAME`，用于明确目标能力证据。

标准输出始终一行 JSON：成功为 `{"ok":true,"result":...}`，退出码 0；运行期校验失败为 `{"ok":false,"error":"..."}`，退出码 1。`list` 读取当前基线目录，`show` 读取重放后的草稿候选。命令只准备本地草稿；不会发网络请求、连接服务器、提交发布或假装完成设备验证。
# P0 第二轮接口补充

## 当前 provides 对 629 模板的支持

`GET /api/studio/weapons/capabilities` 读取武器编辑器实际使用的 `provides` / `client_profile`，不切换档案、不写草稿。返回 `invoke629`：

```json
{
  "invoke629": {
    "supported": true,
    "capabilities": [
      {"id": "client.kind424.damage_convert@1", "provided": true},
      {"id": "official.kind629.invoke_skill@1", "provided": true}
    ],
    "patch20": {"linked": true, "recorded": true, "supported": true},
    "evidence": {"status": "available", "sha256": "<64 hex>", "clientProfile": null},
    "checks": [{"rule": "weapon.invoke-provides", "status": "满足", "message": "629 模板所需 provides 声明已齐全", "blocking": false}]
  },
  "scope": "provides-declaration",
  "runtime": "未执行",
  "note": "只表示当前 provides 声明；候选生成仍检查实际 SWF 分支和输入哈希，不代表装机实测。"
}
```

`supported` 必须同时满足两个能力 ID、424 声明中的 `patches` 包含整数 `20`，以及顶层 `patches` 中补丁 20 的 `status=recorded`。该判断与模板创建共用函数。声明缺项时 `supported=false`、check 为「问题」且 blocking；未选择、不可读或无效 provides 时 `supported=false`、能力 `provided` 和补丁 `linked/recorded` 为 `null`、证据 `status=unavailable`、check 为「未执行」且 blocking。它只证明声明条件，生成与交付时的真实 SWF 和兼容检查仍需通过。

## 图标尺寸响应

图标导入成功或 preview 的 `icons[]` 中，`size` 固定为两个整数的数组 `[宽, 高]`，表示提交的 PNG 尺寸；`atlasSize` 固定为 `[宽, 高]` 或 `null`，不再省略该键。

| `kind` | `size` | `atlasSize` | 输出含义 |
|---|---|---|---|
| `weapon` | `[20,20]` | `null` | 独立武器 PNG，不写图集 |
| `soul` | `[40,40]` | 当前图集实际尺寸，例如 `[2048,1024]` | 图集中的 40×40 图标；独立回退 PNG 为 20×20 |
| `material` | `[40,40]` | 当前图集实际尺寸，例如 `[2048,1024]` | 同上，另需 `item_id` |

图集尺寸来自实际基线，不能在前端硬编码为示例值。仍禁止扩画布，现有图集条目的坐标和像素继续逐项校验。

## 10. 专属武器全套配置

`POST /api/studio/weapons/<id>/set` 在已有武器或已经克隆的新武器草稿中追加 `weapon_set` 请求。
各项均可省略；省略时不启用、不额外写入相应配置。可先 `/clone`，再 `/set`，最终仍由同一个武器草稿重放、保存和 `build_draft` 交付。
`?preview=true` 运行相同校验并返回最终行，不写草稿或预留 ID。所有写接口沿用 Token、Origin、Host 守卫。

```json
{
  "noSoul": true,
  "awakeningMaterial": "10000311",
  "enhancementCategory": {
    "sourceCategory": "7", "code": "exclusive_weapon", "name": "专属武器·觉醒"
  },
  "enhancement": {
    "maxLevel": 120,
    "stages": [
      {"maxLevel": 68, "costs": []},
      {"maxLevel": 69, "costs": [{"itemId": "10000311", "amount": 1}]},
      {"maxLevel": 70, "costs": [{"itemId": "10000311", "amount": 1}]},
      {"maxLevel": 97, "costs": []},
      {"maxLevel": 98, "costs": [{"itemId": "10000311", "amount": 2}]},
      {"maxLevel": 99, "costs": [{"itemId": "10000311", "amount": 2}]},
      {"maxLevel": 118, "costs": []},
      {"maxLevel": 119, "costs": [{"itemId": "10000311", "amount": 3}]},
      {"maxLevel": 120, "costs": [{"itemId": "10000311", "amount": 3}]}
    ]
  },
  "exchange": {
    "category": {"id": "97"}, "sourceProduct": "990097001",
    "itemId": "10000311", "amount": 3, "count": 1, "stock": 1
  }
}
```

上述 ID 只是已有数据的示例，必须先从目标视图确认存在。实现不绑定示例武器、材料或角色。

| 请求字段 | 类型与行为 |
|---|---|
| `id` | 十进制字符串；HTTP 路径和 CLI 位置参数自动补入，若 body 也提供必须一致 |
| `noSoul` | 布尔值，默认 false；true 禁止生成可领取的魂珠，false 不执行操作，也不撤销之前的 true |
| `awakeningMaterial` | 指定突破替代材料 ID；同时写 CAS `awakening_material_<id>`、服务端 `materialByEquipment` 和本体 c11 对应的 `rarityOverrides` |
| `enhancementCategory` | 类目对象：复用可传 `id` 或已存在的 `code`／`name`；新建需 `sourceCategory`、`code`、`name`，`id` 可省略自动分配 |
| `enhancement.maxLevel` | 整数 1–200；与末阶段等级一致，禁止降低已有强化上限或删掉原有阶段／曲线键 |
| `enhancement.sourceWeapon` | 可选强化母本 ID，默认当前武器；母本必须有强化本体、状态曲线和商店行 |
| `enhancement.stages` | 1–99 项，`maxLevel` 严格递增；每项的 `costs` 必填，允许空数组表示免费区间，否则 1–4 个不重复 `{itemId,amount}`；amount 是正整数 |
| `enhancement.stages[].requireAwakeningLevel` | 可选整数 0–5，默认本体最大突破等级；不得超过本体 c8 |
| `enhancement.products` | 后端写回的分配结果；固定为 `武器ID * 100 + 阶段序号`。请求通常省略，若提供必须与实际分配一致 |
| `exchange.category` | 类目对象，与强化类目相同规则；兑换类目没有独立文字名称列，原生显示采用横幅 |
| `exchange.sourceProduct` | 已有领主币兑换商品母本 ID，必须为 50 列 |
| `exchange.productId` | 可选新商品 ID；检查客户端、服务端映射、所有服务端分类及其他草稿的占用 |
| `exchange.itemId` / `amount` | 价格材料 ID／每次购买所需正整数数量；只写这一种价格，清除母本货币和其他材料 |
| `exchange.count` | 每次兑换得到的武器数量，正整数，默认 1 |
| `exchange.stock` | 每人总限购次数，正整数，无日／月重置；不同于每次兑换的 count |
| `exchange.description` | 可选商品说明，默认“专属武器兑换”；不能含原生 CSV 不支持的分隔符 |

“不出魂珠”使用现有可突破自制武器的结构：equipment c9=false，服务端
`equipment_dissolve.generate_ability_soul=false`，并保持 c10、内部 item、ability_soul 完整。
基础能力本来就是通过 c10 供武器本体读取，装备时强化技能等基础能力也因此仍在本体生效。
不能物理删除这些内部行：客户端在突破／熔炼界面检查 c9 之前会读取它们。
此开关不创建魂珠发放商品，也不会删除玩家已经持有的历史魂珠。已有武器缺服务端熔炼行时拒绝；
本草稿克隆的武器可从自己的克隆母本复制完整熔炼配置后关闭产出，保留其他熔炼返还。

强化采用原生 **per_level**：每行价格乘以该行覆盖的等级数。示例九行对应六个付费节点，
总消耗 12 个材料；不能把六段长区间都写为付费行。每行会清除母本额外货币和材料，
客户端与 `equipment_enhancement_shop.json` 从同一配置生成。官方类目 1–4 有另一套计费语义，
本功能生成 per_level 阶段时拒绝使用这些类目。新增曲线终点延用母本最后一个 HP/ATK 值；
强化能力以母本最大等级作为插值终点的行同步到新上限，不推测新的能力强度或成长数值。

类目按 code／name 查重；已存在则复用，不重写原行。新类目复制所选母本布局和实际存在的横幅，
顺序追加到最后，不调整其他类目序号。兑换新类目会清除母本任务前置。
其他草稿已经预留同名新类目时拒绝重复创建；将该类目合并到来源视图后，其他专武即可按同一 ID 复用。
本功能不生成新横幅美术。所有新增 ID 走 `ids` 规范化／占用查询，版本仍由既有 `versions`／交付参数决定。

材料须同时存在于客户端 item 和服务端 item_ids；图集引用也必须有效。
突破白名单只约束“使用材料替代重复本体”的路径；现有服务器仍允许使用重复本体突破。
配置不会声称从 API 层禁止所有其他突破方式。该能力依赖客户端补丁
`client-patch/equipment-awakening-material`（旧能力 ID `equipment-awakening-material-v1`）和服务端
`equipment_awakening_material.materialByEquipment`。仅添加 CAS、只写白名单或旧客户端忽略配置，都不算支持。

`requires.json` 会列出上述客户端能力和服务端功能；强化、禁出魂珠分别列出
`equipment_enhancement_shop.per_level`、`equipment_dissolve.generate_ability_soul`。
当前旧 WFX 注册表有觉醒材料声明，但新能力目录缺少绑定目标 SWF 的方法哈希；沿用现有 unresolved／unknown
兼容门禁，**开启此项仍可保存与预览，交付兼容检查会阻断，直到补齐可信能力证据**。
不会虚构补丁编号、伪造 provides 或把静态表检查当成服务端已部署。

### 选择项与响应

`GET /api/studio/weapons/set-options`：返回 `version`、`categories.enhancement[]`、
`categories.exchange[]`、`materials[]`、`serverInputAvailable`、`notes` 和 `runtime`。
类目项为 `{id,code,name,order,row,table}`；强化 name 来自 c3，兑换 name 为 c0 的原生代码。
材料项为 `{id,name,icon,serverAvailable}`，名称／图标来自 item c2/c3，未配置服务端时
`serverAvailable=null`。返回当前 item 表中的候选，不在代码中维护“禁忌星铁”等名称或 ID 清单。

POST 成功沿用 `ok/weaponId/subjectKind/allocation/changes/checks/icons/runtime`；有 `weapon_set`
的序列新增 `rows.client[] = {table,path,value}`、`rows.server[] = {target,updates}` 和
`requires = {clientCapabilities,serverFeatures}`。`rows` 是整个候选序列的最终写入值；
client 的 value 可为 CSV 字符串或嵌套状态对象，server updates 为变化的顶层键值／新增列表值。
保存还返回 `change/changeset/status`。自动分配的类目、商品和阶段 ID 存在
`changeset.changes[0].params.requests[].weapon`，重放时再次校验。
强化检查 `weapon.enhancement-cost` 提供 `maxLevel/purchaseMode/materialTotals`；
`weapon.awakening-material` 返回材料 ID、所需能力及 `duplicateEquipmentAllowed=true`。
失败返回 HTTP 400、`ok:false/error/checks`，原草稿不变。`ok=true` 仅表示候选生成或草稿写入成功。

```powershell
python -m wf.studio.draft --view local --server-dir server weapon set-options
python -m wf.studio.draft --view local --server-dir server weapon set 5950001 --request weapon-set.json --preview
python -m wf.studio.draft --view local --server-dir server weapon set 5950001 --request weapon-set.json
```

CLI 支持既有 `--provides`／`--client-profile`，输出一行 JSON。没有新增出包路径，
保存／生成／导出仍用武器草稿现有接口；ZIP、共享表键差异、APK 内置表撞名与兼容检查继续运行。

## 专武全套补充契约

weapon_set 的成功预览与保存都返回 allocation（已补齐 ID 的 weapon spec），含 enhancementCategory.id、exchange.category.id、exchange.productId 和 enhancement.products；预览不占用 ID，保存仍重新检查。GET set-options 增加 products 数组，每项 id/categoryId/name/row/table，供 sourceProduct 选择。

仅设置 enhancementCategory 与修改 enhancement 一样禁止官方类目1..4；检查客户端／服务端阶段归属和集合一致，并同步 per_level 模式与需求。新增强化类目采用10列，清除c2解锁条件和c9结束时间，图片列为c4/c5；新增兑换类目采用13列，保留c2属性、清除c3..c8前置／期限和c11/c12活动限制，检查c9/c10图片。新增商品清除Pickup、campaign与前缀名。

借用强化母本保留目标既有名称、图标、说明和强化能力；无目标强化行时从目标本体回填展示信息。c1/c3/c5/c7阈值钳制到上限；借用曲线可截到上限，但不能删除目标已有等级键。只调整能力等级不会要求外部SWF，交付仍检查能力需求。

觉醒JSON按目标武器子键合并，预览server updates只列递归变更。ID检查同时扫描服务端强化类目、兑换类目映射值与商品内层键。新建类目允许同草稿后续改名；复用类目不记为新定义。noSoul:false单独提交会拒绝；客户端已正确但服务端失配时可以保存镜像修复，纯服务端输出仍须服从标准交付的客户端成员约束，不能声称已出包。
