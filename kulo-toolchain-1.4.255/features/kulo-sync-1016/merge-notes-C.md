# merge-notes-C(serverfix-39,main=kulo origin/main,box=测试服)

| 文件 / 段 | box 意图 | 决定 | 理由 |
|---|---|---|---|
| shop.ts #1(/buy 交易前) | 在事务外提前构建 rewards 数组 | 取 main(不提前构建) | main 把 rewards 构建挪到事务内、库存/余额校验之后(防大数组),功能等价 |
| shop.ts #2(事务内开头) | 删掉事务内 EVENT_ITEM 可用性复查 | 取 main(保留 `now` + 事务内复查) | main 更严;`now` 也供强化分支使用 |
| shop.ts #3(强化分支) | 在强化分支内声明 `now` | 取 main | `now` 已在事务开头声明,box 的写法会重复声明 |
| shop.ts #4(plan 计算) | 与 main 逐字相同 | 取 main | 两侧内容一致(只是锚点错位) |
| shop.ts #5(发奖/提交) | 用事务外的 rewards 发奖 | 取 main(事务内构建 rewards 再发奖) | 与 #1 配套;余额/库存/称号都在同一事务里检查和提交(#31 的语义 main 已有),购买数量整数校验(#33)main 已有 |
| multiSpecialExchange.ts(import) | 不引入 resolveMultiSpecialExchangeCampaign | 取 main | main 新的旧进度恢复逻辑(041f3372)要用它;box 的角色白名单检查 isMultiSpecialExchangeCharacter 已在 main 里 |
| lib/multi-special-exchange.ts(import) | 不引入 PlayerMultiSpecialExchangeCampaign 类型 | 取 main;另外删掉文件末尾 box 带进来的重复 `isMultiSpecialExchangeCharacter` | main 已经吸收白名单(第 40 行);重复导出会让 TS 报错 |
| exBoost.ts(最大超限判定) | 用 getCharacterMaxOverLimit(characterId, rarity) | 取 box | 角色超限 Lv120 扩展(lib/character-overlimit.ts 已合入)需要按角色给上限;非扩展角色的返回值和 main 的 characterMaxOverLimits 一样;import 已自动合成 box 那一侧 |
| management-auth.ts(routeUrl) | 用 request.routeOptions?.url | 取 main(requestRoutePath(request)) | main 抽出了 lib/request-route-path.ts 辅助函数,行为是它的超集或兼容版 |
| gacha.ts(PASS_CARD_POINT) | 箱子扭蛋遇到 PASS_CARD_POINT 时 break 跳过 | 取 main(throw 让结算中止) | main 先中止事务、不扣费,不会出现扣了钱却发不出奖励;box 的写法会白扣费。CHARACTER=6(bughunt 0005)的枚举已经在 types/box-gacha.ts 里 |

tsc 结果:以上 6 个文件没有错误;冲突标记已清零,文件为 LF。

## 需复核
- exBoost:main 的 characterMaxOverLimits 在 routes/api/character.ts 第 215 行仍在用(那不是我负责的文件)。如果超限 120 要全线生效,character.ts 也要改用 getCharacterMaxOverLimit。
- gacha:测试服上的箱子扭蛋数据里如果真的有 PASS_CARD_POINT 奖励,改成 main 的写法后整次抽取会 500。上线前请扫一遍 box gacha 的数据。
- shop:box 的 boss_coin_shop 分类 20/98 是数据改动,不在这几个文件里,请在数据文件那边确认已经带上。
