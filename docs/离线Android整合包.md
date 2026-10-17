# 离线 Android 整合包构建与验收

这是一份操作者流程，不是已完成的真实构建或实机验收记录。只有最后的 `verify` 返回成功并确认 `deliverable=true`，对应目录才可交付给别人。

以下命令都从仓库根目录 `${WF_ROOT}\startpoint-cn` 执行。构建分为“不可变候选 → 指定设备离线验收 → 五文件最终包”三阶段；候选未经设备验收不能直接当成成品。

## 1. 首次创建专用签名者

只在从未创建过离线发行签名者时执行：

```powershell
$repoRoot = (Resolve-Path ".").Path
$buildToolsDir = Join-Path (Split-Path -Parent $repoRoot) "starview-windows\build-tools"
$env:WF_OFFLINE_AAPT = Join-Path $buildToolsDir "aapt.exe"
$env:WF_OFFLINE_ZIPALIGN = Join-Path $buildToolsDir "zipalign.exe"
$env:WF_OFFLINE_APKSIGNER = Join-Path $buildToolsDir "apksigner.bat"
$env:WF_OFFLINE_ADB = '${WF_ROOT}\MuMuPlayer\nx_main\adb.exe'
foreach ($toolPath in @(
    $env:WF_OFFLINE_AAPT,
    $env:WF_OFFLINE_ZIPALIGN,
    $env:WF_OFFLINE_APKSIGNER,
    $env:WF_OFFLINE_ADB
)) {
    if (-not (Test-Path -LiteralPath $toolPath -PathType Leaf)) {
        throw "Required offline tool is missing: $toolPath"
    }
}

python -X utf8 mod-tools/wf_offline_release.py init-signer --confirm CREATE_WF_OFFLINE_RELEASE_SIGNER
```

三件 Android build-tools 必须来自上面推导出的同一个 `starview-windows\build-tools` 目录；ADB 则来自单独的 MuMu 路径，不在该目录。任一文件不存在都会在签名者初始化前立即停止。这四个路径变量不是秘密，只在当前 PowerShell 会话中生效。后续每个 CLI 都要重新执行工具发现，所以至少在设备验收结束前不要清除 `WF_OFFLINE_ADB`，并在最终复核完成前保留全部四个变量。不要设置 `WF_OFFLINE_MUMU_MANAGER`：缺少明确实例配对时，让工具发现报告 `mumu_manager=null` 是预期状态。

`keytool` 会在真实控制台中交互式询问密码。不要把密码放进命令参数、脚本、文本文件或仓库。初始化只创建仓库外的历史 keystore 和公开证书配置；如果它们已经存在，命令会拒绝覆盖。已有发行 key 不轮换、不覆盖、不删除，除非另有明确授权并先制定密钥迁移方案。

## 2. 临时注入密码并构建候选

用 `SecureString` 读取密码，只在当前 PowerShell 进程中临时设置构建所需的环境变量：

```powershell
$signingSecret = Read-Host "Offline signer password" -AsSecureString
$secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($signingSecret)
try {
    $env:WF_OFFLINE_KEYSTORE_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
    Remove-Variable secretPointer -ErrorAction SilentlyContinue
}

$buildLines = $null
try {
    $preflightLines = @(python -X utf8 mod-tools/wf_offline_release.py preflight --source-apk "$env:USERPROFILE\Downloads\base.apk.1" --snapshot-version 1.4.196)
    $preflightExit = $LASTEXITCODE
    $preflightLines | Write-Output
    if ($preflightExit -ne 0) { throw "offline preflight failed with exit code $preflightExit" }

    $buildLines = @(& .\mod-tools\build-offline-android.bat "$env:USERPROFILE\Downloads\base.apk.1")
    $buildExit = $LASTEXITCODE
    $buildLines | Write-Output
    if ($buildExit -ne 0) { throw "offline candidate build failed with exit code $buildExit" }
} finally {
    Remove-Item Env:\WF_OFFLINE_KEYSTORE_PASSWORD -ErrorAction SilentlyContinue
    Remove-Variable signingSecret -ErrorAction SilentlyContinue
}
```

