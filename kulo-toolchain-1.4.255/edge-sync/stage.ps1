$ErrorActionPreference = 'Continue'
$r = 'C:\startpoint-test'; $s = 'C:\startpoint-test-upload\gh-sync-stage'
if (Test-Path $s) { Remove-Item $s -Recurse -Force }
New-Item -ItemType Directory $s | Out-Null
foreach ($d in 'src','assets','scripts','tests','tools','admin','web','data','docs','client-patch','deployment') {
  if (Test-Path "$r\$d") { robocopy "$r\$d" "$s\$d" /E /NFL /NDL /NJH /NJS /NP /XD node_modules active production retired archive inactive __pycache__ work /XF *.db *.sqlite *.log .env *.pem *.key *.keystore *.jks | Out-Null }
}
foreach ($f in 'package.json','package-lock.json','tsconfig.json','tsconfig.cn.json','.gitignore','.env.example','README.md','CLAUDE.md','CONTRIBUTING.md') { if (Test-Path "$r\$f") { Copy-Item "$r\$f" "$s\$f" } }
Set-Location 'C:\startpoint-test-upload'
if (Test-Path gh-sync.tar) { Remove-Item gh-sync.tar }
tar -cf gh-sync.tar -C $s .
"{0:N1} MB" -f ((Get-Item gh-sync.tar).Length / 1MB)
(Get-FileHash gh-sync.tar -Algorithm SHA256).Hash
