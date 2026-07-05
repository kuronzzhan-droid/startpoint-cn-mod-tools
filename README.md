# WF 网页修改器 (wf-mod-tools)

自架 **World Flipper 私服**（[startpoint-cn](https://github.com/DontBeAlarmed/startpoint-cn) 模拟器）的本地数据修改器：一个浏览器界面，点鼠标就能改角色词条 / 技能 / 数值 / 立绘语音，并一键发布让客户端拉取更新。**纯 Python 标准库，无任何 pip 依赖。**

> **No game assets. No game data. No official-service bypass.**
> This repository ships **zero** game content — no client binaries, art, audio, or data packages. It is a local editor for data you legally own, used with a **self-hosted offline** [startpoint-cn](https://github.com/DontBeAlarmed/startpoint-cn) private server for preservation and study. Do **not** use it against official online services or for any commercial purpose.

> ⚠️ 面向自架私服的单机自娱 / 数据保存 / 学习。本仓库**不含任何游戏数据、美术、音频、客户端**——你得自备自己私服的数据包。请勿用于官方在线服务。

首次使用请按 [CHECKLIST.md](CHECKLIST.md) 逐项检查（路径配置 → 启动自检 → 金丝雀发布）。

---

## 能做什么

浏览器打开后，左边选角色/武器，上面切页签改：

| 页签 | 功能 |
|---|---|
| **词条编辑** | 逐字段改词条（基础行/觉醒行分区显示）、单条主位限制开关、删行、从别的角色复制词条行并**自动适配**（属性/文本/觉醒门槛） |
| **角色资料** | 名字/称号/技能名描述/稀有度/元素/定位/声优（① 层）；底部有**单角色一键快照/还原**（数据+资产全打包） |
| **角色资产** | 立绘/觉醒立绘/技能 cut-in/图标/像素图/**语音（ally·battle·home 三分类，带台词文本）**的预览 + 上传替换（带尺寸/格式校验） |
| **基础数值** | HP/ATK 按等级断点改 + 觉醒加成 |
| **技能·倍率** | 技能名称/**游戏内效果描述**/技能能量直接改；技能级别移植/删除、整技能替换；**「效果参数」= ActionDsl 数值原地补丁**（判定范围/帧/强度）；数值倍率批量缩放 |
| **武器·魂珠** | 全部 436 件装备（含主线魂珠），强化词条 + 同键魂珠效果一页编辑，均可增删改 |
| **词条移植** | A→B 整角色 / 行级 / 队长技→词条槽 / 队长技→队长技整段 |
| **词条速查** | 关键字搜全部四表的**中文效果**，看哪些角色共用词条 / 哪些是专属 |
| **新建角色** | 克隆模板成全新 ID（实验；写 16 张按角色索引的表）+ 删除角色回滚 |
| **配方 / 改动日志 / 备份** | 批量配方、每次改动自动记录 + 一键回溯、备份还原 |

每个词条/技能都显示**中文效果描述**（逆向布局 + 枚举直译生成的语义等价文本，不是游戏原文——原文由客户端运行时动态拼，离线复刻不了）。

---

## 环境要求

- **Python 3.10+**（用到 `str | None` 语法）。无需 pip install。
- 一个**已经能跑起来的 startpoint-cn 私服**（本工具只改数据，不含服务端）。
- 你私服用的**数据包**（手机端 `production/upload` 目录）+ 服务端 `assets/cdndata`。
- （可选）MuMu 12 模拟器 + adb —— 只有「adb 直推」这个备用功能要用，正常发布走 CDN 不需要。

---

## 快速开始

### 1. 配置路径（二选一）

**方式 A：环境变量**（改 `wf-gui.bat` 里注释掉的几行，最省事）
```bat
set WF_TARGET_STORE=D:\你的路径\WorldFlipper\dummy\download\production\upload
set WF_CDNDATA=D:\你的服务端\assets\cdndata
set WF_CDN_DIR=D:\你的服务端\.cdn\cn
```

**方式 B：profiles.json**（复制模板）
```bash
cp profiles.example.json profiles.json
# 编辑 profiles.json,把 store / cdndata 改成你的路径(建议写绝对路径)
```

| 变量 / 字段 | 指向 | 说明 |
|---|---|---|
| `WF_TARGET_STORE` / `store` | `.../production/upload` | 手机端数据包目录（② 层：词条/数值/技能/立绘等） |
| `WF_CDNDATA` / `cdndata` | 服务端 `assets/cdndata` | ① 层：character.json / character_text.json（名字/描述） |
| `WF_CDN_DIR` | 服务端 `.cdn/cn` | 发布目标目录（发布器把增量包丢这里，服务端动态扫描） |
| `WF_VOICE_DUMP` | 你的语音 dump 目录 | 可选，见下文「语音」 |
| `WF_GUI_PORT` | 8765 | 网页端口 |

### 2. 启动

```bash
python wf_gui.py        # 或双击 wf-gui.bat
```
自动开浏览器到 http://127.0.0.1:8765 。关掉黑窗口 = 关服务。

### 3. 铁律工作流

**改数据 → 发布 → 客户端生效**，三步缺一不可：

1. 网页里改：每步先点 **「预览」**（只看不写），确认没错再点 **「应用/保存」**（才真正写入，自动备份）。
2. 点右上角 **「发布并重启游戏」**（或命令行 `python wf_publish.py --tables <表>`）。
3. 重启游戏客户端，自动拉增量包生效。

---

## 两层数据架构（决定改哪、怎么生效）—— **必读**

| 层 | 在哪 | 改后怎么生效 |
|---|---|---|
| **① 服务端层** | `assets/cdndata/*.json` | **重启服务端**，客户端 `/load` 拉取。不走 CDN |
| **② 客户端层** | 手机包 `production/upload/<xx>/<hash>` | **必须发布**打增量包到 CDN，客户端重启下载 |

战斗数值/词条/HP/ATK/技能/立绘全在 ② 层；名字/描述/稀有度显示在 ① 层。

---

## 我踩过的坑（血泪，务必看）

### 改了没生效？按顺序排查
1. **数据真改了吗**：不是看 dry-run 预览，是改完读回目标表核对值。
2. **发布了吗**：`.cdn/cn/archive-common-diff/` 有没有新 `pinball-*.zip`。
3. **客户端触发更新了吗**：看服务端日志有没有 `[CDN] get_path`。
4. **游戏真重启了吗**：用正确包名 force-stop（不是 `air.com.leiting.wf`，是 `com.leiting.wf`）。

### 最容易犯的错

- **② 层直接 adb push 到 sdcard 不生效**！客户端只认服务端 CDN 下发的版本。改 ② 层一律走「发布」。adb 直推只是备用手段。
- **改了没点「保存」就发布 → 包里没有改动**。输入框里橙色的数字是"已改未保存"，必须先点保存写进表，再发布。（现已加未保存守卫拦截，但记住这个逻辑。）
- **词条枚举列不可靠**：schema 下标有偏移，**改数值列只信数值本身对面板**，语义查 `docs/词条条件代码全表.md`，别盲信列名。
- **跨属性移植词条会崩客户端（U0000）**：给别的角色加词条效果行，**源与目标属性要一致**；跨属性时客户端生成描述拿到坏串会崩。用「自动适配」功能会自动把属性换成目标的。
- **移植"共鸣型"效果不要去掉共鸣前置**：去前置后客户端生成描述报错崩。保留前置、只改元素列。
- **列序陷阱**：`character_status` 内层是 `hp,atk`；`character_awake_status` 是 `atk,hp`（相反！）。五表列图差头部长度：ability 与武器同列号、leader = -2、soul = -3。
- **新键静默丢失（已修，但引以为戒）**：底层 `set_text_rows` 早期只更新已有键、悄悄丢新键，导致克隆角色时 ② 层没写进去、① 层写了 → 服务端通告了客户端造不出的角色 → **下载完资产崩溃**。现已修 + 加写入后校验。
- **新增角色是大工程**：一个新 character_id 要写 **16 张按角色索引的表**（角色/词条×6/队长技/文本/数值/觉醒/语音/技能预览/站位/立绘定位/立绘属性/玛纳板/玛纳节点/开板条件/技能升级/抽卡音效）。少一张，客户端在对应界面就崩。「新建角色」页已覆盖这 16 张，但**客户端对全新 ID 的最终容错仍需游戏内金丝雀验证**。发放走官方邮件/admin 直接发（新角色不在任何卡池是正常态，不影响）。

---

## 语音（可选）

语音清单来自你自备的 datamine 目录（每个角色一个文件夹，内含 `ally/ battle/ home/` 三类 `.mp3` + `voiceLines.json` 台词）。设 `WF_VOICE_DUMP` 指向它，角色资产页就会列出全部语音带台词、可预览可替换。不设则跳过语音清单，其它功能不受影响。本仓库**不含任何语音文件**。

---

## 资产格式（替换时的要求）

- **PNG**：标准 PNG。sprite sheet / 图标合集**必须与原图同尺寸同布局**（配套 atlas 按坐标切图）；立绘/cut-in 建议同尺寸，可勾「强制」绕过（游戏按原 pivot 摆放，尺寸差会偏移）。工具自动处理存储态的魔数混淆。
- **MP3**：CBR / Layer3（VBR 不支持）。工具自动处理帧头混淆。
- 存储三根：`upload`（通用）/ `medium_upload`（大图立绘）/ `android_upload`（平台）。发布器按 pending 前缀自动分包到对应 CDN diff 目录。

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `wf_gui.py` + `wf_gui.html` | 网页修改器前后端（HTTP 服务 + 单页界面） |
| `wf_mod_tool.py` | 核心引擎：orderedmap 读写 / 嵌套表 / AMF3 schema / 配方 |
| `wf_describe.py` | 行级中文效果描述器（读 `ability_enum_map.json` + `词条条件代码全表.md`） |
| `wf_assets.py` | 角色资产编解码（PNG 魔数 / MP3 帧头混淆）+ 三根定位 + 清单 |
| `wf_dsl.py` | 技能 ActionDsl 数值编辑（AMF3 偏移解析 + U29 等长原地补丁） |
| `wf_publish.py` | CDN 增量发布器 |
| `ability_enum_map.json` / `词条条件代码全表.md` | 逆向出的列布局 + 全枚举中文（描述器依赖） |
| `docs/` | API 契约、字段手册、角色改动规律、资产/新角色方案、逆向指南 |

HTTP API 契约见 [docs/API.md](docs/API.md)，方便二次开发或并入服务端后台。

---

## 免责声明

见 [LICENSE](LICENSE)。工具仅供自架私服的个人使用；不含任何游戏版权内容；使用者自备合法数据并自负其责。
