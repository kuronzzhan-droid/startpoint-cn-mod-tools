# 强化弹射动作工坊：克隆官方三档

PF 工坊将当前视图或目标 APK 中的 `power_flip_action` 三档动作克隆为新键，写入角色草稿的 `pf_action_clone` 改动。作者选择属性名、统一或逐档缩放系数，并可将特效引用替换为已有私有特效族。生成继续使用既有 `compile_draft → build_draft → wf deliver` 流程。

HTTP POST 沿用编辑台的 Host、Origin、Sec-Fetch-Site、`X-WF-Studio-Token` 与 JSON 请求守卫。CLI 在进程内调用相同业务函数。功能只制作本地草稿与本地交付；响应中的 `runtime: "未执行"` 表示尚未做设备战斗验证。

## 母本、参数和不变量

母本合并两种来源：当前视图 `master/skill/power_flip_action.orderedmap` 中的 CDN 键，以及本机 `client_apks` 配置所选目标 APK 的内置表键。标准 `knight`、`fighter`、`ranged`、`supporter` 等可能只在 APK 中存在，界面必须按接口返回的可用项展示。缺 APK 时仅能选择 CDN 母本，并明确显示内置表检查未执行；不能将这种情况显示为内置表查重通过。

新键必须匹配 `[a-z][a-z0-9_]{0,79}`，与母本键不同。写入时检查当前视图、目标 APK 内置表和草稿预留；撞名直接拒绝，不覆盖原键，也不自动改名。保存后 `reservations.power_flip_action` 登记该键，交付的 key-diff 将其计为本草稿自有键。

| 请求字段 | 类型与语义 |
| --- | --- |
| `key` | 必填，新 `power_flip_action` 键，例如 `workshop_dark_pf` |
| `source` | 必填，母本键，例如 `special`；从列表选择，不传本机路径 |
| `element` | 必填，`火` / `水` / `雷` / `风` / `光` / `暗` |
| `scale` | 必填，正数表示三档统一缩放；恰好三个正数依次对应 Lv1、Lv2、Lv3 |
| `effects` | 可选，旧特效族逻辑目录到目标私有族逻辑目录的对象映射 |
| `dryRun` | 可选布尔值，默认 false；true 只预览，不写草稿或预留键 |

属性按内部编号 `火=0、水=1、雷=2、风=3、光=4、暗=5` 转成显式 DSL 元素码 `1..6`。暗的显式元素码 6 仅用于 DSL，不是可玩角色表的 element 值。界面使用中文属性名，不要求作者输入元素码。

倍率在母本的命中项系数上逐项相乘，保留各档原来的分段和相对比例。官方动作的时间、循环、抑制释放、结束通知以及 PF Lv3 判定标记均保留。列表里的名义倍率是静态系数摘要；实际命中数仍受动作分段、碰撞与战斗条件影响，不能把摘要当作实战总伤害。

`effects` 的键是母本引用的 `battle/effect/...` 族目录，值须位于 `battle/effect/skill_unique/...`。目标族必须已存在并具备可用资源；此字段只更换引用，不生成素材，不覆盖共享特效。省略时沿用原特效。界面应使用母本详情返回的族名作为映射键，并展示预载依赖与缺失资源检查。

请求体的准确约束见 `schemas/studio-draft.schema.json` 中 `pfActionCloneRequest`；不接受额外字段、APK 文件路径、任意 DSL 或直接写表行。

## 前端对接：HTTP

### 1. 母本列表

`GET /api/studio/pf-actions?q=spec&clientProfile=test-v34`

`q` 是可选的搜索字符串；`clientProfile` 是可选目标客户端档案名，省略使用编辑台默认档案。所有查询参数最多出现一次，未知参数返回 400。浏览器不能通过此接口指定任意 APK 路径。

成功返回：

```json
{
  "items": [{
    "key": "special", "source": "cdn", "type": "special", "selectable": true,
    "levels": [{"level": 1, "nominalMultiplier": 6},
               {"level": 2, "nominalMultiplier": 11},
               {"level": 3, "nominalMultiplier": 21}]
  }],
  "warnings": [],
  "bundledAvailable": true
}
```

示例倍率仅演示数据形状。`items[].source` 是 `cdn` 或 `bundled`；`type` 是识别出的标准类型或 `custom`。`q` 对键名做不区分大小写的包含匹配。`selectable:false` 表示行冲突、缺 DSL 或不能正确解析，条目带 `error` 且 `levels:[]`；应显示原因并禁用选择。`nominalMultiplier:null` 表示含动态项、分支或无法静态求和，不等于 0。`bundledAvailable` 只表示有可读的目标 APK 输入，不表示每个标准类型都存在。

### 2. 三档详情

`GET /api/studio/pf-actions/special?clientProfile=test-v34`

