# 五处缺陷修复冲突核对（本轮静态）

灰来源固定为 `224aa2a663b7756fc8a34c0f37f1ae61ad81800c` 的1.4.131–1.4.136八个包；我方为锁定1.4.219终态。五处均取我方。

## 凉月159992：三行、四列

以下行号、列号均从0计数。逐包检查灰131–136携带目标表的版本，目标列一直为空；未发现灰另行修复。

| 表 | 键/子行 | 列 | 灰值 | 我方值 | 结论 |
|---|---|---|---|---|---|
| master/ability/ability.orderedmap | 1599921 / #2 | c67 | ``（空串） | `0` | 取我方213修复 |
| master/ability/ability.orderedmap | 1599921 / #2 | c74 | ``（空串） | `1` | 取我方213修复 |
| master/ability/ability.orderedmap | 1599922 / #2 | c67 | ``（空串） | `0` | 取我方213修复 |
| master/ability/leader_ability.orderedmap | 159992 / #5 | c65 | ``（空串） | `0` | 取我方213修复 |

ability行均126列、leader_ability行均124列；除上列四个字段，三行全部内容相同。1599921的c74是initial_multiply，空串导致倍率0，补1恢复叠层。三处cancelable空串补0是声明字段合法性修复，历史构建器记载其旧读取行为已为0，因此不要将这三列宣传成独立战斗加强。

证据：`D:/WF/out/凉月修复-20261016/build_213.py` 的fix调用和字段说明；`handoff-213/CHANGES.md` 第12–18行说明修复范围，第43–46行记载旧版缺自身叠层、213出现自身攻击×12的历史真机A/B。本轮只核对历史记录和当前源字节，没有重跑真机。

## 碧169978：PNG与atlas必须配对

灰链尾仍携带20条square/thumb等通用UI帧，完全缺少立绘设置页所需的`full_shot_illustration_setting_0/1`。灰131–136携带此atlas的各个包均未补入这两帧。我方217终态atlas恰好包含两条正确帧，PNG解码成功，两个裁剪框均在PNG边界内。

灰PNG尺寸 `[2048, 788]`；我方PNG尺寸 `[999, 500]`。两成员均取我方217，完整SHA和两边AMF帧结构见同名JSON。

逻辑路径：

- `character/cnmod_vyrn_dark/ui/illustration_setting_sprite_sheet.png`（medium_upload）
- `character/cnmod_vyrn_dark/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate`（upload）

证据：`D:/WF/out/碧-1.4.216/build/build_217.py` 第2–5行写明C8004和缺失帧根因，本轮直接解码灰/我方源atlas证实这一结构差异。218针对119998及179982–179986；本轮检查218 ZIP不包含上述碧两成员，故这两处应归因217而非218。本轮未启动客户端，C8004是否在目标APK消失仍为未核实。

## 可重跑与证据

运行 `python 交付/build/audit_defects_220.py`。JSON含逐包历史、灰/我方完整行值、逐列差异、atlas全部帧结构、PNG尺寸/SHA、源脚本SHA与行号摘录。审计不修改源目录。
