# 编辑台（studio）：只读浏览 + 草稿替换（M3.2）

日期：2026-10-17。分支 `refactor/m3-studio`。M3.1 只读；M3.2 起可以把立绘、像素、语音替换进**草稿**（`work/studio-drafts/<角色ID>/`，已被 gitignore）。仍然不生成、不导出、不应用、不发布，也不写任何游戏表、store、补丁链或服务器。

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
- BOSS 工坊：占位页，只列计划中的页面。

## 已核对的

- 111183 瓦格纳（1.4.206 视图）：一板显示队长技 6 行、能力 1–3；像素动作 9 个基础 + 2 个特殊，`skill_ready` 中段画面与原图集一致（含光环特效帧、入棺阶段的品红闪帧也是原图集自带）。
- 139985 露迪（加 `--extra-zips-file` 叠到 1.4.222）：显示为「新增 MOD」，四条能力的覆盖文案与数据行描述均出现；像素小人可播放。
- 截图在仓库外 `m3-studio-shots/`。

## 像素渲染口径

- 帧图 = Starling 子纹理：按 `r` 旋转还原、按 `fx/fy/fw/fh` 放回 256×256 未裁剪帧框（复用 `wf_pixelart_vfx.restore_frame`）。
- 帧号语义：图集后缀是「持续到该帧为止」的末帧号（复用 `entry_for_frame` 的口径），时长按 60fps。
- 锚点：frame 的 `x/y` 是帧框左上角相对原点的偏移（官方均为 −128），原点在帧框内 `(−x, −y)`。后端把同一族全部帧裁到共同包围盒后重新打包，锚点相应平移。
- 未做：`flatomo`/parts 特效通道（含镜像层反号问题）不在本版，后端也没有调用 `wf_flatomo_preview_render`（本仓没有这个文件）。

## 占位与缺口

- 只读。保存、生成补丁、导出、应用、发布全部没有；规则条目、能力声明（`wf/caps`）、`requires/provides` 比对都未接入。
- 板位是**推定**：能力 1–3 归一板、4–6 归二板，带觉醒替换/追加标记（ability c3/c4）的行归三板。没有读玛纳板表核对；界面上已说明。三板只看觉醒行，未展示觉醒任务。
- 中文描述来自 `wf_describe` 语义翻译，不是客户端原文；部分写法较生硬（例如「火·MySelf 时」）。
- 「改版官方」只比对表行，不比对资源；官方基线不可用时显示「来源未知」。
- 默认 TIP 只看 kulo active（当前到 1.4.206）。测试服链更新的边（207→222 等）不在 active，需要用 `--extra-zip(s-file)` 手工叠加；没有自动发现。
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
- 预览：浏览器按同一参数实时裁剪并套官方统计蒙版（当前视图「官方原版」角色同名图标 alpha 逐像素中位数，与 `wf.chars.support.masks` 同口径）。保存后由后端用生产代码派生：full_shot（仅上传时）、10 个图标、skill_cutin PNG、**skill_cutin ATF（wf_atf 按原 ATF 的 mip 数重编）**、illustration_setting_sprite_sheet（只重画本槽格子），并跑 `wf_ui_derive_gate.derived_icon_problems`。
- 139985 当前立绘用默认模板重派生，与现有图标肉眼几乎一致（脸锚取自三张定位表）。
- 近似 / 未验证：图标构图（标 ≈）；illustration sheet 用 fit 整图而非官方海报构图；ATF 未上真机；上传立绘的默认脸锚只是统计起点，必须手动拖到眼睛；三张定位表只记目标行。

### 像素（换像素）

- 逐帧 PNG（按文件名排序）或精灵图网格切分；每帧停留帧数与锚点（默认脚底中心 = 逐帧底边中位数）；和原动作同时钟并排播放、锚点对齐。
- 检查：帧尺寸 ≤ 帧框（256²）、必须有透明背景、总时长与原动作不同时提示（生成要平移后续帧号）、可见高度比原动作大 1.6 倍以上提示；图集预算用客户端 MaxRects 移植（`wf_atlas_budget_check.pack`）把其它动作的原区域与新帧一起装箱，估算新 sprite_sheet 尺寸与 layer0 占用，对比官方角色中位 0.17% / 最大 1.09%。
- 草稿只存源帧和参数；重新装箱 sprite_sheet、改写 atlas 和时间轴属于「生成」，列在 `pending`。

### 语音（换语音）

- 列出 character_speech 注册的台词和固定名战斗语音；只能替换已有路径。
- 上传任意 ffmpeg 能读的音频 → 两遍 loudnorm（主页 −14 / 战斗 −12.8 / 技能 −13.1 LUFS）→ 44.1kHz 单声道 96k CBR，再用 `wf_assets.mp3_encode` 做存储态校验（VBR 拒绝）；草稿存标准 MP3，A/B 试听，超过官方同类最长时长提示。ffmpeg 取 PATH 或 `WF_FFMPEG`。

### 本次修改

角色页「本次修改」列出全部草稿改动（缩略图、检查、替换文件表、待生成项），逐项撤销。五个动作：只有「保存」接通；「生成」「导出」显示「待接入 wf deliver（M1 分支）」；「应用」「发布」未接入。状态三栏的保存状态读草稿，检查结果只汇总草稿检查（规则条目仍未执行）。

### 测试与截图

- `tests/test_studio_drafts.py`：守卫（Host/Origin/令牌/类型/大小）、真实 HTTP 往返、schema 自检与正反例、草稿往返（替换、篡改检测、撤销、路径越界）、ffmpeg 转码规格、精灵图切分与锚点、真实视图上的像素往返。
- 截图在仓库外 `m3-studio-shots/m32-*.png`（Edge 无头）。
