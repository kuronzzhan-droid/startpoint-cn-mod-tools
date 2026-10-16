# 服务端 JSON 新增条目（角色超限 1.4.207 候选）

按条目合并到盒子自己的文件，保留盒子的换行风格和测试专用条目。参考整文件在 `server/` 下（基于 kulo 工作区 + 1.4.206 的 character_text），只用来核对，不要整文件覆盖。

| 文件 | 动作 |
|---|---|
| `assets/cdndata/character_text.json` | 只改 `111183` 第 0 行下标 [9]（日珥粉碎＋＋ 的说明，文本见设计说明 2.2）。游戏内显示读的是 action_skill，这里只是保持一致 |
| `assets/mission_char_awake_cnmod.json` | 新增键 `1111831`–`1111834`（与客户端 character_awake_mission 同行） |
| `assets/mission_char_awake_reward_cnmod.json` | 新增键 `1111831`–`1111834`（`1111831` 的 target_progress = 120） |
| `assets/character_awake_extension.json` | 新增 `111183`：第二张盘能力槽 4/5/6 联动觉醒 1 |
| `assets/item_ids.json` | 追加 `10000320` |
| `assets/item_lookup_cnmod.json` | 新增 `"10000320": "超限结晶"` |
| `assets/score_reward_cnmod.json` | `12100088`（终始之龙）末尾追加 `{"position": 4, "name": "", "type": 1, "id": 12199320, "rarity": 0.25}` |
| `assets/rare_score_reward_cnmod.json` | 新增 `12199320`: `[{"name": "", "type": 0, "rarity": 1.0, "id": 10000320, "count": 1}]` |
| `assets/character_overlimit.json` | 新文件，随代码补丁一起（format-patch 里已包含） |

代码补丁：`server-patch/0001-feat-server-character-over-limit-to-level-120-for-li.patch`。
打到测试盒快照时 `src/routes/api/exBoost.ts` 第二处上下文不同，改用 `server-patch/box-only-exBoost.diff`（同样是一行替换）。改完需要重新编译 out/。
