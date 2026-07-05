# 首次运行检查清单

按顺序过一遍，每一步都通过再往下走。卡住时对照最下面的「报错对照表」。

## 0. 环境

- [ ] `python -V` ≥ **3.10**（用到 `str | None` 语法；无需任何 pip 依赖）
- [ ] 有一个**已经能跑起来的 startpoint-cn 私服**（本工具只改数据）
- [ ] 自备数据包：手机端 `WorldFlipper/dummy/download/production/upload` 目录（②层）

## 1. 路径配置（二选一）

**方式 A：环境变量**（编辑 `wf-gui.bat` 顶部注释掉的三行，去掉 `rem` 并改成你的路径）

```bat
set WF_TARGET_STORE=D:\...\WorldFlipper\dummy\download\production\upload
set WF_CDNDATA=D:\...\startpoint-cn\assets\cdndata
set WF_CDN_DIR=D:\...\startpoint-cn\.cdn\cn
```

**方式 B：profiles.json**（`copy profiles.example.json profiles.json` 后编辑，store/cdndata 建议写**绝对路径**）

检查点：

- [ ] `store` 目录下能看到两位十六进制子目录（`00/`、`a3/`…），里面是 38 位无扩展名文件
- [ ] `cdndata` 目录下有 `character.json` 和 `character_text.json`
- [ ] `WF_CDN_DIR` 指到服务端 `.cdn/cn`，其下有 `archive-common-diff/` 目录（发布器往这里丢增量包）

## 2. 模拟器（可选，只影响「发布后自动重启游戏」和 adb 直推）

- [ ] `WF_ADB` 指向 adb.exe（默认自动探测 MuMu 12）
- [ ] `WF_ADB_PORT` 模拟器端口（MuMu 12 默认 16384）
- [ ] 包名是 **`com.leiting.wf`**（雷霆国服；不是 `air.com.leiting.wf`——那是排查浪费半小时的旧包名）

不配 adb 也能用：发布照常打包，游戏手动重启即可拉更新。

## 3. 启动自检

双击 `wf-gui.bat`（或 `python wf_gui.py`），浏览器自动开 `http://127.0.0.1:8765`：

- [ ] 左栏出现**角色列表**（约 500 个）→ ①层 cdndata 读取正常
- [ ] 点任意角色，「词条编辑」出现效果行和绿色中文描述 → ②层 store + 枚举表正常
- [ ] 「词条速查」搜"攻击力"有结果 → 描述引擎正常
- [ ] 改任意数值先点**预览**（dry-run），确认弹出改动明细 → 写入链路正常（不点确认不会写）

## 4. 第一次发布（金丝雀）

1. 找个显眼数值（如某角色 Lv100 HP）改成 9999 → 保存
2. 右上角「发布并重启游戏」→ `WF_CDN_DIR/archive-common-diff/` 应出现新的 `pinball-*-mod*.zip`
3. 重启游戏 → 面板显示 9999 = 全链路贯通；再用「改动日志→一键回溯」还原

## 报错对照表

| 现象 | 原因 | 解法 |
|---|---|---|
| 启动报 `未找到 WorldFlipper/.../upload` | store 没配对 | 设 `WF_TARGET_STORE` 或改 profiles.json |
| 左栏角色列表为空 | ①层没找到 | 设 `WF_CDNDATA` 指向服务端 `assets/cdndata` |
| 发布报错/包找不到 | CDN 目录没配 | 设 `WF_CDN_DIR` 指向服务端 `.cdn/cn` |
| 改了游戏里没变化 | 没发布 / 游戏没真重启 | 按 README「改了没生效」四步排查 |
| 发布后客户端崩溃 | 见 README 血泪坑 | 「改动日志→一键回溯」，然后按坑对照 |
| 页面打不开 | 端口被占 | 看黑窗口提示的实际端口，或设 `WF_GUI_PORT` |

## 回归测试（改完核心引擎后跑）

```bash
python tests/test_core.py
```
