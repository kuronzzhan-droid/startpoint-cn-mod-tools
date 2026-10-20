# 1.4.213 交付:凉月修复 + ★4 结晶校验

叠在测试服链尾 1.4.212(212 = ten-items d519945b…)。所有改动都以测试服现状为底:服务端文件取自盒子副本(assets 于 10-15 22:38 拉取,src 镜像 D:\WF\serverfix-38 已逐文件与盒子核对一致)。

## 一、客户端数据边(1 个包)

| 文件 | 大小 | sha256 |
|---|---|---|
| pinball-1.4.212-1.4.213-1-liangyue-ability-columns-local.zip | 272821 | 6ceac0739cca43d9a89e2134421a40b8043eebdab1420db38d34925e455ae951 |

- 2 个成员:`production/upload/1e/664c1cc8…`(master/ability/ability.orderedmap)、`production/upload/ff/84353774…`(master/ability/leader_ability.orderedmap)。成员 sha 在同目录 integrity.json。
- 内容:凉月 159992 三条词条行补齐客户端必读列。
  - `ability[1599921]` #2(每直击 1 次自身攻击 +10%,最多 12 层):c74 initial_multiply `''`→`'1'`,c67 cancelable `''`→`'0'`
  - `ability[1599922]` #2:c67 `''`→`'0'`
  - `leader_ability[159992]` #5:c65 `''`→`'0'`
- 只有 c74 改变行为:空串被客户端读成 0,该效果的倍率永远是 0。cancelable 空串原本就按 0 读,补 `'0'` 行为不变,只为过门禁。
- 构建器:`D:\WF\out\凉月修复-20261016\build_213.py`(视图 = kulo active 131–206 + extra_zips.txt 里的 207–212)。
- 门禁:`prepush-213-since.txt`(--since 1.4.212)ERROR 0 / WARN 95 → 可以推送;`prepush-213-full.txt`(全量,不带 since)ERROR 12,全是已知的 40193 和 8000201–8000211 缺 item_ids.json,与本包无关。

## 二、服务端改动(逐条)

都要重启服务端;`character-overlimit.ts` 还要先编译 out/。

1. `assets/mana_node.json`(盒子原文件是 CRLF,本文件保持 CRLF)
   - 只改键 `159992`:41 个节点的 items 按客户端 `master/mana_board/mana_node` 原样重建。第一盘光元素 46–49 换成风元素 13–16,第二盘光属性材料 65–67 换成风属性 59–61,通用材料 99 的位置也随客户端表。mana 消耗和 field1/5/6 不变;其余 556 个键逐字节不变。
   - sha256 0f5fe2eb…3c34(改前 37bc40bc…f52f836)。
2. `assets/mana_board.json`(LF)
   - 新增键 `159992`:41 条,取客户端 `master/generated/mana_board` 原样(与服务端镜像派生规则一致);其余键不动。补上后 `open_mana_board`、觉醒消耗查询都能拿到数据。
   - sha256 63528196…7f36(改前 e757a3ce…4233)。
3. `src/lib/character-overlimit.ts`(CRLF,保持)
   - `validateOverLimitRequest` 的零售突破道具判断从「rarity≤4 收 10002 或 10001」改成「★5 只收 10003、★4 只收 10002、★3 及以下收 10002 或 10001」,与客户端 item 表的 target_rarity / allow_below 一致。
   - sha256 e6600768…6cac(改前 66c6a819…66c6)。
4. `tests/character-overlimit.test.js`(CRLF)
   - 新增用例「retail crystals follow the client rarity limits」。新代码 7/7 通过;在改前的 out/ 上跑,这条用例失败,其余 6 条通过(确认用例能抓到旧行为)。
   - sha256 e7d45929…3b90。
- config / .env:无改动。
- 完整 diff:`server-changes.diff`(相对盒子副本)。

## 三、本地自测(本地服 8001 = 盒子 src + 盒子 assets + 以上改动,MuMu-1 com.leiting.wf 本地包)

- 凉月学满两块玛纳盘(23 + 18 = 41 节点):扣的是 13–16 风材料,46–48 光材料一个没动;第二块盘解锁(`open_mana_board`)成功。改前同一角色开第二块盘返回 500(本地服 character.json 也缺凉月,换成盒子 assets 后修正)。
- 觉醒消耗:41 个节点 `getManaNodeAwakeCost` 全部能算出来;修前 mana_board 缺行,pedestal 查不到,返回 null(= awake_mana_node 400)。客户端目前不给凉月开放「角色觉醒」入口(凉月不在 character_awake_event 表里),所以觉醒按钮这一步在真机上点不到,只核了服务端算价。
- 3 条空列真机 A/B(全伤害木人,队长凉月):
  - 1.4.212:凉月头像下只有全队共享的攻击 ×8,没有她自己的叠层;
  - 1.4.213:凉月多出自身攻击 ×12(叠满),其他两人没有。
  - 对比图在 `liangyue_ab_hud.png`。确认原来失效,修后生效。
- 超限结晶:★4 碧安卡用 ★4 破星结晶 10002 从 5 突破到 6 成功(10002 −1)。客户端界面本来就不会给 ★4 列出 10001,拒绝 ★4 用 10001 这一条由单测覆盖。

## 四、收尾

- 本地 8001/8003 已停。
- MuMu-1:只动过 com.leiting.wf(本地包)。该包 info.json 已退回 1.4.212,两张被 213 覆盖的表已回写 212 版本(md5 已核)。com.leiting.wt(测试服 v33)全程没动。
