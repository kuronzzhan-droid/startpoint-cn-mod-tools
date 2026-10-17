# 本地变更集交付

`python -m wf deliver changeset.json --out work/m1/deliver/candidate` 从已暂存的变更集生成交付，不安装、部署或发布。输出必须在当前工具 checkout 内且为空；不会覆盖已有交付。

变更集采用 `schemas/change-set.schema.json`。客户端每个成员声明 `root`、逻辑路径、相对暂存文件、前后 SHA-256；`before_sha256: null` 表示前置视图不存在该成员。`server_changes` 以服务端相对路径表示 JSON 等镜像文件，只生成 `server/` 下的暂存副本。`changes` 可保留逐键、逐行、逐格的审阅记录。路径逃逸、摘要漂移、重复目标和版本回退直接拒绝。

交付包含：

- 历史 `pinball-<from>-<to>-<seq>-<slug>.zip`、每包 integrity、汇总 integrity 和旧 manifest 条目。
- `patches/<to>/patch-manifest.json` 及 common、medium、android 三层 inner ZIP；空层使用 `.empty`。每个 ZIP 实际压缩后的容器不超过 5 MiB，单成员无法容纳时失败。
- `delivery-manifest.json`、`requires.json`、`SHA256SUMS` 和独立 `assert_box.py` / `assert-box.json`。`installed_size` 是本批变更成员解压写入的总字节数，不是整个客户端资源视图的 `totalSize`。
- 自动执行 `prepush --since <from>` 的 JSON 和日志。`validation/` 是用于检查的本地副本，不是安装内容。

需要已有链和内容基线时显式传入 `--baseline-active`、可重复的 `--baseline-zip`、`--base-store`。`--server-dir` 只读取三份 prepush 所需 JSON，不加载其服务程序、不向该目录写入。前置摘要与所给基线核对，后置摘要与候选叠层核对；服务端前后摘要分别与原 JSON 和本地候选副本核对。

继承 prepush 的 ERROR 会使命令返回非零。缺少基础数据、服务端前置输入或 kulo #35 服务模块时，检查记录为待验证，不能据此声称完整部署验证通过。本模块另行检查本地版本边、seq 连续性、重复、分叉、断链和前后摘要；这些结果保存在 `prepush.json` 的 `local_contract`。M2 之前能力解析为 `pending-m2`，`clientCapabilities` 字段始终存在；空列表不表示已证明任何客户端都兼容。

断言脚本只读，可在交付目录单独使用：

```powershell
python assert_box.py --phase pre --manifest <旧manifest.json> --active <旧active> --store <production> --server-dir <服务端目录>
python assert_box.py --phase post --manifest <新manifest.json> --active <新active> --store <production> --server-dir <服务端目录>
```

版本和摘要来自生成的 `assert-box.json`，不用手改脚本版本号。运行断言本身不会部署文件。

上游结构沿启动器 `docs/在线更新协议.md` 引用的固定提交核对：[官方 patch manifest schema](https://github.com/DontBeAlarmed/startpoint-cn/blob/b2e40c3f1b24b704e5881fbefa12be101ea78134/docs/cdn/patch-manifest.schema.json)、[Overlay 契约](https://github.com/DontBeAlarmed/startpoint-cn/blob/b2e40c3f1b24b704e5881fbefa12be101ea78134/docs/cdn/patch-overlay.md)。`compatibleClient: CN 1.8.1` 是该容器协议要求的标识，不替代本批 MOD 内容的能力匹配或客户端实测。

历史 221 变更集由 `python -m recipes.halloween221_changeset --package-root <完整historical221重建的pkgroot> --out <本仓输出>` 产生。此入口只消费完整重建 package；期望交付 ZIP 只用于后续独立逐成员比较。Windows 读深层 DSL 文件时保留扩展长度路径，避免普通 `is_file()` 把长路径漏当成不存在。
