param([string]$Kw, [int]$Elem = -1)
# 在角色列表打开筛选，按名称关键字过滤（Elem: 0火1水2雷3风4光5暗，-1 不动属性），点第一个角色
$w = 'D:\WF\out\十项收尾-20261015\device\wf.ps1'
$xs = @(153, 307, 462, 617, 771, 926)
& $w -Action tap -X 95 -Y 560 -Wait 3 | Out-Null
& $w -Action tap -X 793 -Y 228 -Wait 2 | Out-Null
& $w -Action tap -X 950 -Y 385 -Wait 1 | Out-Null
& $w -Action tap -X 230 -Y 988 -Wait 1 | Out-Null
if ($Elem -ge 0) { & $w -Action tap -X $xs[$Elem] -Y 1182 -Wait 1 | Out-Null }
& $w -Action tap -X 198 -Y 545 -Wait 1 | Out-Null
& $w -Action tap -X 540 -Y 422 -Wait 2 | Out-Null
$d = (& $w -Action disp | ConvertFrom-Json).logical
& $w -Action shell -Command "am broadcast -a ADB_INPUT_TEXT --es msg '$Kw' >/dev/null 2>&1" | Out-Null
& $w -Action screen -Name find_kw | Out-Null
