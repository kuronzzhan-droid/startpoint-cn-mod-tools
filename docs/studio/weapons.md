# 独立武器工坊后端接口

武器接口以 `/api/studio/weapons` 为前缀，不需要 quest。读取使用编辑台当前视图和显式配置的本机服务端输入；编辑写入 `work/studio-drafts/weapons/<武器ID>/changeset.json`，保存、生成和导出复用现有编辑台机制。`WF_STUDIO_DRAFTS` 或启动时的草稿根覆盖同样生效。

所有 ID 都用十进制字符串。所有 POST 都要求 `Content-Type: application/json` 和当前会话的 `X-WF-Studio-Token`；Host、Origin、Sec-Fetch-Site 沿用编辑台守卫。失败通常返回 HTTP 400 和 `{"error":"原因"}`；鉴权失败为 403，详情不存在为 404。写入错误不会留下部分草稿。这里的 `runtime: "未执行"` 表示未做设备实测。

## 1. 全局列表

`GET /api/studio/weapons?q=剑&element=1&rarity=5&limit=200`

| 参数 | 语义 |
| --- | --- |
| `q` | ID、名称、内部代码包含匹配，不区分大小写 |
| `element` | 服务端装备分类，整数 -1..5；不是魂珠可装备属性限制 |
| `rarity` | 整数 1..5 |
| `limit` | 默认 200，范围 1..2000；筛选后截断 |

每个参数最多出现一次。省略属性或稀有度表示不过滤，响应示例：

```json
{
  "schema": "wf-studio-weapons/1",
  "version": "1.4.254",
  "items": [{
    "id": "5010005", "name": "示例武器", "rarity": 5,
    "element": 1, "icon": "item/example_weapon", "soulId": "5010005",
    "isMod": false, "hasEnhancement": true, "hasAwakening": true
  }],
  "total": 1, "count": 1, "limit": 200,
  "notes": ["属性来自服务端 equipment_element 分类，不推导能力的属性限制。"]
}
```

`total` 是筛选后的总数，`count` 是返回条数。图标是逻辑路径，可使用现有 `/api/boss/icon.png?path=<URL编码后的逻辑路径>` 读取，该图标接口不依赖副本。

`isMod` 由官方装备基线判断是否新增键：新增 true，官方已有 false，基线不可用 null。修改官方武器不会变成“新增 MOD”。`element` 在本机服务端输入缺失时为 null。`hasEnhancement` 表示存在强化本体，`hasAwakening` 取装备原生最大觉醒等级；这些字段不代表实际运行验证。

列表读取当前基线；尚未生成交付的武器通过第 5 节的草稿列表发现，再用详情接口读取候选状态。

## 2. 武器详情

`GET /api/studio/weapons/5010005`

返回列表卡片字段以及以下详情字段；如果该武器有独立草稿，返回校验输入哈希后的重放候选。示例展示摘要字段（实际响应还含完整原生行）：

```json
{
  "schema": "wf-studio-weapon/1", "version": "1.4.254",
  "id": "5010005", "weaponId": "5010005", "subjectKind": "weapon",
  "curves": {
    "base": {"count": 2, "first": {"level": 1, "hp": 100, "attack": 20},
             "last": {"level": 5, "hp": 200, "attack": 40}},
    "enhancement": {"count": 0, "first": null, "last": null}
  },
  "awakening": {
    "maxLevel": 5, "serverInputAvailable": true,
    "materialId": null, "material": null, "clientMaterial": null,
    "rarityOverride": null, "standardMaterials": []
  },
  "references": {"shops": [], "gacha": []},
  "changeset": null, "status": {"state": "clean", "label": "无草稿改动", "changes": 0},
  "checks": [], "runtime": "未执行"
}
```

| 字段 | 内容 |
| --- | --- |
| `equipment` | 本体记录，包含 `row`、表路径及来源 |
| `soul_item` / `ability_soul` | 通过本体 c10 关联魂珠 item 与能力魂记录，二者 ID 不假定与武器相同 |
| `equipment_enhancement` / `equipment_enhancement_ability` | 强化本体与强化能力记录 |
| `base_status` / `enhancement_status` | 完整基础曲线和强化曲线；本接口 `status` 单独表示草稿保存状态 |
| `curves` | 两类曲线的点数及首尾 HP/攻击 |
| `enhancement_chain` | 强化商品阶段、原生行、材料、普通货币、等级范围 |
| `materials_to_120` / `user_costs_to_120` | 沿用现有模型的到 120 级材料/普通货币累计 |
| `awakening` | 本机专用材料限制、稀有度覆盖、客户端材料文案和原生通用材料行；缺少输入时显式标注 |
| `references` / `referenceCoverage` | 商店及客户端/服务端装备卡池引用及扫描范围；权重 0 的条目仍是引用，不等于开放获取 |
| `changeset` / `status` / `checks` | 草稿、保存状态及规则结果；未设置魂珠属性时包含继承提醒 |

记录类型字段包含 `table`、`path`、`row`、`source`；找不到关联行时为 null。前端须处理 null，不推断其已经通过验证。

商店引用扫描客户端的领主币商店、活动道具商店和强化商店，以及本机服务端的 `boss_coin_shop`、`event_item_shop`、`event_item_shop_rank_p5b`、`general_shop`、`star_grain_shop`、`treasure_shop`、`equipment_enhancement_shop` JSON。服务端来源是否可用逐个列在 `referenceCoverage.serverShops`；false 表示缺少输入，不代表没有该类商店。羁绊兑换通过已核实的 `general_shop.json` 奖励关系关联，不猜其他客户端商店列位。

