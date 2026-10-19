# BOSS 工坊第二期：地形、商店武器与行为

本页补充 [副本工坊接口](boss.md)。所有操作使用同一 `bossRequest` schema、`BossEditor`、独立 boss 草稿目录与既有交付桥。请求先在内存中重放，预览不保存；保存记录输入摘要，生成时重新重放并检查。输出是本地候选，不执行服务器应用、设备安装或发布。前端页面不属于 M6 交付范围。

## 读取与调用

`GET /api/boss/<quest>/terrain`、`/shops`、`/weapons`、`/behavior`、`/timeline` 返回候选子模型，统一外层为 `questId`、`section`、`data`、`checks`、`runtime`。`<quest>` 仍是 URL 编码的完整选择器。这些接口复用原有 Host 守卫，读取不会建立新草稿。`weapons` 合并关联商店武器与本草稿新克隆武器；普通详情响应也通过 `draftWeapons` 返回尚未上架的新武器。

CLI 使用相同路径：

```powershell
python -m wf.studio.draft --tip 236 --manifest inputs/manifest.json --store inputs/store131/upload --zip-dir inputs/patches --server-dir inputs/server boss hard_multi:1006/1 --section terrain
python -m wf.studio.draft --tip 236 --manifest inputs/manifest.json --store inputs/store131/upload --zip-dir inputs/patches --server-dir inputs/server boss boss_battle:1/81/5 --request work/boss/request.json --preview
```

`--section` 只读取已有副本，不能与 `--request`、`--preview` 或 `new` 混用。修改继续使用 `POST /api/boss/drafts/<quest>`；加 `?preview=true` 只预览。去掉 CLI `--preview` 将请求写入草稿；随后使用 `save <quest> --boss` 或 `POST /api/boss/drafts/<quest>/save` 校验并标记已保存，才能构建。完整字段约束见 `python -m wf.studio.draft schema --def bossRequest`。

## 地形与波次

读模型逐层保留原始 objectgroup、BOUNDS、复活位和命名站位，附 `bindings` 明确 field_data、field、zone 与各层 zone 行的对应关系。坐标保留 Tiled 原值，并提供客户端中心点换算值；9 个复活位另附队伍与成员索引。

| operation | 必需字段 | 行为 |
|---|---|---|
| `terrain_replace` | `terrain` | 选择当前视图已有的地形逻辑路径；层名必须与当前波次相同 |
| `terrain_position` | `layer`、`action`、`name` | `action` 为 `add`、`update`、`delete`；前两者必须提供 `x`、`y`，可提供 `width`、`height` |
| `terrain_add_layer` | `sourceQuest`、`sourceLayer` | 复制现有来源的一层及对应 zone 敌人行；可用 `transitionSourceQuest` 指定已有转场来源 |

示例：

```json
{"operation":"terrain_position","layer":"0","action":"add","name":"p_extra","x":120,"y":80,"width":16,"height":16}
```

派生地形、field_data、zone 和必要 field 行只归当前副本使用，原共享成员保留。已有交付资源占用时按 `_v2`、`_v3` 等序号派生，同草稿重复修改复用当前代，支持上链后再次编辑。换地形时，原有 CUSTOM_POSITION 按前后 BOUNDS 原点偏移保留坐标语义；不会仅因新旧地图都有 `p1` 就采用不同含义的位置。add 缺少任一坐标直接报错；add/update 与换图后保留的站位完整矩形必须位于所属层 BOUNDS 内，允许边界相切。未修改的原生辅助站位不因此新增全局阻断。新增、删除、移动站位均重新检查同屏冲突及 routine/esdl/动作闭包引用。

追加层自动补前层 GATE、TRANSIT 和 field c7/c8，末层去除转场出口。来源若缺可证明的转场对象或动画，操作失败。新敌人遭遇来源必须与目标推荐属性一致；额外转场来源仅提供出口和动画。多波缺 c7/c8、边界或复活位不完整、重复或缺失站位都进入原有阻断门禁。

## 商店与武器

`shops` 展示分类、商品、价格、货币、库存与限购字段，并关联装备、魂珠、强化词条、状态和到 120 级的材料链。服务端同步检查来自显式提供的只读镜像；客户端读模型不把服务器运行状态写成已验证。

| operation | 请求对象 | 行为 |
|---|---|---|
| `shop_add` | `shop.category`、`shop.sourceProduct` | 从已有商品克隆，自动分配 `productId` |
| `shop_edit` | `shop.category`、`shop.productId` | 修改商品名称、说明、现有图标引用、价格、库存或奖励 |
| `shop_delete` | `shop.category`、`shop.productId` | 同步删除客户端商品、category_map 和服务端分类内商品 |
| `weapon_clone` | `weapon.sourceWeapon` | 克隆装备、魂珠、状态、强化词条和材料链，分配装备与强化商品 ID |
| `weapon_materials` | `weapon.id`、`weapon.stages` | 修改指定强化阶段的材料，并同步服务端对应商品 |

