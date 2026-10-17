# YAML 平衡配方

统一入口：

```powershell
python -B -m wf balance recipes/balance/balance1017-223.yml
python -B -m wf balance recipes/balance/balance1017-223.yml --write --output work/m1/balance/223-run1
```

默认只读校验。`--write` 生成本仓的 `changeset.json`、`payload/`、检查报告和用于历史验收的 ZIP；正式交付元数据、分包、prepush 由 `wf deliver <changeset.json>` 统一处理。输出存在时拒绝覆盖，换一个运行目录即可。所有旧值断言和编码回读完成后才开始写入。

`balance1017-223.yml` 包含八角色的 50 个操作、519 个逐格断言，涉及 27 个键、3 张表。配方记录具体值，执行时不导入旧角色脚本、不读取期望 223 ZIP。历史入口 `python -m recipes.balance1017 --write` 原样保留，供兼容和历史对照。

每个操作记录 `character`、`table`、`key`、从 0 开始的 `row`、旧 `row_count` 和 `cells`。每格必须有 `column`、`old`、`new`，数字也用字符串；禁止漏掉旧值、重复地址和无变化写入。默认列号采用 ability 126 列：leader 自动把 c3…c125 映射到自身 c1…c123，c0 保持不变，ability 的 c1/c2 在 leader 中不存在。明确写 `column_space: native` 可以直接用目标表列号。

```yaml
op: set_cells
character: '100'
table: leader_ability
key: '100'
row: 1
row_count: 3
cells:
  - {column: c51, old: '10000', new: '20000'} # 实际 leader c49
```

`set_cells` 支持 ability、leader_ability、action_skill 和 custom_ability_string。action_skill 必须用字符串 `level: '1'`、`'2'` 或 `'3'` 指定档位，目标角色实际缺少该档时拒绝修改；文本在原 CSV 单元格上完整断言并重新转义。能力多行叶先按 CSV 行解析，再寻址；直接按逗号切分得到的 125n+1 字段不可当作一行修改。合击资格只看第一行 c1 是否为 `true`，报告记录改动前后资格。

`insert_row` 和 `delete_row` 用于能力/队长行：必须覆盖该行全部 126/124 个单元格。插入每格 `old: null`，删除每格 `new: null`；`row_count` 锁定当前行数，避免不知情地增删错位。关联效果可使用相同的 `group` 字段说明意图。

输入支持两种形式：`historical-lock` 读取已有 active/extra 两份 SHA-256 锁，适合历史重放；`manifest` 从 `tip` 推导新视图，可附 `lock`，所有路径相对本配方。每次构建前后复验输入摘要。任何旧值漂移、非法行、取消成原值的编辑或逆向版本边都会报「问题」，不跳过、不覆盖其他键。

结构合同见 `schemas/balance-recipe.schema.json`，可通过 `wf check` 检查。配方保留 `manual_version`、`target_client`、`experimental`、`capabilities` 元数据；M1 的能力列表默认为空结构，不代表已经完成客户端能力验证。
