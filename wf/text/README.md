# 角色文本 API 与命令

`TextWorkspace(view, server_path, rank_path)` 以只读视图统一读取角色三档 `action_skill` 的 c0/c1、关联 `custom_ability_string`、`desc_override`、完整 `character_text` 与两个服务端镜像（`character_text.json`、`character_text_rank_p5b.json`）。关联既按角色/技能代码的客户端键约定，也按该角色能力和队长技引用的字符串键查找。没有觉醒档时不虚构第三档。

称号使用零基 **c3**，即第四个 CSV 单元格；c2 是长介绍。`wf_wiki_catalog.character_entry` 和 `wf.chars.support.table_rows.character_text_row` 均给出同一映射。技能镜像为 c4/c5、c6/c7、c8/c9。能力文案与覆盖文案在 `custom_ability_string` 中，服务端 `character_text.json` 没有能力文本字段，因此不会向该 JSON 塞入不存在的列。

```powershell
python -B -m wf text read 149999 --tip 1.4.224 --server-text <只读character_text.json> --rank-text <只读character_text_rank_p5b.json> --output work/m1/text/149999.json
python -B -m wf text check 149999 --tip 1.4.224 --server-text <只读character_text.json> --rank-text <只读character_text_rank_p5b.json>
python -B -m wf text edit work/m1/text/edit.json --tip 1.4.224 --server-text <只读character_text.json> --rank-text <只读character_text_rank_p5b.json> --output work/m1/text/edit-1 --id text-1 --name 文本同步 --to-version 1.4.225 --slug text-sync --created-at 2026-10-17
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

修改技能名称或描述时，每个实际存在的档位都要给出旧值断言；无需变化的档位可以提供相同 old/new。技能文本会一起写入 action_skill、客户端 character_text 和服务端镜像。`character_text` 的 c4–c9 不允许绕过 action_skill 单改。队长名称 c10 同步 character c18。共用技能键或共用 custom 字符串拒绝单角色修改，先明确归属并分配独立键。编辑必须显式提供两个服务端文件，任一文件缺失都失败；它们是稀疏表，角色可只存在于一个镜像，工具更新所有已存在条目，不向另一表新增角色。两个镜像都没有该角色时失败。

`prepare_edit` 在内存断言与检查，`stage_edit` 只向新的本仓目录写入。两个服务端文件都进入读取快照，并在暂存前再次核对；未改的压缩叶子按原字节保留。JSON 只替换该角色首行被编辑列的字符串 token，原键序、缩进、LF/CRLF、未改列的转义形式和附加行全部按原字节保留，不整文件重排。输出 `changeset.json` 使用 `wf-change-set/1`，包含客户端 payload 和两个 `server_changes` 完整 JSON 镜像，均有前后 SHA-256；无该角色的镜像原样输出，前后摘要相同。原客户端输入和服务端文件始终只读，输出可交给 `wf deliver`，交付时须提供服务端基线核验两个前置摘要。能力文案的客户端专属属性在每条变更中明示；同步服务端文本行不等于部署。

规则检查拒绝生命值100%以下的恒真条件、称号/技能名/明确引号名称中的“…之核”，以及可证明的重复强化文本。只出现相同效果名称时返回“待验证”，不会把语义猜测当成确定错误。门禁比较编辑前后的问题集合，并跟踪跨字段规则引用的强化键；因此修改 custom/override 导致 action_skill 新增重复也会拒绝。与本次编辑无关的原有问题仍随输出保留。所有字段 old/new 相同且客户端没有实际改动时，prepare_edit 明确拒绝；不会靠重写相同 CSV 的引号产生空操作补丁。

```powershell
python -B -m wf text explain <prepush-224-since.json> --tip 1.4.224 --server-text <历史镜像character_text.json> --rank-text <历史镜像character_text_rank_p5b.json> --output work/m1/text/warnings.json
```

`explain` 对每个稳定 fid 从完整表回读，核对原日志前120字，再保留全文、实际表键/列、输入 SHA-256 和差异片段。历史输入已漂移则标为“待验证”，不声称还原了原警告。退出0仅表示归因过程完成，不表示这些警告已修好。M1 的78条逐项结果见 `docs/m1/text-warnings.md` 与同名 JSON：78条均可解释且均保留“问题”状态，未自动改动玩家文案。

M2.1 接入面板文案规范全部 10 节、58 条规则：`wf text rules` 查看依据和覆盖边界，`wf text audit-standard --tip 1.4.N --output work/m2/text/audit.json` 全表只读核查，`wf check text <读取快照.json>` 使用相同规则。47 条部分检查仅覆盖列举写法，11 条保留人工语义核对；无命中不表示尚未核对的数据、条件和效果已满足。技能 c0 按名称约束检查并保留升级后缀，c1 各档比较非数值写法，允许持续时间、层数等数值变化。

M5.1 将规则目录升级为 1.2.0、60 条（49 条部分检查、11 条人工核对）。读取快照新增可选 `override_slots`：按角色引用的队长/能力表和**槽行 c0** 精确关联 `desc_override_<c0>`，每条关联保留表、键、行号、角色 ID 和 c1 主位限制。全表审计也扫描没有角色归属的槽和覆盖键，不从 `_leader`、`_ls`、`_1`–`_6` 后缀猜槽位；139985 的 `desc_override_lady_android_halloween` 因此会纳入。旧快照仍可读取，但缺少槽位元数据时，依赖主位/能力归属的判断保留待验证。

所有覆盖串禁止「自身为队长时」和 `X%（觉醒后 Y%）` 双值；词条低级/满级列不是觉醒前后。整槽能力行 c1 都是 `false` 时，每个非空行必须精确带 ` <icon id='main'>  `（前 1、后 2 个半角空格），字面「Ⓜ」不合法。混合主位/非主位行的槽不会被强制给每行加图标，但已有图标仍核对格式。禁止用「／」把两条效果压在一行；属性/角色名枚举、规范指定的六属性结算列表和技能描述的官方分隔符不按压行报错。压行的自动判据仅覆盖分隔符两侧均有明确效果词或增减数值的写法。

`draft build` 在编译成员汇总后重新解码实际输出表，再执行同一套覆盖文案规则，不信任保存的旧检查结果。修改的覆盖串或槽位变化新引入的问题阻断；历史无关问题随草稿结果保留为非阻断警告。作者依据与 SHA-256 记录在规则目录的 `author_rules_sources`。1.4.227 起的逐版本只读审计见 [M5.1 文案审计](../../docs/m5/m51-text-audit.md)，未修改原文。

`wf text check`、`wf check text` 和全表核查都按角色键计算 p5b 整行覆盖 base 的生效文本，与客户端 character_text c5/c7/c9 对照。差异报 `text.server_effective` 问题；缺少任一完整服务端镜像为待验证，不把未加载镜像当作无差异。详见 [面板文案规则与只读核查](../../docs/m2/text-standard.md)。
