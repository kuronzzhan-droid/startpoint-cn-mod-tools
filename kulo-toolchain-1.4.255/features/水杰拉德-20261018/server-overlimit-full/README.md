# 服务端：水杰拉德全程超限（配 v35h，作者 10-19「开修」）

1. `src/lib/character-overlimit.ts` 打 `character-overlimit-full-route.diff`（基于 serverfix-39 = 盒子代码），重新编译 out/。
   - 新配置项 `full_route_characters`：名单内角色第 1–4 次突破也只收超限结晶 10000320 + extra_costs（悖论之核），不收重复角色；第 5–8 次照旧。
2. `assets/character_overlimit.json` 追加 `"full_route_characters": [129989]`（按键合并，其余不动）。
3. 重启。客户端须 v35h（数据键 `wfx_overlimit_full_129989=1` 随下一个数据包）；旧客户端会在第 1–4 次照官方列破星结晶，服务端会拒（Attempted to use invalid item），不崩。
