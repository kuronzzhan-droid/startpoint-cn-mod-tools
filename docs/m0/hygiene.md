# M0 公开仓卫生扫描

扫描对象是本 worktree 的已跟踪文件与未忽略的新增候选文件（含归档）。不读取外部源仓历史，不访问服务器或设备，不改写 Git 历史。`work/`、本机 profile、Git 元数据不进入公开候选快照；本报告两个文件为避免自引用不纳入快照，并单独保证只含去值定位信息。

候选快照共 **1999 个文件**；文件名和内容摘要清单见本地 `work/m0/hygiene/scope.json`，清单整体 SHA256：`2eef67ba97f5ca7df8747fb2da675e7de88d66d4bbd5283032b3625aa81cb9dc`。该证据对应扫描时的快照；后续只修测试/说明时无需把无风险文字改动解释为新的服务验收。

## 密钥与 token

使用源目录中只读的 gitleaks **8.24.3**：`gitleaks dir work/m0/hygiene/snapshot --redact=100 --no-banner --no-color --report-format json --report-path work/m0/hygiene/gitleaks-redacted.json`。工具退出 **1**，有 **24 条规则命中**。逐条检查上下文后，全部是游戏资源key/摘要、测试占位或私钥格式阻断标记，**本扫描范围内未发现真实密钥/token**。未添加 gitleaks 大范围排除项。

| 文件与行 | 规则 | 复核结论（去值） |
|---|---|---|
| `assets/weapon-awaken/build_icons.py:145` | `generic-api-key` | 游戏道具素材key，不是API密钥 |
| `assets/weapon-awaken/manifest.json:143` | `generic-api-key` | 游戏道具素材key，不是API密钥 |
| `docs/examples/legacy-character-adoption.rolf.json:18` | `generic-api-key` | 游戏资源表的outer_key/tableKey，不是API密钥 |
| `docs/examples/legacy-character-adoption.rolf.json:35` | `generic-api-key` | 游戏资源表的outer_key/tableKey，不是API密钥 |
| `release-contracts/abyss_weapon_balance_v1.json:11` | `generic-api-key` | 资源键序列的SHA256摘要，不是API密钥 |
| `release-contracts/abyss_weapon_balance_v1.json:13` | `generic-api-key` | 资源键序列的SHA256摘要，不是API密钥 |
| `scripts/check-hygiene.sh:59` | `private-key` | 卫生门禁的精确整行豁免定义或负向植入样本；不是实际凭据 |
| `scripts/check-hygiene.sh:61` | `private-key` | 卫生门禁的精确整行豁免定义或负向植入样本；不是实际凭据 |
| `scripts/check-hygiene.sh:63` | `private-key` | 卫生门禁的精确整行豁免定义或负向植入样本；不是实际凭据 |
| `scripts/check-hygiene.sh:66` | `private-key` | 卫生门禁的精确整行豁免定义或负向植入样本；不是实际凭据 |
| `tests/fixtures/balance_20260927_rolfwt26.json:1` | `generic-api-key` | 游戏资源表键或回归fixture的模块/变量名，不是账户凭据 |
| `tests/fixtures/balance_20260927b_philia.json:1` | `generic-api-key` | 游戏资源表键或回归fixture的模块/变量名，不是账户凭据 |
| `tests/fixtures/balance_20260927b_regis.json:1` | `generic-api-key` | 游戏资源表键或回归fixture的模块/变量名，不是账户凭据 |
| `tests/test_offline_bundle.py:803` | `generic-api-key` | 明确命名为fixture的测试密码占位，不是服务凭据 |
| `tests/test_offline_bundle.py:1114` | `generic-api-key` | 明确命名为fixture的测试密码占位，不是服务凭据 |
| `tests/test_offline_bundle.py:1124` | `generic-api-key` | 明确命名为fixture的测试密码占位，不是服务凭据 |
| `tests/test_offline_bundle.py:825` | `private-key` | 用于验证私钥阻断的测试片段；只有格式头和prefix/suffix占位，无PEM密钥体 |
| `tests/test_offline_bundle.py:904` | `private-key` | 用于验证私钥阻断的测试片段；只有格式头和prefix/suffix占位，无PEM密钥体 |
| `tests/test_offline_bundle.py:981` | `private-key` | 用于验证私钥阻断的测试片段；只有格式头和prefix/suffix占位，无PEM密钥体 |
| `tests/test_paradox_weapon.py:573` | `generic-api-key` | 非法资源路径测试值，不是API密钥 |
| `tests/test_paradox_weapon.py:579` | `generic-api-key` | 非法资源路径测试值，不是API密钥 |
| `tests/test_wfx_gate.py:326` | `generic-api-key` | 游戏效果/资源模板key，不是API密钥 |
| `tests/test_wfx_gate.py:344` | `generic-api-key` | 游戏效果/资源模板key，不是API密钥 |
| `wf_offline_bundle.py:111` | `private-key` | 私钥格式阻断器的标记字符串；无PEM密钥体 |

## 地址、邮箱与账号

补充扫描覆盖 IPv4、家目录账号、邮箱、数字账号形态与英文街道地址。正则候选逐条结果在 `docs/m0/hygiene.json`；文件路径和行号可追溯，报告不记录真实地址、账号值或可逆的值摘要。正则命中不等于泄漏。

