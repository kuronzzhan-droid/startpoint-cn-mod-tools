exec(open('scan_se.py',encoding='utf8').read().split('import re')[0])
open(r'D:/WF/out/赛瑞斯重做-20261015/fx/_scripts/official_se.txt','w',encoding='utf8').write("\n".join(sorted(se)))
print(len(se))
