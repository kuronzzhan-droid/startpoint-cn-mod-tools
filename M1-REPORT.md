# M1 五个 P0 后端功能执行报告

日期：2026-10-17。分支：`refactor/m1-p0`，基线：M0.1 `3c749fc`。

## 范围与交付

任务书的五个入口已实现：`python -m wf view / balance / check / text / deliver`，其中 `check dsl` 提供 629 签名与上下文门禁。所有源码、配置修改、依赖、缓存、临时记录、测试夹具、重建包和检查报告都写在当前 worktree；外部历史输入只读。没有操作 `m0-consolidate`、`m3-studio`，没有 push，没有运行、部署或修改服务器，没有连接设备。

临时依赖和产物放在被忽略的 `work/m1/`，没有安装到系统目录，也没有提交原始游戏成员。任务书明确要求的本报告放在仓库根；长期 CLI 使用文档和规则目录入库。执行日志和逐成员比较保持为本地文件。

## 实现与验收

| 功能 | 实现 | 已取得的实际证据 |
|---|---|---|
| `wf view` | manifest 依赖链、数值 seq、可配置 ZIP 目录和补充清单；有序 ZIP SHA 与实际 store 成员锁 | `1.4.224` **602 个角色、119 ZIP、1,464 个叠层成员**，与独立 `studio-extra-224.txt` 视图逐成员一致；锁定后再读成功 |
| `wf balance` | 数据驱动 YAML；每格旧值断言；124/126 列映射；多行叶；实际技能 1/2/3 档；custom 文本；首行 c1 合击资格 | 223 新配方 **8 角色、50 操作、519 格、27 键、3 表**，重跑 **3/3 成员逐字节一致** |
| `wf.dsl.sanitize_for_629` / `wf check dsl` | 删除 PF 专属命令、只包通知的超时 Wait 和 RemoveEvent；检查正式根布局、签名和 629 上下文 | 真实 221 PF3 **497 字节 → 问题**；真实 222 修复 **463 字节 → 满足**；消毒后的树无禁命令 |
| `wf text` | action_skill、custom、desc_override、客户端 character_text 与服务端 JSON 的统一读取、旧值断言及双端暂存 | 602 角色均可解析；历史 **78/78 text WARN** 完整回读匹配、逐条归因；真实 CLI read/explain 和双端变更集合同检查通过 |
| `wf deliver` | 实际 ZIP 大小 ≤5 MiB、seq 拆包、双 manifest、integrity、SHA256SUMS、安装字节、参数化 assert_box、requires、自动 prepush | 本 worktree 完整重建 221 后出包，**11 ZIP、310/310 成员逐字节一致**；旧 manifest 语义一致；上游固定 schema 通过；独立前后断言 exit 0 |

任务要求的平衡、变更集、交付清单、requires 四份 JSON Schema 已完成，另有用于统一检查文本读取快照的 schema。`wf check` 先校验结构，再运行可执行规则；结果包含满足、问题、待验证、不适用、未执行五态和独立 blocking 标记。规则目录 17 条，每条注明范围、依据性质、来源和修订，未实现自动验证的知识条目不会被标成满足。

本机 kulo manifest 停在 206。已在忽略的 `profiles/local.json` 配置必要 ZIP 目录，并选择已确认的 `rel224/manifest-1.4.224.json` 补充清单；没有把手工 ZIP 清单改名充当自动推导。相同目录保留了 220 不同历史草稿，自动发现全部清单会正确报冲突，显式选择完整清单后才构建。旧 `studio-extra-224.txt` 只用于独立验收。

历史 221、历史 222 和新公开消毒 API 分开：原历史重建公式保持原字节；新 API 会进一步移除只含通知的 Wait，而 222 已交付的空 Wait 由检查器接受。没有为通过反例而改写历史输入。

## 文本 WARN 逐条结论

完整结论在 [text-warnings.md](docs/m1/text-warnings.md) 和对应 JSON。78 条分为 9 类：效果或参数描述不同步 47、旧日文技能名 14、镜像混写两档倍率 4、标点空白 3，其余五类各 2（内部标识符、档位标记、旧倍率、仅强化摘要、高档强化写进低档）。全部保留原“问题”状态，工具没有加入忽略名单或批量替用户决定新文案。

角色 `700007` 的 action_skill 描述为内部标识符 `ruin_lady_no_piercing`，已明确说明应先修客户端文本，不能把该值复制到镜像当作修复。官方称号使用**零基 c3**，c2 是角色介绍；三档 action_skill 使用 **1/2/3**，不是 0/1/2。CAS 能力文字没有服务端 character_text 对应列，不编造字段。

## 字节与格式证据

