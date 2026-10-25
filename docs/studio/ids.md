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
- 服务端支持仓库根目录或 assets 根目录。未指定时 `serverChecked=false`；指定的目录不存在、已存在的来源文件损坏或草稿声明文件丢失时失败，不返回假空闲。
- 草稿同时查询顶层/变更预留、客户端表和服务端 JSON 文件，以及尚未物化文件的请求。角色文案覆盖键、武器/BOSS 的 629 模板派生文案键、已有觉醒材料规则派生键均算预留。原生表使用 `stored`；读取旧导入声明时兼容 `deflate`/`raw-deflate` 的单一 raw-deflate 流，并复核已有的大小及 SHA-256 声明。

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
