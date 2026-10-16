# 1.4.216 交付：碧 169978 + 灰的五重 evil 预载

叠在测试服链尾 1.4.215 上（215 = balance-1016 b7fd0783…）。来源：灰 Ku1o/startpoint-cn-kulo main 87b9b14d（灰 1.4.134→135）+ cc94fcca（灰 1.4.135→136）。

## 一、客户端包（3 个分包，同一版本边）

| 文件 | 大小 | sha256 |
|---|---|---|
| patch/pinball-1.4.215-1.4.216-1-vyrn-character-local.zip | 5175908 | edaddf77cc491ea4923d6dc28c0d3c44dfdfbfa7f2d980f6bbc8dd027d784319 |
| patch/pinball-1.4.215-1.4.216-2-vyrn-character-local.zip | 5173220 | 87dc87f6e81d4bd13117f43f4ac22e006c23d6bb4c4309fe2270408a4c9ac02b |
| patch/pinball-1.4.215-1.4.216-3-vyrn-character-local.zip | 4153658 | 7752602536ad93be637e8154542b7036c0203ff7f1c135c79c6fe5c609946d58 |

- 每包旁有 integrity.json（成员清单、成员 sha、合并过的表与行）。清单条目在 `manifest-entry-1.4.216.json`（chain 三包、archive_integrity 齐全；盒子 manifest 是 CRLF+2 空格，按惯例追加）。
- 共 146 个成员：灰 1.4.135 的 144 个 + 灰 1.4.136 的 2 个。
- 与我方链 131–215 重叠的 39 个成员：
  - 28 个我方没改过（我方字节 = 灰的基线），直接取灰版。其中有凉月 159992 的 21 个美术成员（灰重切了凉月技能图集）、凉月获取台词修正（character_speech 159992，语音路径 a→ally/join）。
  - 11 张表三方合并，0 冲突：10 张只加碧的行（ability 1699781–6、action_skill cnmod_vyrn_dark、character/character_text/character_status 等各加 169978、立绘槽 4 条）；general_boss 只改 mod_fb2_035_evil_w02 / 037_evil_w01 / 039_evil_w02 三行的第 149 列（加 fb2_preload$evil_fixed_green），第 109 列我方 186 的 fb3_buff$entrance 原样保留，表内其余逐字未变。
- 不需要新 APK。
- 构建器：`build/merge.py`（TIP=215 FINAL=1）；与 1009 recut 188–191 同法。

## 二、自检

- prepush --since 1.4.215：ERROR 0 / WARN 96 → 可以推送（日志在 zip 旁 `*.prepush-since.txt/json`）。
- prepush 全量：ERROR 12 / WARN 89，ERROR 全是旧的 40193、8000201–8000211 缺 item_ids.json，与 215 全量逐条相同（215 那份多一条 WARN 是它的服务端副本没合 #35）。
- 灰的碧称号测试 tests/vyrn-character-degrees.test.cjs 4/4。
- 本地服（凉月修复 localsrv=盒子 213 + 214/215 包 + 215 的 149989/149990 两键 + 本包与服务端改动），MuMu-1 com.leiting.wf：
  - 从 1.4.212 下载 16MB 增量到 1.4.216，进主城正常；
  - 碧打开：名字/称号/暗/辅助/立绘正常；玛纳板 2/2 全开正常；
  - 升级：exp 归零后在「等级强化」长按，1→28 级，经验池扣减，服务端全 200；
  - 碧当队长打五重决战超级：战斗正常（队伍太弱 game over，非报错）；
  - 换强队打到第 1 区第 3 波 evil（伊尔考普斯 / devil_commander_evil）约 2 分钟直到清波进下一区，无报错、无卡死。绿炮弹在满屏特效里截图分辨不出，未单独确认。
- 设备已复原：wf 资源回写 212 版 53 个、删除 122 个新增文件（md5 逐个核对 ok=53 bad=0），info.json 回 1.4.212，cache/app 已清；8001/8003 已停。

## 三、服务端改动（全部按键追加，不整文件覆盖；需重启）

键级条目在 `handoff/server-entries/vyrn-server-entries.json`；也可在盒子 assets 副本上跑 `build_server.py <盒子assets> <输出>`（逐文件断言：重序列化与原文一致、目标键原本不存在、其余键逐一未动；保留原换行风格）。

| 文件 | 改动 |
|---|---|
| assets/cdndata/character_rank_p5b.json | +键 169978（客户端 character 行原样） |
| assets/cdndata/character_text_rank_p5b.json | +键 169978（名字/简介/技能文案，已与客户端 action_skill 一致） |
| assets/character_rank_p5b.json | +键 169978 {element 5, name 碧, rarity 5, skill_count 6} |
| assets/mana_node_cnmod.json | +键 169978（41 节点，已核对与客户端 mana_node 表一致） |
| assets/mana_board.json | +键 169978（41 条，客户端 generated 行原样）。213 也改这个文件（+159992），要在盒子当前版上按键合并 |
| assets/degree_character_mod.json | +键 9910090「我不是蜥蜴！」、9910091「巴哈姆特碎片」 |
| assets/character_degree_rewards.json | characters[] 末尾 +{character_id:169978, degree_ids:[9910090,9910091]} |
| src/lib/character-degree-catalog.ts | CHARACTER_DEGREE_CHARACTER_IDS 末尾 +169978；AUTHOR_CATALOG +[169978,[9_910_090,9_910_091]] |
| out/lib/character-degree-catalog.js | 同上两处（编译产物，已在本地服验证） |

- config / .env：无改动。
- 盒子基线：本表按 10-15 22:5x 的盒子 assets 副本核对；部署时请对盒子当前内容再跑一遍 build_server.py 的断言（9910090/91 与 169978 不得已存在）。

## 四、给每个存档和模板发一只碧（交给部署线程执行）

照 1009 凉月的做法（tmp\grant-chars.cjs，只增不减，已有行跳过）。文件：`handoff/grant-vyrn.json`、`handoff/grant-chars.cjs`。

1. 等 8003 无 Established 连接；备份 `.database`（停服快照）和 `config\tester-template.json`。
2. Stop-ScheduledTask StarPointTestServer，确认 node 退出。
3. 把两文件放到 `C:\startpoint-test\tmp\`，在 `C:\startpoint-test` 下跑：`node tmp\grant-chars.cjs tmp\grant-vyrn.json`。输出每个 player_id 的 {chars,nodes,bonds}，新补的号应为 {1,41,2}。
4. 模板 `config\tester-template.json`：
   - data.tables.players_characters.rows 追加 1 行（列序见该表 columns）：id 169978, entry_count 1, evolution_level 1, over_limit_step 4, protection 0, join_time/update_time 同模板凉月行, exp 379988, stack 0, mana_board_index 2, player_id 1, 其余 null；
   - players_characters_mana_nodes.rows 追加 41 行 [value, 0, 169978, 1]（value 取 grant-vyrn.json 的 mana_nodes）；
   - players_characters_bond_tokens.rows 追加 2 行 [1,2,1,169978]、[2,2,1,169978]（按 columns 顺序 mana_board_index,status,player_id,character_id）；
   - summary.rowCount += 44（导入器校验行数）。
5. Start-ScheduledTask，读回：一个老号、一个新建号各查 players_characters id=169978（exp 379988、over_limit_step 4）、mana_nodes 41 条、bond_tokens 2 条。

碧满级突破 4 后，称号 9910090/91 由现有发放流程在木桩练习补领（灰的称号逻辑，未改）。
