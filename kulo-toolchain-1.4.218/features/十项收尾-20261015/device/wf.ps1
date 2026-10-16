param(
  [ValidateSet('screen','tap','key','shell','start','disp')][string]$Action='screen',
  [string]$Name='screen', [int]$X=0, [int]$Y=0, [int]$Key=4, [string]$Command='', [double]$Wait=1.5
)
# MuMu安卓设备-1 (index 1) only. Game package com.leiting.wf.
$ErrorActionPreference='Stop'
$manager='D:\WF\MuMuPlayer\nx_main\MuMuManager.exe'
$out='D:\WF\out\十项收尾-20261015\device\shots'
New-Item -ItemType Directory -Force $out | Out-Null
function Sh([string]$t) { & $manager sh -v 1 -c $t }
$inv=(& $manager info -v all | Out-String) | ConvertFrom-Json
if ($inv.'1'.name -notmatch '-1$' -or -not $inv.'1'.is_android_started) { throw 'MuMu -1 not running' }
function Disp {
  $a=Sh 'dumpsys activity activities' | Out-String; $d=$null
  foreach($l in ($a -split "`n")) { if($l -match '^Display #(\d+)'){$d=[int]$Matches[1]}; if($l -match 'topResumedActivity=.*com.leiting.wf/'){break} }
  if($a -notmatch 'topResumedActivity=.*com.leiting.wf/'){ throw 'wt not resumed' }
  $i=Sh 'dumpsys display' | Out-String
  $m=[regex]::Match($i,"DisplayViewport\{[^}]*displayId=$d,\s*uniqueId='local:(\d+)'")
  if(-not $m.Success){ throw 'no viewport' }
  @{logical=$d;physical=$m.Groups[1].Value}
}
function Shot { $s=Disp; $e=Sh "screencap -d $($s.physical) -p | base64"; $p=Join-Path $out "$Name.png"; [IO.File]::WriteAllBytes($p,[Convert]::FromBase64String(($e -join ''))); $p }
switch($Action){
  'disp' { Disp | ConvertTo-Json -Compress }
  'start' { Sh 'am start -n com.leiting.wf/air.com.leiting.wf.AppEntry' | Out-Null; Start-Sleep $Wait; Shot }
  'screen' { Shot }
  'tap' { $s=Disp; Sh "input -d $($s.logical) tap $X $Y" | Out-Null; Start-Sleep $Wait; Shot }
  'key' { $s=Disp; Sh "input -d $($s.logical) keyevent $Key" | Out-Null; Start-Sleep $Wait; Shot }
  'shell' { Sh $Command }
}
