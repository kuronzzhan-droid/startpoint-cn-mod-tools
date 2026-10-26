# 协力角色工坊：召唤数据行与前端对接

召唤工坊把角色或现有 `multiball` 克隆为宿主角色草稿中的 `summon_clone` 改动。写入位置沿用 `work/studio-drafts/<宿主角色ID>/changeset.json`；正式克隆角色的草稿也可承载召唤角色。输入视图、store、补丁链和服务端镜像只读。生成交付继续使用现有 `compile_draft → build_draft → deliver/check/compat` 链路。

本接口产出 `multiball`、`multiball_level`、所需 HP/攻击曲线及可选 `custom_ability_string` 数据行，不修改角色技能 DSL，也不复制外观素材。技能模板任务可读取响应中的 `skillTemplate`，另行添加召唤动作。`runtime` 为“未执行”，表示没有设备或联机实测证据。

## HTTP 与请求守卫

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/studio/summon/templates?q=<关键词>` | 查询可选角色与现有 multiball 母本 |
| GET | `/api/drafts/<cid>/summon` | 读取宿主角色草稿中的全部召唤角色 |
| POST | `/api/drafts/<cid>/summon` | 校验、编译预检并写入一个召唤角色 |
| POST | `/api/drafts/<cid>/summon?preview=true` | 相同预检，返回计划写入的行，不写草稿 |

`cid` 是宿主角色的十进制字符串 ID，与新 `multiball` ID 分开。POST 沿用编辑台的 `Content-Type: application/json`、`X-WF-Studio-Token`、Host、Origin 和 Sec-Fetch-Site 守卫；预览请求也使用同一守卫。`preview=true` 查询参数或 JSON 中 `"preview": true` 任一启用即只预览。查询参数 `preview` 只接受单个小写 `true` 或 `false`，错拼、空值和重复值返回 400，不会误作保存；`q` 也只接受单个值。预览不会创建草稿目录或预留 ID；正式提交时重新校验占用，前端不能把预览得到的 ID 当作锁定分配。

请求定义为 `schemas/studio-draft.schema.json#/$defs/summonCloneRequest`。最小请求：

```json
{"template":{"kind":"character","id":"263002"}}
```

较完整的请求示例（示例技能、动作键须存在于当前视图）：

```json
{
  "template": {"kind": "character", "id": "263002"},
  "id": "1990001",
  "image_prefix": "touyakiren_ceo",
  "element": 5,
  "panel": {"mode": "scaled", "hp_scale": 1.2, "attack_scale": 0.8},
  "pf_type": 4,
  "skill": {"mode": "specified", "key": "example_skill", "level": "1"},
  "assist": true,
  "lifetime": {"seconds": 30},
  "extensions": {
    "flip_pf": {"enabled": true, "min_interval_frames": 0},
    "ball_pf_action": "example_summon_pf"
  },
  "preview": true
}
```

| 字段 | 类型、缺省与语义 |
| --- | --- |
| `template` | 必填对象；`kind` 为 `character` 或 `multiball`，`id` 是规范正整数十进制字符串 |
| `id` | 可选的新 multiball ID 字符串，范围 1–2147483647；省略则通过 `ids.next_id` 查询，正式写入后登记预留 |
| `image_prefix` | 可选外观代码，仅小写字母、数字、下划线；角色母本默认角色 code，球母本默认 c1；写入 multiball c1 |
| `element` | 内部属性整数 0–5：火、水、雷、风、光、暗；省略继承母本。DSL 显式元素码另加 1 |
| `panel` | 可选对象，默认 `{"mode":"source"}`；面板策略详见下节 |
| `pf_type` | 可选整数 0–4，依次为剑士、格斗、射击、辅助、特殊；默认继承母本 c6 |
| `skill` | 可选对象，默认 `{"mode":"inherit"}`；`mode` 为 `inherit` 或 `specified`，后者必填 action_skill 的 `key`；可选正整数字符串 `level` 指定进化档，默认最高数值档 |
| `assist` | 可选布尔值，控制援护布局 c8；角色母本默认 true，球母本省略时继承 |
| `lifetime` | 可选对象，`frames` 与 `seconds` 二选一；帧为 1–2147483647 整数，秒为正有限数，按 60 fps 向上取整后也须在该范围；默认 2147483647 帧 |
| `extensions.flip_pf` | 可选对象，`enabled` 必填布尔值；启用时产生弹板 PF 扩展键，可选 `min_interval_frames` 为 0–2147483647 整数 |
| `extensions.ball_pf_action` | 可选非空字符串，指向已有 `power_flip_action` 键；该行必须提供三档非空动作路径；只引用动作，不克隆动作或资源 |
| `preview` | 可选布尔值，默认 false；true 与查询参数 `preview=true` 等效 |

