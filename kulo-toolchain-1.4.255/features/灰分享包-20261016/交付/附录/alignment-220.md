# 测试服 1.4.219→1.4.220 对齐审计

逐键比较灰 1.4.131–1.4.136 相对共同祖先 1.4.130 的增量。
测试219已包含全部可导入灰增量，因此本边为合法空ZIP（22字节），仅升版本号。
保留测试219后续修复，包括五重增益、凉月能力/队长技和碧C8004资源。
测试219既有GM本体及训练数据保持；对齐边不重复发放或删除。

统计：{"binary_same": 192, "binary_keep_ours": 2, "row_same": 730, "row_keep_ours": 6}

## 已有后续改动，保留测试219

- `production/medium_upload/35/5ea2b823b907bc8bd62e5e0e05b8c0840f3328` / `完整资源`：保留测试219资源终态及C8004修复。完整双方值和SHA见JSON。
- `master/ability/ability.orderedmap` / `1599921`：测试219已有独立或后续修改；不以灰旧行覆盖。完整双方值和SHA见JSON。
- `master/ability/ability.orderedmap` / `1599922`：测试219已有独立或后续修改；不以灰旧行覆盖。完整双方值和SHA见JSON。
- `character/cnmod_vyrn_dark/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate` / `完整资源`：保留测试219资源终态及C8004修复。完整双方值和SHA见JSON。
- `master/battle/boss/general_boss.orderedmap` / `mod_fb2_035_evil_w02/100`：测试219已有独立或后续修改；不以灰旧行覆盖。完整双方值和SHA见JSON。
- `master/battle/boss/general_boss.orderedmap` / `mod_fb2_037_evil_w01/100`：测试219已有独立或后续修改；不以灰旧行覆盖。完整双方值和SHA见JSON。
- `master/battle/boss/general_boss.orderedmap` / `mod_fb2_039_evil_w02/100`：测试219已有独立或后续修改；不以灰旧行覆盖。完整双方值和SHA见JSON。
- `master/ability/leader_ability.orderedmap` / `159992`：测试219已有独立或后续修改；不以灰旧行覆盖。完整双方值和SHA见JSON。

## 产物

- `pinball-1.4.219-1.4.220-1-align-live-local.zip`，22字节，SHA256 `8739c76e681f900923b900c9df0ef75cf421d39cabb54650c4b9ad19b6a76d85`。
- `manifest-entry-align-1.4.220.json`：version=1.4.220，depends_on=1.4.219。
