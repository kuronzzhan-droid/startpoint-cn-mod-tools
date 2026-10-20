$r = 'C:\startpoint-test'
foreach ($d in 'src','assets','scripts','tests','tools','admin','web','data','docs','client-patch','deployment') {
  if (Test-Path "$r\$d") {
    $f = Get-ChildItem "$r\$d" -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
      $_.FullName -notlike '*\asset-patch\active\*' -and $_.FullName -notlike '*\node_modules\*' -and $_.FullName -notlike '*\asset-patch\production\*'
    }
    "{0} {1} files {2:N1} MB" -f $d, $f.Count, (($f | Measure-Object Length -Sum).Sum / 1MB)
  }
}
(Get-Item "$r\assets\asset-patch\manifest.json").LastWriteTime
(Get-Content "$r\assets\asset-patch\manifest.json" -Raw | ConvertFrom-Json).cdn_version
Get-ChildItem "$r\assets\asset-patch\active" -File | Measure-Object Length -Sum | ForEach-Object { "active {0} files {1:N0} MB" -f $_.Count, ($_.Sum / 1MB) }
