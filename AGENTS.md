# 编辑台协作规则

## 工作边界

编辑台只写草稿和本地交付；游戏表、原始 store、APK、补丁输入和服务端镜像只读。
不部署、不安装客户端、不连接或修改正式服；本地 commit 不代表 push、merge 或发布授权。
前后端分工时只修改任务授权目录，保留其他人的未提交工作。
作者的 `profiles/local.json` 不随代码修改；路径来自环境变量或本机配置。

## 先读

1. `README.md` 与 `profiles/README.md`：入口、环境和配置优先级。
2. `docs/studio/README.md`：草稿、启动、体检与只读接口。
3. `docs/m2/client-profiles.md`：客户端能力证据及默认档案边界。
4. 涉及交付时阅读 `docs/studio/bundle-keys.md`、`key-diff.md` 与 `rehearsal.md`。

## 常用命令

```text
python -m pip install -r requirements-dev.txt
python -m wf.studio doctor
python -m wf.studio doctor --json
python -m wf.studio
studio.bat
python -m wf.studio.draft --help
python -m pytest tests -k "studio or m51 or client_profiles or m22" -q
python scripts/check_no_hardcoded_paths.py
```

## 红线与代码卫生

- 公开仓库不提交本机绝对路径、真实服务器地址、账号、密钥、APK 或官方资产。
- 能力依据实际方法及其引用上下文；未知能力写待验证，不按版本名推断。
- 不放宽断言掩盖缺陷；缺本机输入的集成测试明确 skip 并说明缺什么。
- 代码文件保持适当大小，新增职责及时拆分；每项独立可验证功能通过适用检查后单独提交。
- 临时计划和执行记录默认在仓库外；用户明确指定的 `work/` 报告保持忽略，不加入版本控制。
- 未请求的 push、外部发布、安装和部署不属于本地任务。