| 证据 | 本地路径 |
|---|---|
| 224 视图完整逐成员比较、锁 | `work/m1/view/acceptance.json`、`acceptance.lock.json` |
| 223 YAML 输出及比较 | `work/m1/balance/replay223/changeset.json`、`comparison.json` |
| 221 完整重建报告 | `work/m1/deliver/rebuild/halloween-full/historical221-m1/build-report.json` |
| 221 最终变更集 | `work/m1/deliver/halloween221-source-final/changeset.json` |
| 221 最终交付 | `work/m1/deliver/halloween221-accepted/` |
| 221 完整比较与双格式验证 | `work/m1/deliver/acceptance221-final.json` |
| 221 独立 assert_box 前后断言 | `work/m1/deliver/assertions221-final.json` |
| 221/222 真实 PF3 检查 | `work/m1/dsl/acceptance.json` |
| 统一检查命令回读 | `work/m1/check-balance223.json`、`check-changeset223.json`、`check-delivery221.json`、`check-requires221.json` |

223 与 221 输出容器使用本次时间戳或确定性时间戳，因此 ZIP 整体 SHA 与历史不同。每个成员相同；将 DOS 时间戳归零后容器也一致。各自 manifest 中的 SHA 均独立与对应容器核对，没有用历史 SHA 冒充新 ZIP 摘要。

221 本批变更成员的安装字节为 **46,654,053**，旧格式 ZIP 下载字节为 **44,703,762**。这些值不代表整个客户端的资源安装总量。上游清单沿启动器文档引用的固定提交 `b2e40c3f1b24b704e5881fbefa12be101ea78134` 的 [官方 schema](https://github.com/DontBeAlarmed/startpoint-cn/blob/b2e40c3f1b24b704e5881fbefa12be101ea78134/docs/cdn/patch-manifest.schema.json) 核验；common、medium、android 每归档都带 SHA-256，实际文件位于 `patches/<ver>/archive-*-diff/`。无内容层使用启动器现有测试认可的 `.empty`。

## 反证与审阅修复

五个功能均有负向测试，并实际执行内存变异，让删除关键逻辑后的现有测试失败；没有修改已提交生产源码来制造通过：

| 模块 | 实际变异 | 结果 |
|---|---|---|
| view | 略过最终输入复核 | 对应 manifest 漂移用例 exit 1 |
| balance | 删除旧值断言、删除 leader 列映射、允许非首行决定合击 | 3/3 变异被检测 |
| DSL | 消毒 API 改成原样返回 | 禁命令清除测试 exit 1 |
| text | 文案规则函数改成无发现 | 原测试 exit 0，变异后因未抛 ValueError 而 exit 1 |
| deliver | 源摘要函数固定返回已认可摘要 | 源内容篡改测试 exit 1 |

独立复核后已修复并增加回归：store 首读摘要被第二次读覆盖；输入/输出锁共享可变对象；显式 manifest 混入 profile 的补充清单；action_skill 第三档枚举；custom/override 跨字段重复强化漏拦；无变化文本输出；Windows 长 DSL 路径漏收；服务端前置摘要漏验；缺少基线时的空文件断言；DSL 根布局漏验；交付检查只相信 prepush 自报状态、未核对报告和断言引用的问题。

## 全量检查

最终冻结源码 `5bcaf6b` 的整轮 pytest 为 **3746 passed、354 skipped、26 warnings，exit 0，277.15 秒**。命令为 `python -B -m pytest --basetemp=work/m1/pytest-frozen-tmp --junitxml=work/m1/pytest-frozen.xml`，终端日志和退出码分别在 `work/m1/pytest-frozen.log`、`pytest-frozen-exit.json`。

JUnit 包含子测试的累计计数为 tests=6366、skipped=357、failures=0、errors=0。终端的主测试数量和 JUnit 的含子测试数量分别报告，没有混用。跳过主要来自未配置的完整 store、外部 client-patch、可选角色包和平台专属夹具；跳过项不计作已验证。26 条警告均为既有路径环境变量别名兼容用例。

此前整轮运行也为 exit 0（3714 passed、354 skipped）；随后新增检查边界测试，最终再跑了上述完整冻结轮，未用定向重跑代替全量结论。

路径扫描为 **0 命中**，证据 `work/m1/path-scan-final.json`；原仓提交卫生门禁 `bash scripts/check-hygiene.sh --all` **exit 0**；`git diff --check` 通过。结构化验收汇总、产物 SHA-256 及计数口径在 [validation.json](docs/m1/validation.json)。所有测试缓存及卫生门禁临时文件均在 worktree 内。

## 保留的验证边界

221 自动 prepush 实际为 **ERROR 0、WARN 103、INFO 10、exit 0**。本仓快照没有加载外部 kulo #35 服务端检查模块，其状态保留**待验证**。独立离线链完整性、seq、前后成员摘要检查及生成的 assert_box 已通过；这些结果不等同服务端模块或客户端运行验证。历史文本 WARN 的解释也不等同修改已部署文本。

`requires.json` 按 M1 要求有完整字段，能力解析保留 `pending-m2`；空能力集合不能宣称任何客户端都兼容。未进行设备、服务器、发布或安装验证，均属于本任务明确排除的范围。

## 本地提交

已按模块及独立修复分开提交；完整提交清单见 `git log 3c749fc..HEAD --oneline`。主要实现提交为 balance `3608a7c`、text `5d3097e`、view `6e6e42a`、DSL `87c406e`、统一 check `3576464`、deliver `0714c6c`；审阅修复各有独立提交。未 push。

使用入口和格式示例见 [docs/m1/README.md](docs/m1/README.md)。
