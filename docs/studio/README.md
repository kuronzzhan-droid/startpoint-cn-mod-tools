# 编辑台（studio）：草稿编辑与本地交付（M4a）

M3.1 提供只读浏览；M3.2 起可以把立绘、像素、语音替换进**草稿**（`work/studio-drafts/<角色ID>/`，已被 gitignore）。M4a 新增词条草稿 API/CLI，并通过 `draft build` 生成本地交付。输入主表、store、补丁链和服务器目录均只读；应用、发布和前端生成按钮不属于本次后端接口。

## 启动

前提：`profiles/local.json` 已配置 `wf_root`（见 `profiles/example.json`）；Python 只用标准库 + 仓内已有依赖（Pillow）；Node 24。

```powershell
# 1. 构建前端（首次或改了 studio/src 之后）
cd studio
npm install
npm run build
cd ..

# 2. 启动后端（必须在仓库根目录运行）
$env:PYTHONUTF8 = '1'
python -m wf.studio            # 打开 http://127.0.0.1:8790/
```

常用参数：

| 参数 | 作用 |
|---|---|
| `--tip N` | 视图 TIP 小版本号。默认取 kulo `assets/asset-patch/active` 里最新补丁边的目标版本（当前 206） |
| `--extra-zip ZIP` | 在 active 链之后叠加一个补丁 ZIP，可重复，按顺序后者覆盖前者 |
| `--extra-zips-file TXT` | 每行一个 ZIP 路径的清单，可重复；例如万圣角色构建用的 `build/extra_zips.txt` |
| `--chain-manifest JSON` | 补丁链清单（kulo `asset-patch/manifest.json` 格式）。TIP 之后已启用的边按 `archive_integrity` 的文件名、大小、SHA-256 在搜索目录里找 ZIP 并依次叠加 |
| `--zip-dir DIR` | 查找补丁 ZIP 的目录，可重复（最多下探 4 层） |
| `--no-chain` | 不按清单自动叠加 |
| `--port` / `--host` | 默认 `127.0.0.1:8790` |
| `--warm` | 启动时预读角色列表（首次约 1 秒，用于与官方基线比对） |

不带参数启动时，清单和搜索目录读 `profiles/local.json`：`paths.studio_chain_manifest`（相对 `wf_root`）与 `studio_zip_dirs`（列表）；也可用环境变量 `WF_STUDIO_CHAIN_MANIFEST`、`WF_STUDIO_ZIP_DIRS`。没配清单时只叠 active。本机配置示例（不入库）：

```json
{"wf_root": "<资料根>", "paths": {"studio_chain_manifest": "ghmain/assets/asset-patch/manifest.json"},
 "studio_zip_dirs": ["rel1016", "rel219", "rel224", "out"]}
```

这样直接 `python -m wf.studio` 就叠到 1.4.224（34 个 ZIP，与手写清单逐个 SHA-256 一致；同名不同内容的构建会按哈希挑对）。`--extra-zips-file` 仍可用，和清单重复的同名 ZIP 只叠一次。

开发前端：另开终端在 `studio/` 运行 `npm run dev`，Vite 会把 `/api` 代理到 8790。

数据来源：`wf.view.base149.HistoricalView`——store131 + kulo active 中 131→TIP 的补丁边 + 额外 ZIP，全部内存读取。「新增 MOD / 改版官方 / 官方原版」用 kulo `.cdn/cn` 官方归档（`OfficialBaseline`，`write_cache=False`）比对角色、能力、队长技、技能行得出，不比对立绘与像素资源。

## 能用的

- 外壳：一级「编辑内容」「补丁管理」，右上「词条速查」（Ctrl+K）随时打开；顶部显示当前内容与资源版本、只读标记。
- 角色工坊
  - 角色列表：按名字、称号、ID、代码名搜索；按来源（新增 MOD / 改版官方 / 官方原版）和属性筛选。
  - 角色详情：标签页「一板 / 二板 / 三板（觉醒）/ 技能 / 像素小人」。
  - 每条能力：有覆盖文案时先显示玩家文案（`desc_override`），再逐行显示 `wf_describe` 生成的中文描述；「原始字段」折叠，按 `ability_enum_map.json` 标出区块与字段名。
  - 状态按 Codex 状态语言分三栏：保存状态「只读查看·无修改」、检查结果「未执行」、实测情况「未记录」。没有接入的检查一律显示「未执行」，不算通过。
  - 技能：action_skill 的名称、文案、能量，以及技能 DSL 的节点摘要。