拒绝未声明字段与错误类型；数字字符串只用于 ID 和技能进化档，不用于属性、PF 类型、面板数值、帧数或布尔开关。主动技能的输入使用 `action_skill` 键，实际 multiball c9 存放该档的技能 DSL 路径，并联动名称、weight 与 autoplay 相关字段。角色母本或 `specified` 技能缺省选择最高数值进化档，使用该档 action_skill c5 的最大 weight 写入球的 c11；weight 是原生技能充能参数，不是施放间隔秒数。已有球的默认继承保留 c9–c19；显式选择 `level` 时要求能唯一解析到母本技能键，存在多个同路径键时应改为 `specified`。

寿命不在 multiball 表里，没有“寿命列”。它只写入草稿参数及 `skillTemplate` 中的召唤动作参数；技能 DSL 接入后才影响实际召唤寿命。

## 面板与列继承

- `source`：角色母本读取嵌套 `character_status`，在其定义域内逐整数等级展开，保留角色曲线原生的向上取整结果；现有球读取 `multiball_level` 指定的原生 HP/攻击曲线和参数，保留其原生取整语义。
- `scaled`：同样使用母本断点，分别乘 `hp_scale`、`attack_scale`；未填倍率为 1，倍率须为有限数，支持范围为 1e-15–2147483647。
- `manual`：必须给出 `levels`，每项为 `{"level":1,"hp":100,"attack":20}`；等级为 1–2147483647 的整数，HP 为至少 1 的有限数，攻击为非负有限数。级别不得重复。最终面板按客户端整数口径向下取整；面板值与缩放后结果不得超过 int32 最大值。

`source` 不接受倍率或手填断点；`scaled` 不接受 `levels`；`manual` 不接受倍率。面板只表达基础曲线，不把玛纳板、觉醒、编队加成或其他能力当作角色 status 的一部分。

数值按客户端双精度计算；输出使用可往返读取的浮点表示，保留小数精度。摘要按原生计算顺序与容差取整：`floor(base × curve × correction + 1e-10 + 1e-10)`。例如非常接近整数的小数可能因这两个原生容差项取到该整数；前端应直接显示后端 `panel` 摘要，不自行套用简单 floor 或四舍五入。

角色母本派生独立的 28 列球定义：身份 c0–c7 取角色对应字段或新球身份；c8 为援护布局；c9–c19 来自选中的 action_skill；c20–c23 为无额外援护能力槽；c24 为缩放 1，c25 为 kind 0，c26/c27 为 false。现有球母本完整复制原行，再修改本接口明确支持的列，其余列保留。响应 `preservedColumns` 是列号（如 `c2`、`c20`）到保留值的对象，前端应显示原值，不推断未知列具有新行为。

曲线和球定义使用新键；共享表按整文件输出，保留其他键及原始行字节。新增平表行按原生压缩格式编码。母本输入摘要记录在 change 参数中，读取/交付时若输入变化则拒绝静默重放。

## 成功响应

母本列表返回以下对象：

```json
{
  "schema": "wf-studio-summon-templates/1",
  "version": "1.4.285",
  "items": [{
    "kind": "character", "id": "263002", "name": "母本名称",
    "imagePrefix": "touyakiren_ceo", "element": 5, "pfType": 4,
    "skill": {"key": "example_skill", "level": "1", "name": "技能名称", "path": "battle/action/skill/example"},
    "panelAvailable": true
  }],
  "total": 1, "count": 1
}
```

`items[].kind/id` 可直接作为请求的 `template`。`q` 用于名称、ID 与代码检索。列表给出显示与选取信息；是否能生成仍以 POST 的完整输入、依赖和占用检查为准。

POST 预览与保存共用以下主要字段：

