exec(open('scan_se.py',encoding='utf8').read().split('import re')[0])
from collections import Counter
c=Counter(); ex={}
for k,v in se.items():
    for name,s in v:
        c[s['volume']]+=1; ex.setdefault(s['volume'],(name,k))
print(c.most_common()); print(ex)
