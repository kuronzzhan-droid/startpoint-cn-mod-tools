# 本地归档夹具

M0.1 将 86 个仅由 `archive/legacy` 使用的整行游戏表 JSON 从跟踪目录移到
`private-assets/tests/fixtures/`。其中 `balance_2026092*` 为 75 个、7,931,475 字节；
其余 11 个为旧角色技能输入快照，合计迁移 8,049,592 字节。
文件内容没有修改，逐项大小、原位置、现位置和 SHA-256 在
[`private-fixtures.json`](private-fixtures.json)。84 个归档测试文件的直接路径已改为新位置。
归档仍不参与默认 pytest 收集，也不因此恢复旧模块的运行环境。

活动测试仍使用的三个模板 JSON 和两个 gz 没有迁移，列入公开资源审查。
只移除当前树中的跟踪，不改写旧提交；旧 Git 历史仍可能含这些数据。

取得方式：从有权使用的原始夹具导出或作者提供的本地资料副本，按清单的 `local`
位置放置，并核对 SHA-256。已有本仓旧历史的作者也可在本仓根执行下面的离线恢复：

```python
import hashlib
import json
from pathlib import Path
import subprocess

root = Path.cwd()
manifest = json.loads((root / "docs/m0/private-fixtures.json").read_text(encoding="utf-8"))
for item in manifest["files"]:
    raw = subprocess.check_output([
        "git", "show", f'{manifest["source_commit"]}:{item["source"]}'
    ])
    assert hashlib.sha256(raw).hexdigest() == item["sha256"], item["source"]
    destination = root / item["local"]
    if destination.exists():
        assert destination.read_bytes() == raw, destination
        continue
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
```

这段操作只读 Git 对象，只向本仓忽略目录恢复文件；不从服务端或运行中游戏抓取数据。
没有相应历史或授权副本时，保留归档而不执行这些旧回归，不用生成假数据替代。
