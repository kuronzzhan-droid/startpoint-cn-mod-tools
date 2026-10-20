# 平衡表 1016 子任务说明（给子代理）

你在做 World Flipper 国服私服的角色平衡数据改动。只写 `D:/WF/out/平衡1016/chars/` 下你负责角色的文件，别的地方一律只读。
不要调用任何 mcp__hearthbot__ 工具；不碰模拟器、服务器、git、kulo 工作区、E:\tool。Windows 上用 `python`（不是 python3），设 `PYTHONIOENCODING=utf-8`。回复用中文。

## 输入
- 平衡表（已按截图逐行核对行归属）：`D:/WF/out/kulo-patch-toolkit/research/balance_sheet_20261016_raw.md`。只做你负责的角色块。「进化技能」行作者拿来写技能改动，按技能处理（两档技能 _1/_2 都改，除非文字明确只说进化）。
- 规则：表为准（能力行写目标值）；数值写不进去时选最接近表意的实现并在 md 里写明；不要顺手改表里没提的东西。
- 框架：`D:/WF/out/平衡1016/fw.py`（读它）。`F.ab(key)/F.le(key)` 返回可变行（ability 126 列 / leader 124 列），直接改元素即可；`F.cas_replace(key, [(old,new)])` 改覆盖文案；`F.skill_text(cid, code, [(old,new)])` 同步改技能描述（action_skill 两档 + character_text + 服务端镜像）；`F.dsl(program)` 取可变 DSL 树；`F.rows(lp,key)` 改任意表；`F.log("...")` 写一句中文改动说明（会进玩家看的改动清单，写清旧值→新值）。
- 看角色现状：`cd D:/WF/out/kulo-patch-toolkit/cursed_abyss/build; export WF_TIP=206; export WF_EXTRA_ZIPS="$(cat D:/WF/out/十项收尾-20261015/extra_zips.txt);D:/WF/out/十项收尾-20261015/patch/pinball-1.4.211-1.4.212-1-ten-items-local.zip"; PYTHONIOENCODING=utf-8 python dump_char.py <cid>`（解码后的队长/能力行 + 玩家看到的 OVR 文案）。参考已有改法：同目录 balance_1015.py、balance_1014.py、balance_1012.py、rolf_moon_skill_206.py、rolf_direct_104.py（DSL 改倍率/伤害类型的写法）。
- 列位与枚举：同目录 layout.py（wf_describe 的 enum_map/col()）；ability 值列常见 c113/c114（min/max，单位 1/1000%，即 10000=10%），持续块阈值 c100/c101、次数上限 c102，冷却 c35（帧，60=1秒），触发 c97 等；以 dump 的解码为准逐列核对。
- 客户端行为查 `D:/WF/startpoint-cn/out/codemap/README.md`（rg 检索），反编译在 `D:/WF/decompile-complete-20261014`。记忆卡在 `~/.claude/projects/D--WF-startpoint-cn/memory/`：伤害类型与 buffTargetAs 见 wf-dsl-damage-attribution-bufftargetas.md、wf-ability-damage-families.md；固有层数上限见 wf-unique-cap-none-trap.md、wf-acunique-value-is-stack-count.md；文案规则见 wf-leader-override-text-rules.md、wf-skill-enhance-text-rule.md、wf-no-hplow-text-discipline.md。「技能伤害改为能力伤害结算」= 判定区/根头伤害归属改 2（能力），参照风巨蜥 149998 的写法（它是 102 = 完整能力伤害，需要 damage-type-rules-v1 客户端能力，现行 v33 已带；跟它保持一致）。

## 产出（每个角色一份）
1. `chars/c<cid>.py`：`def apply(F):` 里完成该角色全部改动。每处改动前 assert 旧值（锁住现状），改后 F.log。文案（OVR / 技能描述）同步改成新数值，格式跟原文一致。
2. `chars/c<cid>.md`：逐条列「表里怎么写 → 改了哪张表哪个键哪一行哪几列（旧→新）→ 游戏内文案改成什么」，以及任何不得不解读或做不到的地方（一句话说原因和你的处理）。
3. 自检：`cd D:/WF/out/平衡1016; PYTHONIOENCODING=utf-8 python check.py c<cid> ...`，PROBLEMS 必须为「无」，前后对比要和表一致。

最后回报：每个角色一两行结论 + 所有需要作者拍板的疑点。
