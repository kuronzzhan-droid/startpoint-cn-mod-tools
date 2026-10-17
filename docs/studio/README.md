# 编辑台（studio）第一版：只读浏览

日期：2026-10-17。分支 `refactor/m3-studio`。本版只读：不保存、不生成、不导出、不应用、不发布，也不写任何游戏表。

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
