import zipfile, json
from base149 import *
A=Path(r'D:/WF/startpoint-cn-kulo/.cdn/cn/archive-common-full')
_src=json.load(open(Path(__file__).with_name('official_src.json')))
def official(lp):
    z,n=_src[lp]
    return q.parse_node(zipfile.ZipFile(A/z).read(n))