路径使用 URL 编码后的母本键。仅接受可选 `clientProfile` 查询参数；不存在返回 404 和 `error` 字符串。前端必须先读取详情，再显示各档命中项、系数、属性与特效族，不能按 PF 类型猜测固定命中次数。

成功响应字段：

| 字段 | 内容 |
| --- | --- |
| `key/source/type/selectable` | 与列表条目相同 |
| `warnings` | 来源限制等提醒字符串数组 |
| `levels` | Lv1、Lv2、Lv3 顺序的三个详情对象 |
| `levels[].level/path` | 档位编号和母本 DSL 逻辑路径 |
| `levels[].hitCount` | `CreateNormalAttack` 命中项数量；不是实战累计命中次数 |
| `levels[].hitAreaCount` | `CreateHitArea` 判定区节点数量 |
| `levels[].coefficients` | `[{index, elementCode, terms:[{min,max,...}]}]`，完整保留倍率项的其他字段 |
| `levels[].elements` | 命中项使用的原始 DSL 元素码数组 |
| `levels[].effectFamilies` | 直接特效与按属性解析的特效族路径数组 |
| `levels[].markers` | 各判定区原始判定标记数组，包括 PF Lv3 相关标记 |
| `levels[].nominalMultiplier/nominalNote` | 名义倍率数字或 null，以及解释该统计口径的文字 |

详情只读取母本，草稿候选的三档结果从克隆预览响应读取。不可选或内容冲突的母本返回 400；不要用空白详情掩盖解析失败。

### 3. 克隆预览与写入

`POST /api/drafts/123456/pf-action?preview=true&clientProfile=test-v34`

```json
{
  "key": "workshop_dark_pf",
  "source": "special",
  "element": "暗",
  "scale": [1.2, 1.4, 1.6]
}
```

`preview=true` 或请求体 `dryRun:true` 都表示干跑。查询值只接受字面量 `true` / `false`；正式写入省略 preview 或设为 false，并移除 `dryRun:true`。预览不创建草稿改动、不预留新键，正式提交会重新核对占用与输入，因此应处理预览后出现的占用错误。

每次成功写入新增一个 `pf_action_clone`，同一角色草稿可以包含多个不同的新 PF 键。已有键不可通过再次克隆覆盖；需要改变已有候选时，先通过既有撤销接口撤销对应改动，再重新创建。保存按钮沿用 `POST /api/drafts/<cid>/save`，生成按钮沿用角色草稿交付接口。

预览与正式写入共同返回：

| 字段 | 内容 |
| --- | --- |
| `ok/preview` | 成功标记与是否干跑 |
| `characterId/key/source` | 所属角色、产出新键、母本键 |
| `sourceKind` | 母本来源 `cdn` 或 `bundled` |
| `element/elementCode` | 属性名与转换后的显式 DSL 元素码 |
| `scale` | 规范化为 Lv1/Lv2/Lv3 的三个缩放系数 |
| `levels` | 三档候选摘要，结构同详情；`path` 指向新动作路径 |
| `dependencies` | 所需资源及预载依赖，每项包含 `kind/root/logical/required/status/references`，已读取资源另含 `sha256/size` |
| `tables` | 共享表写入规划：`[{logical, addedKeys:[新键]}]` |
| `files` | 产物规划：`[{root,logical,size,sha256}]`，不含素材原始字节或本机路径 |
| `checks` | HTTP 五态检查对象数组 `[{rule,status,message,blocking}]` |
| `warnings` | 非阻断的来源或支持范围提醒 |
| `buildable/runtime` | 本地候选是否具备生成条件；设备实测固定为 `未执行` |

`dependencies` 是需要随调用场景预载的输入清单，不能据此推断目标客户端已经加载了资源。`status="existing"` 表示已读到依赖，含 `sha256/size`；`status="compiled_reference"` 是本次生成的私有 DSL 子程序引用，没有来源文件摘要，其产物摘要在 `files` 中。`required` 表示是否必需；缺少必需资源会直接返回 400，当前不会在成功响应中列一个假装可用的缺失项。可选的 Android ATF 只有存在时才进入清单。

预载检查覆盖显式 DSL 引用、特效 parts/timeline/PNG/atlas、parts 到 atlas 的条目关系以及 timeline 声音。`ResolveByElement 255` 原样跟随执行者属性，按内部元素 0..6 检查全部七色；它不会因为攻击改成暗属性而自动固定为暗色。客户端隐式命中特效、flatomo 嵌套 MovieClip 和运行时动态资源仍需冷缓存设备验收。

正式写入还返回 `change`、`changeset` 和 `status`。`change.kind="pf_action_clone"`、`target={"key":"新键"}`；`params.spec` 是去掉 `dryRun` 的请求，`params.inputs` 保存母本与资源摘要，`params.reservations.power_flip_action` 保存新键。草稿 `files/pending` 为空，实际产物在编译时派生。`changeset` 是完整角色草稿，`status` 沿用已有保存状态对象。预览没有这些已写入状态字段。

