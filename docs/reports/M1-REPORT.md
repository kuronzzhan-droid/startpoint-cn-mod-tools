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

完整结论在 [text-warnings.md](../../docs/m1/text-warnings.md) 和对应 JSON。78 条分为 9 类：效果或参数描述不同步 47、旧日文技能名 14、镜像混写两档倍率 4、标点空白 3，其余五类各 2（内部标识符、档位标记、旧倍率、仅强化摘要、高档强化写进低档）。全部保留原“问题”状态，工具没有加入忽略名单或批量替用户决定新文案。

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

路径扫描为 **0 命中**，证据 `work/m1/path-scan-final.json`；原仓提交卫生门禁 `bash scripts/check-hygiene.sh --all` **exit 0**；`git diff --check` 通过。结构化验收汇总、产物 SHA-256 及计数口径在 [validation.json](../../docs/m1/validation.json)。所有测试缓存及卫生门禁临时文件均在 worktree 内。

## 保留的验证边界

221 自动 prepush 实际为 **ERROR 0、WARN 103、INFO 10、exit 0**。本仓快照没有加载外部 kulo #35 服务端检查模块，其状态保留**待验证**。独立离线链完整性、seq、前后成员摘要检查及生成的 assert_box 已通过；这些结果不等同服务端模块或客户端运行验证。历史文本 WARN 的解释也不等同修改已部署文本。

`requires.json` 按 M1 要求有完整字段，能力解析保留 `pending-m2`；空能力集合不能宣称任何客户端都兼容。未进行设备、服务器、发布或安装验证，均属于本任务明确排除的范围。

## 本地提交

已按模块及独立修复分开提交；完整提交清单见 `git log 3c749fc..HEAD --oneline`。主要实现提交为 balance `3608a7c`、text `5d3097e`、view `6e6e42a`、DSL `87c406e`、统一 check `3576464`、deliver `0714c6c`；审阅修复各有独立提交。未 push。

使用入口和格式示例见 [docs/m1/README.md](../../docs/m1/README.md)。

## M1.1 审查修复与最终验收

日期：2026-10-17。本节记录对 `M1.1-任务书.md` 全部 13 项的处理；涉及旧行为时，以本节为准。所有源码、临时依赖复用、缓存、验收产物和执行记录只写当前 worktree；外部输入只读。按主题完成本地提交，未 push，未操作服务器或设备。任务书限定其他路径只读，因此临时记录保存在忽略的 `work/m1.1/`，不纳入版本控制。

| 项目 | 最终行为与反证 |
|---|---|
| H1 | manifest tip 与历史锁推导的有效链尾必须等于 `from_version`；224 视图伪报 from=226 会拒绝。历史锁先验证 extra ZIP 版本边和 seq，不能只相信标签。 |
| H2 | deliver 默认要求 `wf view` / manifest 基线；没有基线即问题、非零退出。唯一缺失基线豁免是显式 `--no-baseline-i-know`，清单和报告均留痕；已提供基线中的过期 from、已占用 to（含禁用边）、同版本重铸仍拒绝。 |
| H3 | balance、deliver 出包前从四张能力类表推导 629 动作，并跟踪 `path$program`。按能力/技能键差异与 DSL 可达性选根；删除被引用技能、无法完整构建相关闭包、非 common 层 combat 表/DSL 均拒绝。真实 221 PF3 被 deliver 阻断且没有 ZIP，222 修复树在相同真实能力上下文通过。 |
| M1 | 选择任务书允许的“直接拒绝”方案：balance 禁止 action_skill c0/c1 和 custom_ability_string 修改，提示改用 `wf text`。 |
| M2 | text 同时读取并校验 character_text 与 character_text_rank_p5b 两份服务端镜像；稀疏镜像只修改已有角色键，不擅自补键。两个输入都纳入快照与 server_changes 前置摘要。 |
| M3 | 服务端 JSON 仅替换选中列的字符串 token，保留键序、缩进、换行与未改内容字节。deliver 对每份 server_changes 强制验证服务端前置摘要；缺 server-dir 不能被客户端基线豁免放行。交付回读也要求服务端 pre/post 证据一致。 |
| M4 | CSV 保留原 CRLF/LF 及末尾换行状态；编辑前执行 split→join 断言。13 个真实 CRLF 叶子均有逐项往返、修改、恢复回归。 |
| M5 | balance 校验角色归属；共享键列出全部所有者并要求每个操作显式 `shared_ok: true`。真实 resistance_princess_3halfanv 的 111165、119999 两所有者已验证。 |
| M6 | Wait 检查不再限定 4 项；支持不同节点包装和变长参数。消毒保留额外效果回调，包括具名 JSON 形式。 |
| L1 | 单元格编辑、插入或删除导致首行 c1 合击资格变化时，报告明确警告与 before/after。 |
| L2 | manifest 自动发现排除 `manifest-entry-*.json`；显式指定仍按正常冲突规则验证。 |
| L3 | check_delivery 比较分层 ZIP 与 legacy 的成员集合、层归属和每成员摘要；即使重新计算了 ZIP 自身 SHA，内容、缺失、多余或错层仍拒绝。 |
| L5 | 基线 ZIP 从 manifest 链选择并只读引用；active 中未登记草稿不参与，validation 内不复制任何基线 ZIP。 |

### 官方 629 正向对照与范围

