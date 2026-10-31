# WF-CN Mod Tools · 世界弹射物语（国服）离线数据修改工具链

面向 [DontBeAlarmed/startpoint-cn](https://github.com/DontBeAlarmed/startpoint-cn) 本地服务端的离线数据修改与可视化创作工具链：支持角色基础数值（HP/ATK）、词条、队长技、面板文案、立绘、像素小人、语音、BOSS 副本与武器的查看、草稿编辑、门禁校验及本地 CDN 增量热更下发。

## ⚠️ 免责声明

- 本工具仅限个人在**本机或家庭局域网自建环境**下用于学习与技术研究，仅针对**使用者自行合法拥有**的游戏资源进行离线修改；切勿将服务端端口（尤其是管理端口）暴露至公网。
- **本仓库不包含、不分发任何客户端 APK、官方 CDN 数据包、立绘、像素或语音等游戏本体资产，也不提供任何下载渠道**；所有工具只读取使用者在本机自行准备的文件。
- 修改联网正式服数据、用于作弊或任何商业用途均可能违反相关服务条款与法律法规，一切风险与后果由使用者自行承担。
- 逆向所得的字段语义与编解码实现仅供技术交流；上游开源生态（`wfax` / `wdfp-extractor`）已公开同类资源解析逻辑。

## 我想做什么

| 你想做的事 | 从这里开始 |
|---|---|
| **零基础从头搭环境，亲手改一次角色 HP 并还原** | **[新手入门教程（00 → 07）](docs/tutorial/00-开始之前.md)** |
| **打开可视化 Studio 编辑台（只写草稿、不改现网）** | [06｜打开编辑台](docs/tutorial/06-打开编辑台.md) · [编辑台详细说明](docs/studio/README.md) |
| **改角色词条、队长技、面板文案、技能倍率或基础 HP/ATK** | [改词条与数值](docs/guide/改词条与数值.md) · [词条与文案规范](docs/experience/词条与文案规范.md) |
| **克隆模板角色，换上立绘/像素/语音做成全新自制角色** | [做新角色](docs/guide/做新角色.md) |
| **生成本地候选交付包、隔离沙盒预演、热更发布与安全回滚** | [发布与回滚](docs/guide/发布与回滚.md) · [发布事故复盘](docs/experience/发布事故复盘.md) |
| **选择客户端档案、扫描自备 APK 能力、了解扩展 `wfx` 效果码** | [客户端补丁与APK](docs/guide/客户端补丁与APK.md) |
| **把 Mod 导出成分享包，或安全装载他人的分享包** | [分享包](docs/guide/分享包.md) |
| **查命令行报错、「改了没生效」或游戏弹窗崩溃码** | [07｜报错对照表](docs/tutorial/07-报错对照表.md) · [崩溃码速查](docs/experience/崩溃码速查.md) |
| **检索全部现行技术文档、字段手册与历史档案** | **[仓库文档总目录（docs/README.md）](docs/README.md)** |

## 环境与快速配置

- **运行环境**：Windows 10 / 11（64 位推荐）；**Python ≥ 3.11**（运行依赖见 [`requirements.txt`](requirements.txt)，开发测试依赖见 [`requirements-dev.txt`](requirements-dev.txt)）；**Node.js ≥ 20.12.0**（构建 `studio/` 前端及运行上游 `startpoint-cn` 服务端）。
- **本机路径配置**：在仓库根目录将 [`profiles/example.json`](profiles/example.json) 复制为 **`profiles/local.json`**（已被 Git 忽略），填入本机物化后的 `store`（`.../production/upload`）与 `startpoint-cn` 服务端目录。解析优先级为 **`WF_*` 环境变量 > `profiles/local.json`**，工具不做隐式全盘扫描（字段说明见 [`profiles/README.md`](profiles/README.md)，手把手步骤见 [04｜配置工具](docs/tutorial/04-配置工具.md)）。
- **常用入口**（均在仓库根目录执行，无需加旧版 `mod-tools/` 前缀）：
  ```bat
  python wf_store_materialize.py --help   &:: 从服务端 .cdn/cn 本地物化可读写 store
  python wf_selftest.py                   &:: 20 项只读环境与往返自检
  python wf_gui.py                        &:: 启动传统网页修改器（http://127.0.0.1:8765）
  python -m wf.studio --view local        &:: 启动 Studio 编辑台（http://127.0.0.1:8790，需先构建 studio/）
  ```

## 目录说明

| 目录 / 文件 | 说明 |
|---|---|
| `wf/` | 核心 Python 包：分层只读视图 `wf.view`、编辑台后端 `wf.studio`、数值/文案变更集 `wf.balance` / `wf.text`、交付门禁 `wf.deliver`、APK 能力检查 `wf.apk` 等 |
| `wf_*.py` / `wfx_*.py` | 根目录命令行与图形修改器脚本入口（`wf_store_materialize.py`、`wf_selftest.py`、`wf_gui.py`、`wf_publish.py`、`wf_character_flow.py`、`wf_dev_catalog.py`、`wfx_gate.py` 等） |
| `studio/` | Studio 编辑台前端工程（Preact + TypeScript，首次使用在 `studio/` 下执行 `npm install && npm run build`） |
| `wf_release_v1/`、`release-contracts/` | `.wf-release.zip` 独立发行包构建、校验、本机受管安装与事务回滚实现 |
| `profiles/` | 本机路径配置模板 `profiles/example.json` 与说明；个人配置保存至 `profiles/local.json` |
| `docs/` | 新手教程 `tutorial/`、任务手册 `guide/`、避坑经验 `experience/`、编辑台专题 `studio/` 等，总目录见 [`docs/README.md`](docs/README.md) |
| `schemas/`、`data/`、`templates/`、`recipes/` | JSON Schema、枚举与注册表数据、资源模板及离线复现配方（详见 [`recipes/README.md`](recipes/README.md)） |
| `scripts/`、`tests/` | 仓库卫生检查脚本（如 `scripts/check_no_hardcoded_paths.py`）与 `pytest` 回归测试套件 |
| `work/` | 运行时本地工作区（Git 忽略）：存放编辑台草稿 `studio-drafts/`、候选交付包、改动日志与临时产物 |
| `CN-Mod字段手册.md`、`词条条件代码全表.md`、`ability_enum_map.json`、`WF_PATHLIST_recovered.txt` | 字段语义手册、枚举映射与哈希路径表（后三项由工具在运行时直接读取，请保留在根目录） |
| `archive/` | 已冻结的历史专项脚本与旧归档，不作为日常入口 |

## 致谢

- [Duosion/starpoint](https://github.com/Duosion/starpoint) · [DontBeAlarmed/startpoint-cn](https://github.com/DontBeAlarmed/startpoint-cn) — 服务端模拟器
- [wfax](https://github.com/blead/wfax) · [wdfp-extractor](https://github.com/ScripterSugar/wdfp-extractor) — 资源提取与格式转换

## License

GPL-3.0-or-later（与上游 `startpoint-cn` 一致）。