输入非法或占用冲突返回 HTTP 400：

```json
{
  "ok": false,
  "error": "PF 键已占用",
  "characterId": "123456",
  "checks": [{"rule": "pf.inputs", "status": "问题", "message": "PF 键已占用", "blocking": true}],
  "runtime": "未执行"
}
```

`checks[].status` 使用编辑台五态：`满足`、`问题`、`待验证`、`不适用`、`未执行`；依据 `blocking` 阻止后续动作。鉴权失败仍由统一守卫返回 403。失败不修改已有草稿。

草稿内部 `change.checks` 与 CLI 顶层 `checks` 保持原生 `level/code/message` 格式；HTTP 仅对响应顶层转换为五态，并添加 `pf.runtime: 未执行`。不要把 `change.checks` 直接绑定到要求五态字段的组件。

### 4. 草稿内 PF 键与召唤工坊

`GET /api/drafts/123456/pf-actions`

该接口只读本角色草稿，供召唤工坊选择 `wfx_ball_pf_action_<球>` 的值；不接受查询参数。应保存所选 PF 键，不使用显示文字或母本键替代。草稿键存在仅说明有本地制作记录，不能显示为已投递或设备已验证。撤销 PF 改动后重新刷新候选列表，避免继续引用已撤销键。

响应为 `{"characterId":"123456","items":[...]}`。没有草稿或没有 PF 改动时 `items:[]`。每项字段如下：

| 字段 | 内容 |
| --- | --- |
| `key` | 新 PF 键 |
| `source` | 母本键 |
| `element` | 克隆请求的中文属性名 |
| `changeId` | 所属改动 ID，可用于通用撤销接口 |
| `reference` | 给 `wfx_ball_pf_action_<球>` 引用的准确值，当前与 `key` 相同 |
| `state` | 固定 `draft`，表示未作为当前视图基线中的键核对 |

召唤工坊使用这些引用时必须同时编译所属角色草稿中的 PF 改动；只复制字符串而遗漏 PF 行和 DSL 不构成完整交付。本接口不修改球配置或其他工坊草稿。

## CLI

命令与 HTTP 使用同一请求定义，输出沿用草稿 CLI 的一行 JSON：成功 `{"ok":true,"result":...}`，失败 `{"ok":false,"error":...}` 并返回非零退出码。

```powershell
python -m wf.studio.draft pf-action list --q special
python -m wf.studio.draft pf-action show special --client-profile test-v34
python -m wf.studio.draft pf-action clone 123456 --key workshop_dark_pf --source special --element 暗 --scale 1.2 1.4 1.6 --preview
python -m wf.studio.draft pf-action clone 123456 --request work/pf-request.json
python -m wf.studio.draft pf-action keys 123456
python -m wf.studio.draft save 123456
```

`list/show/clone` 支持 `--client-profile` 与可重复 `--apk`；显式 `--apk` 覆盖所选档案的本机 `client_apks`。`clone --request` 使用 UTF-8 JSON，可同时提供 `--key/--source/--element/--scale` 覆盖对应字段；`--effects` 读取 UTF-8 JSON 映射文件。`--scale` 只能给一个或三个值。`--preview` 与 HTTP 干跑一致。

草稿输入快照锁定目标 APK 的 SHA-256，草稿中不保存 APK 本机绝对路径。生成交付时应使用制作时相同的 `clientProfile` / `client_apks` 配置；若制作使用显式 `--apk`，生成也传相同文件，例如：

```powershell
python -m wf.studio.draft pf-action clone 123456 --request work/pf-request.json --apk work/inputs/target.apk
python -m wf.studio.draft build 123456 --from 1.4.100 --to 1.4.101 --out work/studio-deliveries/pf-101 --apk work/inputs/target.apk --allow-unknown-client
```

版本号仅演示格式，实际来源和目标版本沿用现有版本查询与分配。示例的 `--allow-unknown-client` 是显式允许缺少 provides 的本地交付，兼容性仍标未确认，不代表实际客户端验收通过。`keys` 只读草稿目录，不加载来源视图。

## 生成与验收边界

草稿仅保存请求、输入摘要和新键预留，编译时重放母本。共享 `power_flip_action` 表完整投递并只增加新行；新行按既有平表格式压缩。DSL 与必要资源引用随现有交付链处理，官方生命周期节点和 PF Lv3 标记不会被参数编辑删除。

交付继续运行 bundle-check 和 key-diff。缺 APK 时 bundle-check 为 skipped / 未执行，不能冒充通过；输入变化或目标撞名会阻断，必须根据新基线重新制作。来源、草稿保存、交付检查和设备实测是独立状态。最终战斗表现、特效播放和 p13 球引用仍需要实际目标客户端验证。
