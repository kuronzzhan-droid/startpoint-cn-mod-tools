# 客户端补丁与APK

本手册面向 Windows 新手。说明客户端补丁档案怎么选、如何检查自备 APK 的能力与兼容性、如何填写数据驱动 `wfx` 效果码，以及如何制作离线 Android 单机整合包。

> 相关原文参考：
> - 客户端能力声明与兼容性匹配：[`m2/capabilities.md`](../m2/capabilities.md)、[`m2/client-profiles.md`](../m2/client-profiles.md)、[`m2/matrix.md`](../m2/matrix.md)
> - v35e 客户端档案与参数约束边界：[`m2/v35e-registration.md`](../m2/v35e-registration.md)、[`m2/wfx-v35-configuration.md`](../m2/wfx-v35-configuration.md)
> - 本地自用 APK 登记说明：[`m6/local-clients.md`](../m6/local-clients.md)
> - P13 私有扩展键与 APK 内置表撞名门禁：[`studio/p13-keys.md`](../studio/p13-keys.md)、[`studio/bundle-keys.md`](../studio/bundle-keys.md)
> - 数据驱动 WFX 效果码速查表：[`客户端补丁效果码速查.md`](../客户端补丁效果码速查.md)
> - 离线 Android 整合包冻结方案参考：[`离线Android整合包.md`](../离线Android整合包.md)

---

## 一、先分清边界：工具能做什么、你要自备什么

1. **本仓库不提供任何 APK、官方 CDN 或官方资源下载渠道**：
   凡涉及客户端 `.apk`、提取出的 `.swf`、数据包缓存或 Android 构建工具，均需你在本机自行准备。下文只说明文件放哪、怎么用命令检查放对了没有。
2. **`python -m wf apk` 是只读检验与能力登记工具，不是 APK 改包器**：
   它负责读取你自备的 APK 或 SWF，识别里面打过哪些补丁、支持哪些词条分支，并生成 `provides.json` 供发包门禁核对。它**不会**替普通联机 APK 修改服务器地址、注入字节码或重签名。
3. **如果你发的数据用到了客户端补丁专属能力，未装对应补丁的客户端会直接崩溃或失效**：
   例如扩展瞬发码 `724`（Fever 槽增减）、持续码 `422/423/424`（技能槽突破 100%）在原版无补丁客户端上读取会立即报 `C7050` 闪退；`wfx:` 效果码在不支持的客户端上则会静默变成空效果。因此每次出包都必须指定正确的 `--client-profile`。

---

## 二、客户端档案（`client_profiles.json`）怎么选

发包工具（`wf deliver`、`wf.studio.draft build`、`wf_publish.py`、`wf_share_variant.py`）都通过 `--client-profile <档案名>` 决定放行哪些机制：

| 档案名 | 适用客户端类型 | 说明与默认场景 |
|---|---|---|
| `official` | 未打任何补丁的原版客户端 | 0 项扩展能力；只允许官方原生词条码，任何补丁扩展都会被拦截 |
| `test-v34` | 测试客户端 v34 系（`com.leiting.wt`） | `wf deliver` 与 Studio 编辑台的**默认档案**，支持面板文案覆盖、伤害类型转换、回槽规则等基础补丁 |
| `test-v35e` | 测试客户端 v35e 系（`com.leiting.wt`） | 支持 `wfx:` 效果查询（`wfx-effect-query-v1`）、`hidden_` 隐藏固有图标、双形态 UID、四档 PF、自适应属性等 v35 机制 |
| `local-v35k3`（及 `local-*`） | 本机自用客户端（`com.leiting.wf`） | 仅登记到本机 `work/local-clients/` 供个人核验，不作为公开测试服分发基准 |
| `local-mumu` | 本机模拟器开发档案 | `wf_publish.py` 与 `wf_character_flow.py` 的默认本机档案（对外发分享包时切勿用此档案） |
| `gray-1047` | 早期 1047 系客户端 | 仅含早期 7 项基础补丁的旧客户端兼容档案 |
| `p12b` / `p13` | 含召唤物/双 PF 私有扩展键的客户端 | 允许 `custom_ability_string` 写入自定义角色 PF、召唤物 PF 等 `wfx_*` P13 扩展键（部分继承能力在注册表中标 `待验证`） |

---

## 三、任务一：检查自备 APK 的能力并与补丁包核对兼容性

### 第 1 步：查看仓库当前登记的客户端档案与能力列表

- **做什么**：在工具仓根目录打开 PowerShell，运行：
  ```powershell
  python wfx_gate.py profiles
  ```
