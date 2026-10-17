# M0.1 公开资源逐目录审查

当前树待审二进制 237 个、11,882,858 字节，分属 20 个直接目录，按完整资源包归成以下 17 个可勾选目录。相对公共 master `fd433b0` 新增 PNG 213 个，全部 PNG 233 个，另有 2 个 JPG 和 2 个 gz。
审查意见中的“新增 230 张”与本次按 `git ls-files` / `git ls-tree fd433b0` 逐路径统计不一致；本清单列出实际全部文件，不据旧估算遗漏目录。这里只标记疑似来源，未代作者认定版权或授权。

按 M0.1 任务书末尾“作者裁决（10-17 03:39）”，下表全部记为“可公开”并保留原位。这是作者本次授权决定的记录，不是工具对权利来源的独立认定；已明确要求移出的归档游戏数据夹具另行处理。
表中数量与体积含子目录，每个文件只计一次。移出时连同该目录的源码和元数据整体移动，使 manifest、批准记录和图像的相对关系保持不变；例如 weapon-awaken 的 icons 不单独拆走。直接所属目录的独立统计保存在 JSON 的 `direct_directories`。

| 目录 | 文件数 | 字节 | 相对 master 新增 | 类型 | 作者决定 |
|---|---:|---:|---:|---|---|
| `art/status-icons-20260917` <!-- asset-dir:art/status-icons-20260917 --> | 3 | 10,913 | 3 | .png × 3 | [x] 可公开 / [ ] 移出 |
| `assets/abyss-equipment` <!-- asset-dir:assets/abyss-equipment --> | 15 | 6,402 | 0 | .png × 15 | [x] 可公开 / [ ] 移出 |
| `assets/abyss-equipment-lv120` <!-- asset-dir:assets/abyss-equipment-lv120 --> | 15 | 6,821 | 15 | .png × 15 | [x] 可公开 / [ ] 移出 |
| `assets/abyss-gacha-banners` <!-- asset-dir:assets/abyss-gacha-banners --> | 3 | 6,663,738 | 0 | .png × 3 | [x] 可公开 / [ ] 移出 |
| `assets/abyss-gacha-tickets` <!-- asset-dir:assets/abyss-gacha-tickets --> | 2 | 1,510 | 0 | .png × 2 | [x] 可公开 / [ ] 移出 |
| `assets/bianca-dragon-icons` <!-- asset-dir:assets/bianca-dragon-icons --> | 3 | 13,311 | 3 | .png × 3 | [x] 可公开 / [ ] 移出 |
| `assets/bond-weapons` <!-- asset-dir:assets/bond-weapons --> | 18 | 270,538 | 18 | .png × 18 | [x] 可公开 / [ ] 移出 |
| `assets/celtie-fever-icons` <!-- asset-dir:assets/celtie-fever-icons --> | 2 | 9,801 | 2 | .png × 2 | [x] 可公开 / [ ] 移出 |
| `assets/cursed-weapons` <!-- asset-dir:assets/cursed-weapons --> | 81 | 302,785 | 81 | .png × 81 | [x] 可公开 / [ ] 移出 |
| `assets/five-boss` <!-- asset-dir:assets/five-boss --> | 2 | 897 | 2 | .png × 2 | [x] 可公开 / [ ] 移出 |
| `assets/five-boss-v2` <!-- asset-dir:assets/five-boss-v2 --> | 58 | 550,047 | 58 | .png × 58 | [x] 可公开 / [ ] 移出 |
| `assets/nephtim-fever-icons` <!-- asset-dir:assets/nephtim-fever-icons --> | 1 | 5,900 | 1 | .png × 1 | [x] 可公开 / [ ] 移出 |
| `assets/paradox` <!-- asset-dir:assets/paradox --> | 8 | 20,985 | 8 | .png × 8 | [x] 可公开 / [ ] 移出 |
| `assets/weapon-awaken` <!-- asset-dir:assets/weapon-awaken --> | 18 | 7,509 | 18 | .png × 18 | [x] 可公开 / [ ] 移出 |
| `assets/weapon-gacha` <!-- asset-dir:assets/weapon-gacha --> | 2 | 1,574,317 | 2 | .png × 2 | [x] 可公开 / [ ] 移出 |
| `tests/fixtures` <!-- asset-dir:tests/fixtures --> | 2 | 8,992 | 2 | .gz × 2 | [x] 可公开 / [ ] 移出 |
| `wiki` <!-- asset-dir:wiki --> | 4 | 2,428,392 | 4 | .jpg × 2, .png × 2 | [x] 可公开 / [ ] 移出 |