BAT 会继承当前 PowerShell 中的三件套路径和密码环境变量，但不会解析或持久化三件套路径，也不会打印、询问、设置、处理或保存密码；普通构建中的 Python 进程只读取继承的 `WF_OFFLINE_KEYSTORE_PASSWORD`。即使预检或构建失败，上面的 `finally` 也只清除密码环境变量，三件套路径会保留给后续设备与 finalize/verify 命令继续发现。若 PowerShell 被强制终止，重新打开终端，或立即执行：

```powershell
Remove-Item Env:\WF_OFFLINE_KEYSTORE_PASSWORD -ErrorAction SilentlyContinue
Remove-Variable signingSecret -ErrorAction SilentlyContinue
```

`build-candidate` 的最后一行是稳定 JSON。不要手抄或猜候选 ID；从该 JSON 的 `build_id` 读取：

```powershell
if (-not $buildLines -or $buildLines.Count -eq 0) { throw "build-candidate emitted no result" }
$buildResult = $buildLines[-1] | ConvertFrom-Json
if (-not $buildResult.ok -or $buildResult.status -ne "awaiting_device_acceptance") {
    throw "candidate is not awaiting device acceptance"
}
$candidateId = [string]$buildResult.build_id
if ([string]::IsNullOrWhiteSpace($candidateId)) { throw "build-candidate JSON has no build_id" }
$candidateDir = Join-Path "out\wf-offline-android\1.4.196" (".candidate-" + $candidateId)
$candidateId
```

设备被修改前，先只读复核不可变候选：

```powershell
python -X utf8 mod-tools/wf_offline_release.py verify --candidate $candidateId
if ($LASTEXITCODE -ne 0) { throw "candidate verification failed" }
```

候选目录不是最终交付目录。候选证据、APK 客户端构建报告、设备 probe/验收收据以及失败摘要等 sidecar 都必须留在最终五文件目录之外。

## 3. 选择并准备唯一设备

推荐新建一个专门用于验收的干净 MuMu 实例。若复用已有实例，先在宿主机另行核实备份共享存储根目录下的 `WorldFlipper/save_haxe`；`WorldFlipper/save_haxe` 或 `WorldFlipper/dummy` 仍存在时，设备准备门禁会拒绝继续。备份和清理属于操作者单独确认的步骤，工具不会删除或重命名整个 `WorldFlipper` 目录。

在任何 `prepare-device` 之前，先完成以下离线条件：

1. 打开飞行模式。
2. 明确关闭 Wi-Fi。
3. 明确关闭移动数据。
4. 确认没有默认路由、活动网络或依赖中的伴随服务。

列出设备，并从 `adb devices -l` 中选择唯一一个状态为 `device` 的精确 serial。不要使用显示名、实例名或硬编码的旧 serial：

```powershell
& $env:WF_OFFLINE_ADB devices -l
$adbSerial = Read-Host "Exact online ADB serial from adb devices -l"
if ([string]::IsNullOrWhiteSpace($adbSerial)) { throw "ADB serial is required" }
```

先执行只读 probe。它只读取指定设备的离线状态、共享数据存在性、包状态和崩溃日志，不执行 `pm clear`、卸载、安装或共享目录清理：

```powershell
python -X utf8 mod-tools/wf_offline_release.py device-probe --candidate $candidateId --serial $adbSerial
if ($LASTEXITCODE -ne 0) { throw "device probe failed; do not prepare this device" }
```

`prepare-device` 会对精确 serial 执行 `pm clear`、卸载旧 `com.leiting.wf`（若存在）并安装候选 APK，因此确认串必须和当前 serial 逐字符绑定：