- **预期看到什么**：终端逐一列出 `local-mumu`、`gray-1047`、`official`、`test-v34`、`test-v35e`、`local-v35k3`、`p12b`、`p13` 等档案名称及各自支持的能力项。
- **不对怎么办**：如果报找不到模块，确认当前目录位于工具仓根目录（包含 `wfx_gate.py` 和 `client_profiles.json`）。

### 第 2 步：从自备 APK 提取静态能力证据（`provides.json`）

- **做什么**：准备好你的客户端 `.apk`（或解出的 `.swf`），执行只读扫描：
  ```powershell
  python -m wf apk provides <自备客户端APK路径> --output work/apk/provides.json
  ```
- **预期看到什么**：命令退出码为 `0`，在 `work/apk/provides.json` 生成该 APK 实际具备的能力 ID 列表与方法哈希摘要。
- **不对怎么办**：
  - 报路径不存在：检查 `<自备客户端APK路径>` 是否填了正确的文件后缀 `.apk`。
  - 生成的 `provides.json` 中扩展能力为空：说明这是一个未打补丁的原版 APK（对应 `official` 档案），或补丁特征不在已知注册表内。

### 第 3 步：（可选）登记本机自用的 v35 客户端档案并查看词条分支

- **做什么**：如果你手头有本机自用的 `com.leiting.wf` v35 系 APK，想把它登记成本机 `local-*` 档案以便在 Studio 编辑台选择（详见 [`m6/local-clients.md`](../m6/local-clients.md)）：
  ```powershell
  python -m wf apk register-local <自备v35客户端APK路径> --profile local-<自定义名称>
  python -m wf apk kinds --profile local-<自定义名称> --swf <自备v35客户端APK路径>
  ```
- **预期看到什么**：`register-local` 将方法证据写入被 Git 忽略的 `work/local-clients/local-<自定义名称>/`；`kinds` 输出来自实际 SWF 的各能力表 `kind` 支持分支。
- **不对怎么办**：若报包名或 SWF 哈希校验不符，说明该 APK 不是 `register-local` 支持的本机自用包类型；此时直接用第 2 步产出的 `--provides work/apk/provides.json` 传给 `wf deliver` 或 `draft build` 即可。

### 第 4 步：核对交付包与目标 APK 的能力兼容性及内置表撞名

- **做什么**：对已经打好的交付目录（`<交付目录>`，内含 `requires.json`），执行能力匹配与 AssetBundle 撞名预检：
  ```powershell
  python -m wf check compat --requires <交付目录>/requires.json --provides work/apk/provides.json
  python -m wf.studio.draft bundle-check --apk <自备客户端APK路径> --delivery-dir <交付目录>
  ```
- **预期看到什么**：
  - `wf check compat` 返回兼容通过（退出码 `0`），没有缺失能力（`missing` 为空）；
  - `bundle-check` 首次运行会在本机应用数据目录生成 APK Bundle 键缓存，随后确认补丁未与 APK 内置表重名冲突（防 `C7051`）。
- **不对怎么办**：
  - `compat` 列出缺失能力：要么升级客户端 APK 到支持这些能力的版本，要么回编辑台删掉触发该能力的扩展词条。
  - `bundle-check` 报撞名：修改新角色/新资产的内部英文代号（`code`），避开 APK 内置 Bundle 已占用的路径。

---

## 四、任务二：填写数据驱动 `wfx` 效果码与开关词条

v35 系客户端补丁把许多新机制做成了“纯填表触发”，无需每次改客户端代码。完整效果码清单见 [`客户端补丁效果码速查.md`](../客户端补丁效果码速查.md) 与根目录 `wfx_registry.json`。

### 1. 三类填表位置与代码门禁纠偏（必看）

1. **`unique_condition.orderedmap` 的 `c0`（识别串）列**：
   - 格式固定为 5 段冒号分隔：`wfx:<效果码>:<arg>:<value>:<flags>:<标签>`。
   - 标签以 `hidden_` 开头（如 `hidden_atk_up`）时，在 `test-v35e` 等支持 `wfx-hidden-unique-icons-v1` 的客户端上会自动隐藏战斗角色头顶的状态小图标。
   - **代码门禁纠偏（与早期速查文档的 3 处差异，以现行代码为准）**：
     - **码 `34` 与码 `35` 严禁填 0 档位**：早期速查表曾写码 `34` 档位为 0 时按每 1% 连续计算，但现行 `wf/wfx_semantics.py` 与 `wfx_registry.json` **明确禁止 0 档位**（`(arg // 10) % 100 == 0` 会直接报错阻断），请务必填非零档位。
     - **码 `33` 的 `flags` 不能填负数**：注册表要求码 `33` 的 `flags ≥ 0`（仅码 `28`、`29` 允许负 `flags`），填负数会被发包门禁拦截。
     - **码 `36` 已纳入注册表**：`wfx:36:<arg>:<Fever倍率万分比>:<平时倍率>:<标签>`（合击角色强化弹射，需 `unison-power-flip-v1`）；码 `30–36` 均要求目标客户端具备 `wfx-effect-query-v1`。
