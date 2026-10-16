# 工具与产物位置(手写)

脚本清单(首行说明)自动生成在 [gen-tools.md](gen-tools.md)。

| 东西 | 位置 | 备注 |
|---|---|---|
| builder 脚本(平衡、木人、深渊武器、五重…) | `D:\WF\bughunt-20261014\builder\*.py` | 一个脚本 = 一版增量包,docstring 首行写「叠加在 1.4.N 上」。视图版本由环境变量 `WF_TIP` 选(默认值写在各脚本里),额外 zip 用 `WF_EXTRA_ZIPS`(`;` 分隔) |
| builder 公共库 | `builder/base149.py`、`live149.py`、`p192_common.py` | **坑**:`live149.py` 把 `wf_dsl`、`wf_character_revision` 等从一个旧 Claude 会话的 scratchpad(`…\Temp\claude\…\0f92a444…\scratchpad\oldrepo_modtools`)import。那个目录被清掉,builder 就全部跑不起来 |
| 敌等级缺口检查 | `builder/level_gap_check.py` | `python level_gap_check.py [--json out.json] [--quiet]`,退出码 1 = 有缺口(U_3be147) |
| 即时道具等级行检查 | `bughunt-20261014/out/c8601_fix_verify.py`,`builder/bh_items.py` | C8601;报告 `out/c8601_fix_report.md` |
| 木人变体(eii/dii 首个踩坑点) | `builder/dummy_variants.py` | 产 `pinball-1.4.179-1.4.180-1-dummy-variants-local.zip` |
| 补丁包(生效中) | `D:\WF\startpoint-cn-kulo\assets\asset-patch\active\`(约 200 个 zip + candidates/) | 只读。bughunt 副本在 `bughunt-20261014\repo\assets\asset-patch\active` 和 `boxtree\…` |
| 补丁包(审计/历史) | `startpoint-cn-kulo\assets\asset-patch\audit\` | 按「功能-版本」命名 |
| 服务端 bug 复现 | `D:\WF\bughunt-20261014\findings\scripts\repro_f01..f22.cjs` + `_harness.cjs` | 汇总 `findings/server_findings.json`、`server_hunches.md`;分数缩放 `codex_score_scale_report.md` |
| 服务端修复补丁(待合) | `bughunt-20261014\handoff\000{1,2,3}-*.patch` | 联机 EXP、单人清关容错、单人分数缩放只限可联机关 |
| 五重 layer0 模拟/门禁 | `out\性能与漏洞审计-20261009\layer0-sim\fb_layer0_{sim,gate}.py` | 结论见同目录 `五重layer0数据侧门禁结论-20261009.md` |
| 性能与漏洞审计报告 | `D:\WF\startpoint-cn\out\性能与漏洞审计-20261009\` | 总报告.md、server-*.md、apk-patches.md、client-perf.md |
| 服务端自带工具/测试 | `D:\WF\startpoint-cn-kulo\tools\*.cjs`、`tools\fantasy-gauntlet-mod-tools\` | wf-mod skill 的工具在后者 |
| 反编译 AS3 | 见 [client.md](client.md) | — |

## 坑

- builder 脚本都是「在某个视图上叠加」,`WF_TIP` 不对就会在错的基线上出包,出包前先看 docstring 写的是哪一版。
- 不要拿 store 当官方基线;官方分位要用弹国服 restored 或 bundle(memory: wf-official-baseline-not-store)。
- 改补丁包是整文件投递,本地少键 = 删行(发布键闸门)。