价格使用 `[{"itemId":"123","amount":10}]`，奖励使用 `[{"kind":4,"id":"456","amount":1}]`，其中 kind 0 为道具、4 为装备。商品必须属于当前副本关联分类；分类同号行缺失会被拒绝。商品和武器 ID 同时排除客户端表、服务端记录及其它已存在草稿占用。分配结果写回草稿请求，后续重放使用相同 ID。

`shop_add` 和 `shop_edit` 可设置 `availableFrom`、`availableUntil`，格式为 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:MM:SS`，结束时间还可用 `null`。新增默认从 `2000-01-01` 起且不结束，不继承来源过期窗口；客户端 c25/c26 与服务端同步。非法日期或倒置窗口阻断。来源商品相对服务端固定时刻 `2025-08-05` 已过期时，返回非阻断 `boss.shop.availability` 提示。C8004 核对 `item`、`item_icon`、`item_sec`、`scene/general` 四类实际图集成员及对应 PNG；孤立 PNG 不能代替图集成员。商店和武器名称、描述拒绝半角逗号，允许中文逗号。

武器克隆可提供 `name`、`description`、`icon`、`enhancedIcon`、`hpMultiplier`、`attackMultiplier` 和 `abilities`。词条只允许语义字段，不开放原始列号：

```json
{
  "operation": "weapon_clone",
  "weapon": {
    "sourceWeapon": "5930011",
    "name": "工坊验收武器",
    "hpMultiplier": 1.1,
    "abilities": [{
      "table": "ability_soul",
      "row": 0,
      "block": "instant_content",
      "strength": [1000, 2000]
    }]
  }
}
```

例中的 row/block 必须与所选母本的实际词条匹配。支持的表为 `ability_soul`、`equipment_enhancement_ability`，支持的 block 为 `instant_content`、`during_content`；可修改 `kind` 及该 kind 实际使用的 `strength`。列位和可支持 kind 使用 M2.4 客户端 SWF 分支证据，错误列位、未消费字段及不支持的 kind 被拒绝。交付所选 `client_profile` 传入武器编译校验；显式 provides 则检查其绑定 SWF。普通预览采用档案配置中的默认值，亦可构造 `BossEditor(client_profile=...)`。完全缺少客户端证据的 unknown-client 武器编译拒绝。

克隆同步 `equipment_awakening_material.json.materialByEquipment` 中的来源限制，保留其它映射原文；限制文件也进入输入快照和 ID 占用检查。诅咒 `591*` 或 PARADOX `5920001` 缺少限制证据时拒绝，避免回落到普通觉醒材料。请求中的新描述同步本体与强化表 c6。

`icon` 从当前装备表 c6 的既有引用中选择，并连同对应魂珠的真实 c3/c4 引用组合一起复用；非空图集名还要在实际加载图集中存在。`enhancedIcon` 从强化装备表 c4 的既有引用中选择。这些操作不创建新图像或图集格。

`weapon_materials` 示例：

```json
{"operation":"weapon_materials","weapon":{"id":"5930011","stages":[{"productId":"593001101","costs":[{"itemId":"49300","amount":10}]}]}}
```

上述 ID 是结构示例，调用前应从读模型选择真实武器、阶段和货币。服务端 JSON 按键或分类内商品局部合并，未修改商品 value 的原文保留；orderedmap 保留未修改叶子的压缩字节。

强化阶段还可提供 `userCost: {"type":2,"amount":3}`，或用 `null` 清除该阶段的用户货币费用。`userCost` 与道具 `costs` 分开表示；仅允许 type 1/2，type 0 付费星导石在请求和继承克隆阶段均拒绝。type 2 是羁绊证，不表示按阶收费。强化等级从 0 开始，各阶段按截断到 120 的上限差计算购买次数；读模型逐阶段给出起始强化等级、到 120 的购买次数及累计材料。武器克隆本身不自动上架，需要随后用 `shop_add` 把新武器 ID 放入装备奖励。

## 行为与时间线

`behavior` 同时提供 GeneralBoss 的 routine、marker 触发槽和 StandardBoss 的已解码 EnemyDsl 状态机，包含试炼条及免伤相关引用。`timeline` 的时间原点为每个状态进入时，帧率为 60；条件退出、循环和未知时长保留表达式或空区间，不推测一条固定战斗播放顺序。

| operation | 字段 | 范围 |
|---|---|---|
| `behavior_replace` | `enemyCode`、`slot`、`sourceEnemyCode`、`sourceSlot` | 将已有 marker 触发槽换成同 boss 或其它 boss 的现有招式 |
| `behavior_parameters` | `enemyCode` 加所需参数 | 修改已有招式或状态参数 |

参数对应关系：`intervalFrames` 需要 `state`；`trialThreshold` 需要 `state`；`damageMultiplier` 需要 `slot`。`form` 用于选择 StandardBoss 的形态。不能用这些请求从零创建行为。

`behavior_replace` 和 `damageMultiplier` 仅支持 GeneralBoss；换招的目标槽和来源槽都必须已有 marker 触发。StandardBoss 当前支持既有状态的间隔和试炼阈值编辑。

`intervalFrames` 只修改原有 Time / TimeElapsed.Frame 终止状态。`trialThreshold` 支持 GeneralBoss 原有 HitCountCheck、StandardBoss 的常量 HitCountCheck 或 DamageCheck 百分比；SkillChain 阈值限定 4–9，DamageCheck 百分比不超过 100。`damageMultiplier` 是选中 marker 动作闭包内 CreateNormalAttack 当前倍率的乘数，不是绝对赋值；重复提交该操作会继续相乘。

HitCountCheck 次数与 `intervalFrames` 必须为整数；DamageCheck 百分比可用小数，范围为大于 0 且不超过 100。请求 schema 的 `trialThreshold` 使用 number；实际操作按试炼种类约束。客户端 TypePacker 导出的 `TrialDamageCheckParams.percentage` 为 Float，见 `wf/boss/enemy_types.json`。计数小数会被明确拒绝，避免客户端按整数读取后静默截断。

借招在候选中隔离相关敌人和资源引用，检查程序递归或无界循环、特效和预载闭包、命名站位与图集预算。预载缺失或无法证明支持的借招被拒绝。GeneralBoss 的 marker 槽与 StandardBoss 的状态动作是不同结构，读模型会标明槽编辑能力。

GeneralBoss routine 改名会同步复制该 routine 下的全部自身 watch，保留相位跳转及动作预载可达性。GeneralBoss、watch 和递归 General Funnel 动作中的 `CustomPosition` 进入统一站位门禁，借招、删站位与换图均受约束。重复调倍率复用该槽拥有的动作克隆，继续按当前倍率相乘，不累积废弃克隆。Repeat 按嵌套与跨程序调用的整个闭包估算展开量，超过上限、非正次数、非整数次数或递归拒绝。

`GET /api/boss/<URL编码关卡>/timeline-summary` 返回 `{moves:[{name,label,timeline}],note}`，读取当前草稿候选。每个 `timeline` 复用 `build_timeline` 的 `events/lanes/arms/unknown/unmodeled/issues/subprograms` 格式，并附 `stateInterval`（状态 ID、起止帧、触发帧、退出条件及跳转）。已知触发帧以状态进入为零点，事件、隐藏/消除时刻和运动时刻一起平移；未知触发保留动作相对帧及空触发帧。跨波次同一首领分别保留，初始化和 watch 根动作显示为触发时刻未知。子程序维持自身时间原点，不拼接虚构的全战斗顺序。缺失程序及未建模节点保持显式提示。

裸 `battle/action/...` 路径可以通过静态结构与依赖门禁，但这仅是源码推断。新增派生目录下裸路径动作的加载证据标为「待验证」；预览、编译的 `boss.behavior-loading` 及时间线提示不会把本地回读写成真机加载通过。

隔离前会从当前候选检查伤害共享、partner watch、GeneralBossAlive 和 StandardFunnel 对首领代号的反向引用。存在这类固定身份链接的首领会明确拒绝编辑，并返回引用链；扫描所需表或资源缺失也会拒绝。当前阶段不迁移这些机制的整条引用闭包，因此鲨鱼、部分有联动随从的 StandardBoss 等不能直接套用通用隔离编辑。

无损 esdl 文档保留原始 wire 图像及可读字段；用 `decode_esdl` / `encode_esdl` 往返。将文档保存为 JSON 时使用 `ensure_ascii=True`，使旧资源中的非 UTF-8 字节能够无损保留。展示接口对这类字节使用可见转义；展示树不替代用于重新编码的无损文档。

## 验证边界

草稿、预览和编译共用门禁。真实副本的操作验收、反证、未改成员字节核验、完整 pytest、路径扫描及 221/223 历史回归见 [M6 报告](../../M6-REPORT.md)。三人图集估计继续保留 M5.1 的下界与输入完整性状态；静态预算、解包回读和客户端档案匹配都不代表设备或三人房运行已经通过。
