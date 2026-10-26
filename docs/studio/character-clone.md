# 从母本克隆新 ID 角色

克隆写入标准 `work/studio-drafts/<新 ID>/changeset.json`，基线表、store、ZIP 与服务端镜像只读。新角色通过已有 `build`、`check`、`compat` 生成本地交付；生成不代表发布或真机通过。

## CLI

全局视图参数仍置于子命令之前。每次命令输出一行 JSON。

```powershell
python -m wf.studio.draft --manifest manifest.json --store store131 --zip-dir archives --tip 1.4.285 --server-dir server character clone --from 151006 --to 139988 --code new_character
python -m wf.studio.draft --manifest manifest.json --store store131 --zip-dir archives --tip 1.4.285 scratch-promote scratch-new-character --to 139988 --code new_character
```

`character clone` 还接受 `--skill copy|reuse`、`--element 0..5`、`--name 显示名`、`--preview`。默认 `copy` 创建独立的 `action_skill` 键，技能 DSL 路径继续复用母本；`reuse` 保留原技能键。两种策略都会为母本已有的队长与能力槽创建独立键，原有空槽保持为空。

元素参数仅接受整数 0–5，并且必须等于母本。跨属性所需的技能 DSL 元素偏移、能力条件、音效与材料联动尚未完成，因此明确阻断，不能只改角色显示属性。`rarity` 请求字段明确拒绝（即使值与母本相同），星级只能继承母本；CLI 不提供 `--rarity`。

`scratch-promote` 的母本必须已有正式角色 ID。省略 `--code` 时使用 scratch 占位代码去掉 `scratch_` 前缀。升级先克隆角色，再复用 `scratch.bind` 的像素四件重命名、逐动作迁移与断言；空 scratch 也可升级。原 scratch 保留，记录 `boundTo`，不能重复升级。步骤失败回滚新角色目录并恢复 scratch 元数据。已有 ID 的像素绑定仍用 `scratch-bind`。

## HTTP

HTTP 写操作使用编辑台既有 Origin / Token 守卫。CLI 在进程内调用相同业务函数。

`POST /api/studio/characters/clone`：

```json
{"from":"151006","to":"139988","code":"new_character","skill":"copy","name":"新角色"}
```

`POST /api/studio/characters/scratch-new-character/promote`：

```json
{"to":"139988","code":"new_character"}
```

请求属性以 `schemas/studio-draft.schema.json` 的 `characterCloneRequest` 为准。`from`、`to` 是字符串 ID，`code` 使用既有角色代码校验。普通成功响应包含 `characterId`、`code`、`changeset`、`status`、`tables`、`assets`、`checks`、`buildable`、`runtime`。`ok=true` 表示草稿写入成功；资产未齐时仍可保存待完善的草稿，此时 `buildable=false`，交付阶段会阻断。`runtime` 固定为“未执行”。

`POST /api/studio/characters/clone?preview=true` 使用相同请求体、Origin / Token 守卫与前置检查，返回 `preview:true`、`characterId`、`code`、`tables`、`serverTables`、37 项 `assets`、`checks`、`buildable`、`runtime`；不创建草稿目录，不写任何文件，也不预留 ID。`tables[]` 是本次将写入草稿的客户端表，包含 `logical`、`root`（`common`）、`addedKeys`（新增外层键数组）、`size`（字节数）、`sha256`。`serverTables[]` 是后续交付的五张服务端表规划，每项含 `target`、`addedKeys`、`baselineVerified`；配置了 `server_dir` 时，在内存中完成派生/键合并检查，并返回 `beforeSha256`、合并后 `sha256` 与 `size`。没有 `server_dir` 时，目标以相对于 assets 的名称给出、`baselineVerified:false`，响应含阻断的 `character.server_inputs` 检查且 `buildable:false`；仍可保存普通草稿，交付前补齐基线。预览之后提交仍重新检查占用和输入。CLI 的 `--preview` 同样不落盘。

HTTP 顶层 `checks[]` 与武器接口一致，字段为 `rule/status/message/blocking`，`status` 使用五态枚举：`满足`、`问题`、`待验证`、`不适用`、`未执行`。输入非法、ID 占用、跨属性、`rarity`、缺表或服务端镜像不完整等失败返回 **HTTP 400**，含 `ok:false`、`error`、`characterId`、`subjectKind:"character"`、阻断的 `character.inputs` 检查及 `runtime`。预览发现待替换资产时返回 200、`buildable:false`，相应资产检查为 `问题` 且 `blocking:true`。草稿内部 `changeset.changes[].checks` 保持既有 `level/code/message` 存储格式。

