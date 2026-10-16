# 十项收尾本地验证：从超限 localsrv（已含 1.4.207–211 与其服务端补丁）复制独立副本，叠 1.4.212。不写 kulo 工作区。
$ErrorActionPreference = 'Stop'
$src = 'D:\WF\out\角色超限-120\localsrv'
$dst = 'D:\WF\out\十项收尾-20261015\localsrv'
if (Test-Path $dst) { throw "exists: $dst" }
New-Item -ItemType Directory $dst | Out-Null
foreach ($d in 'src','out','data','config','web','admin','scripts','.database','tests') { if (Test-Path "$src\$d") { Copy-Item -Recurse "$src\$d" "$dst\$d" } }
New-Item -ItemType Directory "$dst\.logs" | Out-Null
foreach ($d in '.cdn','node_modules','tools','client-patch','docs','deployment','tmp') {
  $t = @((Get-Item "$src\$d" -Force).Target)[0]
  if ($t) { New-Item -ItemType Junction -Path "$dst\$d" -Target $t | Out-Null }
}
Get-ChildItem $src -File -Force | ForEach-Object { Copy-Item $_.FullName "$dst\$($_.Name)" }
New-Item -ItemType Directory "$dst\assets" | Out-Null
Get-ChildItem "$src\assets" -File | ForEach-Object { Copy-Item $_.FullName "$dst\assets\$($_.Name)" }
foreach ($d in 'asset_lists','cdndata','gacha-movie-variants','gacha_movie_configs') { Copy-Item -Recurse "$src\assets\$d" "$dst\assets\$d" }
New-Item -ItemType Directory "$dst\assets\asset-patch\active" -Force | Out-Null
Get-ChildItem "$src\assets\asset-patch" -File | ForEach-Object { Copy-Item $_.FullName "$dst\assets\asset-patch\$($_.Name)" }
foreach ($d in 'artwork','audit','dev-catalog') { $t = @((Get-Item "$src\assets\asset-patch\$d" -Force).Target)[0]; New-Item -ItemType Junction -Path "$dst\assets\asset-patch\$d" -Target $t | Out-Null }
Get-ChildItem "$src\assets\asset-patch\active" -File | ForEach-Object { New-Item -ItemType HardLink -Path "$dst\assets\asset-patch\active\$($_.Name)" -Target $_.FullName | Out-Null }
Copy-Item 'D:\WF\out\十项收尾-20261015\patch\pinball-1.4.211-1.4.212-1-ten-items-local.zip' "$dst\assets\asset-patch\active\"
'done'
