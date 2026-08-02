# WF-CN Mod Tools · 世界弹射物语(国服)数据修改工具链

面向 [startpoint-cn](https://github.com/DontBeAlarmed/startpoint-cn) 私服的离线数据修改工具:
可视化 / 命令行修改角色词条、基础数值(HP/ATK)、觉醒加成、能力魂、队长技、技能能量、
角色资料,并经服务端 CDN 增量下发到客户端生效。

## ⚠️ 免责声明

- 本工具仅用于**学习、研究、单机 / 私服环境**下对**你自己拥有的**游戏资源进行修改。
- **仓库代码不包含任何游戏本体资产**(数据包、APK、美术、语音等版权内容归游戏运营方所有)。
  CDN 直解只读取使用者自己部署的 startpoint-cn 服务端 CDN;使用者需自备合法获得的游戏资源。
  Release 提供的客户端整合包为**自签名私服客户端**,仅供离线自架私服的个人使用(见下「客户端整合包」)。
- 修改联网正式服数据、用于作弊或商业用途均可能违反游戏服务条款,由使用者自行承担后果。
- 逆向所得的字段语义 / 解密方式仅供技术交流;上游生态(wfax / wdfp-extractor)已公开同类逻辑。

## 环境

- Python ≥ 3.10(仅标准库,无第三方依赖)
- 已部署的 startpoint-cn 服务端 **+ 它那份基础 CDN(`.cdn/cn`)**:既用来物化数据,也用来下发改动
- 或一份合法的手机端游戏数据包(`WorldFlipper/dummy/download/production/upload`)
- 可选:MuMu 12 模拟器 + adb(用于直接同步 / 重启游戏)

## 快速开始

> 本仓是**平铺布局**:`wf_*.py` 都在仓根,命令直接写 `python wf_xxx.py`(不带 `mod-tools/` 前缀)。

### 前提(先读)

**CDN 直解不是凭空生成数据包**,而是**从你自己那份基础 CDN 本地重放**出来的。它替你省掉的是
"另外再自备一份手机端数据包 `production/upload`"(约 10 GB),**不是**省掉基础 CDN。开跑前确认:

- **基础 CDN 仍须自备**:按服务端仓库 `deploy.ps1` 的说明取得并放到服务端仓内 `.cdn/cn`
  (版权原因本仓不分发任何游戏资产)。
- **三个 full 目录一个都不能少**:`.cdn/cn/archive-common-full`、`.cdn/cn/archive-medium-full`、
  `.cdn/cn/archive-android-full`(官方约 11 GB dump 自带)。缺任一个,工具直接报
  `full archive directory is missing: <目录>` 并退出,**不写盘**。
- **官方链尾要 ≥ mod 链起点(本链为 `1.4.90`)**:够不到时重放出来的是**不含任何 mod 内容的
  纯官方 store**。这种情况工具会告警并以非零码退出;确认只要官方段,再加
  `--allow-partial-chain` 显式放行。
- **本仓与服务端仓是分开的两个目录**,`.cdn/cn` 不在默认位置时用 `--cdn <服务端仓>/.cdn/cn`
  指定,同时用 `--server-dir <服务端仓>` 告诉工具服务端在哪(也可用环境变量
  `WF_CDN_DIR` / `WF_SERVER_DIR`)。
- **跑完 `--write-profile` 后**:若 GUI 角色列表为空,检查 `profiles.json` 的 `cdndata` 是否
  指向服务端的 `assets/cdndata`(平铺布局下可能还需自行补 `cdndata` / `server_dir`)。

### 首选:从服务端 CDN 直解

已经部署 startpoint-cn、且服务端仓内有 `.cdn/cn` 时走这条。

```bash
# 1) 先做只读规划(默认 dry-run,不会创建或写入目标目录)
python wf_store_materialize.py --dest ../wf-store-fresh

# 2) 确认规划后物化、校验,并写入当前版本档案
python wf_store_materialize.py --dest ../wf-store-fresh --apply --verify --write-profile

# 3) 首跑自检
python wf_selftest.py

# 4) 启动网页修改器
python wf_gui.py          # 浏览器打开 http://127.0.0.1:8765
```

`--dest` 必须不存在或是空目录。物化结果写到
`<dest>/production/{upload,medium_upload,android_upload}`;不加 `--apply` 时始终只规划、不写盘。
`--official-only` 可只重放官方归档链,终点固定为 `1.4.54`。

### 备用:自备手机端数据包

自备合法数据包并手工配置版本档案。

```bash
cp profiles.example.json profiles.json
# 编辑 profiles.json,把 store 指向你的 production/upload 目录

python wf_selftest.py
python wf_gui.py
```

### 开始修改后

```bash
# 把改动打成 CDN 增量包(客户端增量更新时拉取)
python wf_publish.py --tables ability,character_status

# 重启服务端 + 重启游戏 → 改动生效
```

## 客户端整合包(Release 下载)

只想直接游玩(连**本服**)、不需要自己改数据的玩家,从本仓
[Releases](https://github.com/kuronzzhan-droid/startpoint-cn-mod-tools/releases)
下载**「深渊连战+三自制角色整合包 v2.0」**(`WorldFlipper-abyss-v2.apk`,约 133 MB):

- 五合一客户端补丁(免登录 / 服务器重定向 / 深渊装备战斗门控 / 赛瑞斯双形态 P-code / 逐角色 render-scale),
  启动后自动增量更新到 1.4.107,邮箱领取三位自制角色(赛瑞斯 / 史黛拉 / 杰拉德)
- ‼️ 本包**硬编码指向服主自己的服务器**,对官服无效;**自建服请勿使用**——照服务端仓库的
  [部署攻略](https://github.com/kuronzzhan-droid/startpoint-cn/blob/release/modes-20260714/docs/%E9%83%A8%E7%BD%B2%E6%94%BB%E7%95%A5.md)
  重打指向你自己服务器的客户端
- 从 v1.0 升级:**签名已变更,须卸载旧包再装**;卸载会开新号,找服主按 `device_id` 重绑老存档
- 本仓 Releases 即整合包**唯一发布地**(原独立仓 wf-abyss-client 已于 2026-07-29 并入本仓并注销;
  v1.0 历史包同步迁入),SHA-256:`9b539c210a80d76856ddbdf67e426746c020e9b389f78a63771a750327608772`

## 目录结构(约定)

```
mod-tools/
├── wf_*.py                可执行工具与库,全部平铺在根(同目录互 import;见下表)
├── *.bat                  Windows 一键入口(wf-gui / wf-mod)
├── README.md / API.md / WF_mod_tool_usage.md      使用文档(留根)
├── CN-Mod字段手册.md(.html) / 词条条件代码全表.md   核心参考(全表被 wf_describe 运行时读取)
├── ability_enum_map.json / WF_PATHLIST_recovered.txt / HarvestedPaths.csv
│                          运行时数据(逆向产物,工具按固定文件名读取,勿移动)
├── *.csv                  路径/目录采集产物(生成物,可由工具箱重建)
├── profiles.json          数据包档案(本地配置;模板见 profiles.example.json)
├── requirements.txt       pip 依赖(仅 Pillow;图像/金丝雀类工具用)
├── docs/                  分析报告·设计方案·逆向结论(过程性文档,不参与运行)
├── schemas/               角色包 manifest 的 JSON Schema 契约
├── tests/                 unittest 自测(755 项:核心读写/DSL/发布/角色包/资产治理/dev Catalog/roguelike 门禁/CDN 物化)
├── examples/              recipe 配方示例
├── work/                  运行期状态(待发布清单/改动日志/角色快照),自动生成
└── server-patch/          startpoint-cn 服务端 mod-admin 补丁(更新服务端后套回)
```

约定:**代码平铺、文档进 docs/、运行时数据留根、生成物可重建**。
新增分析/方案类 md 一律放 `docs/`;工具按文件名读取的数据(上面第 5 行)不要挪。

## 工具一览

| 工具 | 用途 |
|---|---|
| `wf_gui.py` + `wf_gui.html` | 网页修改器,分组导航(角色 / 武器 / 全局 / 系统):词条(含**词条工坊**结构化组装) / 数值 / 技能·倍率(含**效果词条**命令级编辑、**强化弹射**) / 资料 / 资产 / 新建角色 / 武器·魂珠 / Boss·副本 / 速查 / 移植 / 配方 / 工具箱 / **增量整合** / 日志 / 备份 |
| `wf_mod_tool.py` | 核心引擎:orderedmap(含嵌套表)读写、AMF3 schema 解析、recipe 配方、版本档案 |
| `wf_store_materialize.py` | **首次部署首选**:从自己服务端的 `.cdn/cn` 本地重放到全新 store;默认只规划,`--apply` 才写盘 |
| `wf_selftest.py` | **首跑自检**:物化/配置版本档案后先运行;环境可用性检测 + 功能模拟演练(--deep 含金丝雀写入闭环,写完即复原);GUI 工具箱可跑 |
| `wf_publish.py` | 把改动打成增量包发布到服务端 CDN(与官方增量更新同构) |
| `wf_pack_consolidate.py` | **增量包整合**:手选/上传多个已发布增量包按发布顺序合并去冗余,产出 `pinball-<最早from>-<最新to>` 单包(GUI「增量整合」页签同源;产物只写 work 输出目录,不碰 CDN/原包) |
| `wf_chain_squash.py` | **整链压缩**:mod 增量链(≥base)压成最终版合集单边 + 全历史版本硬链桥 + verify/retire/undo,治链条无限变长 |
| `wf_dev_catalog.py` | **dev Catalog 适配层**:把上游 dev 分支 `content:sync` 的整套 CDN 校验移植到 Python(错误码逐一对应),`audit` 体检 / `emit` 产出 dev 格式 manifest + 合并 EntityLists / `heal-layers` 补缺层占位包 / `export-pack` 产出**分享包**(含 `requires.json` 依赖声明)/ `verify-baseline` 金样验证。运行时接收与启动前编译两条路径并存,只读不改现有链目录 |
| `wf_enhancement_policy.py` | **去增强策略引擎**:审计 mod 链终态里的"个人增强"(全角色平衡/官方角色重做/boss 血量上调),官方基准=官方 CDN 归档重放(非 store 备份,钉死哈希启动即校验);纠缠表按行重建(官方 key 取官方值、自制行原样保留),被改官方资产文件走 drop-list。只做策略与重建,不写 zip 不碰 CDN |
| `wf_enhancement_switch.py` | **增强开关**:在「官方原版」与「已冻结增强态」之间按 `(key, path, col)` 地址逐格取值,分类开关可逆切换而不碰自制角色/武器/模式;枚举·哨兵锁行 + 子桶跨越锁行两条护栏,E1/E2 自检等式不成立拒写;snapshot/plan/apply/rollback 全链路 |
| `wf_share_variant.py` | **分享包双变体构建**:同一批内容产出 full(自服完整终态,含个人增强)/ content-only(官方行回滚官方原值,被改官方资产不下发)两个变体,`requires.json` 声明 `pack.variant`/`enhancement`/`enhancementDetail`;按收方链尾重新锚定,产物只写 work 输出目录,已消费的 from-to 边拒绝重切 |
| `wf_boss.py` / `wf_quest_lib.py` | Boss 数值 + 22 类副本列表;quest 系三层压缩索引嵌套表读写 |
| `wf_assets.py` / `wf_dsl.py` / `wf_describe.py` | 角色资产编解码;技能 ActionDsl 编辑(AMF3);行级中文描述 |
| `wf_dsl_sig.py` | 技能/强化弹射 DSL 命令签名表(自反编译 AS3 生成:112 命令+6 事件+46 枚举类+42 种 AC 状态词条,含中文标注) |
| `wf_atf.py` | skill_cutin 的 ATF(ETC1)纹理重编码——战斗真机只读 ATF 不读 PNG,替换 cut-in 时自动/手动重生成 |
| `wf_export_assets.py` | 全量解密导出(下载包+bundle → 逻辑路径目录树;GUI 工具箱可跑) |
| `wf_recover_pathlist.py` | 复原哈希→逻辑路径表 WF_PATHLIST_recovered(GUI 工具箱可跑) |
| `wf_decrypt_all.py` | 单文件零依赖版全量解密(不依赖本工具链任何文件,便于独立分发) |
| `wf_rogue_rewards.py` / `wf_rogue_build.py` / `wf_rogue_shop.py` | **深渊连战 roguelike**:自制 rush 活动 700099(每轮不同 boss)+ 15 把专属武装(equipment+ability_soul)+ 深渊代币兑换商店的纯数据生成 |
| `wf_rogue_banner.py` / `wf_rogue_nerf.py` / `wf_rogue_reroll.py` / `wf_rogue_save.py` | roguelike 运营工具:换专属横幅 / 逐轮修正曲线(boss·炮台 HP·ATK) / 一键重开 / 独立武器池存档 |
| `wf_field_catalog.py` | **场地效果目录**(深渊法阵弹药库):扫全库 action DSL 解出 StartBuffField / StartModifierField / CreateFlood 场程序(效果种类+数值+时长,过滤带攻击判定的脏程序),自动分类产出 `rogue_field_menu.json`;附**锻造**变体程序(净化/数值缩放,build→parse 自校验) |
| `rogue_field_menu.json` / `rogue_special_bosses.json` / `rogue_layout_plan.json` | roguelike 数据文件:场地效果菜单(wf_field_catalog 产出,GUI 图鉴与 wf_rogue_build 的单一事实源)/ 原味保护·移植白名单(authentic boss 名单)/ 连战工坊布局计划(GUI 写入,层级排程+逐层诅咒) |
| `tests/test_rogue_chain_gate.py` | roguelike **引用完整性门禁**回归:三表并集判悬空 boss + 发布清单必带 battle 表(2026-07-26 进本崩/C8601 事故的回归防线) |
| `wf_character_workspace.py` / `wf_character_pack.py` / `wf_character_requirements.py` | **自制新角色·打包**:角色包工作区、manifest(schema 契约见 `schemas/`)、统一 37 项资源契约 |
| `wf_character_flow.py` / `wf_release.py` / `wf_character_rollback.py` | **自制新角色·发布**:preflight→发布→CDN 增量链锚定→一键回滚 |
| `wf_kyle_canary.py` / `wf_canary_skin.py` | 克隆金丝雀端到端验证 / 皮肤·立绘替换(需 Pillow) |
| `wf_seris_release_pack.py` | 双新角色(赛瑞斯/史黛拉)发布包组装实例 |
| `wf_asset_maintenance.py` / `wf_asset_policy.py` / `wf_asset_quarantine.py` / `wf_asset_archive.py` / `wf_asset_inventory.py` | 资产治理:清单/维护策略(`asset-maintenance-policy-v1.json`)/隔离区/归档 |
| `wf_remediation_baseline.py` / `wf_server_auth.py` | 运维基线快照(自动脱敏)/ 服务端管理 API 的 Bearer 认证 |
| `wf_char_editor.py` | ① 层角色资料(名字 / 描述 / 稀有度 / 元素…)编辑 |
| `wf_scan_masterdata.py` / `wf_extract_paths.py` / `wf_harvest_paths.py` | 数据定位 / 路径逆向 |
| `wf_unique_mech.py` | 独特机制挖掘与下放分析(输出方案到 `docs/`) |

## 能力总览(② 层可改项)

技能能量(action_skill) · 队长技移植/修改(leader_ability) · 角色词条增删改(ability,含**词条工坊**自选条件/触发/目标/效果组装) ·
词条主位限制开关(全局 + 单条) · 能力魂(ability_soul) · **武器词条(equipment_enhancement_ability)** ·
技能效果命令级编辑(**效果词条**:改参数/删段/从全库插入命令) · **强化弹射**(改种类/提取内置动作可编辑/克隆新种类+词条override激活) ·
基础数值/觉醒/倍率 · 一键发布到 CDN(客户端只下增量)· **自动改动日志 + 一键回溯** · **全链路自检** ·
**增量包整合/整链压缩**(历史增量包去冗余合并,后发布覆盖先发布)·
**dev 架构兼容**(发布同时产出 dev 格式 catalog/EntityLists,新边自动补齐三层占位包)·
**分享包导出**(把整链或任意区间打成收方零工具即可落地的包,附 `requires.json` 依赖声明)。
**移植不崩的规律见下方规律方案。**
端点清单见 [角色改动规律方案.md §7](docs/角色改动规律方案.md) 或 [API.md](API.md)。

## 文档

使用类(根目录):

- **[CN-Mod字段手册.md](CN-Mod字段手册.md)** — 最重要:全字段语义、枚举、单位、各表结构、CN/global 差异、安全规则。
- **[词条条件代码全表.md](词条条件代码全表.md)** — 真实列图 + 全枚举名(配 `ability_enum_map.json`;被 wf_describe 运行时读取)。
- [API.md](API.md) — 网页修改器的 HTTP API 契约。
- [WF_mod_tool_usage.md](WF_mod_tool_usage.md) — 命令行 recipe 用法。

分析与方案(docs/):

- **[角色改动规律方案.md](docs/角色改动规律方案.md)** — 改动规律总纲:五表列图、五类改动标准做法、**移植铁律(同属性/别去共鸣/统一sid/跨表重排)**、做不到的边界、效果代码速查、工具能力矩阵。
- **[角色包工作流.md](docs/角色包工作流.md)** — 自制新角色从工作区到发布的完整流程(manifest/preflight/发布/回滚)。
- **[新角色制作心得.md](docs/新角色制作心得.md)** — 双新角色(赛瑞斯/史黛拉)上线全程沉淀:先例原则、解析器 schema、崩溃图鉴、发布链路坑。
- **[分享包收方指南.md](docs/分享包收方指南.md)** — 面向**收方服主**(不装任何工具):分享包结构、full / content-only 变体选择、链尾衔接前提、main / dev 两种服务端的落地步骤、`requires.json` 字段速查、常见问题。
- **[去增强变体.md](docs/去增强变体.md)** — 面向发包方:content-only 变体的设计与操作(官方基准=官方 CDN 归档、纠缠表按行重建、官方资产 drop-list),配套 `wf_enhancement_policy.py` / `wf_share_variant.py`。
- **[增强开关.md](docs/增强开关.md)** — 自服运维:分类关闭/恢复个人增强的逐格取值模型、两条锁行护栏、自检等式与回滚,配套 `wf_enhancement_switch.py`。
- [角色生成器方案.md](docs/角色生成器方案.md) / [角色生成器-Codex任务书.md](docs/角色生成器-Codex任务书.md) — 角色生成器设计与任务书。
- [角色数据逆向与修改指南.md](docs/角色数据逆向与修改指南.md) — 两层数据架构 + HP/ATK / 觉醒破解过程。
- [版本切换设计.md](docs/版本切换设计.md) — 多版本档案(profile)设计。
- [深渊连战-随机方案-当前.md](docs/深渊连战-随机方案-当前.md) — 深渊连战(700099)随机方案**当前生效版单一事实源**:生成命令、楼层排程、数值归一。
- [深渊连战-随机要素全表.md](docs/深渊连战-随机要素全表.md) — 每层可随机要素穷举:随机轴/写入列/取值空间,配合上文方案使用。
- [索拉斯双阶段boss分析与深渊连战增强方案.md](docs/索拉斯双阶段boss分析与深渊连战增强方案.md) — 双阶段转场机制逆向(quest 阶段链)+ 深渊连战增强方案演进编年体(P0–P11)。
- 其余:形态切换/资产替换/强化弹射逆向结论、Boss 与副本分析、深渊连战 roguelike 方案等,见 `docs/` 目录。

配套还有一个 Claude Code skill(`.claude/skills/wf-mod/`),把整条工作流固化,便于用 AI 辅助操作。

## 致谢

- [Duosion/starpoint](https://github.com/Duosion/starpoint) · [DontBeAlarmed/startpoint-cn](https://github.com/DontBeAlarmed/startpoint-cn) — 服务端模拟器
- [wfax](https://github.com/blead/wfax) · [wdfp-extractor](https://github.com/ScripterSugar/wdfp-extractor) — 资源提取 / 转换

## License

GPL-3.0-or-later(与上游 startpoint-cn 一致)。
