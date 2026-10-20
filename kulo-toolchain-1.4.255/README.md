# kulo 补丁工具链快照 1.4.255(2026-10-20)

测试服链尾 1.4.255 时的工具与构建脚本存档,接 `snapshot/1.4.218-20261016`。

- `kulo-patch-toolkit/`:本地链构建脚本、`prepush/wf_prepush_check.py` 推送前自检、APK 字节码补丁脚本、各版本平衡构建器、平衡表调研笔记。
- `codemap/`:代码地图与 `gen_codemap.py` 生成器(去掉了含服务器地址的两页)。
- `edge-sync/`:每条补丁边同步到 startpoint-cn 与 kulo 的脚本(`sync_edge.sh`)和各版本平衡改动说明。
- `features/`:1.4.213–1.4.255 各交付的构建脚本与说明:水杰拉德、万圣四角色、平衡 1016/1017、面板核对与面板生效审计、乘区标签与修正、气绝设计、角色超限、赛瑞斯重做、碧、凉月修复、十项收尾、灰分享包、联机子进程重建补丁。

只收脚本和文档;store131 数据视图、官方资源、补丁 zip、APK、数据库、密钥、服务器地址与本地服版 SWF 脚本不在此仓库。补丁 zip 见 startpoint-cn 仓库 Release `patches-<版本>`;v35 客户端补丁源码见 startpoint-cn 的 `apk-patches/112`–`143`。
