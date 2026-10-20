# 第三轮 GM 武器获取边界审查

固定灰 1.4.136 本地源码和 assets；我方 1.4.219 全部非 asset-patch JSON、131–219 CDN 终态和未修改的可定位基础获取表。只读静态审计；未运行服务器、客户端或网络。

固定灰 ref：`224aa2a663b7756fc8a34c0f37f1ae61ad81800c`。服务端扫描 183 个 JSON，解析失败 0；我方 CDN 终态 1180 个成员，其中可解码 69 个；额外扫描未修改的基础获取表 1817 张。

## 结论

- GM 本体、魂珠、状态、能力引用之外，未发现当前输入数据中的 GM 商店、掉落、奖励、任务、兑换、邮件或礼包获取行；排除明细为零，不构造不存在的行。
- 固定灰源码的普通/宝物/星粒/活动/领主币商店读取显式商品表；getShopItemSync 不用 item_ids/equipment_ids 自动生成商品。武器卡池使用显式 gacha.pool。
- equipment_ids 中注册 GM 不会扩展五重诅咒掉落：候选固定为 5910101..5910129，再与注册表求交集；5990001..6 不在候选中。
- item_ids/equipment_ids 是注册/校验数据，同时让既有管理后台可识别这些 ID。已有管理接口手工给道具/发送附件可显式授予 GM；这是需管理员操作的既有能力，不是新邮件/礼包条目或玩家正常获取。
- equipment_dissolve.generate_ability_soul 和升级/分解会在已持有该 GM 武器时产出同 ID 魂珠；它们要求已持有武器，属于本体正常使用配套，不能从空账号生成第一把 GM。item_sale 为出售已有魂珠换玛纳，不是买入。
- 普通新建账号经 insertDefaultPlayerSync 显式初始化空物品与空装备，并不枚举 item_ids/equipment_ids；管理后台 newSave 可另恢复管理员预置的 V2 默认模板。此运行目录模板和历史库存未读取、未核实，本包不提供或修改模板。
- 未发现获取行与正常内容混在一行且不可拆分的情况。
- 本审计不能证明线上数据库没有历史GM附件/库存，也不核实运行时配置；这些属于未核实，包内不新增任何GM获取条目。

## 新账号／默认模板核对

固定灰 `src/data/domains/player.ts:665` 显式调用 `insertPlayerItemsSync(playerId, {})`，`:668` 调用 `insertPlayerEquipmentListSync(playerId, {})`。普通新建、登录建号调用同一默认函数，注册 ID 不会自动授予全物品或全装备。
管理后台 `newSave` 另可加载管理员预置的 V2 完整模板，再恢复其库存；模板来自运行目录中的 `default_save.json`。线上模板、历史邮件及库存均未读取、未核实，本包未提供或修改模板。固定 ref 代码位置和 SHA256 记录在下方源码证据与 JSON 中。

## GM 本体服务端行（并非商品/奖励）

| 文件 | 键 / ID | 解释 |
|---|---|---|
| `assets/equipment_dissolve.json` | `5990001–5990006` | 已持有武器升级/分解产魂珠；正常使用配套 |
| `assets/equipment_element.json` | `5990001–5990006` | 属性登记 |
| `assets/equipment_ids.json` | `5990001–5990006` | 装备注册及后台附件校验；五重只与固定诅咒候选池求交 |
| `assets/equipment_lookup.json` | `5990001–5990006` | 名称/稀有度/分类 |
| `assets/equipment_max_level.json` | `5990001–5990006` | 最大觉醒等级 |
| `assets/item_ids.json` | `5990001–5990006` | 魂珠注册及后台道具/附件校验 |
| `assets/item_lookup_cnmod.json` | `5990001–5990006` | 魂珠文本 |
| `assets/item_sale.json` | `5990001–5990006` | 出售已有魂珠换玛纳；不是购买 |

## 客户端终态 GM 行

| 表 | 键 | 引用数 |
|---|---|---|
| `master/item/equipment.orderedmap` | `5990001–5990006` | 6 |
| `master/item/item.orderedmap` | `5990001–5990006` | 6 |
| `master/item/equipment_status.orderedmap` | `5990001–5990006` | 12 |
| `master/ability/ability_soul.orderedmap` | `5990001–5990006` | 6 |

## 刻意不收入的 GM 获取途径行

当前输入中未发现可列出的 GM 获取行，故实际排除行数为 **0**。逐类扫描的空结果记录在 JSON；不能把武器本体/魂珠注册表伪报为商品或奖励。

## 通用代码入口核对

以下均为固定灰 ref 的源码行号；完整片段及 SHA256 保存在同名 JSON：

- `src/lib/assets.ts`：36, 38, 722, 727, 731, 796, 802, 806, 1030
- `src/lib/content-master.ts`：21, 31, 33, 51
- `src/lib/gacha.ts`：149, 155, 466
- `src/multi/five-boss/rewards.ts`：86, 87, 111, 113
- `src/routes/api/exchange.ts`：13, 15, 50, 51, 59, 110
- `src/routes/api/equipment.ts`：114, 134, 135, 164, 166, 224, 225, 246
- `src/routes/api/sell.ts`：6, 12, 52, 114, 181, 244
- `src/lib/item-sell.ts`：3, 47
- `src/routes/web_api/mail.ts`：3, 30, 31, 123, 155, 161, 226
- `src/routes/web_api/player.ts`：473
- `src/lib/management-auth.ts`：68, 78, 148, 157, 162, 177, 181
- `src/cn-server.ts`：163, 287, 451
- `src/routes/api/mail.ts`：2, 11, 59, 90, 91, 92, 110, 111, 113, 117, 119, 121, 138, 139, 188, 189, 190, 203, 302
- `src/data/domains/player.ts`：616, 665, 668
- `src/routes/cn/tool.ts`：4, 5, 137, 140
- `src/routes/api/tool.ts`：4, 65
- `src/lib/player-login.ts`：5, 220
- `src/routes/web_api/server.ts`：759, 763, 771
- `src/data/defaultSave.ts`：13, 46, 52, 55
- `src/data/domains/account.ts`：178, 186
