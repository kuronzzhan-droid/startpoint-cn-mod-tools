# prepush 原工具用法与副作用审计

原工具：`D:\WF\out\kulo-patch-toolkit\prepush\wf_prepush_check.py`。
本次SHA-256：`df9535bb83a6943431e1151f2d460e7ae8f37e9d604ea07dae9866a28ea87e70`。

已实际运行 `--help`。该工具启动即import `wf_quest_lib`，需：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH='D:\WF\startpoint-cn-kulo\tools\fantasy-gauntlet-mod-tools'
python 'D:\WF\out\kulo-patch-toolkit\prepush\wf_prepush_check.py' --help
```

工具的Python路径只读加载解析器，实际检查使用 `q.parse_node`，不调用会备份/保存store的 `save_table`。脚本唯一直接写文件处为1066行 `args.json.write_text`；完整检查还会调用Node加载 `--server-dir/out/routes/cn/asset.js`。不能直接拿真实服务端目录运行：当前工作树已编译asset.js不导出所需检查，且真实模块顶层会require服务端依赖树、执行 `reportPatchChainIntegrity()`；其完整副作用不需要靠本任务冒险验证。

`交付/build/run_prepush.py` 已构造全位于工作区的虚拟server：

- `assets/` 从 `cache/server-merged-assets/` 复制合并结果。
- `assets/asset-patch/active/` 保存灰固定ref全链126个已启用档案与本次14个新包；`manifest.json` 为灰manifest+新条目，cdn_version1.4.220。
- 灰3个历史档案在git中为LFS pointer；直接只读 `.git/lfs/objects/` 中已存在对象，并逐一断言pointer SHA-256/size，不运行git-lfs、不联网。
- `out/routes/cn/asset.js` 来自固定ref的 `src/routes/cn/asset.ts`。用TypeScript AST抽出原文 `parseVersion`、`compareVersion`、`parseDiffArchiveName`、`checkPatchChainIntegrity` 及其接口，通过已有TypeScript编译器转译，无服务端import、无替代stub。另用合法/重复seq/seq缺口/缺文件四组输入核对真实检查行为。
- 来源ref、完整源hash、函数原文hash、生成JS hash及自测输入结果写入 `交付/prepush-chain-source.json`；全部126档案来源与内容hash写入 `交付/prepush-inputs.json`。
- 基础store只读 `D:\WF\out\kulo-patch-toolkit\store131\production`，`--since 1.4.136` 由包名筛到136构造灰基线。新220包与完整基线的差异才算本次新增。
- 原checker通过subprocess原路径运行，未修改/降级其规则，不使用allowlist，不设置 `--only` 跳检查。TEMP/TMP均限制到工作区。

可重跑完整检查：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
python 'D:\WF\out\灰分享包-20261016\交付\build\run_prepush.py'
```

输出 `交付/prepush.txt`、`prepush.json`、`prepush-summary.json`。退出0表示ERROR0，退出1表示有ERROR（包括启动异常），退出2是原工具环境/参数问题。最终结果以最近一次summary及包hash核对为准。

完整检查证明数据链/文本/道具伴随/等级可达性在静态视图内通过；APK内置空桩表、真实客户端加载和灰服务端运行均不在该工具证明范围内。`--git-since` 不用于虚拟目录（没有Git仓），服务端文本行与action_skill的实际差异仍会列WARN；客户端character_text的新变化会按since视图严格列ERROR。