- 像素小人（L1 素材级预览）：播放/暂停、逐帧、拖动时间轴、速度 0.25–2×、循环、洋葱皮（前一帧 30%、后一帧 15%）、最近邻缩放 1–8×、锚点十字、三种背景、帧条点选；列出 18 个官方动作槽及本角色有无。
- 词条速查：在当前视图所有能力/队长技数据行（约 7500 行）的中文描述、角色名、词条键中检索，点击跳到对应角色的板。
- 补丁管理：列出 kulo `manifest.json` 登记的补丁与视图实际叠加但清单未登记的 ZIP；详情页显示说明、改动列表、ZIP 成员（哈希路径）。
- 头像：列表和详情头部用角色原生方形头像 `ui/square_0.png`（缺则依次退到 `thumbnail_0`、`square_132_132_0`、`square_round_136_136_0`），懒加载，后端内存缓存。
- 「全套资源」标签：按 立绘 / UI 图标 / 像素 / 技能 cutin / 特效 / 语音 / 其它 分组列出角色资源；每项显示逻辑路径、所在 CDN 根（通用/大图/安卓）、来自 store131 基底还是哪条补丁边、尺寸/大小、与官方 CDN 是否一致、预览（图片缩略图、mp3 内嵌播放器）。语音组顶部是 character_speech 台词表（类型、可见条件、台词、播放）。cutin 组标出 PNG 与 ATF 是否都在（真机读安卓根 ATF）。模板必备或被引用但不存在的项标红「缺失 / 引用但缺失」。
- 深链接：`#/character/<ID>[/<标签>]` 直接打开角色，例如 `#/character/139985/assets`。
- BOSS 工坊（[副本工坊说明](boss.md#编辑台界面)）：总览按 主线领主战 / 官方领主战 / 共同决战 / 五重决战 / 练习木人 分组，可按名字、属性、来源筛选；副本详情分「遭遇 / 奖励与商店 / 调整参数」三页，左列同组难度、右列五态检查；改等级、倍率、属性、BGM、场景先实时预检，阻断项不能写入，C8016「待验证」须显式确认；五档可一起改；「新建共同决战」向导从后端白名单选模板来源并显示分配的 ID；「本次修改」抽屉与角色同一套保存 / 生成 / 导出。五重入口（BothBoss）只读。

## 已核对的

- 111183 瓦格纳（1.4.206 视图）：一板显示队长技 6 行、能力 1–3；像素动作 9 个基础 + 2 个特殊，`skill_ready` 中段画面与原图集一致（含光环特效帧、入棺阶段的品红闪帧也是原图集自带）。
- 139985 露迪（加 `--extra-zips-file` 叠到 1.4.222）：显示为「新增 MOD」，四条能力的覆盖文案与数据行描述均出现；像素小人可播放。
- 截图在仓库外 `m3-studio-shots/`。

## 像素渲染口径

- 帧图 = Starling 子纹理：按 `r` 旋转还原、按 `fx/fy/fw/fh` 放回 256×256 未裁剪帧框（复用 `wf_pixelart_vfx.restore_frame`）。
- 帧号语义：图集后缀是「持续到该帧为止」的末帧号（复用 `entry_for_frame` 的口径），时长按 60fps。
- 锚点：frame 的 `x/y` 是帧框左上角相对原点的偏移（官方均为 −128），原点在帧框内 `(−x, −y)`。后端把同一族全部帧裁到共同包围盒后重新打包，锚点相应平移。
- 未做：`flatomo`/parts 特效通道（含镜像层反号问题）不在本版，后端也没有调用 `wf_flatomo_preview_render`（本仓没有这个文件）。

## 原浏览界面的范围与保留限制

- 浏览接口保持只读；草稿保存见 M3.2，词条后端与交付 CLI 见 M4a。前端的生成、导出、应用、发布按钮尚未接线。
- 板位是**推定**：能力 1–3 归一板、4–6 归二板，带觉醒替换/追加标记（ability c3/c4）的行归三板。没有读玛纳板表核对；界面上已说明。三板只看觉醒行，未展示觉醒任务。
- 中文描述来自 `wf_describe` 语义翻译，不是客户端原文；部分写法较生硬（例如「火·MySelf 时」）。
- 「改版官方」只比对表行，不比对资源；官方基线不可用时显示「来源未知」。
- 默认 TIP 只看配置的 kulo active；可通过 `--chain-manifest` 与 `--zip-dir` 解析额外补丁链。精确交付使用 M4a 的 manifest 视图，版本来自清单而非目录里的最大文件名。
- 像素：同一族所有动作共用一个包围盒，小动作在大光环角色上显得偏小；声音、points/circles 只计数不播放；L2 编排级与 L3 真机级预览未做。
- 词条速查只做子串匹配，未区分块＋编号身份，也没有「为当前效果找参考」的语境筛选。
- 资源清单靠候选路径探测（恢复路径表 + 模板矩阵 + speech 表 + DSL 特效引用），不在这些来源里的文件（例如自制角色另起名的特效目录且未被 DSL 引用）不会出现；「模板可选」项不存在时不列出。
- 列表头像用 `square_0`，是否就是客户端角色列表实际用的那张没有在客户端代码里核对。
- 特效只按 DSL 引用推出 parts/timeline/贴图/atlas 及 `_end` 段；ResolveByElement 按角色属性派生；未解析 flatomo 内部引用的其它贴图。
- 后端单进程、内存缓存不失效；改了 active 目录需重启。
- 测试：`tests/test_studio.py`（路由表；有真实视图时检查角色列表与 111183 像素数据，否则跳过）。

## M3.2「换得了」：草稿替换

### 写入接口与守卫

- 只有 `POST /api/drafts/...` 会写盘，且只写 `work/studio-drafts/<cid>/`（`WF_STUDIO_DRAFTS` 可改根）。
- 每个进程生成随机令牌：注入到页面 `<meta name="wf-studio-token">`，同时写到 `work/studio-drafts/.session.json` 给本机 agent 用；请求头 `X-WF-Studio-Token`。
- `Host` 必须是本机回环 + 本端口（防 DNS rebinding）；浏览器带的 `Origin` 必须同源（`--allow-origin` 可加 Vite 开发地址）；`Sec-Fetch-Site: cross-site` 直接拒绝；只收 `application/json`，上限 96 MB。
- 服务只允许监听回环地址。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/drafts/<cid>` | changeset + 保存状态 + 五个动作的接通情况 |
| GET | `/api/drafts/<cid>/file?path=` | 读草稿内文件 |
| GET | `/api/characters/<cid>/portrait/<0\|1>` | 立绘槽信息、默认裁剪模板、槽尺寸、形状蒙版槽 |
| GET | `/api/studio/masks/<slot>.png` | 官方统计形状蒙版（首次约 10 秒，缓存到 `_cache/`） |
| GET | `/api/characters/<cid>/voice` | 可替换的台词与语音 |
| GET | `/api/studio/schema` | `schemas/studio-draft.schema.json` |
| POST | `/api/drafts/<cid>/portrait/<form>/source` | 上传新立绘（去掉全透明边后存到 `sources/`） |
| POST | `/api/drafts/<cid>/portrait` | `portraitRequest` → 派生全部 UI 图进草稿 |
| POST | `/api/drafts/<cid>/pixel` | `pixelRequest`（`dryRun: true` 只检查） |
| POST | `/api/drafts/<cid>/voice` | `voiceRequest` → 游戏规格 MP3 |
| POST | `/api/drafts/<cid>/changes/<id>/revert` | 撤销一项 |
| POST | `/api/drafts/<cid>/save` | 「保存」：整份 schema 校验 + 逐文件哈希复核 |

同一套操作的命令行：`python -m wf.studio.draft <list|show|schema|validate|portrait-info|portrait|pixel|voice-lines|voice|revert|save>`，输出一行 JSON。请求体和草稿结构都在 `schemas/studio-draft.schema.json`（`portraitRequest` / `pixelRequest` / `voiceRequest` / `change`），每项改动写入前按 schema 校验。

### 草稿格式

`changeset.json`：`revision` 每次增删 +1，`savedRevision` 等于它才算「已保存」。每项 `change` 有 `files`（逻辑路径、CDN 根、草稿文件、SHA-256、存储态 SHA-256、被替换的原文件哈希与来源层、是否近似）、`pending`（生成时还要写的表行/打包产物，草稿不写）和 `checks`。同一目标（同一立绘槽、同一动作、同一句语音）再次保存会替换旧项并清掉旧文件。

### 立绘（换立绘）

- 上传 PNG 或对当前立绘重新裁剪。编辑器把生产派生代码 `wf.chars.support.images.make_icons / make_cutin` 的参数画成框：脸锚（两眼中点，与 `full_shot_image_attribute` 同语义）、基准框高、6 组图标框（锚点 + 倍数）、skill_cutin 框；拖脸锚时全部框跟着走。为此给 `make_icons` 加了可选的 `icon_factors`（不传时行为不变）。
- 预览：浏览器按同一参数实时裁剪并套官方统计蒙版（当前视图「官方原版」角色同名图标 alpha 逐像素中位数，与 `wf.chars.support.masks` 同口径）。保存后由后端用生产代码派生：full_shot（上传或当前立绘，均捕获原素材摘要）、10 个图标、skill_cutin PNG、**skill_cutin ATF（wf_atf 按原 ATF 的 mip 数重编）**、illustration_setting_sprite_sheet（交付编译时合并所改形态的格子），并跑 `wf_ui_derive_gate.derived_icon_problems`。
- 139985 当前立绘用默认模板重派生，与现有图标肉眼几乎一致（脸锚取自三张定位表）。
- 近似 / 未验证：图标构图（标 ≈）；illustration sheet 用 fit 整图而非官方海报构图；ATF 未上真机；上传立绘的默认脸锚只是统计起点，必须手动拖到眼睛；三张定位表只记目标行。

### 像素（换像素）

- 逐帧 PNG（按文件名排序）或精灵图网格切分；每帧停留帧数与锚点（默认脚底中心 = 逐帧底边中位数）；和原动作同时钟并排播放、锚点对齐。
- 检查：帧尺寸 ≤ 帧框（256²）、必须有透明背景、总时长与原动作不同时提示（编译若会影响其它槽区间则拒绝）、可见高度比原动作大 1.6 倍以上提示；图集预算用客户端 MaxRects 移植（`wf_atlas_budget_check.pack`）把其它动作的原区域与新帧一起装箱，估算新 sprite_sheet 尺寸与 layer0 占用，对比官方角色中位 0.17% / 最大 1.09%。
- 草稿只存源帧和参数；重新装箱 sprite_sheet、改写 atlas 和时间轴属于「生成」，列在 `pending`。

### 语音（换语音）

- 列出 character_speech 注册的台词和固定名战斗语音；只能替换已有路径。
- 上传任意 ffmpeg 能读的音频 → 两遍 loudnorm（主页 −14 / 战斗 −12.8 / 技能 −13.1 LUFS）→ 44.1kHz 单声道 96k CBR，再用 `wf_assets.mp3_encode` 做存储态校验（VBR 拒绝）；草稿存标准 MP3，A/B 试听，超过官方同类最长时长提示。ffmpeg 取 PATH 或 `WF_FFMPEG`。

### 本次修改

角色页「本次修改」列出全部草稿改动（缩略图、检查、替换文件表、待生成项、词条操作），逐项撤销。五个按钮中「保存」「生成」「导出」接通（见下文 M4b），「应用」「发布」未接入。状态三栏：保存状态读草稿；检查结果在当前已保存修订生成过交付时显示该次交付的五态计数，否则显示草稿检查并注明交付规则未执行；实测情况固定「未记录」。

### 测试与截图

- `tests/test_studio_drafts.py`：守卫（Host/Origin/令牌/类型/大小）、真实 HTTP 往返、schema 自检与正反例、草稿往返（替换、篡改检测、撤销、路径越界）、ffmpeg 转码规格、精灵图切分与锚点、真实视图上的像素往返。
- 截图在仓库外 `m3-studio-shots/m32-*.png`（Edge 无头）。

## M4a：词条草稿与完整本地交付

所有生成只写当前 checkout 内的输出目录。`build` 要求空目录，拒绝覆盖已有交付、草稿与输出互相包含、版本回退、目标版本已占用，以及草稿 `baseView` 与 `--from` 不符。不会修改来源 store、kulo、测试服或原草稿。输入版本、ZIP 摘要和实际读取的基线成员写入 `baseline.lock.json`。

### 精确视图与交付 CLI

编辑时可以使用清单锁定来源视图；全局参数写在子命令之前：

```powershell
python -m wf.studio.draft --tip 233 --manifest <manifest-233.json> --store <store131/upload> --zip-dir <补丁目录> portrait-info 139985 --form 0
python -m wf.studio.draft --tip 233 --manifest <manifest-233.json> --zip-dir <补丁目录> ability 139985 --request <修改.json>
python -m wf.studio.draft build 139985 --from 1.4.233 --to 1.4.234 --out work/m4a/example --baseline-manifest <manifest-233.json> --baseline-zip-dir <补丁目录> --base-store <store131/upload> --provides <目标客户端-provides.json>
```

`--drafts` 可选择草稿根目录；`--zip-dir` / `--baseline-zip-dir` 和额外 manifest 参数可重复。不指定 ZIP 搜索目录时沿用 profile 的 `view.zip_dirs`。`build` 另支持 `--base-version`、`--view-lock`、`--server-dir`、`--pathlist`；它要求真实 manifest 基线，不提供放弃基线的开关。服务端目录只作为 JSON 输入，不启动服务。

输出结构：

- `inputs/changeset.json`、内容寻址的 `inputs/blobs/`、原草稿快照与编译检查，可再次由 `wf deliver` 消费。
- `delivery/` 包含 ≤5 MiB ZIP、旧/上游两种 manifest、三层归档、`requires.json`、prepush、奖励键对照、前后摘要断言脚本、基线锁和校验和。
- 自动回读 `wf check` 结果到 `delivery/check.json`；提供 `--provides` 时执行能力和方法摘要匹配到 `delivery/compat.json`。缺能力或 prepush 问题会使 CLI 非零退出；缺少 provides 时 `build-report.ok=false`、`compat="未确认"`，CLI 非零退出。
- 只有显式 `--allow-unknown-client` 才允许缺少 provides 的本地交付。此时兼容性仍为「未确认」，例外记录在交付清单 `client_compatibility.allow_unknown_client` 和报告 `allowUnknownClient`；该参数不能跳过已提供客户端的真实缺能力错误。对最终清单重跑 `wf check` 会保留同一门禁。
- `build-report.json` 汇总状态、版本、草稿修订和产物路径。`compat` 是状态字符串，逐项结果在 `compatChecks`；原始编译检查在 `draftChecks` 和 `delivery/draft-checks.json`，像素预算、技能档位引用等「待验证」也进入最终 `checks`。检查通过属于文件与静态能力证据；`deviceValidation` 固定为「未执行」。
- 客户端成员按精确 CDN 根与基线逐字节比较，服务端 changes 按基线摘要比较；相同成员全部剔除，包括定位表、illustration atlas、frame 和文本镜像。纯无变化草稿拒绝生成空交付。

### 媒体编译约束

立绘覆盖指定形态的 full_shot、十个图标、cutin PNG 与安卓根 ATF。全部目标必须在精确根存在，缺槽报错；草稿 ATF 的尺寸、mip 数、完整格式字段须与参考 ATF 一致，并检查声明长度与各 mip 的实际内容。两个形态共用的 illustration sheet 在编译时合并重画，保留原 atlas；不会因保存第二形态而覆盖第一形态的草稿文件。三张定位表的目标叶子和整表摘要在编辑时捕获，编译时先断言再写。旧 M3 草稿若缺少 `tableBefore`，需在同一来源视图重新保存裁剪。

像素按动作槽分组编译，保留官方 atlas 格式、frame.scale 与锚点。被替换槽独占的旧区域清零并优先回收装箱；未替换槽与其它 atlas 条目的坐标和像素保持不变。末槽按时间轴帧号判断，只有末槽可改总时长，且加长不得覆盖序列外旧端点；其它槽可在原总时长内重分配逐帧时长。pixelart 宽高上限为 4094，包含 layer0 margin 后不得超过 4096；special 上限为 4096。pixelart 实际占用按 `(w+2)(h+2)` 计算，超过官方最大 **184260 px**（247×738 加 margin）报「待验证」，超过 **1000000 px** 报「问题」并阻断。三人房共享图集，单角色预算检查不代表编队运行已经验证。

语音仅替换当前角色已存在的路径；生成前逐帧检查 **44.1 kHz 单声道**、标准 MP3 与存储态往返，拒绝 VBR、半转换、混合采样率/声道、错误根和草稿摘要漂移。编码与 ATF 解析错误均映射为 `DraftError`。新增台词不在 M4a 范围。

### 词条 API 与 CLI

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/characters/<cid>/ability` | 当前草稿态的能力、队长技、技能行及所有者 |
| POST | `/api/drafts/<cid>/ability` | `abilityRequest`；只追加操作到草稿，使用现有写入令牌守卫 |
| GET | `/api/drafts/<cid>/ability/preview?table=ability&key=<键>&row=0` | 原始/草稿行、前后中文描述、五态检查；技能可加 `level` |
| GET | `/api/studio/ability/templates?table=ability&block=instant_content&kind=1` | kind 枚举、可选模板和默认行；kind 可省略 |

对应 CLI：`ability <cid> [--request FILE] [--preview]`、`ability-preview <cid> --table ability --key KEY --row 0`、`ability-templates --table ability --block instant_content [--kind N]`。`ability --preview` 校验请求但不写草稿。文本编辑必须通过全局 `--server-dir`，或启动 HTTP 后端时的同名参数，显式指定两份服务端镜像的根目录。

请求结构由 `schema --def abilityRequest` 输出。`operations` 支持 `set_cells`、`insert_row`、`delete_row`、`move_row`、`attach_key`；表名使用 `ability`、`leader_ability`、`action_skill`。能力/队长技行号从 0 起；能力槽为 1–6，队长技/技能挂接使用槽 0。例如：

```json
{
  "operations": [{
    "op": "set_cells", "table": "ability", "key": "目标键",
    "row": 0, "row_count": 1,
    "cells": [{"column": "c29", "old": "原值", "new": "目标值"}]
  }]
}
```

每格必须提供 `old`/`new`；结构操作要断言整行及 `row_count`。插入格的 old 为 null，删除格的 new 为 null；移动格的 old/new 均为原值，并提供 `to_row`。能力列默认用 126 列空间；队长技列操作必须显式给出 `column_space`：`native` 为自身 124 列，`ability` 为映射前的 126 列。模板接口在顶层和每个选项均回显推荐的 `column_space: "native"`，缺少声明或列空间不匹配会报错。首行 c1 引起合击资格变化会提示待验证；共享键列出全部所有者，必须显式 `shared_ok: true`。

`attach_key` 提供 `old_key` 和新 `key`；挂现有键时确认共享归属，建新键时提供带逐格 null 旧值的 `rows`（技能用 `levels`）。已有键不会被无条件覆盖。换队长技键后显式提示同步 `character c18`、`character_text c10` 及两份服务端文本镜像。能力声明中不允许的表或块会报问题；枚举中没有先例的 kind 保留可编辑并标「待验证」。

一个请求内先处理数值与结构操作，最后处理可见文本。技能挂接与后续 c0/c1 文本编辑应拆成两次请求；同档同文本列在一次请求内只允许出现一次，连续 A→B→C 也分次提交。技能文本请求需要同时给出全部已有档位的断言，沿用 `wf text` 的跨档一致性检查。

action_skill 的结构编辑按客户端档位处理：`level` 指源/插入档，`row=0`，`row_count` 为现有档数，移动的 `to_row` 为目标档位零基序号。插删后平移后续档位，保留 1–3 档；不会生成无法同步玩家文案的多行技能叶子。插入/删除一律报「待验证」，列出全部共享所有者的默认等级、玛纳技能强化/进化节点与觉醒来源；缺引用表会显式标出，不读取玩家存档。技能进化档位与数值 SLv 分开说明。新档经 `client_legality` 检查 24 列及客户端实际解析的字段。技能 c0/c1 及覆盖文案走 `wf text` 规则，两份服务端文本镜像仅在字节发生变化时生成于交付 `server/` 下，原文件保持只读。配置中文解释由 `wf_describe` 产生，不会写入玩家文案。

所有 HTTP 请求均先校验回环 Host，包括草稿 GET/HEAD 和会话 HTML；POST 继续要求 Origin、令牌及 JSON 请求体检查。

### 验证

运行 `python -B -m pytest --basetemp=work/m4a/pytest-tmp`。测试缓存和临时媒体文件均限制在本 checkout；真实视图缺失时仅跳过依赖该视图的测试，编程错误仍会失败。M4a 新增媒体编译、词条语义、交付回读和反证测试；真实 139985 与历史 223/221 的验收结果见根目录 `M4a-REPORT.md`。

## M4b：前端词条编辑、生成与导出

### 词条编辑（一板 / 二板 / 三板 / 技能）

- 每个键一组「效果卡」：中文描述（`wf_describe`）+ 已填字段（区块·字段标注，可直接改）；「高级」折叠里是全部 126/124 列（含空列）。一/二板只显示非觉醒行，三板只显示觉醒行（c3/c4 推定），结构操作仍按全键行号。
- 改格、↑/↓（Alt+↑/↓）、✕ 删除、「+ 添加效果」都只进入**未写入**列表，按 `abilityRequest` 生成带旧值/整行断言的操作；底部常驻条每次变动后 350ms 调 `POST /api/drafts/<cid>/ability/check`（`AbilityEditor.preview`，不写盘）试算前后中文描述与五态检查。有「问题」或共享键未确认时「写入草稿」禁用；Ctrl+S 写入，「放弃」清空。
- 模板选择器：区块 + kind 搜索（编号/中文/英文），有先例/待验证筛选；零先例 kind 标「待验证」仍可选，插入前可选位置；键盘 ↑↓ Enter Esc。
- 提示就地显示：首行 c1（合击资格）变化、共享键（列出全部持有者，须勾选确认 → `shared_ok`）、错表/错块与缺字段（`问题` 指名的列即使为空也显示并标红）、技能 c0/c1 走 wf text 面板规则（违规条目逐条展示）。技能文本编辑会对每一档带旧值断言并同步两份服务端镜像，启动时需 `--server-dir`。
- 已写入草稿但与原版不同的行用 `GET .../ability/preview` 显示「原版 / 草稿」描述对照。
- 覆盖文案编辑、技能档位插删、换键见下文 M4c；技能档位「移动」界面未开放。

### 生成 / 导出

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/deliveries/defaults` | 默认来源版本 = 当前视图末端，目标 = +1 |
| POST | `/api/drafts/<cid>/build` | `{from, to, provides?}` → `deliver_bridge.build_draft`，输出 `work/studio-deliveries/<cid>-<from>-to-<to>-<时间>/`；失败写 `studio-build-error.json` 并如实返回 |
| GET | `/api/deliveries?cid=` | 已生成交付列表（ok、修订号、prepush、五态计数） |
| GET | `/api/deliveries/<名>` | ZIP、清单成员、服务端镜像、requires.json、check/compat 结果、文件列表 |
| GET | `/api/deliveries/<名>/file?path=` | 读取交付目录内文件（限目录内） |

生成沿用编辑台视图的补丁链清单与已解析 ZIP 所在目录作为基线（`ManifestView` 按清单重新锁定），只接受已保存草稿；未提供 provides 时兼容检查为「未执行」。应用/发布按钮保持禁用。

### 默认客户端能力清单(`--provides`)

M4a.1 起，没有客户端能力清单的交付会判为「兼容未确认」，不通过。启动编辑台时给一份 `wf apk provides` 的输出，「生成」就会默认带上它：

```powershell
python -m wf apk provides <v34 APK> --output work/studio-provides/v34-x86.json
python -m wf.studio --provides work/studio-provides/v34-x86.json --server-dir <服务端镜像根>
```

页面上仍然可以改成别的 provides 文件；留空时交付不通过。

## M4c：文案、技能档位、换键（前端 + 只读接口）

写入全部沿用 `POST /api/drafts/<cid>/ability`（`abilityRequest`）：数值/结构/`attach_key` 走 `operations`，desc_override、custom_ability_string、队长名 c10 走 `text`（wf text，两份服务端镜像同步，交付语义不变）。新增的只是只读接口：

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/characters/<cid>/text` | 草稿态 wf text 文档：技能每档 c0/c1、desc_override、custom_ability_string 的逐字段规则（面板规范逐条五态 + 作者规则）、原版值、全部持有者；服务端生效文本（p5b 整行覆盖 base）与客户端镜像列 c4–c10 对照；队长名 c10 与 character c18 |
| POST | `/api/drafts/<cid>/text/lint` | `{text: abilityText}` 投影到草稿文档后跑同一套规则，不写盘（前端实时检查用） |
| GET | `/api/studio/ability/keys?table=&q=&cid=` | 按键名、持有角色名/ID、中文描述检索现有键，列出全部持有者；带 cid 时包含草稿里新建的键 |
| GET | `/api/characters/<cid>/ability` | 增加 `slots`（能力 1–6、队长技、技能键、队长名 c18），供 `attach_key` 的 `old_key` 断言 |

- 「文案」页：每个文本框下显示作者规则（不写「生命值100%以下」类恒真条件；desc_override 不写「自身为队长时」；技能描述不重复强化效果；不用「…之核」命名）和面板规范逐条状态（问题/待验证/满足 + 条款原文与覆盖边界）。改过的字段出现「问题」时禁止写入。「自身为队长时」在 wf text 中只对 `_leader/_ls` 与 `_1–_6` 键判定，编辑台对全部 desc_override 额外检查（仅编辑侧门禁，交付检查未改）。
- 共享的覆盖/技能文本须勾选 shared_ok；wf text 只有请求级 `shared_ok`，前端要求每个共享键都确认后才发送。
- 「技能」页「技能档位」：在某档后插入（复制该档全部列）或删除；后端试算返回的 `ability.skill-tier-references`（默认档位、玛纳技能进化/SLv 节点、觉醒来源、缺引用表、未觉醒最高档缺档）逐项列出，勾选「已核对」后才能写入。档位结构与技能文本、换技能键不能放在同一次写入。
- 换键：能力 1–6、队长技、技能卡片右上「换键…」。挂现有键（检索、持有者、共享确认）或复制当前键为新键（逐格 null 旧值断言）。换队长技键时提示同步 character c18 / character_text c10，可在对话框里一并改队长名（走 wf text）。
- 性能：custom 文本持有者用「名称是键的子串或键出现在能力行」做必要条件预筛，再逐个调用原 `custom_keys`，结果与全表扫描相同（`tests/test_studio_m4c_text.py`），`apply_text` 同样改用它。
- 截图在仓库外 `m4c-shots/`（139985）。

## M6a：像素工坊

角色页「像素工坊」标签，四个子页；右上「数据」可切换「当前视图 / 草稿态」（草稿态 = 把草稿里的整族映射与逐动作替换按生成时同一个编译器合成后再拆解）。所有写入只进草稿，生成仍走 `draft build` / 交付桥。

- **拆解**：两族（pixelart / special）每个动作一条时间轴，图块宽度 ∝ 停留帧数；每张图标出端点帧号、停留帧数、dy（可见底边相对原点的下沉，正 = 往下）；被多个端点复用的图集区域标 `R编号`。点图看 fx/fy、可见尺寸、帧框包围盒、图集区域与全部复用位置。另列复用区域、逐像素重复区域（打包器没去重）、无动作引用区域；调色板按「本体 / 描边 / 特效 / 入棺幽灵模板」分组（启发：在待机/走路出现 = 本体，只在入棺/幽灵/复活出现 = 模板，近黑 = 描边），分组可改，记在本机浏览器。坑位检查：走路帧近乎全透明（瞬移式走路）、脚底/横心漂移、明显超大的帧、frame.scale ≠ 6、原点 ≠ (−128,−128)、layer0 预算与填充率、未去重、带 sounds、缺必需动作（special 缺 special_land/special_pose 记为错误）。
- **母本映射**：检索母本角色，左右两边调色板、逐色映射表（可锁分组：本体只映射到本体色、特效只映射到特效色；「自动建议」按同组明度排名；可自定义颜色），预览母本与映射后同步播放（单个动作或全部动作）。保存 = `pixel_family` 改动：母本整族四件按精确 RGB→RGB 改色（只动 alpha>0 像素，alpha 原样），atlas 条目名与 frame.name 的 `character/<母本>/` 前缀换成本角色，timeline 逐字节照搬（区间、锚点、frame.scale、帧时长全保留）。草稿保存四件文件（PNG + `amf3-deflate`），并记录母本四件 SHA-256 与映射表；生成时后端按母本 + 映射表重算，与草稿逐字节（sheet 逐像素）核对，母本变化或草稿被改都拒绝。
- **程序化动作**：从正面 / 背面 / 躺倒三张底图（可点本角色现有帧，或上传 PNG）按官方配方合成 walk_front、walk_back、kachidoki、into_coffin、ghost_raise、ghost_neutral、revive；与现有动作同钟对照播放。帧为 256² 帧框、原点 (128,128)，左 = 128 − w//2，上 = 128 − h + dy，编译后 fx = −(128 − w//2)、fy = −(128 − h + dy)；整套动作按本角色待机帧 dy 中位数对齐地线（`ground`）。总长默认等于本角色该动作的现有总长，官方端点按比例缩放。保存 = 现有 `pixel_action`。
- **画板**：选族与动作槽，把该动作每张图还原成 256² 帧逐帧编辑：铅笔 / 橡皮 / 填充 / 吸管、撤销、洋葱皮（前 30% / 后 15%）、复制帧、删除帧、整帧上下移 1px（改 dy）、改停留帧数；调色板锁定为本角色（草稿态）颜色，可另加颜色并提示。视图默认是本动作可见范围外扩，可切换整帧。保存 = `pixel_action`（锚点为帧框原点）。
- 生成时同一动作里逐像素相同的新帧共用一个图集区域（官方图集同样复用）。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/characters/<cid>/pixel-workshop?state=view\|draft` | 拆解结果 |
| GET | `/api/characters/<cid>/pixel-workshop/cell/<族>/<端点>.png?state=&trim=` | 单张图（默认裁掉透明边） |
| GET | `/api/characters/<cid>/pixel-workshop/suggest?base=<母本>` | 同组按明度排名的映射建议 |
| GET | `/api/characters/<cid>/pixel-workshop/bases` | 程序化动作的默认底图 |
| GET | `/api/drafts/<cid>/pixels`、`/api/drafts/<cid>/pixels/<族>.png` | 草稿态像素（与「像素小人」同格式） |
| POST | `/api/drafts/<cid>/pixel-remap` | `pixelRemapRequest`（`dryRun` 只检查） |
| POST | `/api/drafts/<cid>/pixel-generate` | `pixelGenerateRequest`（`save: true` 才写草稿） |

命令行（输出一行 JSON）：

```powershell
python -m wf.studio.draft pixel-analyze 139985 --brief [--draft] [--suggest-base 111007]
python -m wf.studio.draft pixel-remap 139985 --base 111007 --suggest [--mapping map.json] [--family pixelart] [--dry-run]
python -m wf.studio.draft pixel-generate 139985 --action walk_front [--front pixelart:2 | --front front.png] [--save] [--out-dir 预览目录]
```

近似与未做：调色板分组是启发式；程序化动作的旋转（胜利 12°/−16°/6°）用最近邻、火花位置由 md5 确定，入棺/幽灵/复活的半透明淡入淡出是近似，官方入棺实为升空消散；躺倒缺省用正面顺时针转 90° 代替；画板没有选区/镜像/多层；预览里半透明像素的改色走浏览器 canvas（可能有 1 级舍入），以后端结果为准。未上真机。测试：`tests/test_studio_pixel_workshop.py`。截图在仓库外 `m6a-shots/`。

### 草稿角色（还没有游戏 ID）

「角色工坊」旁新增「草稿角色」：新建时填名字、属性、母本（代码名或 ID，必须有像素族）。草稿放在 `work/studio-drafts/scratch-<slug>/`（gitignore），changeset 多一段 `scratch`（名字、属性、母本、绑定状态），占位代码 `scratch_<slug>`，不写任何表行。草稿角色只承载像素改动。

- 「当前视图」= 母本整族四件改名到占位代码（区间、锚点、frame.scale 来自母本）；像素工坊四页照常可用（母本映射可以用别的角色当母本、程序化动作、画板都写进这份草稿）。
- **导入像素集**：文件夹或 zip，按文件名识别 `sprite_sheet.png / .atlas / pixelart.frame / .timeline`（special 同构）；可带映射表 JSON（`{"base": 母本代码或 ID, "mapping": {"#src": "#dst"}}` 或 `[{from,to}]`，包里名字含 remap/mapping/palette 的 JSON 自动识别）。atlas/frame 前缀改成本草稿代码，存为 `pixel_family`（mode=import，草稿文件即内容）。有映射表时逐端点对照「母本 + 映射表」：一致的是映射，不一致的按动作列为手绘。区间与母本不同、缺必需动作、frame.scale ≠ 6 会提示；端点越界、四件不全、frame.name 不是 `character/<代码>/pixelart/<族>` 直接拒绝。导入对真实角色同样可用。
- **绑定到角色 ID**：目标 ID 必须在当前视图角色表里。全部像素改动改名到该角色代码后写进 `work/studio-drafts/<ID>/`（同族同动作的旧改动被替换）；母本映射类改动按母本 + 映射表用新代码重算并逐字节核对。草稿角色记下 `boundTo`，不能重复绑定。
- **生成**：草稿角色永远不生成交付。`draft build scratch-…` 与界面「生成」都拒绝并说明：未绑定时提示先绑定，已绑定时提示对绑定的角色 build。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/scratch` | 草稿角色列表 |
| POST | `/api/drafts/scratch` | 新建（`scratchCreateRequest`；写接口一律在 `/api/drafts/` 下） |
| GET | `/api/scratch/<sid>` | 草稿角色信息 |
| GET | `/api/characters/<sid>/pixels`、`…/pixels/<族>.png` | 母本改名后的「当前视图」 |
| POST | `/api/drafts/<cid 或 sid>/pixel-import` | `pixelImportRequest`（`dryRun` 只检查） |
| POST | `/api/drafts/<sid>/bind` | `scratchBindRequest`（`dryRun` 只预览） |
| POST | `/api/drafts/<sid>/build` | 一律拒绝（说明原因） |

像素工坊各接口、草稿读写（读取 / 保存 / 撤销 / 帧保存）都接受 `scratch-<slug>`。命令行：

```powershell
python -m wf.studio.draft scratch-new --name 水杰拉德 --element 水 --base black_wolf_knight_wt23 --slug gerald-water
python -m wf.studio.draft pixel-import scratch-gerald-water --dir <离线像素文件夹> [--remap remap.json] [--dry-run]
python -m wf.studio.draft pixel-analyze scratch-gerald-water --brief --draft
python -m wf.studio.draft scratch-bind scratch-gerald-water --cid <角色ID> [--dry-run]
python -m wf.studio.draft scratch-list | scratch-show <sid>
```

测试：`tests/test_studio_scratch.py`。

## L2：编排级动作预览（技能 / 强化弹射 / 629）

入口：角色页「技能 › 动作预览」；「像素 › 强化弹射预览」是同一个播放器，默认选中强化弹射；BOSS 工坊副本页多一个「出招预览」。只读，不写草稿。

后端 `wf/studio/timeline.py` 把一棵 ActionDsl 树按客户端求值顺序排成 60 帧/秒的事件表（按帧排队处理，`HideEffect` / `RemoveEvent` / `EraseHitArea` 只影响当时已有的东西）：

- 特效（ShowEffect）：路径（含 ResolveByElement 按角色属性派生）、挂载主体、坐标系、偏移、旋转、缩放（DSL 写了就用 DSL，没写用 parts 的 `s`）、图层、寿命。寿命按特效 timeline 推出播放头：`PlayOnlyFirstSequence` 播完第一段；`UntilTargetTerminates` 跟挂载的判定区/参考点同寿；终止时有 `end` 段就跳去播完，没有就当帧删除。特效 timeline 里的音效按播放头落到「声音」轨道。
- 判定区（CreateHitArea 26 参）：形状（圆/矩形/扇形；3600×3600 标「全屏惯用写法」）、对齐、阵型（NWay / Line 按客户端公式展开）、寿命、期望命中数与最小间隔（`lifetime/(N−0.5)`）、每目标上限、伤害归属（根头部 buffTargetAs，判定区 params[23] 覆盖；0=按来源自动：技能/629→技能、PF→强化弹射；101–133 标「转换」）。MoveHitArea 按客户端速度公式画移动。
- 动作：停球、移动球、隐藏角色、震屏、抑制强化弹射、通知 PF 结束；状态：赋予/移除状态、治疗、技能量、Fever 等。
- 等待/循环：Wait n 帧后执行；Repeat(interval, count) 当帧起每 interval 帧一次，最多展开 12 次，其余注明。
- 子程序：多球 / 目标攻击 / 龙卷风参数里的 DSL 路径解析成子时间轴（最多 2 层，循环引用只报不展开），可在播放器里打开。
- 只标注不模拟：命中（命中块在示意时刻展开一次：跟球走的判定区取寿命中点，其余取创建帧）、目标选取（绑定 1 个代表）、分支（全部分支都画，可逐条关掉）、碰撞事件（命中分支 +1 帧，超时分支在窗口末尾）。
- 不丢节点：不在 112 Command / 6 Event 构造表里的名字列为「未知节点」（注明客户端会静默解成 Trace/Wait），合法但没有画面模型的命令进「其它」轨道并计数；同时报主体不在作用域（C16103）、CD 挂在球/角色/敌人上（U_4f5401）、裸 Block 根（F1009）、形状越界。

`wf/studio/effect_render.py` 烘焙 flatomo parts：展开根组每帧的绘制指令（矩阵、alpha、混合模式），把用到的贴图去旋转重新打包。浏览器按「容器（位置·旋转·缩放）× 图层矩阵」画，贴图放在 `(-fx, -fy)`——图层原点是帧框左上角，镜像层跟着矩阵翻转（旧桌面渲染器的锚点 bug 在这里不存在）。颜色变换和 MovieClip 段未应用。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/characters/<cid>/programs` | 技能各档、切换后技能、原生 PF（射击/剑士/辅助模板在 APK 内则标「无法预览」）、722/419 覆盖各档（forLevels=4 标「读第 3 槽，推定」）、629 能力技 |
| GET | `/api/studio/timeline?path=&kind=skill\|pf\|ability_skill&cid=` | 事件表（lanes / events / arms / unknown / unmodeled / issues / subprograms） |
| GET | `/api/studio/effect?path=`、`/api/studio/effect.png?path=` | 烘焙后的特效与贴图 |

战场按 1080×1920 逻辑坐标：-1 场地中心 (540, 960)、-2 左上角 (0, 0)、球/自身默认 (540, 1380)、敌人 (540, 620)，球和敌人可拖动，球方向可调（EF 坐标系跟它走）。场地边界是估计值；小人按所选动作循环（DSL 不控制技能期间的小人动作）。

BOSS「出招预览」请求 `GET /api/boss/<关卡>/timeline-summary`，返回 `{ "moves": [{ "name", "label"?, "timeline": <与 /api/studio/timeline 相同结构> }], "note"? }`。后端从当前草稿逐招调用 `build_timeline`，附 `stateInterval` 和 `timeOrigin`；已知触发帧换算为状态相对帧，条件触发保持未知。同一首领在不同波次分别展示，初始化/watch 根动作保留未知触发提示。裸路径动作加载仍标「待验证」。旧后端接口不存在时显示占位说明。

测试：`tests/test_studio_timeline.py`（金标准事件表、伤害归属、未知节点、子程序与循环引用、循环上限与分支、作用域/坐标系检查、HideEffect 与碰撞分支、烘焙锚点；有真实视图时跑 111183 全部程序）。截图在仓库外 `l2-shots/`。