2. **`custom_ability_string.orderedmap` 的文本与机制开关键**：
   - 面板文案覆盖：`desc_override_<能力c0键>`（写法须遵守 [`改词条与数值.md`](改词条与数值.md) 的 60 条文案规范）。
   - 机制开关键：如 `wfx_unlock_<队长技ID>`、`wfx_adaptive_<能力ID>`、`wfx_pf4_<角色ID>`、`wfx_snapcombo_<键>`；自定义角色 PF、召唤物弹射 PF（`wfx_summon_flip_pf_<ID>`、`wfx_ball_pf_action_<ID>`）等属于 **P13 私有扩展键**，目标档案未声明 P13 时会被 `client-extensions` 门禁直接阻断（详见 [`studio/p13-keys.md`](../studio/p13-keys.md)）。
   - 注意：早期速查表提到的 `wfx_overlimit_full_<角色编号>` 目前未在 `wfx_registry.json` 注册。
3. **`character.orderedmap` 的 `c5`（标签）列**：
   - 双形态角色填 `ModDualForm` 或 `ModDualForm:<固有状态ID>`；v35 角色身份识别填 `wfx_cid_<角色ID>`（详见 [`m2/wfx-v35-configuration.md`](../m2/wfx-v35-configuration.md)）。

### 第 1 步：填表后运行 `wfx_gate.py` 做静态合法性检查

- **做什么**：改完包含 `wfx` 构造的表后，在工具仓根目录运行：
  ```powershell
  python wfx_gate.py check --client-profile <目标客户端档案名> --tables unique_condition,custom_ability_string,ability,leader_ability,character
  ```
- **预期看到什么**：命令退出码为 `0`，无参数越界或能力缺失报错。
- **不对怎么办**：按报错指出的表键和效果码修改参数范围，或者核对是否选错了 `--client-profile`（例如用了 v35 效果码却把档案设成了 `test-v34`）。

---

## 五、任务三：制作与验收离线 Android 单机整合包（1.4.196 冻结流程）

仓库根目录的 `wf_offline_release.py`（及快捷脚本 `build-offline-android.bat`）是一套**专用于 `1.4.196` 历史冻结快照**的单机离线 Android 打包流水线（详见 [`离线Android整合包.md`](../离线Android整合包.md)）。

> **独立仓路径与命令行提醒**：
> 1. 工具仓拆分为独立仓库后，`wf_offline_release.py` 内部仍按工具仓根目录查找两份冻结输入：`弹国服/单机版数据包.zip` 与 `.cdn/cn/archive-common-diff/pinball-1.4.195-1.4.196-1-mod07200253.zip`，并严格核对 `1.4.196` 冻结条目数（`common=113822`、`medium=23458`、`android=1009`）。
> 2. 运行 `python -X utf8 wf_offline_release.py --help` 时，打印完帮助文本后末尾会多出一行 `{"command":"unknown","errors":["0"],"ok":false,"status":"error"}`——这是脚本捕获 `argparse` 退出码的小瑕疵，不影响正常子命令使用。

### 1. 自备工具与材料摆放检查

开始前请自行准备并确认以下 4 项已就位：
1. **Java（含 `keytool`）** 与 **Android SDK Build-Tools / Platform-Tools**（需包含 `aapt.exe`、`zipalign.exe`、`apksigner.bat`、`adb.exe`，并加入系统 `PATH`）。
2. **自备原版底包 APK**（包名 `com.leiting.wf`）。
3. **自备 `1.4.196` 冻结基准数据包与尾包**：按脚本默认相对路径放到（或用目录链接指向）工具仓根目录下的 `弹国服/单机版数据包.zip` 与 `.cdn/cn/archive-common-diff/pinball-1.4.195-1.4.196-1-mod07200253.zip`，且 `profiles/local.json` 已配好对应 `1.4.196` 数据源。
4. **签名密钥库密码环境变量**：在当前 PowerShell 会话设置 `$env:WF_OFFLINE_KEYSTORE_PASSWORD = "<你自己设定的密码>"`（密码只会由脚本在内存读取并自动脱敏，切勿写入任何代码或文档）。

### 第 1 步：首次初始化本机离线签名证书

- **做什么**：在工具仓根目录运行：
  ```powershell
  python -X utf8 wf_offline_release.py init-signer --confirm CREATE_WF_OFFLINE_RELEASE_SIGNER
  ```
