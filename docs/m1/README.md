# M1 离线命令与格式

所有写入限于当前工具仓；外部 store、kulo、已交付 ZIP 和服务端 JSON 仅作输入。不调用服务器、设备或发布流程。运行 `python -m wf --help` 查看五个入口。本机路径和补充 manifest 配置见 [profiles 说明](../../profiles/README.md)。

```powershell
python -m wf view --tip 1.4.224 --write-lock work/m1/view.lock.json --json work/m1/view.json
python -m wf view --tip 1.4.224 --lock work/m1/view.lock.json
python -m wf balance recipes/balance/balance1017-223.yml --write
python -m wf check recipes/balance/balance1017-223.yml
python -m wf check dsl work/example.action.dsl.amf3.deflate --kind 629
python -m wf text read 149999 --tip 1.4.224 --output work/m1/character.json
python -m wf check work/m1/character.json
python -m wf deliver work/example/changeset.json --out work/m1/delivery
python -m wf check work/m1/delivery/delivery-manifest.json
python -m wf check rules
```

`wf balance` 不带 `--write` 时在内存验证旧值、修改和合法性；不写出变更集。实际动作技能档位是 **1、2、3**，角色不一定有全部三档。能力表多行先拆分，再按行号寻址；leader 的列号可按 ability 语义自动映射。详细格式见 [平衡配方](../../recipes/balance/README.md)。

`wf text edit` 需要显式提供只读服务端 `character_text.json` 和读取时的快照摘要。编辑后在本仓输出两端 payload 和统一变更集。技能名/描述改真实 action_skill 并同步镜像，称号按 **零基 c3**；能力文案不往没有对应字段的服务端镜像硬塞。共享技能或字符串必须先解决归属，工具不会自行改其他角色。见 [文本工具](../../wf/text/README.md) 与 [78 条历史 WARN 逐条结论](text-warnings.md)。

`wf deliver` 接受内容寻址的变更集。`--server-dir`、`--base-store`、`--baseline-active`、重复的 `--baseline-zip` 都是只读输入，用于在本仓快照运行 prepush 和前后摘要断言。没有基线时相应检查如实显示未执行或待验证，不能把 `before_sha256=null` 当作已证明文件不存在。详见 [交付器](../../wf/deliver/README.md)。

## 检查结果

`wf check` 对结构化文件执行 JSON Schema，再运行适用的实际检查：平衡配方回读输入并在内存执行旧值断言；变更集回读源 payload 摘要；交付清单回读双格式 ZIP、总量和 prepush 状态；文本快照执行玩家文案规则。未知格式报“未执行”并返回非零，避免被 CI 当作成功。

规则注册表是 [wf/rules/catalog.json](../../wf/rules/catalog.json)，共 17 条，每条有版本、适用范围、要求、依据性质、来源和修订记录。来自混合真机/反编译汇总的条目保留保守标注；未实现自动检查的知识条目不冒充已运行。

| 状态 | 含义 |
|---|---|
| 满足 | 当前输入有对应的实际检查证据 |
| 问题 | 结构、摘要或已适用规则检查失败 |
| 待验证 | 证据不足，或能力解析尚待 M2 接入 |
| 不适用 | 输入不属于该条目范围 |
| 未执行 | 缺少上下文、来源或相应检查器 |

每条机器结果另给 `blocking`。退出码 0 表示执行过的阻断检查没有失败，**不表示所有条目满足，更不表示真机通过**。`requires.json` 在 M1 明确保留 `capabilityResolution: pending-m2`，空能力列表不能解释为没有客户端依赖。

629 检查必须指定 `--kind 629`。未给 kind 时只验证签名，生命周期检查显示未执行；真实 PF 上下文显示不适用。`wf.dsl.sanitize_for_629(tree)` 返回深拷贝，不修改源树；只包 PF 结束通知的 Wait 整体移除，携带有效效果的 Wait 保留。222 历史修复遗留的空 Wait 可接受。历史 221/222 重建配方保持历史语义，新动作应显式调用公开消毒 API。

## 验收复跑

```powershell
python -m scripts.verify_m1_view --extra-list <只读的studio-extra-224.txt>
python -m scripts.verify_m1_dsl
python -m recipes.halloween221_changeset --help
python -m pytest --basetemp=work/m1/pytest-tmp
python -m scripts.check_no_hardcoded_paths --json work/m1/path-scan.json
```

完整命令、实际产物及未验证范围见根目录 [M1-REPORT.md](../../M1-REPORT.md)。临时验收文件在忽略的 `work/m1/`，不纳入版本控制。历史游戏成员的字节明细只存本地验收文件；版本控制内保留摘要和结果，不新增原始游戏资源。