```powershell
$prepareConfirm = "RESET_AND_REINSTALL_COM_LEITING_WF_ON_" + $adbSerial
$prepareConfirm
python -X utf8 mod-tools/wf_offline_release.py prepare-device --candidate $candidateId --serial $adbSerial --confirm $prepareConfirm
if ($LASTEXITCODE -ne 0) { throw "device preparation failed" }
```

在任何可能开始 `pm clear`、卸载或安装的破坏性动作之前，`prepare-device` 会先为当前 serial 的摘要原子创建 `.serial-<digest>.json.reserve` crash-poison；对应的 canonical target 是 `serial-<digest>.json`。路径按 serial 摘要跨所有候选共享，路径本身不含 candidate；候选绑定记录在 canonical 文档中的 `candidate_identity`。因此候选 A 已留下 reserve 或 final sidecar 时，同一 serial 的任何候选 B 都不能再次 prepare。准备完整成功时，只保留 canonical JSON sidecar，并清除对应的 reserve 和临时文件；异常、进程崩溃或状态不明时，reserve 会被有意保留并阻断重试，工具不会自动删除已有占位。device sidecar 始终位于最终五文件目录之外。

不要把这个确认串用于其他设备，也不要按端口、进程名或模糊实例名清理设备。

## 4. 手动导入数据到共享存储根目录

安装后在 Android 设置中授予游戏“所有文件访问权限”。将候选目录里的 `WorldFlipper-数据-1.4.196.zip` 传到设备，然后由操作者手动把 ZIP **直接解压到** `/storage/emulated/0/`。ZIP 自身已经包含顶层 `WorldFlipper/`。

正确结果包括：

```text
/storage/emulated/0/WorldFlipper/dummy/download/production/upload/
/storage/emulated/0/WorldFlipper/dummy/download/production/medium_upload/
/storage/emulated/0/WorldFlipper/dummy/download/production/android_upload/
/storage/emulated/0/WorldFlipper/dummy/info.json
/storage/emulated/0/WorldFlipper/dummy/download/.empty
```

三个资源 store 都必须位于 `WorldFlipper/dummy/download/production/` 下；顶层的 `WorldFlipper/production/`、`WorldFlipper/medium/` 或 `WorldFlipper/android/` 都不是本整合包的正确解压布局。

以下两种布局都错误，必须在首次启动前纠正：

```text
/storage/emulated/0/Download/WorldFlipper/...
/storage/emulated/0/WorldFlipper/WorldFlipper/...
```

工具不会通过 ADB 自动解压数据，也不会自动删除宽泛的 `WorldFlipper` 根目录。保持飞行模式、Wi-Fi 关闭、移动数据关闭，再首次启动游戏。

## 5. 十项人工 QA

在同一个候选、同一个 serial、持续离线且不依赖伴随服务的条件下，逐项实际操作：

1. 首页、编队和角色列表都能打开，无崩溃或“资源文件已损坏”。
2. 原始角色 ID `1` 与新角色 ID `129999`、`139999`、`149999` 均已持有。
3. 三名新角色都能进入战斗并正常施放技能；其中 `139999` 的普通显示与技能资产也完整加载。
4. Seris 双形态切换、技能与强化弹射结果稳定。
5. Gerald 在角色列表、编队和战斗中的缩放均正确。
6. 连战事件 `700099` 至少实际完成一轮，并确认十五轮结构、奖励和代币 `2370099` 均正确。
7. 十五把新武器（`8000101` 至 `8000115`）全部可见，并至少实际获取、装备一把。
8. 武器效果对白名单目标生效、对非白名单目标不生效。
9. 使用游戏菜单“保存”，随后强制停止并重启游戏，角色、奖励、武器和进度仍能恢复。
10. 全程保持飞行模式，且不依赖服务器、CDN、localhost、局域网或任何伴随端口服务。

任意一项失败，都不要创建通过收据、不要 finalize，也不要把该候选交给别人。

## 6. 交互确认设备验收

收据是 final 外部的候选绑定证据。输出路径必须是尚不存在的新文件；下面的默认路径只适合第一次验收：

