# 交付共享表键级差异

编辑台在交付 ZIP 生成后，以该次构建实际使用的 baseline view 逐张检查输出 orderedmap，写出 `delivery/key-diff.json` 和中文核对清单 `delivery/key-diff.md`。所有输入只读；差异检查不会自动补回、合并或删除任何键。

CLI 支持命名视图与链尾选择：

```powershell
python -m wf.studio.draft key-diff --view test175 --tip 290 --zip <delivery-a.zip> --zip <delivery-b.zip> --subject 139988 --md <report.md>
```

`--subject` 可省略；缺少主体信息时键标为 `unknown`。视图解析、ZIP 输入锁和命名视图配置沿用 [chain-views.md](chain-views.md)。重复 `--zip` 的顺序保留；同一成员出现在多个 ZIP 中时逐次列出，每次均与原始 baseline 比较，并在表记录中标明 `archive`。这使中间输出的删键不会被后续 ZIP 补回所掩盖。ZIP 内重复成员和损坏表报错。

## 判定规则

- `added`：输出有、基线没有的键。
- `changed`：两边都有，但存储的原始行字节不同。仅改变表外层键顺序不算行修改；重新压缩而导致行字节改变仍算修改。
- `removed`：基线有、输出没有的外层键，以及发生内层键删除、嵌套表变成叶子或 CSV 行数减少的外层键。后者同时出现在 `changed` 中。当前没有允许删键清单机制，因此任意 `removed` 都使交付 `ok=false`。
- `owned`：有明确证据属于主体的改动键。
- `foreign`：有明确证据影响其他主体的改动键；给警告，不单独阻断。多个角色共同引用的能力键也标为 `foreign`，提醒核对共享影响。
- `unknown`：证据不足，给出非阻断警告并保留人工核对；绝不默认归为自有。

主体证据来自草稿 `characterId`、`code`、顶层和改动 `params.reservations` 中的类型化 ID，以及角色克隆的 `params.ownedRows`、武器克隆请求明确登记的 ID/code。支持 `character`、`multiball`、`weapon`、`soul_item`、`unique_condition`、`string_id`、`mana_node`、`enhancement_shop`，也接受 `soul` / `unique` / `stringcode` 别名。草稿 Schema 在顶层和全部八种改动的 params 中接受这些字段，值必须为不重复的非空字符串数组；未知类型拒绝保存。

`ability_edit` 只把携带新行/档位断言、基线不存在且没有其他角色引用的 `attach_key` 视为新建自有键；仅挂接已有键不会改变归属。`desc_override_<c0>` 根据所有角色实际引用的能力行 c0 判定，多个角色共享仍为 `foreign`。武器克隆新增的 `awakening_material_<id>` 和 `<code>_pf_damage` 只在 custom 字符串表内识别。已有武器魂珠按 equipment 第 10 列引用核对，多个武器共享时仍警告；图标请求的任意 `item_id` 本身只表示编辑对象，证据不足时保持 `unknown`。非角色容器的 code 不参与角色自有前缀规则。

角色表可以补齐 CLI 主体的 code，并提供能力、队长技、技能键的实际持有者。已知角色 code 的完整前缀及 `character/<code>/` 资源键按最长匹配归属；数字子串不用于猜测归属。ID 只在相应类型的表内生效。`wfx_summon_flip_pf_<id>` 和 `wfx_ball_pf_action_<id>` 按登记的 multiball ID 判定；没有登记时保持 `unknown`。任意文本编辑请求本身不是所有权登记。

非 orderedmap 成员只比较 SHA-256，输出 `added` / `changed`，不臆测内部键。无法从侧车完整性清单、逻辑路径表或显式输入恢复逻辑名的 `common` 成员会报错，防止把共享表误当普通文件漏检。其他 CDN 根无法恢复逻辑名的成员，其 `logical` 为 `null`，按非表成员报告。

## Python 与 JSON

```python
from wf.studio.key_diff import compare_delivery, summarize, write_reports

report = compare_delivery(baseline_view, zips, subject=draft_changeset,
                          from_version="1.4.290", to_version="1.4.291")
write_reports(report, delivery_directory)
api_summary = summarize(report)
```

也可给 `delivery_dir=...`，或通过 `members=` 传入 `delivery_inputs.DeliveryMember` 列表复用已读取的 ZIP 字节。

顶层字段：

| 字段 | 含义 |
|---|---|
| `schema` | `wf-studio-key-diff/1` |
| `ok` / `blocking` | 是否允许交付 / 是否存在删键 |
| `status` | `ok`、`warning`（foreign 或 unknown 非空）、`blocked`（removed 非空） |
| `baseline` | `view`、`tip`、`version`（包含额外 ZIP 的完整来源版本） |
| `delivery` | `from`、`to`、按输入顺序去重的归档名 `archives` |
| `subject` | `characterId`、`code`、`subjectKind`、类型化 `reservations` |
| `counts` | 所有表记录的 added/changed/removed/owned/foreign/unknown 次数合计 |
| `tables` | 每次表输出的完整键差异 |
| `files` | 非表成员 SHA-256 差异 |
| `warnings` | 中文提醒，包括 foreign 或 unknown 证据范围 |

每个 `tables[]` 项包含 `logical`、`root`、`member`、`archive`、`from`、`to`、`beforeSha256`、`sha256`、`beforeKeys`、`afterKeys`、六类键列表、对应 `counts` 和 `truncated`。`files[]` 使用相同的路径/版本/摘要字段，并以 `change` 给出 `added` 或 `changed`。新成员 `beforeSha256=null`。仅 ZIP 名可识别版本时自动填充版本区间；不能识别时为 `null`，不会推测。

交付详情 HTTP 字段为 `keyDiff`，没有 `key-diff.json` 时为 `null`。详情摘要每张表的六类键列表**合计最多 200 项**，按 removed、foreign、changed、added、unknown、owned 顺序保留；截断时 `truncated=true`，各项 `counts` 始终是完整计数。完整 JSON 和中文 Markdown 均保留全部键，供并行线程逐键核对。三类变更与三类归属是两个维度，同一键会出现在两个列表中，API 预算按实际列表项计算。

合成测试见 `tests/test_studio_key_diff.py`，覆盖原始行字节、删键阻断、foreign 警告、ID 归属、共享能力、无主体信息、多 ZIP 顺序、SHA-256 文件差异、损坏表及摘要总预算。

每张表新增 `deletions` 详情：`path` 为完整键段数组，`kind` 为 `nested_key_removed`、`nested_map_replaced`、`csv_rows_removed` 或 `csv_replaced`。CSV 减少记录 `beforeRows`、`afterRows`、`removedRows`，按 CSV 记录而非换行符计数，不推测被删除行的 ID。Markdown 保留完整详情。

`build_delivery` 抛出 ValueError 时，构建仍写出 `build-report.json`，以 `buildError.type/message/stage` 保留原始错误，并将消息写入 `prepush.limitations` 和阻断检查。若后续安全检查本身失败，报告同时保存 `inspectionError`，不伪造通过的安全详情。
