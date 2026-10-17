# 角色文本 API 与命令

`TextWorkspace(view, server_path)` 以只读视图统一读取角色三档 `action_skill` 的 c0/c1、关联 `custom_ability_string`、`desc_override`、完整 `character_text` 与服务端镜像。关联既按角色/技能代码的客户端键约定，也按该角色能力和队长技引用的字符串键查找。没有觉醒档时不虚构第三档。

称号使用零基 **c3**，即第四个 CSV 单元格；c2 是长介绍。`wf_wiki_catalog.character_entry` 和 `wf.chars.support.table_rows.character_text_row` 均给出同一映射。技能镜像为 c4/c5、c6/c7、c8/c9。能力文案与覆盖文案在 `custom_ability_string` 中，服务端 `character_text.json` 没有能力文本字段，因此不会向该 JSON 塞入不存在的列。

```powershell
python -B -m wf text read 149999 --tip 1.4.224 --server-text <只读character_text.json> --output work/m1/text/149999.json
python -B -m wf text check 149999 --tip 1.4.224 --server-text <只读character_text.json>
python -B -m wf text edit work/m1/text/edit.json --tip 1.4.224 --server-text <只读character_text.json> --output work/m1/text/edit-1 --id text-1 --name 文本同步 --to-version 1.4.225 --slug text-sync --created-at 2026-10-17
```

编辑文件示例（旧值与 `snapshot_sha256` 必须来自 read）：

```json
{
  "character_id": "149999",
  "snapshot_sha256": "<read返回的完整输入摘要>",
  "action_skill": {
    "1": {"c1": {"old": "旧的一档说明", "new": "新的一档说明"}},
    "2": {"c1": {"old": "旧的二档说明", "new": "新的二档说明"}}
  },
  "character_text": {"3": {"old": "旧称号", "new": "新称号"}},
  "custom_ability_string": {"change_skill_white_wolf_gerald": {"old": "旧强化文案", "new": "新强化文案"}},
  "desc_override": {"desc_override_white_wolf_gerald_1": {"old": "旧覆盖文案", "new": "新覆盖文案"}}
}
```

修改技能名称或描述时，每个实际存在的档位都要给出旧值断言；无需变化的档位可以提供相同 old/new。技能文本会一起写入 action_skill、客户端 character_text 和服务端镜像。`character_text` 的 c4–c9 不允许绕过 action_skill 单改。队长名称 c10 同步 character c18。共用技能键或共用 custom 字符串拒绝单角色修改，先明确归属并分配独立键。新加字段、新键、缺失角色与缺失服务端镜像均明确失败。

`prepare_edit` 在内存断言与检查，`stage_edit` 只向新的本仓目录写入。旧服务端文件与视图在暂存前再次核对；未改的压缩叶子按原字节保留。输出 `changeset.json` 使用 `wf-change-set/1`，包含客户端 payload 和 `server_changes` 的完整 JSON 镜像，均有前后 SHA-256。原客户端输入和服务端文件始终只读，输出可交给 `wf deliver`。能力文案的客户端专属属性在每条变更中明示；同步服务端文本行不等于部署。

规则检查拒绝生命值100%以下的恒真条件、称号/技能名/明确引号名称中的“…之核”，以及可证明的重复强化文本。只出现相同效果名称时返回“待验证”，不会把语义猜测当成确定错误。门禁比较编辑前后的问题集合，并跟踪跨字段规则引用的强化键；因此修改 custom/override 导致 action_skill 新增重复也会拒绝。与本次编辑无关的原有问题仍随输出保留。所有字段 old/new 相同且客户端没有实际改动时，prepare_edit 明确拒绝；不会靠重写相同 CSV 的引号产生空操作补丁。

```powershell
python -B -m wf text explain <prepush-224-since.json> --tip 1.4.224 --server-text <历史镜像character_text.json> --rank-text <历史镜像character_text_rank_p5b.json> --output work/m1/text/warnings.json
```

`explain` 对每个稳定 fid 从完整表回读，核对原日志前120字，再保留全文、实际表键/列、输入 SHA-256 和差异片段。历史输入已漂移则标为“待验证”，不声称还原了原警告。退出0仅表示归因过程完成，不表示这些警告已修好。M1 的78条逐项结果见 `docs/m1/text-warnings.md` 与同名 JSON：78条均可解释且均保留“问题”状态，未自动改动玩家文案。