```powershell
$receiptPath = "out/wf-offline-android/1.4.196/device-acceptance.json"
python -X utf8 mod-tools/wf_offline_release.py device-accept --candidate $candidateId --serial $adbSerial --receipt-out $receiptPath
if ($LASTEXITCODE -ne 0) { throw "device acceptance failed" }
```

命令会再次 probe，并按上一节的十项检查逐项询问。只有在刚刚亲自复核对应项目后才输入完整的 `yes`；任何 `no`、空输入或中断都会失败，且不会生成有效通过收据。收据绑定候选 `build_id`、APK/数据 ZIP 哈希和盐化后的设备 serial 摘要，不能借给另一个候选或另一个设备使用。

## 7. Finalize 与最终复核

只有设备验收成功后才 finalize：

```powershell
python -X utf8 mod-tools/wf_offline_release.py finalize --candidate $candidateId --receipt $receiptPath
if ($LASTEXITCODE -ne 0) { throw "finalize failed" }

$finalDir = "out/wf-offline-android/1.4.196/WF离线整合版"
python -X utf8 mod-tools/wf_offline_release.py verify --bundle $finalDir
if ($LASTEXITCODE -ne 0) { throw "final bundle verification failed" }

Remove-Item Env:\WF_OFFLINE_KEYSTORE_PASSWORD -ErrorAction SilentlyContinue
Remove-Variable signingSecret -ErrorAction SilentlyContinue
Remove-Item Env:\WF_OFFLINE_AAPT -ErrorAction SilentlyContinue
Remove-Item Env:\WF_OFFLINE_ZIPALIGN -ErrorAction SilentlyContinue
Remove-Item Env:\WF_OFFLINE_APKSIGNER -ErrorAction SilentlyContinue
Remove-Item Env:\WF_OFFLINE_ADB -ErrorAction SilentlyContinue
```

最终目录必须恰好只有五个文件：

```text
WorldFlipper-离线整合版.apk
WorldFlipper-数据-1.4.196.zip
导入说明.txt
build-manifest.json
SHA256SUMS.txt
```

只有最终 `verify` JSON 同时报告成功和 `deliverable=true` 才可分发。接收者仍应先按 `SHA256SUMS.txt` 校验前四个文件，再按 `导入说明.txt` 导入。

## 8. 失败恢复与不可触碰边界

- 已存在的 `WF离线整合版` final 永不覆盖；不要为重试而删除旧 final，应保留它并查明冲突。
- 任一构建、probe 或 QA 失败后，立即停用该候选；不要修改候选内容、复用旧收据或绕过门禁，重新构建会得到新的候选 ID。
- `prepare-device` 遗留的 `.serial-<digest>.json.reserve` 表示破坏性设备状态可能只完成了一部分。同一 serial 若已有候选 A 的 reserve 或 final sidecar，任何候选 B 都会被跨候选阻断，换 candidate ID 不能绕过，工具不会自动删除已有占位。不得随手删除 reserve 或 final sidecar，也不得据此假定设备仍然干净；应停用该候选和该实例，核查共享数据备份、已安装包与设备当前状态，优先改用新的干净实例和新候选。清理这些 sidecar 必须另行取得精确授权并按专门恢复流程执行。
- source APK 只读；实时 `弹国服/`、`.cdn/`、`assets/`、`work/` 和用户未提交 WIP 都不作为构建写入目标，也不得为打包而还原或清理。
- candidate、客户端报告、probe/验收收据、失败摘要是 final 外部证据，不得塞进最终五文件目录。
- 历史签名 key 不自动轮换、不覆盖、不删除；任何密钥处置都需要独立、明确授权。
- 不把数据包解压在 `Download` 下，也不额外再套一层 `WorldFlipper`。
- 失败摘要只用于诊断，不能当作成功 manifest；没有真实 `verify` 结果时，不得声称候选或最终包已经构建完成。