- **预期看到什么**：终端输出 `{"certificate_sha256":"...","command":"init-signer","ok":true,"signer_ready":true,"status":"ok"}`，证书保存在当前用户目录下的 `.wf-offline-release` 中（本机真机全链路标「未实测」）。
- **不对怎么办**：若报找不到 `keytool` 或密码未设置，先检查 Java 是否已装好以及 `$env:WF_OFFLINE_KEYSTORE_PASSWORD` 是否已在当前窗口赋值。

### 第 2 步：执行预检并构建离线候选包

- **做什么**：指定你自备的底包 APK 和一个安全的输出目录（不能选 `弹国服`、`.cdn`、`assets`、`work` 这四个受保护目录，建议用默认的 `out/wf-offline-android`），依次运行预检、构建与候选校验：
  ```powershell
  python -X utf8 wf_offline_release.py preflight --source-apk <自备底包APK路径> --snapshot-version 1.4.196 --output-root out/wf-offline-android
  python -X utf8 wf_offline_release.py build-candidate --source-apk <自备底包APK路径> --snapshot-version 1.4.196 --output-root out/wf-offline-android
  ```
  *(注：双击或运行 `.\build-offline-android.bat <自备底包APK路径>` 等价于直接执行上面第二条 `build-candidate` 命令。)*
  拿到输出 JSON 中的 `candidate`（候选目录名，记为 `<候选ID>`）后，校验候选包：
  ```powershell
  python -X utf8 wf_offline_release.py verify --candidate <候选ID> --snapshot-version 1.4.196 --output-root out/wf-offline-android
  ```
- **预期看到什么**：三条命令输出的 JSON 均带 `"ok":true`，候选目录生成重签名后的离线 APK 与外部离线数据包 ZIP，并通过密钥泄漏扫描（`secret-scan`）。
- **不对怎么办**：
  - 报缺少 `aapt` / `zipalign` / `apksigner`：把 Android SDK 的 `build-tools/<版本号>` 目录加进系统环境变量 `PATH` 后重开 PowerShell。
  - 报 `scan-store` 或 `legacy-tail-gates` 数量不符：说明当前 `store` 或冻结包不是 `1.4.196` 快照高度。

### 第 3 步：飞行模式真机验收并封板定稿（`finalize`）

- **做什么**：将一台测试 Android 手机**开启飞行模式并关闭 Wi-Fi 与移动数据**，用 USB 连接电脑开启 USB 调试（通过 `adb devices` 查出设备序列号 `<设备序列号>`），按顺序执行真机探测、重装准备、考入数据包、10 项人工打钩验收与封板（真机环节标「未实测」）：
  1. 探测飞行模式与干净环境：
     ```powershell
     python -X utf8 wf_offline_release.py device-probe --candidate <候选ID> --serial <设备序列号> --output-root out/wf-offline-android
     ```
  2. 清理旧包并安装候选离线 APK（确认口令为 `RESET_AND_REINSTALL_COM_LEITING_WF_ON_` 拼上 `<设备序列号>`）：
     ```powershell
     python -X utf8 wf_offline_release.py prepare-device --candidate <候选ID> --serial <设备序列号> --confirm RESET_AND_REINSTALL_COM_LEITING_WF_ON_<设备序列号> --output-root out/wf-offline-android
     ```
  3. 将候选目录里的离线数据包 ZIP 解压放入手机内部存储根目录 `/storage/emulated/0/`（使手机内形成 `/storage/emulated/0/WorldFlipper/dummy/download/production/{upload,medium_upload,android_upload}` 三层目录），在全程飞行模式下启动游戏完成 10 项功能检查。
  4. 记录 10 项人工验收回执（交互式逐项输入 `yes`）、封板产出最终目录并做终验：
     ```powershell
     python -X utf8 wf_offline_release.py device-accept --candidate <候选ID> --serial <设备序列号> --receipt-out out/wf-offline-android/1.4.196/<候选ID>/qa-receipt.json --output-root out/wf-offline-android
     python -X utf8 wf_offline_release.py finalize --candidate <候选ID> --receipt out/wf-offline-android/1.4.196/<候选ID>/qa-receipt.json --output-root out/wf-offline-android
     python -X utf8 wf_offline_release.py verify --bundle out/wf-offline-android/1.4.196/WF离线整合版 --output-root out/wf-offline-android
     ```
- **预期看到什么**：最后一条 `verify --bundle` 输出 `"deliverable":true,"ok":true,"status":"verified"`，在 `WF离线整合版` 目录下产出完整的 5 件套最终交付物。
- **不对怎么办**：
  - `device-probe` 报离线门禁未通过：确认手机已打开飞行模式，且 Wi-Fi 开关没有在飞行模式下被单独重新打开。
  - `prepare-device` 中途拔线中断后重跑被锁死：为防脏状态污染，中断会留下 `.reserve` 保护锁，请重新跑一次 `build-candidate` 生成新 `<候选ID>` 再验收。
