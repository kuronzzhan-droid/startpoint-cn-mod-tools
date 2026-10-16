# 角色超限本地验证：把 kulo 复制成独立副本（不写 kulo 工作区），叠 1.4.207 与服务端补丁
$ErrorActionPreference = 'Stop'
$src = 'D:\WF\startpoint-cn-kulo'
$dst = 'D:\WF\out\角色超限-120\localsrv'
if (Test-Path $dst) { throw "exists: $dst" }
New-Item -ItemType Directory $dst | Out-Null
foreach ($d in 'src','out','data','config','web','admin','scripts','.database') { Copy-Item -Recurse "$src\$d" "$dst\$d" }
New-Item -ItemType Directory "$dst\.logs" | Out-Null
foreach ($d in '.cdn','node_modules','tools','client-patch','docs','deployment','tmp') { if (Test-Path "$src\$d") { New-Item -ItemType Junction -Path "$dst\$d" -Target "$src\$d" | Out-Null } }
Get-ChildItem $src -File -Force | ForEach-Object { Copy-Item $_.FullName "$dst\$($_.Name)" }
# assets：顶层文件与小目录复制；asset-patch/active 用硬链接
New-Item -ItemType Directory "$dst\assets" | Out-Null
Get-ChildItem "$src\assets" -File | ForEach-Object { Copy-Item $_.FullName "$dst\assets\$($_.Name)" }
foreach ($d in 'asset_lists','cdndata','gacha-movie-variants','gacha_movie_configs') { Copy-Item -Recurse "$src\assets\$d" "$dst\assets\$d" }
New-Item -ItemType Directory "$dst\assets\asset-patch\active" -Force | Out-Null
Get-ChildItem "$src\assets\asset-patch" -File | ForEach-Object { Copy-Item $_.FullName "$dst\assets\asset-patch\$($_.Name)" }
foreach ($d in 'artwork','audit','dev-catalog') { New-Item -ItemType Junction -Path "$dst\assets\asset-patch\$d" -Target "$src\assets\asset-patch\$d" | Out-Null }
Get-ChildItem "$src\assets\asset-patch\active" -File | ForEach-Object { New-Item -ItemType HardLink -Path "$dst\assets\asset-patch\active\$($_.Name)" -Target $_.FullName | Out-Null }
'done'
