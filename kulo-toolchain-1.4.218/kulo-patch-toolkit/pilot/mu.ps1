param([string]$Action='shot',[int]$X=0,[int]$Y=0,[int]$X2=0,[int]$Y2=0,[string]$Name='wfshot')
$mm='D:\WF\MuMuPlayer\nx_main\MuMuManager.exe'
$pic=(Get-ChildItem "$env:USERPROFILE\Documents" -Directory -Filter 'MuMu*' | Select-Object -First 1).FullName + '\Pictures'
$acts = & $mm sh -v 1 -c "dumpsys activity activities | grep -E 'Display #|topResumedActivity'; echo"
$disp = $null; $cur=$null
foreach ($l in $acts) { if ($l -match 'Display #(\d+)') { $cur=$matches[1] }; if ($l -match 'topResumedActivity=.*com\.leiting\.wf') { $disp=$cur } }
if (-not $disp) { $disp='0' }
if ($Action -eq 'shot') {
  $ids = & $mm sh -v 1 -c "dumpsys SurfaceFlinger --display-id; echo"
  $best=$null; $bestSize=0
  foreach ($l in $ids) {
    if ($l -match 'Display (\d+) .*displayName="([^"]+)"') {
      $id=$matches[1]; $dn=$matches[2]
      if ($dn -eq 'mumuscreen000' -and $disp -ne '0') { continue }
      $f="/sdcard/Pictures/$Name-$id.png"
      & $mm sh -v 1 -c "screencap -d $id -p $f; echo" | Out-Null
      $hp=Join-Path $pic "$Name-$id.png"
      if (Test-Path $hp) { $s=(Get-Item $hp).Length; if ($s -gt $bestSize) { $best=$hp; $bestSize=$s } }
    }
  }
  if ($best) { Copy-Item $best "$PSScriptRoot\$Name.png" -Force }
  "display=$disp shot=$PSScriptRoot\$Name.png"
} elseif ($Action -eq 'tap') { & $mm sh -v 1 -c "input -d $disp tap $X $Y; echo"; "tapped $X,$Y on $disp" }
elseif ($Action -eq 'swipe') { & $mm sh -v 1 -c "input -d $disp swipe $X $Y $X2 $Y2 400; echo"; "swiped on $disp" }
elseif ($Action -eq 'back') { & $mm sh -v 1 -c "input -d $disp keyevent 4; echo"; "back on $disp" }