| 响应字段 | 含义 |
| --- | --- |
| `ok` / `preview` | 请求成功与是否只预览 |
| `characterId` / `multiballId` | 宿主角色 ID 与本次新球 ID，均为字符串 |
| `spec` | 本次请求去掉 preview 并补齐实际分配的 id；其余省略参数继续按本文默认规则解释，不展开成全部默认字段 |
| `allocation` | 写入前的 `ids` 查询结果，含 kind、id、available、owners、viewVersion、serverChecked、reserved；reserved=false 表示查询本身不预留，保存后的召唤预留以 changeset.changes[].params.reservations 为准 |
| `rows` | 待写入行数组：每项有逻辑表路径 `logical` 和键 `key`；平表用 `rows` 二维字符串数组，曲线用 `levels` 展示嵌套断点 |
| `checks` | 现有五态规则数组，使用 `rule/status/message/blocking`；前端按状态和 blocking 展示 |
| `requires` | 从生成数据推导的客户端能力 ID 列表；交付时继续合并到 requires.json |
| `skillTemplate` | 给技能模板使用的召唤动作参数和接入说明，详见下节；不表示 DSL 已修改 |
| `skill` | 本次采用的主动技能摘要，字段为 key、level、name、path；直接继承球路径时 key/level 可为 null |
| `panel` | 面板摘要，含 count、first/last 的 level/hp/attack、rounding、contextLevel、outsideDomain |
| `preservedColumns` | 保留列号到原值的对象 |
| `ownedRows` | 本次新增的自有键，格式为逻辑表路径到键数组 |
| `reservations` | 本次改动的 multiball/string_id 预留声明；仅预览时只是计划 |
| `runtime` | “未执行”，无本次设备运行结论 |
| `change` / `changeset` / `status` | 仅正式保存响应提供：本次 change、整份草稿、草稿保存状态 |

`GET /api/drafts/<cid>/summon` 返回 `schema:"wf-studio-summons/1"`、`version`、`characterId`、`items`、`status`、`runtime`。每个 item 的完整字段是 `changeId`、`characterId`、`multiballId`、`spec`、`rows`、`checks`、`requires`、`skillTemplate`、`skill`、`panel`、`preservedColumns`、`ownedRows`、`reservations`、`runtime`；它没有 POST 专用的 `allocation`、`ok` 或 `preview`。没有召唤改动时 `items` 为空数组。原有保存、撤销和交付接口直接复用宿主草稿；撤销目标为对应 `changeId`，释放该改动的预留。

请求错误返回 HTTP 400：

```json
{
  "ok": false,
  "error": "具体失败原因",
  "characterId": "199000",
  "checks": [{"rule":"summon.inputs","status":"问题","message":"具体失败原因","blocking":true}],
  "runtime": "未执行"
}
```

失败情况包括非法字段/数值、母本或技能键不存在、ID 占用、输入漂移、缺曲线及扩展键引用错误。错误不应呈现为成功预览。鉴权等 HTTP 守卫失败仍使用编辑台既有错误格式。草稿内部 `change.checks` 保持既有 `level/code/message` 格式，与 HTTP 顶层五态 checks 区分。

## 给技能模板的可用参数块

`skillTemplate` 提供 `command`、`multiballId`、`lifetimeFrames`、原生位置参数数组 `parameters`、可插入 Block 的完整 `node`、`inserted:false`、`callbackSubjectIds` 和中文 `instructions`。例如默认常驻寿命的新球 `1990001`：

```json
{
  "command": "CreateSummonsMultiball",
  "multiballId": "1990001",
  "lifetimeFrames": 2147483647,
  "parameters": [
    1,
    1990001,
    [{"min": 2147483647, "max": 2147483647}],
    ["E1", ["None"]],
    ["None"],
    ["None"],
    0,
    false,
    "summon_1990001_activation",
    900,
    901,
    ["Block", []],
    null
  ],
  "inserted": false,
  "callbackSubjectIds": [900, 901]
}
```

完整 `node` 是 `["Command", ["CreateSummonsMultiball", ...parameters]]`，其中省略号表示将上面的数组逐项展开，实际响应直接返回展开后的有效 JSON。技能编辑器应使用实际响应的 `node`，将其插入目标技能 DSL 的 Block。前两个参数为数量与球 ID，第三个为寿命区间；900/901 是回调主体示例 ID，接入已有技能时要重新分配未占用、彼此不同的主体 ID。末尾 null 继承召唤上下文 `slv`，面板使用上下文 `clv`；调用等级须落在面板定义域内，越界会触发客户端原生错误。插入 DSL 后仍需完成其自身编译、预载和设备验证。

