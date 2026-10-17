# 罗尔夫 wt26 设备装配工具集（2026-08-12 会话产出）

从会话 scratchpad 抢救归档。全部针对 **MuMu 设备-2 的离线单机版**直推场景，
不走 `wf_publish`/`wf_character_flow` 发布链。交接见 `../docs/交接-20260812夜-罗尔夫装配.md`。

共同约定：设备落点 `/sdcard/WorldFlipper/dummy/download/production/{upload,medium_upload,android_upload}`；
经 MuMu `private_shared` 中转（`${WF_ROOT}\MuMuPlayer\vms\MuMuPlayer-15.0-0\private_shared` ↔ VM 内 `/mnt/shared/private_shared`）；
adb 直连不可用，一律走 `MuMuManager.exe sh -v 0 -c`。

| 脚本 | 作用 | 状态 |
|---|---|---|
| `haxe_serial.py` | **Haxe 序列化往返器**（save_haxe 读写）。`loads`/`dumps`，支持 o/q/b/a/l/y/R/r/i/d/z/n/t/f/k/m/p/s/v/w/j | ✅ 真存档字节恒等自检通过；直接 `python haxe_serial.py [存档]` 即自检 |
| `table_regression_fix2.py` | 表回归审计+修复：设备原表(备份)+仅本角色键，raw 行级格式无关 | ✅ 已修复 12 张表，复审全绿 |
| `slot_audit.py` | 13 medium 槽位内容哈希比对（设备 wt26 件 vs 杰拉德同名件） | ✅ 28/28 |
| `gate_runner.py` | 对账表 C 节 8 道验收门跑批 | ✅ 7 过 1 待真机 |
| `prefix_audit_fix.py` | 借壳资产内嵌旧 code_name 全量审计+改写 | ✅ 揪出 2 件图集 |
| `pixel_rebuild.py` | 像素主 sheet + **独立 special sheet** 分别正确落位 | ✅ |
| `ui_full_rebuild.py` | ui 全族按官方尺寸+alpha 蒙版重建（18 张） | ✅ |
| `cutin_build.py` | skill_cutin PNG(1024×512) + 配对 ATF 重编码 | ✅ |
| `rolf_pf_v2.py` | 722 三档 = 官方 ranged DSL(`RG_ranged.json`) + 辅助段摘 `ACFlying` | ✅ 已推，真机表现待查 |
| `bind_skin_orb.py` | 皮肤绑「延续的黄金」100012 + 存档持有/编队/装备 | ✅ 数据全对，真机仍显示 steampunk（未解） |
| `rolf_install.py` / `rolf_push.py` | 角色整套克隆（临时区）与推送 | ⚠ `rolf_push.py` 曾整表覆盖导致回归，**改用前先读交接 §3-1** |
| `asset_gap.py` / `device_audit.py` | 资产缺口探测 / 设备实况取证 | ✅ |

## 硬性提醒

1. **绝不整表覆盖设备 master 表** —— 一律「设备原表 + 仅本角色键」重建（`table_regression_fix2.py` 的模式）。
2. **合法性校验只用 `wf_client_legality.client_legality_problems('ability'|'leader_ability', row)`**，不要手写判据。
3. **改 save_haxe 前后各跑一次 `haxe_serial` 往返自检**，不恒等就别推。
4. 路径白名单、特效目录 `sprite_sheet` 命名、special 独立 sheet 三条见交接 §3-2/3/4。