| 类别 | 候选数 | 人工复核 |
|---|---:|---|
| 回环/未指定地址 | 204 | 本机地址 |
| 私网IPv4形态 | 65 | RFC1918网段、Android模拟器别名、网络测试与文档占位 |
| 街道地址形态 | 2 | Python表达式误报 |
| 数字账号形态 | 17 | 游戏能力UID，并非玩家账号 |
| 家目录账号形态 | 18 | 非法路径阻断/门禁测试样本；实际源账号已配置化或脱敏 |
| 文档保留IPv4 | 10 | RFC5737示例 |
| 公网IPv4形态 | 4 | 全部来自目标校验器的拒绝测试 |
| 邮箱形态 | 52 | 测试域名、门禁植入样本、公开工具署名；另有素材@2x文件名误报 |

已修复的真实本机信息包含旧 APK 源端点/LAN 目标（改用显式环境变量）、个人下载/签名密钥路径（改用路径配置），以及原始收编决策 JSON 中 2 个 `literal` 字段的个人家目录前缀（改为 `${USER_HOME}`，原始源文件 SHA256 保留）。root 同步处理了角色归档的 scratch 路径、ASR 模型路径、素材 prompt 来源路径。外部原文件与 Git 历史均未更改。

## 原仓卫生门禁

实际执行 `bash scripts/check-hygiene.sh --all` 的当时退出码为 **0**（`work/m0/hygiene/repository-hygiene.log`）。该命令只读 Git 已跟踪清单，当时大量 C 新增/归档文件尚未 stage，**这个 0 不能作为完整候选范围通过的证据**。

因此另按原脚本的四条正则、禁用文件名、逐文件逐整行豁免规则，对 **1991 个完整候选文件**执行等价扫描，得到 **18 条阻断**（`work/m0/hygiene/legacy-gate-candidates.json`）。它们是归档导致精确豁免路径变化，或新增模块的正向阻断测试尚未登记；未发现真实凭据。逐条如下。最终 stage 全量后的原门禁结果应以根报告的最后一次验收为准。

| 文件与行 | 原规则 | 原因 |
|---|---|---|
| `archive/legacy/tests/test_release_v1_canonical.py:132` | `HOME_RE` | 原有精确行豁免仍指向归档前路径，迁移后不再匹配 |
| `archive/legacy/tests/test_release_v1_canonical.py:133` | `HOME_RE` | 原有精确行豁免仍指向归档前路径，迁移后不再匹配 |
| `archive/legacy/tests/test_release_v1_canonical.py:135` | `HOME_RE` | 原有精确行豁免仍指向归档前路径，迁移后不再匹配 |
| `archive/legacy/wf_release_v1/_loopback_http.py:27` | `IP_RE` | 原有精确行豁免仍指向归档前路径，迁移后不再匹配 |
| `archive/legacy/wf_release_v1/platform.py:47` | `IP_RE` | 原有精确行豁免仍指向归档前路径，迁移后不再匹配 |
| `archive/legacy/wf_release_v1/target.py:37` | `IP_RE` | 原有精确行豁免仍指向归档前路径，迁移后不再匹配 |
| `tests/test_offline_bundle.py:825` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |
| `tests/test_offline_bundle.py:861` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |
| `tests/test_offline_bundle.py:904` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |
| `tests/test_offline_bundle.py:955` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |
| `tests/test_offline_bundle.py:981` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |
| `tests/test_offline_bundle.py:1037` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |
| `tests/test_wiki_battle_package.py:258` | `HOME_RE` | 新收编模块的非法路径拒绝fixture尚未在旧门禁精确行表登记 |
| `wf_offline_bundle.py:111` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |
| `wf_offline_bundle.py:112` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |
| `wf_offline_bundle.py:113` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |
| `wf_offline_bundle.py:114` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |
| `wf_offline_bundle.py:115` | `SECRET_RE` | 新收编模块的私钥格式阻断标记/测试断言尚未在旧门禁精确行表登记 |

上述 18 条命中对应 17 条不同的文件+整行规则（同一断言在同文件重复），已经逐条登记。修复后对 **1997 个完整候选文件**再做同一等价扫描，**命中 0**（`work/m0/hygiene/legacy-gate-final.json`）。保留原始 18 条发现，未把复核过程抹成最初即为零。

实际执行 `bash scripts/tests/test-hygiene.sh`，退出 **0**：干净基线、7种泄漏植入、豁免文件内新增IP、篡改豁免行共 **10 项通过**。自测原本创建临时目录后没有进入该目录，会把追加与checkout作用到当前仓；本次已修为只复制必要样本到 `work/m0/hygiene-selftest/case.*` 的隔离Git夹具，且递归清理前核对绝对路径边界。负向测试没有改动主worktree的未提交文件。日志见 `work/m0/hygiene/gate-selftest.log`。

## 结论边界

结果覆盖本次公开候选文件内容和列出的启发式规则，不表示对 Git 历史、二进制内部数据、所有可能的自然语言地址或远端账户做了穷尽安全证明。gitleaks 的原始规则退出码保留为 1，不能改写成工具零命中；人工复核结果与工具计数分开记录。报告、扫描及必要脱敏不构成 push、发布或服务端变更授权。