## p13 扩展与交付

启用 `flip_pf` 时生成 `wfx_summon_flip_pf_<id>`，值为 `1` 或 `1:<最小间隔帧>`；`enabled:false` 不生成启用键。设置动作时生成 `wfx_ball_pf_action_<id>`，值为目标 PF 动作键。两者都是 `custom_ability_string` 的单行单列值，分别推导 `client.summon.flip_pf@1` 与 `client.ball.pf_action@1`。主动技能的 cutin 预载能力按现有推导器处理。声明支持、降级和缺少证据的区别见 [p13 扩展接口](p13-keys.md)。

`summon_clone.params` 保存 `spec`、`inputs`（逻辑路径到 SHA-256 或不存在时 null）、`ownedRows`（表路径到本次新增键数组）和 `reservations`。草稿根登记 `reservations.multiball`，扩展字符串键也登记为 `string_id`。多项召唤改动分别归属各自目标；共享键差异检查把已登记的新增行算作本草稿自有键。

交付保留 [bundle-check](bundle-keys.md)、[key-diff](key-diff.md) 和 client-extensions 检查。目标 APK 未提供时，内置撞名检查是未核对/跳过，不能显示“通过”。PF 动作不存在、不是单行三列、三档任一路径为空或占位值、带首尾空白/换行，均在编辑预检拒绝；与目标 APK 内置键冲突会在交付阻断。不能以 p13 版本名称代替 APK 或方法证据。

## CLI

全局视图参数置于 `summon` 之前。`--request` 是 UTF-8 JSON 文件路径，可含 BOM；内容与 HTTP body 相同。

```powershell
python -m wf.studio.draft --view test175 summon templates --q 拉芙
python -m wf.studio.draft --view test175 summon 199000
python -m wf.studio.draft --view test175 summon 199000 --request work/summon-request.json --preview
python -m wf.studio.draft --view test175 summon 199000 --request work/summon-request.json
python -m wf.studio.draft schema --def summonCloneRequest
python -m wf.studio.draft validate work/summon-request.json --def summonCloneRequest
```

省略 `--request` 为读取；单独 `--preview` 会报错。`templates` 仅接受查询，不接受 `--request/--preview`；`--q` 仅用于 templates。可用全局或 summon 命令后的 `--server-dir` 补充只读服务端 ID 占用证据。

CLI 输出沿用一行 JSON 包装：成功为 `{"ok":true,"result":<上述响应>}`，业务失败为 `{"ok":false,"error":"原因"}` 并以退出码 1 结束。完成写入后，使用现有 `save <cid>` 和 `build <cid> --from ... --to ... --out work/...`；版本分配和检查继续走现有 versions/build 机制。

## 接线补充与安全边界

模板 GET 接受 `limit`（默认100，上限500）、`offset`（默认0）和可选 `rarity`（1..5）；CLI 对应 --limit/--offset/--rarity。返回 items/total/count/limit/offset，每项增加整数 rarity，默认 ★4 优先，再按星级降序和类型／ID 排序。搜索不会将缺失技能键转成字符串 none。

响应 `skillTemplate` 同时给 lifetimeFrames/durationFrames、maxCount=1、selfOnly=true，并提供可直接交给技能模板的 summon 子对象。两端寿命均为 1..2147483647 帧，默认2147483647约定常驻；超出 AMF3 29位整数范围时用精确 Number 编码。同角色草稿的新召唤物可直接被技能模板引用并联合编译。

预览和编译使用本草稿已有角色／词条／PF 的有效输入；任一母本快照漂移都须重新预览保存。重存只释放当前 summon_clone 自己的预留，不能释放手工顶层预留、其他 change 的文案键或 string_id。新预留记录在 change.params.reservations，不再复制到顶层。旧草稿同时声明相同顶层预留且无法证明来源时会阻断，应显式核对后移除重复声明或重建草稿。

无主动技能的母本不能请求继承技能档位；原生 ATK 修正为0的球可克隆。image_prefix 必须有角色、原生球或像素资源证据；非角色前缀的主动技能球还须有 skill_cutin_0。能力需求分析沿 multiball.c9 追踪主动程序、沿 wfx_ball_pf_action 追踪 PF 三档程序，交付继续核对其能力与资源。
