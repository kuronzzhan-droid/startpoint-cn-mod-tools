"""从 author-content-1043 的 vm.py 派生 vm2：补 coerce_s / increment_i / ifgt 与 AVM 的字符串 add。"""
from pathlib import Path

src = Path(r"D:/WF/startpoint-cn-kulo/client-patch/author-content-1043/rules/tests/vm.py").read_text(encoding="utf8")
rep = [
    ("        if key == 'length':",
     "        if isinstance(obj, str) and key == 'substr':\n"
     "            return lambda a, n: obj[a:a+n]\n"
     "        if key == 'length':"),
    ("        elif op in ('coerce', 'coerce_a', 'convert_b'): pass",
     "        elif op in ('coerce', 'coerce_a', 'convert_b'): pass\n"
     "        elif op in ('coerce_s', 'convert_s'):\n"
     "            v = stack.pop(); stack.append(None if v is None and op == 'coerce_s' else (v if isinstance(v, str) else str(v)))\n"
     "        elif op == 'increment_i': stack.append(int(stack.pop()) + 1)"),
    ("'add': lambda: c+b,", "'add': lambda: (c+str(b)) if isinstance(c,str) else ((str(c)+b) if isinstance(b,str) else c+b),"),
    ("elif op in ('ifeq', 'ifne', 'iflt', 'ifge', 'ifle', 'ifngt'):",
     "elif op in ('ifeq', 'ifne', 'iflt', 'ifge', 'ifle', 'ifngt', 'ifgt'):"),
    ("'ifngt': lambda: not c > b}[op]()", "'ifngt': lambda: not c > b, 'ifgt': lambda: c > b}[op]()"),
]
for a, b in rep:
    assert src.count(a) == 1, a
    src = src.replace(a, b)
Path(__file__).with_name("vm2.py").write_text(src, encoding="utf8")