新 ID 草稿可以由 `/api/drafts` 发现，并沿用 `/api/characters/<cid>` 以及现有像素、资产、头像读取接口查看候选数据；角色总名册仍表示基线。读取按单个草稿叠层解析，不修改全局视图。

## 克隆内容与检查

- 必需表：character、character_status、character_text、mana_board、mana_node、character_image、full_shot_image_attribute、trimmed_image、character_speech、skill_preview_character；按技能策略新增 action_skill 键。母本非空的队长与能力槽还必须有对应 leader_ability / ability 原行。
- 母本有行时同步 character_gacha_sound、character_awake_status、upskill、mana_board2_open_condition、character_stance_detail。保留无关角色与表行原始字节。
- 角色身份 c27 使用新 ID。客户端 c17 是队长键，非空时改为新 ID；c19–c24 非空槽分别改为 `新 ID + 槽号 1–6`，复制对应能力键的完整压缩行（含多条 CSV 记录），检查新键冲突；既有工具将 c17 命名 `character_id` 属于历史别名，不作为修改其他表归属的依据。母本能力效果及共用文本引用保持原语义。
- 玛纳节点使用 `新 ID * 2` 加原三位后缀，节点键、节点行、板位置与逗号分隔前置引用同时重映射；母本编号不合约、残留旧节点、目标节点或预留段冲突均拒绝。二板开放时间复用现有 `open_condition_row`：晚于兼容时钟 `2025-08-05` 的新角色日期钳制为 `2015-03-01 12:00:00`，母本原行不变。
- character_speech 必须是五列，主页行（kind=0）必须同时覆盖觉醒前可见（constraint 0/2）与觉醒后可见（1/2），其他 kind 的行不能代替主页行，避免 2265。c3 支持多行字幕；c4 是单个语音路径，含 CR/LF 时拒绝，不能拆成多个 MP3。带角色路径的语音引用改为新代码；可读的固定战斗语音及注册语音一起克隆。交付再次检查主页字幕两态与 c4 单路径。
- ★4+ 检查 special 四件与 `special_land`、`special_pose`，保留母本真实帧范围与 `sequence.kind`，不把 187/188 等通用帧界强套到母本。
- 使用 `wf_character_requirements.char_asset_requirements` 的固定 37 项资产矩阵。每项提供 `logical/source/root/status/label`；状态为 `reuse`（复用母本）、`pending`（待替换）、`derived`（已派生）、`not_applicable`（不适用）。★1–★3 的 special 四件标为不适用，不复制且不阻断，仍返回全部 37 项；★4+ 四件必须齐备并具备有效获取动作。剧情横幅不计入 37 项。
- 来源表和资产保存 SHA-256，编译复核母本、目标旧值和草稿文件，输入漂移必须重建。ID 检查共用当前视图、服务端镜像与全部草稿的预留登记查询。

立绘换图继续调用既有上传与裁剪接口。新 ID 的 `DraftOps` 按该草稿叠层解析资源；两态保存后，既有派生器输出 30 项：26 个立绘/图标/ATF、共享立绘图集以及三张定位表。共享 atlas 沿用母本，蒙版与 ETC1 编码仍由既有实现负责。像素、立绘、语音媒体改动可随克隆一起编译。克隆草稿暂不接受追加 `ability_edit` 的交付，避免在未同步新角色文本镜像时产生不完整结果。旧草稿若仍共享母本能力键，或已跨属性、跨星级修改，交付拒绝并要求重建。

服务端生成读取显式 `--server-dir`（服务端仓根含 assets，或直接 assets 目录），**五表都必须存在**：character.json、cdndata/character.json、cdndata/character_text.json、mana_node.json、mana_board.json。按客户端结果派生新增角色条目，使用文本切片按键合并，保留所有原有键值的原始字节（包括数字/转义/空白形式）。所有五表均进入共享键守卫；缺少完整基线或丢失旧角色键时阻断，目标新 ID 已存在立即阻断。没有服务端输入目录时允许制作草稿，生成交付会要求补齐。

## 验证范围

合成测试包含节点及前置引用、原行保留、两种技能策略、37 项清单、两态字幕、★4+ 获取动作、服务端五表、预留冲突、scratch 有/无像素升级、立绘 30 项派生，以及真实 `build_draft → build_delivery → prepush/check/compat` 链路。缺客户端 provides 的测试显式使用 `--allow-unknown-client`，兼容性保持“未确认”。以上为本地静态与产物验证，不包含联网、设备运行、联机或发布。

资产读取接口 /api/characters/<cid>/assets 对克隆草稿额外返回 cloneAssets（37 项清单）；该字段根据当前草稿的立绘/像素等改动动态更新为复用母本、待替换或已派生，低星不使用的 special 四件保持不适用。