## 来源与范围

- `assets/five-boss-v2/deep_king/frames` 独占 51 张 boss 帧图、93,078 字节，计入 five-boss-v2。cursed-weapons/status 的 21 张图为 37,181 字节。weapon-awaken/icons 直接 16 张、6,577 字节，handoff 子目录另 2 张、932 字节。武器图标、横幅、状态图与 wiki 图均已按作者本次裁决记为可公开，目录名称仅用于清单分组。
- `tests/fixtures` 的两个 gz 是池表快照；该目录还保留活动测试使用的三个 JSON 模板及两份文本夹具，选择此目录会一并移出。
- `assets/bond-weapons/official_baseline.json` 等文本元数据可能含游戏行；虽然不计入二进制统计，选择目录会一并移出。
- 4 个 archive `.bak*` 经 UTF-8 检查均为文本（3 个 Python、1 个 JSON），不属于二进制，仍保留在历史归档中；三份 Python 的 docstring 本来就是多行。
- 逐文件原始 SHA-256、大小及是否 master 已有见 [public-assets-inventory.json](public-assets-inventory.json)。86 个已移出的 JSON 夹具另见 [private-fixtures.md](private-fixtures.md)。

## 后续改变选择时的本地操作

当前决定不需要迁移。如果作者后续将部分目录改选“移出”，先编辑本表复选框，再在本仓根运行：

```powershell
python -B scripts/split_private_assets.py
python -B scripts/split_private_assets.py --apply
python -B -m pytest
git diff --check
git status --short
```

脚本默认只打印计划；`--apply` 只执行明确勾选“移出”的目录，目标固定为本仓忽略的 `private-assets/<原相对路径>`。目标同名文件已存在、资产摘要漂移、越界、链接或冲突决定都会拒绝；不同名的既有私有夹具可保留并合并。迁移异常会回退已写引用和移动。脚本不提交、不推送、不改写历史。

Python 中能静态证明位于本仓资源目录的 Path 表达式改为资源解析函数，兼容单字符串与多段 `/` 拼接；不猜测 `self.store` 等未知根，不改裸 `wiki` 标签。JS/CJS/MJS/TS 中静态相对导入及 `path.join/resolve(__dirname, ...)` 按调用文件位置迁移，保留包名和内部相对关系。JSON、HTML 和文档中的明确仓根相对引用同步迁移。被移动脚本添加相对仓根引导，保持直接 Python CLI 可用；尚不存在的输出保留目录锚点之后的路径拼接。动态产生且未出现在静态源中的自定义引用不在静态改写保证内，应按计划检查改动并运行相应功能验证。

22 项合成回归通过，覆盖移动、引用重写、目标冲突、源和目标链接、未知根保护、新输出和失败回退。独立审阅另用真实目录 junction、直接 CLI、两份真实测试源的只读计划、新输出及空目录回滚完成 5 项实证复查，均通过，记录在 `work/m0/asset-review/recheck-results.json`。隔离副本实际迁移全部 17 目录后，Python 子集 342 passed、101 skipped、184 subtests passed，Node 14 项通过，237 项资源摘要相同，详见 [private-assets-rehearsal.md](private-assets-rehearsal.md)。本轮没有对真实资源执行 `--apply`；当前全“可公开”的审查表生成空迁移计划。

当前 Git 历史仍包含旧资产，即使后续工作树移出，也不等于从公开历史移除；发布与历史整理由作者另行决定。
