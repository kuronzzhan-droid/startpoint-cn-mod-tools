# 技能模板：克隆官方技能并调整参数

技能模板在角色草稿中保存 `skill_template` change。作者选择一个官方 `action_skill` 母本，即可修改伤害系数、元素与伤害归属，按需复制并换色特效族，或在技能开头插入召唤节点。写入继续使用现有角色草稿；交付仍走 `compile_draft → build_draft → deliver/check`。

来源主表、官方基线与 store 均只读。预览只返回候选摘要和检查，不创建草稿文件、不预留键。保存草稿成功与静态交付检查通过均不代表真机实测通过；接口的 `runtime` 为 `未执行`。

## HTTP 与前端对接

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/studio/skill-templates?q=` | 查询可作为母本的官方技能 |
| GET | `/api/studio/skill-templates/<key>` | 读取母本伤害节点与特效族 |
| POST | `/api/drafts/<cid>/skill-template?preview=true` | 干跑同一请求，返回候选摘要和检查 |
| POST | `/api/drafts/<cid>/skill-template` | 将技能模板变更写入角色草稿 |

`cid` 是目标角色的数字字符串 ID；`key` 使用列表返回的 action_skill 键，作为 URL 路径段时须编码。查询参数 `q` 是可选搜索字符串。GET 继续检查 Host；两个 POST，包括干跑，均使用现有 `X-WF-Studio-Token`、Host、Origin、Content-Type 与请求体大小守卫。

POST 也接受 body 中的 `preview: true`。query/body 任意一处指定 true 都执行预览；body 只接受 JSON 布尔值，query 只接受字面值 `true` / `false`。错误类型返回 400，不回退为保存。

### 母本列表

列表响应的 `templates[]` 每项包含：

| 字段 | 含义 |
|---|---|
| `key` | action_skill 母本键 |
| `characters` | 使用这个母本技能的角色 |
| `names` | 母本各档位的技能名称 |
| `tiers` | 母本的技能档位 |
| `damageNodeCount` | 可编辑伤害节点数量 |
| `effectFamilies` | 母本引用的特效族 |
| `cloneable` | 已通过母本 DSL 静态校验；列表中的候选为 true |

顶层另有 `count`、`officialOnly: true`、`provenance: "official-archive"` 和 `unavailable[]`。`unavailable[]` 的每项为 `key/reason`，列出无法解码或输入不完整而跳过的母本。`characters[]` 每项为 `id/code/name/element`，`tiers` 是档位字符串数组，`effectFamilies` 是逻辑目录字符串数组。搜索结果为空时保留数组结构；官方基线不可用时返回 400，前端不应自行回退到未经验证的其他技能来源。

### 母本详情

详情顶层含 `key`、`officialOnly`、`provenance`、`characters`、`contextElement`、`tiers`、`cloneable`、`damageNodeCount`、`effectFamilies` 和 `effects`。`contextElement` 是可唯一确定的母本角色内部元素，无法唯一确定时为 null；用于解析按元素选择的特效。`cloneable` 表示全部档位通过 DSL 静态检查；资源完整性仍由预览复核。`tiers[]` 中每个档位含下列字段：

| 字段 | 含义 |
|---|---|
| `level` | 档位字符串，提交 `nodeCoefficients` 时用作外层键 |
| `name` / `row` | 技能名称及原 action_skill 行 |
| `program` / `logical` | 原程序路径及压缩 DSL 逻辑路径 |
| `inputSha256` | 官方 DSL 输入的 SHA-256 |
| `damageNodes` | 该档位伤害节点；结构见下表 |
| `effectFamilies` / `effectPaths` | 该档位特效族目录及具体引用路径 |
| `cloneable` / `checks` | 该档位是否通过 DSL 静态检查；这里的检查记录为 `level/code/message`，与 POST 的五态检查结构不同 |

`damageNodes[]` 字段：

| 字段 | 含义 |
|---|---|
| `path` | 裸 DSL 树中的 JSON Pointer，逐节点编辑必须原样回传 |
| `constructor` | 伤害构造名：`CreateNormalAttack`、`CreateRatioAttack` 或 `CreateFixedAttack` |
| `coefficientKind` | 系数含义：`attack_multiplier` 攻击力倍率、`hp_ratio` 生命值比例、`fixed_damage` 固定伤害；分别对应上面的三种构造 |
| `coefficient` | 原 SLvValue 系数数组，各项包含 `min/max`，可能含运行时倍率引用字段 |
| `element` | 原内部元素值；继承属性或构造没有独立元素参数时为 null |
| `elementCode` / `elementInherited` | 原 DSL 元素码及是否继承；继承码为 255。`CreateRatioAttack` 与 `CreateFixedAttack` 没有独立元素参数，两者均返回 `elementCode: null`、`elementInherited: false` |
| `attribution` | 母本当前有效归属码；常见值为 0 自动、1 技能、2 能力、3 PF、4 直击 |
| `subject` | 原伤害主体参数 |

顶层 `effects[]` 每项为 `path/family/previewUrl`。只有现有渲染接口可读取且当前视图素材与官方母本完全一致时才给 `previewUrl`，否则为 null；前端须显示不可预览状态，不能改用其他特效图片。非 null URL 使用既有 `/api/studio/effect.png?path=...` 端点。详情不会返回原始 DSL 字节或整棵树。

### 请求字段

请求结构见 `schemas/studio-draft.schema.json` 的 `skillTemplateRequest`。除 `source`、`newKey` 外均为可选字段。

```json
{
  "source": {"key": "official_skill"},
  "newKey": "example_skill",
  "scale": 1.25,
  "element": 2,
  "attribution": 1,
  "recolor": {"hueShift": 90},
  "summon": {"multiballId": "200001", "maxCount": 1, "selfOnly": true}
}
```

上例字段值仅为格式示例。母本技能键须存在于官方基线；新技能键由作者命名并通过占用检查；协力角色 ID 须已存在于所选视图。

| 字段 | 类型与含义 |
|---|---|
| `source` | 对象。使用 `{ "key": "..." }` 按 action_skill 键选择，或 `{ "characterId": "...", "key": "..." }` 按母本角色与可选技能键选择；角色模式使用该官方角色的主技能，若同时传 key 必须一致 |
| `newKey` | 新 action_skill 键，格式为 `[A-Za-z0-9_][A-Za-z0-9_-]{0,127}`；检查已有键与其他草稿 reservations 的占用 |
| `scale` | 非负有限数值，全局伤害倍率缩放系数，省略时为 1；只作用于伤害系数 |
| `nodeCoefficients` | 按档位、JSON Pointer 路径指定伤害系数：`{ "1": { "<节点路径>": 数值或SLvValue数组 } }`；路径直接使用详情返回值。SLvValue 数组形如 `[{ "min": 2.5, "max": 2.5 }]` |
| `element` | 角色内部元素整数 0–5：火、水、雷、风、光、暗；仅改写原生具有独立元素参数的伤害节点，DSL 写入时转换为显式码 `element + 1` |
| `attribution` | 可选伤害归属：`1` 技能伤害，`3` 强化弹射伤害；省略时继承母本 |
| `recolor` | `{ "hueShift": 数值 }` 色相旋转，范围 -360..360；或 `{ "pairs": [{ "from": "#RRGGBB", "to": "#RRGGBB" }] }` 指定颜色对。颜色对不能为空，不能重复 from |
| `summon` | 可选开头召唤块；字段与限制见下文 |
| `preview` | HTTP/CLI 请求适配层的可选布尔开关；任意预览开关为 true 时都不写草稿 |

指定节点的 `nodeCoefficients` 优先于全局 `scale`，没有逐节点覆盖的伤害节点才应用全局系数；缩放保留原 SLvValue 的运行时倍率引用字段。三种伤害构造均可调整各自系数，前端须按 `coefficientKind` 区分攻击力倍率、生命值比例和固定伤害。倍率编辑不调整帧数、判定形状或其它时序参数。属性改写与伤害归属分别映射到 DSL 的元素参数和伤害 `params[9]`，前端应分别展示，不把强化弹射归属当作独立倍率。`element` 只改原生具有独立元素参数的伤害节点；不会给 `CreateRatioAttack` 或 `CreateFixedAttack` 添加元素字段，也不改变角色表属性，不联动能力条件、材料或独立文案。本功能不能代替完整的跨属性角色制作。

引用到的特效族始终完整克隆到目标角色 `code` 目录下；省略 `recolor` 时保留原颜色，仍创建私有族。换色使用仓库既有实现，不跨角色继续共用母本族。

原生系数还可能含 `alv_min/alv_max`、`alv2_min/alv2_max`（直到 alv6）及嵌套 `vlv` 数值项。全局 scale 同时缩放这些数值上下界，保留 `vid/mul` 等运行时引用。逐节点数组仅改写明确提供的、原本存在的上下界，未填写的字段保持；单个数值只适用于单项、单组上下界，复杂 alv/vlv 系数必须用数组表达。提交的节点路径始终取自官方母本详情；插入召唤后，候选摘要中的树路径会顺延，不应拿它覆盖母本路径。

开头召唤 `summon`：

| 字段 | 类型、默认值与限制 |
|---|---|
| `multiballId` | 必填，正整数的数字字符串，最大 2147483647；必须已存在于所选视图的 multiball 表，可手填该已有 ID |
| `maxCount` | 1–99 的整数，默认 1；未达到上限时本次增加一个召唤物 |
| `selfOnly` | 布尔值，默认 true；true 仅计算自身召唤数量 |
| `durationFrames` | 可选正整数帧数，默认 3600；须小于 2 的 28 次方 |
| `effectPrefix` | 可选召唤特效逻辑前缀，必须位于 `battle/effect/`；省略时使用既有官方召唤特效族 |

原生计数目前只支持 `selfOnly: true` 配合 `maxCount: 1`；仅自身且上限大于 1 会明确拒绝。较大上限必须用 `selfOnly: false` 的原生队伍计数。达到上限时保留现有召唤物，不替换、不刷新寿命。召唤所需的特效同样复制到目标角色目录。

当前未实现与其他分支召唤工坊草稿的联合编译，不能直接读取尚未进入所选视图的召唤草稿。此类 ID 须先通过既有交付流程进入来源视图，再用于技能模板。

### 预览与保存响应

预览成功返回下列公共字段；保存成功在这些字段之外增加 `change`、`changeset` 和 `status`：

| 字段 | 含义 |
|---|---|
| `ok` | 本次业务请求是否成功 |
| `preview` | 是否为干跑 |
| `characterId` / `code` | 目标角色 ID 与代码名 |
| `newKey` | 候选新 action_skill 键 |
| `summary` | 候选改动摘要；含 `sourceKey`、`levels`、`damageNodeCount`、`effectFamilies` |
| `checks` | 五态规则数组；每项为 `rule/status/message/blocking`，可附规则明细 |
| `buildable` | 当前候选是否具备继续构建的条件；最终交付仍重新检查 |
| `reservations` | 本次拟登记的新键，例如 `{ "action_skill": ["example_skill"] }`；预览不持久登记 |
| `runtime` | `未执行`；不能显示为真机通过 |
| `change` | 保存生成的 `skill_template` change |
| `changeset` | 保存后的完整角色草稿 |
| `status` | 现有草稿保存状态；写入后继续沿用保存/生成流程 |

`summary` 的完整结构：

- `sourceKey` / `newKey`：母本与新键。
- `levels[]`：每档含 `level`、新 DSL 的 `logical`、修改后的 `damageNodes` 和该档 `summary`。该档摘要包含 `damageNodeCount`、`scale`、`nodeOverrideCount`、`element`、`elementCode`、`attribution`、`summon`、`timingAndGeometryPreserved`、`effectFamilies`；`summon` 为 null 或含完整召唤参数及 `countMode` 的对象。
- `damageNodeCount`：各档伤害节点总数。
- `effectFamilies[]`：每项含 `source`、`target`、`effects`、`changedPixels`、`resources`、`completeDependencies`。`effects` 描述原引用到新引用的映射；`resources[]` 每项含 `root/source/target/sourceSha256/sha256`，记录各 CDN 根的复制或派生资源摘要。
- `files[]`：候选交付成员，每项为 `root/logical/size/sha256`。干跑时这些文件只在内存中生成，响应中的路径与摘要不表示已有磁盘文件。

`checks[].status` 使用 `满足`、`问题`、`待验证`、`不适用`、`未执行`。任何 `blocking: true` 均须呈现为阻断；不能仅凭 HTTP 200 或 `runtime` 文本判断交付完成。详情键不存在时返回 HTTP 404 与 `error`。POST 请求非法或业务检查拒绝时返回 HTTP 400：

```json
{
  "ok": false,
  "error": "拒绝原因",
  "characterId": "100001",
  "subjectKind": "character",
  "checks": [{"rule": "skill-template.inputs", "status": "问题", "message": "拒绝原因", "blocking": true}],
  "runtime": "未执行"
}
```

业务异常附带的逐项检查保留在 `checks` 中。前端可先选择母本、读取详情，再提交 preview；正式保存使用相同业务请求并去掉 preview，后台仍重新读取来源和检查占用。每个角色保存一个 `skill_template` change，再次提交替换该项；允许沿用本项的 `newKey` 反复调参，其他草稿占用的键仍会被拒绝。

## CLI

全局视图参数放在子命令之前。请求文件按 UTF-8 读取，也接受 UTF-8 BOM。

```powershell
python -m wf.studio.draft --view local skill-templates list --q 激光
python -m wf.studio.draft --view local skill-templates detail official_skill
python -m wf.studio.draft --view local skill-template 100001 --request skill-template.json --preview
python -m wf.studio.draft --view local skill-template 100001 --request skill-template.json
python -m wf.studio.draft save 100001
```

`skill-template` 必须提供 `--request`；文件内容与 HTTP body 相同。文件中的 `preview: true` 和命令行 `--preview` 任意一个生效即只预览。命令行不需要 HTTP 会话令牌，在进程内调用同一编辑器。

标准输出为一行 JSON：成功 `{"ok":true,"result":...}`、退出码 0；运行期失败 `{"ok":false,"error":"..."}`、退出码 1。后续交付使用已有 `draft build <cid> --from ... --to ... --out work/...`，继续接受相同基线、版本、provides/APK 与静态门禁参数，详见[编辑台交付说明](README.md)。

## 编译与证据边界

编译重新生成新 action_skill 行、裸 DSL 树与新特效资源；保存时在 `changes[].params.reservations.action_skill` 登记新键，供现有 ID 查询识别。新增平表行压缩保存，共享表整文件投递并保留既有键。构造名、分支体、Array 数值参形状、元素显式码范围、坐标系主体等 DSL 检查在生成前执行，防止静默吞节点和已知 F1009/F1034 错误。

后续交付继续执行 PR #26 的 APK 内置表撞名、共享表键差异、图标透明区及客户端扩展能力检查。未选择 APK、缺少 provides 或没有设备结果时，应保留该门禁实际返回的未知、未执行或阻断状态。模板预览不替代完整交付检查与真机验证。