引用中的 `scope` 区分 client/server；服务端记录还带 `source`、`path`、`product`、`matches`，活动商店带 eventType/eventId。一个商品的客户端记录、服务端镜像和附加表各自返回证据，不可直接用引用条数作为去重后的商品数。

## 3. 克隆武器

`POST /api/studio/weapons/clone`，请求体直接传 BOSS 版的 `weapon` spec，不再包裹 operation/weapon：

```json
{
  "sourceWeapon": "5010005",
  "name": "工坊新武器", "description": "新武器说明",
  "soulDescription": "魂珠说明", "soul_elements": "all",
  "hpMultiplier": 1.2, "attackMultiplier": 1.1
}
```

支持原有 `id`、`icon`、`enhancedIcon`、`abilities`、`enhancementProducts`。图标沿用既有武器/魂珠配对和加载资源检查，能力编辑沿用武器专用列位及客户端能力检查。`id` 省略时按既有 5950001..5999999 分配；会检查客户端表、本机服务端镜像、BOSS 草稿和独立武器草稿的占用。`enhancementProducts` 通常省略并自动分配。

`soul_elements` 可传 `"all"`、`"auto"` 或 1..6 个不重复的整数 0..5，例如 `[0,3]`。它们分别写 item[12] 为 `0,3,2,1,4,5`、`30`、逗号分隔列表。省略时继承母本并返回 `weapon.soul-elements-inherited` 非阻断提醒。`soulDescription` 写 item[5]，可选；未给时继承母本。`description` 是武器及强化武器说明。

响应摘要示例：

```json
{
  "ok": true, "weaponId": "5950001", "subjectKind": "weapon",
  "allocation": {
    "sourceWeapon": "5010005", "id": "5950001",
    "enhancementProducts": ["595000101"], "soul_elements": "all"
  },
  "status": {"state": "dirty", "label": "草稿 1 项 · 未保存", "changes": 1, "savedAt": null},
  "checks": [], "runtime": "未执行"
}
```

实际响应还含 `change`、`changeset`、逐叶 `changes` 和 `serverTargets`。`allocation` 保留原请求字段并补齐 ID。追加 `?preview=true` 可预检，不写草稿、不占用 ID；预检响应包含候选 allocation/changes/checks，但不含 change/changeset/status，正式提交可能获得不同 ID。

## 4. 编辑强化材料

`POST /api/studio/weapons/5950001/materials`

```json
{
  "stages": [{
    "productId": "595000101",
    "costs": [{"itemId": "2370099", "amount": 10}],
    "userCost": {"type": 2, "amount": 100}
  }]
}
```

路径给出武器 ID；请求中可省略 `id`，如传入必须相同。`productId` 必须属于该武器，材料必须在当前视图存在；商品阶段 ID 使用详情或克隆 allocation 返回值。`userCost` 缺省保留、null 删除，type 只接受 1/2。客户端行和服务端强化商品镜像同步编译。可以直接编辑基线武器，也可以继续编辑同 ID 的克隆草稿，不要求所属 BOSS。支持 `?preview=true`。

响应结构同克隆，`allocation` 为 null。一个武器的全部操作保存为同一个可重放 change；后续操作 revision 递增，重放会重新检查原输入哈希。

## 5. 本次修改、保存、生成交付

| 方法及路径（相对前缀） | 用途 |
| --- | --- |
| `GET /drafts` | 返回 `{"subjectKind":"weapon","drafts":[...]}`，列表条目沿用 `characterId` 容器字段，值是武器 ID |
| `GET /drafts/<id>` | 返回 weaponId、兼容字段 characterId、subjectKind、changeset、status、actions |
| `POST /drafts/<id>/save`，body `{}` | 校验并保存，返回 `{"status":{...}}` |
| `POST /drafts/<id>/changes/<changeId>/revert`，body `{}` | 撤销整组可重放武器操作，返回 status |
| `GET /deliveries/defaults` | 当前视图版本、候选目标版本、客户端档案及输出目录 |
| `POST /drafts/<id>/build` | 复用 `build_draft`，同步返回 build-report；`{"background":true}` 返回后台任务 |
| `POST /drafts/<id>/build/cancel` | 取消后台生成 |
| `GET /deliveries`、`GET /deliveries/jobs/<name>` | 交付列表、生成进度 |
| `GET /deliveries/<name>`、`GET /deliveries/<name>/file?path=...` | 交付详情和导出文件 |

生成示例请求（版本和 clientProfile 应从 defaults 取值）：

```json
{"from":"1.4.254","to":"1.4.255","background":true}
```

生成重新验证 schema、命名空间、基线版本、输入 SHA-256、能力与材料规则，并通过现有本地交付流程生成客户端补丁、服务端镜像及断言、能力检查和清单。输出在 `work/studio-deliveries/weapons/`；变更集 ID 为 `studio-weapon-<id>-<版本>`，与同号角色和 BOSS 隔离。缺少所需本机服务端输入会拒绝写入或生成。

原有 device-result 读取、写入及导入接口同样挂在上述交付前缀下，绑定 `kind: "weapon"`。生成成功与设备实测分别报告；本次接口不会执行发布或部署。前端可将 `/drafts` 的武器条目加入“本次修改”，对对应武器调用 build，再使用交付列表和文件接口导出。
