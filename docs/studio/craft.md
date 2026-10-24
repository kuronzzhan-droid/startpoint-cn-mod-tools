# 编辑台：交稿四件套

外部画师交稿用的四个工具，都在角色页里：前三个在「像素」下，交接单是单独一页。

## 像素 › 批量预检

一次检查一整批逐帧 PNG（文件夹或 zip），按文件名归到动作槽：

- `动作_帧号.png`、`动作-帧号.png`、`动作/帧号.png`、`动作.png`（单帧），例如 `neutral_01.png`、`walk_front/03.png`；
- 带 `_sp` 的是本体 + 特效/召唤物的**合成帧**（`neutral_sp_01.png`、`neutral_01_sp.png`、`neutral_sp/01.png`）：只报出来，不会归进待机这类基础动作；
- 每个动作走「单动作替换」同一套规则（帧框、透明背景、锚点、动作槽、图集预算），停留帧数按原动作总长均分；
- 每个动作可以标「带召唤物」和用途：没标但可见宽度超过原动作 1.6 倍时提示「可能带召唤物」；标了就不再按体型报放大。
- 「写入通过的 N 个动作」只把没有错误的动作逐个写成单动作替换，标记记在改动的 `origin` 里。

接口：`POST /api/drafts/<id>/pixel-precheck`（`{family, files | zip, actions: {动作: {includesCompanion, purpose}}, apply}`）。

## 像素 › 场地比例

关卡 → `field_data` → 地形 `BOUNDS`，按运行时像素画（地形 ×6 = 客户端的 1080×1920 战场；像素小人 ×`frame.scale`）。
默认主线 1-2-1（`1002001`），也可以直接填地形路径。小人和叠上去的特效图都能拖动；「导出定位参考图」是 1080×1920 原尺寸，带 120px 网格和复活位编号。

接口：`GET /api/stage-scale?quest=<id>` 或 `?terrain=battle/terrain/...`（只读）。

## 像素 › 图集重排

MaxRects 重排当前视图的 sprite_sheet（`wf_battle_atlas_repack`：只搬整块区域，不裁边、不旋转、不重采样，每块前留 2px），
在几十个候选宽度 × 两种排序里取面积最小的。给结果之前先过等价校验：

1. atlas 记录除 x/y 外逐条相同；
2. 按记录顺序取出的像素块哈希相同；
3. 每个端点按游戏方式（旋转、fx/fy、未裁剪帧框）从新旧两张图各还原一遍，逐字节比对。

写入草稿是一条整族替换（`pixel_family`，mode=import，来源 `kind: atlas_repack`），生成时和「整族导入」走同一条编译路径。
草稿里已经有这一族的整族替换时拒绝（重排只对当前视图做）。

接口：`GET /api/characters/<id>/atlas-repack?family=`、`GET .../atlas-repack/<family>.png`、`POST /api/drafts/<id>/atlas-repack`。

## 交接单

三栏分开：

1. **作者说明**：标题、作者、这一套是什么、每个动作的用途/是否带召唤物/备注、其它注意事项。存在草稿目录 `sources/handoff/notes.json`，不进 changeset，不影响生成；
2. **草稿里的真实文件**：changeset 里实际存着的文件和逐帧源图（路径、大小、SHA-256），不按说明推断；
3. **还没接入游戏的部分**：要等「生成」才编进游戏文件的部分（各改动的 pending）、未保存的草稿、说明里写了但草稿里没有的动作、说明和导入标记对不上的地方。

「导出 Markdown」可以直接发给画师或作者。接口：`GET /api/drafts/<id>/handoff[?format=md]`、`POST /api/drafts/<id>/handoff-notes`。

这四个功能的点子来自灰的 [StarPoint-Character-Studio](https://github.com/Ku1o/StarPoint-Character-Studio)，代码在本仓库里另写。
