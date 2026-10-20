param([int]$Seconds=15)
$mm='D:\WF\MuMuPlayer\nx_main\MuMuManager.exe'
& $mm sh -v 1 -c "dumpsys SurfaceFlinger --timestats -clear -enable; echo" | Out-Null
Start-Sleep $Seconds
$out = & $mm sh -v 1 -c "dumpsys SurfaceFlinger --timestats -dump; echo"
$cur=$null
foreach ($l in $out) {
  if ($l -match 'layerName = (.*)') { $cur=$matches[1] }
  if ($cur -and $cur -match 'leiting' -and $l -match 'averageFPS = ([\d.]+)') { "fps=$($matches[1]) layer=$cur" }
}
& $mm sh -v 1 -c "dumpsys SurfaceFlinger --timestats -disable; echo" | Out-Null
