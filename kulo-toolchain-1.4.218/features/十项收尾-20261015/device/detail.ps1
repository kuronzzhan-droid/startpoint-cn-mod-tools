param([string]$Name, [int]$Right = 0, [int]$Left = 0, [int]$Pages = 4)
# 从当前角色详情页向右切 $Right 个，展开详情，滚动截 $Pages 屏，拼成一张 sheet
$w = 'D:\WF\out\十项收尾-20261015\device\wf.ps1'
$shots = 'D:\WF\out\十项收尾-20261015\device\shots'
for ($i = 0; $i -lt $Right; $i++) { & $w -Action tap -X 1030 -Y 770 -Wait 1.6 | Out-Null }
for ($i = 0; $i -lt $Left; $i++) { & $w -Action tap -X 50 -Y 770 -Wait 1.6 | Out-Null }
& $w -Action tap -X 540 -Y 1300 -Wait 2 | Out-Null
$d = (& $w -Action disp | ConvertFrom-Json).logical
& $w -Action screen -Name "${Name}_0" | Out-Null
for ($p = 1; $p -lt $Pages; $p++) {
  & $w -Action shell -Command "input -d $d swipe 600 1600 600 500 1200" | Out-Null
  Start-Sleep 1
  & $w -Action screen -Name "${Name}_$p" | Out-Null
}
python -c "
from PIL import Image
ims=[Image.open(r'$shots\${Name}_%d.png'%i).convert('RGB').crop((0,100,1080,1760)) for i in range($Pages)]
s=Image.new('RGB',(1080*$Pages,1660),'white')
[s.paste(im,(i*1080,0)) for i,im in enumerate(ims)]
s.resize((540*$Pages,830)).save(r'$shots\${Name}_sheet.png')"
# 收起详情回到立绘态，方便继续切换
& $w -Action shell -Command "input -d $d swipe 600 500 600 1700 300" | Out-Null
& $w -Action shell -Command "input -d $d swipe 600 500 600 1700 300" | Out-Null
& $w -Action shell -Command "input -d $d swipe 600 500 600 1700 300" | Out-Null
& $w -Action shell -Command "input -d $d swipe 600 500 600 1700 300" | Out-Null
