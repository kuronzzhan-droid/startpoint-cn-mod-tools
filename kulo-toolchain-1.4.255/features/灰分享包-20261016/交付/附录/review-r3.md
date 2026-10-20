# 第三轮独立交付读回复核

**结论：PASS**。独立读取交付ZIP/sidecar/manifest/server-entries，并从固定灰Git ref和我方219来源重新比对；未运行构建、应用脚本、服务器或客户端。

- 正式边 1.4.136→1.4.220：14 包、960 个唯一成员，总 68220884 字节；每包不超过 5 MiB；ZIP CRC、成员唯一性、逐成员 SHA256、sidecar、manifest 和 report 相互一致。
- 恢复终态独立比对：156 个原排除表键、63 个资源与我方 219 一致；21 个训练木桩的客户端与服务端均逐键一致。
- GM：25 个本体表键＋1 个 DSL；30 个最终客户端数字 ID 叶行引用全部属于允许本体表（另含 gm_direct_hits 文本键 1 个）；未分类引用 0，获取途径引用 0。
- 服务端：26 个文件、1438 个操作，逐键预期基线与固定灰 Git ref 一致；48 个 GM 操作只在 8 个本体/注册/使用配套文件，GM 获取操作 0。
- 五重：2074 个客户端叶行及 buff 二进制依赖保留我方终态；原 5 处凉月/碧缺陷修复全部仍取我方。
- 测试服对齐边：1.4.219→1.4.220，22 字节空 ZIP，0 成员，CRC/SHA256/manifest 一致。

本轮既有 prepush 证据已绑定当前 manifest 与全部 ZIP：正式边 ERROR 0／WARN 162，对齐边 ERROR 0／WARN 95，均退出 0、无 allowlist。本审查没有重跑检查器。`report.json` 仅核对锚点和关键数字，不绑定整文件 SHA256，避免后续汇总形成循环绑定。

说明中“GM只带数据”及“零实际获取行”准确：当前来源没有可列出的GM商品／掉落／奖励等行，不虚构剔除项；正文同时保留了既有管理员手工授予、已有武器产生魂珠和线上状态未核实的边界。

## 新账号／默认模板核对

固定灰 `src/data/domains/player.ts:665` 显式调用 `insertPlayerItemsSync(playerId, {})`，`:668` 调用 `insertPlayerEquipmentListSync(playerId, {})`。普通新建、登录建号均调用该默认创建函数；并不枚举 `item_ids`／`equipment_ids` 发全物品或全装备。
管理后台 `newSave` 另可加载管理员预置的 V2 完整模板，再恢复其库存；模板由运行目录中的 `default_save.json` 提供。其线上内容以及历史库存均未读取、未核实，本包不提供或修改模板。逐文件固定 ref 的行号、SHA256 与片段见 JSON。

## 当前产物 SHA256

| 文件 | 字节 | SHA256 |
|---|---:|---|
| `pinball-1.4.136-1.4.220-1-hui-share-20261016.zip` | 5177006 | `b31d498acbd5e3ae3fe402bdaef7b96761a84ee9178bc9ef85596079e816a49d` |
| `pinball-1.4.136-1.4.220-2-hui-share-20261016.zip` | 5177006 | `70dc88c726cdd7ed817316f4cdc5809fd0d37b9cbc623f4848ffe876348b3e5c` |
| `pinball-1.4.136-1.4.220-3-hui-share-20261016.zip` | 5177005 | `0424777d2e75bd2f821ca930e547f810a96c14e6d398570db27d1078e63f636c` |
| `pinball-1.4.136-1.4.220-4-hui-share-20261016.zip` | 5176916 | `56493db3e3e0ac314467fa2c0efbaa15e84d9f7ebd83fbdf6e4cbf03d084cb64` |
| `pinball-1.4.136-1.4.220-5-hui-share-20261016.zip` | 5176910 | `2057357c021aaf8c02262fa672a22a32c005adf5b0a76b39cefce49c6fb16312` |
| `pinball-1.4.136-1.4.220-6-hui-share-20261016.zip` | 5176697 | `ae6370791f7fd5671f583dce4c4e0cba59ae2b21389cd0494ca2e174231ee392` |
| `pinball-1.4.136-1.4.220-7-hui-share-20261016.zip` | 5176513 | `2cf8702d3a32967270dcb418c3730f99a333029e7745f1b74518fb141a9e258e` |
| `pinball-1.4.136-1.4.220-8-hui-share-20261016.zip` | 5175915 | `3045d3c44363a503e952457aca5dcf45e13bc55c3046334da59fc9980dd2b76f` |
| `pinball-1.4.136-1.4.220-9-hui-share-20261016.zip` | 5174959 | `9abd7db241b22681044786ba5003b919dc1bda8c024eee3d3596598d38ba8825` |
| `pinball-1.4.136-1.4.220-10-hui-share-20261016.zip` | 5174395 | `2ba944431cd12ba9cbad1a888d73b369b56b455addf0c345c5fd09d6574dee93` |
| `pinball-1.4.136-1.4.220-11-hui-share-20261016.zip` | 5173417 | `e044ae97a5cb88cda3781809af26a1a0012deda05da5255ffa561e06fda49413` |
| `pinball-1.4.136-1.4.220-12-hui-share-20261016.zip` | 5171334 | `edec39b831b03838763d8ed041262920e857dc212df32d3472233dcff53f4ae1` |
| `pinball-1.4.136-1.4.220-13-hui-share-20261016.zip` | 5163842 | `cb96e44736c4f5d36b865e5cb1cedf0c8679fe06a019643179b3af1ef7d95113` |
| `pinball-1.4.136-1.4.220-14-hui-share-20261016.zip` | 948969 | `3240c748c9f23d4e1a93220de4a2d81865f4266c73d4378a39a913086ada6013` |
| `pinball-1.4.219-1.4.220-1-align-live-local.zip` | 22 | `8739c76e681f900923b900c9df0ef75cf421d39cabb54650c4b9ad19b6a76d85` |

## 边界

- 获取路线通用源码核查见gm-route-review-r3；受管理身份保护的既有手工授予接口仍可识别登记ID。
- 本审查不修改或重跑prepush证据；已核对本轮既有检查结果为ERROR0，并绑定其manifest和ZIP SHA256。
- report只核对锚点与关键数字，不承诺最终report整文件哈希。
- 运行时与历史数据库状态未核实。