使用 `OfficialBaseline` 读取指定 CN 官方归档至 **1.4.54**，开启 pinned 表摘要核验；没有把含 MOD 的 store131 当官方语料。四张能力类表共 **3 处 629 引用、3 棵唯一树**，其中 ability 1 处、leader 2 处。RemoveEvent、SetPowerFilpSuppress、NotifyPowerflipEnd、Wait 均为 **0 次**，没有额外子程序引用。因此本次语料没有提供需要降为“待验证”的合法正例，现有禁用类别继续报问题。结论只覆盖这些已核验归档，不能外推其他地区或后续官方版本。

可复现入口与输入成员摘要见 [629 说明](../../wf/dsl/README.md)、[official-629-corpus.json](../../docs/m1/official-629-corpus.json)。现有独立签名检查器对官方 CreateSummonsMultiball 的 null 回调有误报；自动 629 门禁检查二进制解析与生命周期，不借该旧签名缺口阻断官方正例。

### 两次历史字节验收

- **223：3/3**。原 YAML 包含 7 个历史 custom 文本操作，正常 balance 现在应拒绝。固定入口 `python -B -m recipes.balance_replay223` 校验原配方及两份输入锁的固定摘要，在内存重建并逐成员核对原始字节摘要；不产生 ZIP、payload 或可交付 changeset。证据：`work/m1.1/balance/223-byte-verification.json`。
- **221：11 ZIP、310/310**，差异成员 **0**，旧 manifest 语义一致，上游固定 schema 验证通过。使用原 M1 已完整重建且内容寻址的 changeset，重新运行归档与双清单生成层；期望 ZIP 在生成后只读比较。证据：`work/m1.1/acceptance221.json`，重跑脚本 `work/m1.1/verify221.py`。本轮没有重新生产立绘/语音等资产。
- 这两项证明历史编码和包装兼容性；不声称新公开入口允许旧风险内容。真实 221 的 497 字节 PF3 经 `build_delivery` 精确命中 SetPowerFilpSuppress 与只含通知的 Wait，出包前阻断；同一真实能力叶搭配 222 的 463 字节修复树通过。完整旧 221 changeset 也实际阻断于 `work/m1.1/dsl/real221-block/`，ZIP 数为 0；该完整变更集运行使用显式无基线选项与旧 store，因此其额外缺依赖诊断不冒充完整历史 220 基线验证。

### 最小文本写回的真实输入验收

以 1.4.224 视图角色 149998 编辑称号：普通镜像 **566** 个未改顶层键、rank 镜像 **44** 个未改顶层键逐字节保持；目标角色只替换 c3 字符串 token。外部两份输入原字节未变，证据 `work/m1.1/text/real-mirror-evidence.json`。实际镜像是稀疏集合，普通表 567 键、rank 表 45 键、交集 18 键、rank 独有 27 键，所以不把“两份同步”实现成给缺失角色凭空补行。

### 反证、全量检查与本地提交

实际执行 **16 组**进程内变异：balance 5 组、text 2 组、DSL 3 组、deliver/view 6 组，全部使对应原测试变红；其中强制 LF 会使 **13 个真实 CRLF 用例全部失败**。变异不修改生产源码文件。四份证据为 `work/m1.1/balance/mutation-evidence.json`、`text/mutation-evidence.json`、`dsl/mutation-evidence.json`、`mutations/evidence.json`（后三项同在 `work/m1.1/`）。

最终源码冻结在 `adb1b59`，整轮命令 `python -B -m pytest --basetemp=work/m1.1/full-tmp --junitxml=work/m1.1/pytest-full.xml`：**3831 passed, 354 skipped, 26 warnings in 336.16s (0:05:36)**，**exit 0**，耗时 338.0 秒。只复用了当前 worktree 已有的 `work/m1/deps`，未安装系统依赖。完整日志与退出码为 `work/m1.1/pytest-full.log`、`pytest-full-exit.json`。

JUnit 含子测试累计 tests=6451、skipped=357、failures=0、errors=0，与终端主测试计数分别报告。跳过项不计作已验证；仍主要是缺少完整外部数据或可选包、平台专属条件。第一次启动后发现 Wait 回调保留问题并主动中止；第二轮暴露两个新增 CLI 单测在宿主进程安装不可撤销审计钩子，污染既有硬链接测试。已隔离这两处单测，顺序组合回归 294 passed、1 skipped、46 subtests passed，随后从头完成本节所列整轮。前两次日志分别保存在 `pytest-interrupted*`、`pytest-contaminated*`，不混作通过证据；生产写入限制没有放宽。

路径扫描 **0 命中**（`work/m1.1/path-scan-final.json`），提交卫生 `bash scripts/check-hygiene.sh --all` **exit 0**（`hygiene.log`），`git diff --check` 通过。全量结束后仅追加本报告及修正文档示例；未改变已验证源码。

本地主题提交：`a8413d6`（草稿发现与分层成员）、`652c198`（双镜像最小写回）、`99fb911`（629 解析）、`b8188f0`（balance 绑定和数据保真）、`9185c7f`（真实 PF3 与删除技能回归）、`6fbbed0`（deliver 基线与主门禁）、`27f4ce4`（不完整闭包拒绝）、`de50455`（Wait 额外回调保留）、`adb1b59`（CLI 单测隔离）。本节与最终文档更新另行本地提交；完整记录见 `git log 3db4134..HEAD --oneline`。

这些结果属于本地工具、文件与回归验证。未进行客户端设备实测、服务端运行验证、安装或发布；`requires` 的能力匹配仍按原 M1 范围保留 `pending-m2`。
