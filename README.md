# WF-CN Mod Tools · 世界弹射物语(国服)数据修改工具链

面向 [startpoint-cn](https://github.com/DontBeAlarmed/startpoint-cn) 私服的离线数据修改工具:
可视化 / 命令行修改角色词条、基础数值(HP/ATK)、觉醒加成、能力魂、队长技、技能能量、
角色资料,并经服务端 CDN 增量下发到客户端生效。

## ⚠️ 免责声明

- 本工具仅用于**学习、研究、单机 / 私服环境**下对**你自己拥有的**游戏资源进行修改。
- 本工具仓库**不包含、不分发任何游戏本体资产**(数据包、APK、美术、语音等版权内容归游戏运营方所有)。
  CDN 直解只读取使用者自己部署的 startpoint-cn 服务端 CDN;使用者需自备合法获得的游戏资源。
- 修改联网正式服数据、用于作弊或商业用途均可能违反游戏服务条款,由使用者自行承担后果。
- 逆向所得的字段语义 / 解密方式仅供技术交流;上游生态(wfax / wdfp-extractor)已公开同类逻辑。

## 环境

- Python ≥ 3.10；图像与历史配方依赖见 `requirements.txt`，测试依赖见 `requirements-dev.txt`
- 已部署的 startpoint-cn 服务端(首选仓内已有 `.cdn/cn`;用于物化数据和下发改动)
- 或一份合法的手机端游戏数据包(`WorldFlipper/dummy/download/production/upload`)
- 可选:MuMu 12 模拟器 + adb(用于直接同步 / 重启游戏)

## M0 独立工具仓入口

本仓现在采用独立根目录布局。公共视图、APK 补丁和交付检查分别位于
`wf/view`、`wf/apk`、`wf/deliver`；现有通用 `wf_*.py` 导入入口继续保留。
日期、角色专项脚本及旧备份在 `archive/legacy`，不作为活动兼容层或测试入口。
来源取舍、真实交付重建和验证边界见 [M0-REPORT.md](docs/reports/M0-REPORT.md)。

复制 `profiles/example.json` 为忽略的 `profiles/local.json`，填写本机资料根或各输入路径。
环境变量 `WF_ROOT`、`WF_STORE`、`WF_KULO`、`WF_RUNTIMES` 优先于该文件；
`WF_PATHS_PROFILE` 可指定另一份路径配置。旧 `WF_PROFILE=cn` 仍用于游戏版本档案，
不会被误当作路径文件。解析路径不会创建或修改输入目录。

从本仓根运行 `python -m pytest` 和 `python scripts/check_no_hardcoded_paths.py`。
历史重建入口与只读输入要求见 [recipes/README.md](recipes/README.md)；默认产物在
忽略的 `work/m0`，运行指定配方不包含部署步骤。

## 原 C 工具使用说明

> 以下保留 C 源的嵌套部署说明。独立工具仓运行时，命令中的 `mod-tools/`
> 前缀应去掉；服务器与 CDN 输入须显式配置。以下部署、同步示例不是 M0 已执行动作。

### 前提(先读)

**CDN 直解不是凭空生成数据包**,而是**从你自己那份基础 CDN 本地重放**出来的。它替你省掉的是
"另外再自备一份手机端数据包 `production/upload`"(约 10 GB),**不是**省掉基础 CDN。开跑前确认:

- **基础 CDN 仍须自备**:按本仓 `deploy.ps1` 的说明取得并放到仓内 `.cdn/cn`
  (版权原因不随仓分发任何游戏资产)。
- **三个 full 目录一个都不能少**:`.cdn/cn/archive-common-full`、`.cdn/cn/archive-medium-full`、
  `.cdn/cn/archive-android-full`(官方约 11 GB dump 自带)。缺任一个,工具直接报
  `full archive directory is missing: <目录>` 并退出,**不写盘**。
- **官方链尾要 ≥ mod 链起点(本链为 `1.4.90`)**:够不到时重放出来的是**不含任何 mod 内容的
  纯官方 store**。这种情况工具会告警并以非零码退出;确认只要官方段,再加
  `--allow-partial-chain` 显式放行。
- **跑完 `--write-profile` 后**:若 GUI 角色列表为空,检查 `profiles.json` 的 `cdndata` 是否
  指向服务端的 `assets/cdndata`(必要时手工补 `cdndata` / `server_dir`)。
- store 基线落后于目标客户端的后果与其他补救路子,见 [docs/self-host-modes.md 「前提 0」](../docs/self-host-modes.md)。

### 首选:从服务端 CDN 直解

已经部署 startpoint-cn、且仓内有 `.cdn/cn` 时走这条。

```bash
# 1) 先做只读规划(默认 dry-run,不会创建或写入目标目录)
python mod-tools/wf_store_materialize.py --dest ${WF_ROOT}/wf-store-fresh

# 2) 确认规划后物化、校验,并写入当前版本档案
python mod-tools/wf_store_materialize.py --dest ${WF_ROOT}/wf-store-fresh --apply --verify --write-profile

# 3) 首跑自检
python mod-tools/wf_selftest.py

# 4) 启动网页修改器
python mod-tools/wf_gui.py          # 浏览器打开 http://127.0.0.1:8765
```

`--dest` 必须不存在或是空目录。物化结果写到
`<dest>/production/{upload,medium_upload,android_upload}`;不加 `--apply` 时始终只规划、不写盘。
`--official-only` 可只重放官方归档链,终点固定为 `1.4.54`。

### 备用:自备手机端数据包

自备合法数据包并手工配置版本档案。

```bash
cp mod-tools/profiles.example.json mod-tools/profiles.json
# 编辑 profiles.json,把 store 指向你的 production/upload 目录

python mod-tools/wf_selftest.py
python mod-tools/wf_gui.py
```

### 开始修改后

```bash
# 把改动打成 CDN 增量包(客户端增量更新时拉取)
python mod-tools/wf_publish.py --tables ability,character_status

# 重启服务端 + 重启游戏 → 改动生效
```

## 目录结构(约定)

```
mod-tools/
├── wf_*.py                旧命令入口:只剩几行转发,`python wf_xxx.py` / `import wf_xxx` 照旧可用(见下表)
├── wf/tools/<组>/         工具本体(abyss/weapon/rogue/boss/content/wiki/release/share/assets/art/character/core)
├── *.bat                  Windows 一键入口(wf-gui / 一键平衡包 / 导出 / 采集)
├── README.md / API.md / WF_mod_tool_usage.md      使用文档(留根)
├── CN-Mod字段手册.md(.html) / 词条条件代码全表.md   核心参考(全表被 wf_describe 运行时读取)
├── ability_enum_map.json / WF_PATHLIST_recovered.txt / HarvestedPaths.csv
│                          运行时数据(逆向产物,工具按固定文件名读取,勿移动)
├── *.csv                  路径/目录采集产物(生成物,可由工具箱重建)
├── profiles.json          数据包档案(本地配置;模板见 profiles.example.json)
├── docs/                  分析报告·设计方案·逆向结论(过程性文档,不参与运行)
├── tests/                 pytest 自测(核心读写/DSL/ATF)
├── examples/              recipe 配方示例
├── work/                  运行期状态(待发布清单/改动日志/角色快照),自动生成
├── server-patch/          startpoint-cn 服务端 mod-admin 补丁(更新服务端后套回)
└── qq_monitor/            QQ 群反馈监控管线(NapCat)
```

约定:**文档进 docs/、运行时数据留根、生成物可重建**。根目录 `wf_<名>.py` 已搬到
`wf/tools/<组>/<名>.py`,旧文件只剩几行转发,`python wf_<名>.py ...` 与 `import wf_<名>` 照旧可用;
直接运行新位置请用 `python -m wf.tools.<组>.<名>`。新代码请直接放进 `wf/` 包里。
`wf_char_editor.py`、`wf_patch_ability_main_position.py` 暂留根目录(词条编辑相关,另行整理)。
新增分析/方案类 md 一律放 `docs/`;工具按文件名读取的数据(上面第 5 行)不要挪。

## 工具一览

| 工具 | 用途 |
|---|---|
| `wf_gui.py` + `wf_gui.html` | 网页修改器,分组导航(角色 / 武器 / 全局 / 系统):词条(含**词条工坊**结构化组装) / 数值 / 技能·倍率(含**效果词条**命令级编辑、**强化弹射**) / 资料 / 资产 / 新建角色 / 武器·魂珠 / Boss·副本 / 速查 / 移植 / 配方 / 工具箱 / 日志 / 备份 |
| `wf_mod_tool.py` | 核心引擎:orderedmap(含嵌套表)读写、AMF3 schema 解析、recipe 配方、版本档案 |
| `wf_store_materialize.py` | **首次部署首选**:从自己服务端的 `.cdn/cn` 本地重放到全新 store;默认只规划,`--apply` 才写盘 |
| `wf_selftest.py` | **首跑自检**:物化/配置版本档案后先运行;环境可用性检测 + 功能模拟演练(--deep 含金丝雀写入闭环,写完即复原);GUI 工具箱可跑 |
| `wf_publish.py` | 把改动打成增量包发布到服务端 CDN(与官方增量更新同构) |
| `wf_boss.py` / `wf_quest_lib.py` | Boss 数值 + 22 类副本列表;quest 系三层压缩索引嵌套表读写 |
| `wf_assets.py` / `wf_dsl.py` / `wf_describe.py` | 角色资产编解码;技能 ActionDsl 编辑(AMF3);行级中文描述 |
| `wf_dsl_sig.py` | 技能/强化弹射 DSL 命令签名表(自反编译 AS3 生成:112 命令+6 事件+46 枚举类+42 种 AC 状态词条,含中文标注) |
| `wf_atf.py` | skill_cutin 的 ATF(ETC1)纹理重编码——战斗真机只读 ATF 不读 PNG,替换 cut-in 时自动/手动重生成 |
| `wf_export_assets.py` | 全量解密导出(下载包+bundle → 逻辑路径目录树;GUI 工具箱可跑) |
| `wf_recover_pathlist.py` | 复原哈希→逻辑路径表 WF_PATHLIST_recovered(GUI 工具箱可跑) |
| `wf_decrypt_all.py` | 单文件零依赖版全量解密(不依赖本工具链任何文件,便于独立分发) |
| `wf_char_editor.py` | ① 层角色资料(名字 / 描述 / 稀有度 / 元素…)编辑 |
| `wf_scan_masterdata.py` / `wf_extract_paths.py` / `wf_harvest_paths.py` | 数据定位 / 路径逆向 |
| `wf_all_analysis.py` / `wf_unique_mech.py` / `wf_balance_suite.py` 等 | 平衡分析与增强总包(本地工作流;输出报告到 `docs/`) |

## 能力总览(② 层可改项)

技能能量(action_skill) · 队长技移植/修改(leader_ability) · 角色词条增删改(ability,含**词条工坊**自选条件/触发/目标/效果组装) ·
词条主位限制开关(全局 + 单条) · 能力魂(ability_soul) · **武器词条(equipment_enhancement_ability)** ·
技能效果命令级编辑(**效果词条**:改参数/删段/从全库插入命令) · **强化弹射**(改种类/提取内置动作可编辑/克隆新种类+词条override激活) ·
基础数值/觉醒/倍率 · 一键发布到 CDN(客户端只下增量)· **自动改动日志 + 一键回溯** · **全链路自检**。
**移植不崩的规律见下方规律方案。**
端点清单见 [角色改动规律方案.md §7](docs/角色改动规律方案.md) 或 [API.md](API.md)。

## 文档

使用类(根目录):

- **[CN-Mod字段手册.md](CN-Mod字段手册.md)** — 最重要:全字段语义、枚举、单位、各表结构、CN/global 差异、安全规则。
- **[词条条件代码全表.md](词条条件代码全表.md)** — 真实列图 + 全枚举名(配 `ability_enum_map.json`;被 wf_describe 运行时读取)。
- [API.md](API.md) — 网页修改器的 HTTP API 契约。
- [副本工坊后端](docs/studio/boss.md) — M5 副本读模型、参数草稿、共同决战模板、API / CLI 与本地交付。
- [交稿四件套](docs/studio/craft.md) — 编辑台的像素批量预检、场地比例预览、图集重排(等价校验)、稿主交接单。
- [WF_mod_tool_usage.md](WF_mod_tool_usage.md) — 命令行 recipe 用法。

分析与方案(docs/):

- **[角色改动规律方案.md](docs/角色改动规律方案.md)** — 改动规律总纲:五表列图、五类改动标准做法、**移植铁律(同属性/别去共鸣/统一sid/跨表重排)**、做不到的边界、效果代码速查、工具能力矩阵。
- [角色数据逆向与修改指南.md](docs/角色数据逆向与修改指南.md) — 两层数据架构 + HP/ATK / 觉醒破解过程。
- [版本切换设计.md](docs/版本切换设计.md) — 多版本档案(profile)设计。
- 其余:形态切换/资产替换/强化弹射逆向结论、Boss 与副本分析、六属性平衡分析(生成物)等,见 `docs/` 目录。

配套还有一个 Claude Code skill(`.claude/skills/wf-mod/`),把整条工作流固化,便于用 AI 辅助操作。

## 致谢

- [Duosion/starpoint](https://github.com/Duosion/starpoint) · [DontBeAlarmed/startpoint-cn](https://github.com/DontBeAlarmed/startpoint-cn) — 服务端模拟器
- [Ku1o/startpoint-cn-kulo](https://github.com/Ku1o/startpoint-cn-kulo)(灰) — 服务端分支;编辑台的技能时间轴预览参考了灰的 [StarPoint-Character-Studio](https://github.com/Ku1o/StarPoint-Character-Studio),部分回放测试改编自 startpoint-cn-kulo;像素批量预检、场地比例预览、图集重排、稿主交接单这四个功能的点子来自 StarPoint-Character-Studio(代码在本仓库里另写,没有拷贝)
- [wfax](https://github.com/blead/wfax) · [wdfp-extractor](https://github.com/ScripterSugar/wdfp-extractor) — 资源提取 / 转换

## License

GPL-3.0-or-later(与上游 startpoint-cn 一致)。
