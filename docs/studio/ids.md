# ID 与资源版本查询契约

查询只读取当前视图、指定服务端镜像、全部角色/BOSS/武器草稿；返回建议不会写预留记录，也不保证其他进程之后不占用。正式 clone 仍执行自身碰撞检查。

```
python -m wf.studio.draft --view test175 ids check character 199000 --server-dir D:/mirror
python -m wf.studio.draft --view test175 ids next weapon --near 5950001
python -m wf.studio.draft versions next --view test175
```

CLI 共用 `--drafts`、`--manifest`、`--store`、`--zip-dir` 等视图配置，成功或失败都输出一行 JSON。支持 kind：`character`、`multiball`、`weapon`、`soul_item`、`unique_condition`、`string_id`、`mana_node`、`enhancement_shop`。

- `check` 返回 `kind/id/available/owners/viewVersion/serverChecked/reserved`。`owners` 每项含 `owner`、`source`（view/server/draft）与表或文件 `location`；`reserved` 恒为 false。
- `next` 从 `--near` 开始含该值向上查询，补充 `skipped` 及每个跳过值的来源。未给 near 使用工具的建议起点，不宣称该区间有项目专属授权。字符串有尾号则递增，否则附加 `_1`。
- `mana_node` 的 ID 参数是角色 ID，对应原生 `cid * 2` 前缀后的三位节点号，即 `cid*2000` 至 `cid*2000+999` 的 1000 个节点范围，返回 `segment.characterId/start/end`。既查外层角色键也查实际节点行，能发现其他角色持有该段；相邻奇数前缀不会误算进本段。
- 武器同时查询原生关联表与强化商店 ID 的 `id // 100` 所属武器，魂珠查询整个 item 空间以防与材料冲突。
- 角色查询包含 speech/image 关联表、`character` 外层键及 c27 `identity_character_id`。c17 在客户端是 `leader_ability.id`，不作为额外角色 ID；旧工具把它命名为 `character_id` 不改变客户端语义。能力、队长技、魂珠表的 c0 文本引用计入 `string_id`，外层能力键不混入文本键。
- 服务端还查询根目录/`cdndata` 的 rank 角色镜像、超限配置的 `characters` 数组、玛纳表外层角色键及装备分解表。领主币商店按分类/商品下 `rewards[].type/id` 读取 Item/Equipment 引用，不把分类、商品 ID 或角色奖励当武器。
- 服务端支持仓库根目录或 assets 根目录。未指定时 `serverChecked=false`；指定的目录不存在、已存在的来源文件损坏或草稿声明文件丢失时失败，不返回假空闲。
- 草稿同时查询顶层/变更预留、客户端表和服务端 JSON 文件，以及尚未物化文件的请求。角色文案覆盖键、武器/BOSS 的 629 模板派生文案键、已有觉醒材料规则派生键均算预留。原生表使用 `stored`；读取旧导入声明时兼容 `deflate`/`raw-deflate` 的单一 raw-deflate 流，并复核已有的大小及 SHA-256 声明。
- 角色克隆的完整表载荷按 `params.ownedRows` 只查询此次新增的键；旧版克隆草稿按目标角色键查询，不把所选历史视图之后的母本表内容算成克隆预留。克隆的继承能力文案仍归母本引用，随后新增文案由独立请求收集。
- 武器克隆文本键遵循构建器：显式 code 使用 `code` 与 `code_soul`；省略 code 使用 `boss_workshop_<id>` 与 `boss_workshop_soul_<id>`。能力请求支持 `insert_row`、`set_cells`、`attach_key`，按真实 layout 和 `column_space` 收集 c0、629 文案槽与 unique-condition 引用；ability c2 是类别，不算 unique ID，补丁借作规则掩码的列也不算。

HTTP GET：

| 路径 | 参数 | 行为 |
| --- | --- | --- |
| `/api/studio/ids/check` | `kind`, `id` | 查当前启动视图与启动时 `--server-dir` |
| `/api/studio/ids/next` | `kind`, 可选 `near` | 同上，查询下一空闲值 |
| `/api/studio/versions/next` | 可选 `view` | 指定命名视图；省略使用当前视图 |

HTTP 不接收任意服务端目录参数，继续使用应用启动时配置的镜像。参数错误返回 400；所有读取保留现有 Host 检查。

版本登记可选放在 `release-contracts/version-reservations.json`，结构由 `schemas/version-reservations.schema.json` 校验：

```json
{
  "1.4.283": {"purpose": "深渊之兽", "owner": "负责人", "date": "2026-10-25"},
  "1.4.284": {"purpose": "深渊之兽", "owner": "负责人", "date": "2026-10-25"}
}
```

这是格式示例，不会自动登记实际预留。CLI 可用 `--reservations-file` 指向其他本地登记。返回 `view/current/next/skipped/reservationsFile/reserved`，从所选视图实际叠加后的版本加一并跳过已登记版本。若特意选择历史 tip，清单里更晚已声明的数字版本（含禁用条目）也不会再次分配；对应 `skipped` 条目带 `source=manifest` 和 `location`。日期必须是有效 ISO 日期，数字版本不得有前导零；登记无效则查询失败。

无清单的 `HistoricalView` 同时扫描自身 `active` 目录里的正式增量包文件名，跳过已出现的版本；`skipped` 的来源为 `active`，候选包不算正式版本。HTTP 交付 defaults 和 build 在省略 `to` 时使用同一查询，自动跳过预留及已声明版本。显式 `to` 仍是调用方选择；CLI `build` 要求显式 `--to`，不隐式分配，也不写预留表。
