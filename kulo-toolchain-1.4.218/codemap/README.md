# WF 代码地图(codemap)

给 Claude / Codex / Antigravity 共用的查找索引。只是查找辅助,不是手册。位置:`D:\WF\startpoint-cn\out\codemap\`(out/ 不入库,别提交)。

## 先看哪页

| 问题 | 页 |
|---|---|
| 改某张表游戏里没变化 / 要同改哪些表 / C8601、U_3be147、C7050 | [data-tables.md](data-tables.md) |
| 客户端某功能在哪个 AS3 类 | [client.md](client.md) → [gen-client-classes.md](gen-client-classes.md) |
| 某张 master 表被哪些客户端类读 | [gen-client-master-tables.md](gen-client-master-tables.md) |
| 服务端某接口在哪个文件、写哪个库模块 | [gen-server-routes.md](gen-server-routes.md) |
| 服务端持久化机制、联机、测试服专属补丁 | [server-notes.md](server-notes.md) |
| 服务端环境变量 | [gen-server-env.md](gen-server-env.md) |
| 服务端读哪些 JSON | [gen-server-json.md](gen-server-json.md) |
| builder 脚本、补丁包、检查脚本、复现脚本在哪 | [tools.md](tools.md) → [gen-tools.md](gen-tools.md) |

`gen-*.md` 由脚本生成,别手改;其余是手写的坑。

## 源树(全部只读)

| 名称 | 路径 |
|---|---|
| 客户端反编译 AS3 | `D:\WF\_archive\kept\弹国服-tools-and-decompile\scripts` |
| 补全中的反编译副本 | `D:\WF\decompile-complete-20261014`(别改) |
| 服务端(kulo) | `D:\WF\startpoint-cn-kulo\src` |
| 测试盒服务端快照(盒子专用补丁只在这里) | `D:\WF\bughunt-20261014\boxtree\src` |
| bug 狩猎工作区 | `D:\WF\bughunt-20261014`(builder/、findings/、handoff/、out/) |
| 审计报告 | `D:\WF\startpoint-cn\out\性能与漏洞审计-20261009\` |

## 重新生成

任何工具都能跑,只依赖 Python 标准库,约 5 秒:

```bash
python D:\WF\startpoint-cn\out\codemap\gen_codemap.py
```

只跑一部分:在后面加 `client`、`server` 或 `tools`。本机 `python3` 是商店占位程序,要用 `python`。
源路径写在脚本顶部的常量里(`AS3`、`KULO`、`BUILDER`、`PATCH_ACTIVE`),换源树改这几行即可。

## 查找习惯

- 先 `rg` 本目录,命中后按 `路径:行号` 去源树读。out/ 可能被 ignore 规则跳过,所以带 `-uuu`:

```bash
rg -n -uuu -g "*.md" "C8601|U_3be147|action_skill" D:\WF\startpoint-cn\out\codemap
```

- 错误码先查 [data-tables.md](data-tables.md) 顶部的「错误码一行速查」,每行字段齐全,单行命中即可用。
- 生成页里的行号是生成时刻的;源码改过就重跑脚本。
- 手写页的结论多数来自 Claude memory(`C:\Users\12101\.claude\projects\D--WF-startpoint-cn\memory\`),细节去那里搜对应卡片。
