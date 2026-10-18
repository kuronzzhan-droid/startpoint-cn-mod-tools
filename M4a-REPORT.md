# M4a 执行报告：草稿交付与词条编辑后端

日期：2026-10-18。工作分支：`refactor/m4-studio-deliver`。任务基线：M2.1 与 M3.1/M3.2 的合并提交 `a55d4da`。

## 范围与输入

已执行上级目录《M4a-任务书.md》，并读取总方案第 5、6、7、12、13 节及 M1/M2 报告。代码、草稿、临时文件、测试缓存、交付和执行证据均只写当前 worktree；其他目录仅作为只读输入。未 push、部署、安装、操作设备或改动 8790 上的编辑台。

真实验收固定使用 1.4.233 的 manifest 依赖链和 store131 基线，解析 45 个 ZIP。历史链、实际读取成员的 SHA-256 与输入重验结果保存在 `work/m4a/baseline/` 和各验收目录。原 233 shipped 包 SHA-256 保持 `7c648747f7f1747a05968296d843036afa0da5362ae7b7d31e657f3092fc2f34`。本次 `1.4.233 → 1.4.234` 是针对固定历史视图的本地测试候选版本，不代表正式版本分配或部署。

临时脚本、原始游戏数据、完整日志和交付放在已忽略的 `work/m4a/`；只有代码、测试、接口说明、本报告和精简验收摘要入库。

## 实现

| 模块 | 完成行为 |
|---|---|
| 合并后测试环境 | 修复已删除的 `_profile` 引用，使用现有 `profile_data()`；来源版本支持 ManifestView 字符串版本。解除 pytest 对 `work/m0/pytest-tmp` 的固定依赖，真实视图 fixture 使用 `tmp_path`，缺数据规范 skip，程序错误仍失败。 |
| 草稿交付桥 | `wf/studio/deliver_bridge.py` 将草稿编译为 M1 内容寻址变更集；锁定 from 视图，复核角色、版本、素材摘要、表旧值，再执行现有 `wf deliver`、`wf check` 和可选目标客户端 compat。所有产物置于 `--out/inputs` 与 `--out/delivery`。 |
| 立绘 | 指定形态 full_shot、十个图标、cutin PNG/Android ATF、共享 illustration sheet 和 atlas；保存时捕获三张定位表整表与叶子旧值。双形态不会相互覆盖草稿文件。读取 CDN 根精确区分 medium/common/android。 |
| 像素 | 按源帧与锚点编译 atlas、timeline、sprite_sheet，保留原 frame 字节与 scale；追加装箱保护未改区域，逐帧回读未改槽，检查实际 4096² 预算及战斗 margin。 |
| 语音 | 只替换角色已有 common 路径，再次验证 CBR、完整帧、草稿/存储态摘要及往返。新增台词留给 M4c。 |
| 词条 | 能力、队长技、action_skill 的改格、插删移动、挂新键/换键；逐格与整行旧值断言、126/124 映射、完整共享所有者与显式 shared_ok、首行 c1 提示、能力声明表/块检查、原 CSV 分隔符与未改压缩叶保留。 |
| 文本与技能档位 | 文本复用 `wf text`，同步客户端及两份服务端镜像。技能结构编辑对应连续 1–3 档单行叶，插删移动后同步/清空镜像 c4–c9；缺镜像、错误键绑定、非法新档均拒绝。 |
| 预览、模板、接口 | GET 前后行及 `wf_describe` 中文说明、五态结果；kind 枚举与先例模板，零先例仍可选并标待验证。API 与 CLI 共用 AbilityEditor，写 API 沿用 Host/Origin/令牌守卫。 |

交付继承 M1/M2 的 ≤5 MiB 分包、两种 manifest、三层归档、requires 推导、629 门禁、prepush、奖励键对照、前后摘要断言脚本和基线锁；没有复制一套独立出包算法。CLI/API 用法、完整参数及请求边界见 [编辑台说明](docs/studio/README.md)。

## 真实验收

### 139985：双形态重裁、neutral 换色、一条语音替换

在全新草稿目录保存 `_0/_1` 两形态重裁，微调脸锚，替换 neutral 两帧颜色；已有 `battle/skill_ready` 语音重新按目标响度编码。最终草稿包含 25 个文件，两形态各 12 个，另加 1 条语音。通过桥接出完整交付，prepush exit 0。

- 3 个 ZIP、36 个成员；最大 ZIP **5,139,165 字节**，低于 5 MiB。
- 25 个草稿文件的存储态与解包成员逐字节一致，三张定位表共 6 个目标叶子符合草稿。
- neutral 2 帧与草稿 RGBA 一致；另外 8 个动作的 426 帧位置逐字节一致；frame 原始字节、scale、锚点保留。
- sprite_sheet、atlas、timeline 能由现有编辑台播放器后端读回。
- 139985 可枚举 70 个资源，其中 37 个未改资源逐字节一致；实际核对的 2,378 个未改视图成员一致。该数量对应已枚举/已读取范围，不宣称覆盖未知逻辑路径。
- 源帧篡改和定位表旧值漂移均被拒绝。

最终证据：`work/m4a/acceptance-final/media-acceptance.json`、`media-untouched-assets.json`、`media-source.lock.json`；交付位于 `work/m4a/acceptance-final/media/delivery/`。较早一轮保留在 `work/m4a/acceptance/`，没有覆盖。

最后精确根修复后，另以 `source-binding-confirmation.json` 确认六项真实立绘输入均仅存在于正确根，旧选择与新精确根读取逐字节相同，媒体来源锁再验通过；冻结代码重新编译词条也与既有交付 1/1 成员一致。因此沿用上述完整出包证据，没有把仅定向测试算作真实交付验收。

### 139985：改格、插行、移行、删行

四次请求都保留在草稿操作序列中：能力键 `1399851` 的 c51 从 50000 改为 49000；在 `1399852` 插入新行，移动到首行后删除原指定行。生成 1 个 ZIP、1 个能力表成员。

- **378 个单元格**逐格符合独立预期。
- **3,553 个未改能力叶**的文本及压缩字节一致；**1,427 个未改视图成员**一致。
- 实际运行 `wf check` exit 0、`wf check compat` exit 0。
- 改坏旧值断言会拒绝；从 provides 移除 `client.text.desc_override@1` 后 compat **exit 1**。
- 另用公开 `python -m wf.studio.draft ... build` 完整出包，CLI **exit 0**；与 API 生成的 changeset 相同、1/1 成员逐字节一致。

证据：`work/m4a/acceptance/ability-acceptance.json`、`inputs-and-cli-acceptance.json`、`ability-source.lock.json` 及 `ability-*.log`；交付位于 `work/m4a/acceptance/ability/delivery/` 和 `ability-cli/delivery/`。

### 历史字节回归

- **223：3/3 成员逐字节一致**，摘要 `work/m4a/baseline/223.json`。
- **221：11 个 ZIP、310/310 成员逐字节一致，差异 0**；旧 manifest 语义一致、固定上游 schema 通过，摘要 `work/m4a/baseline/221.json`。

221 验证的是成员与归档契约；ZIP 容器摘要可以不同，也不表示其历史风险 PF3 内容通过当前公开交付门禁。

## 反证与验证范围

新增测试覆盖草稿版本/身份错误、输入与素材摘要漂移、错误输出目录/覆盖、prepush 和 compat 失败传播、跨根同路径冲突、双形态草稿覆盖、缺图标、稀疏 atlas 串帧、锚点越界、预算超限、未改动作变化、语音新路径/VBR/截断、共享键未确认、错表错块、错误列映射、行数/完整行断言缺失、镜像缺失/漂移、违规文案、文本误绑定及非法技能档位。缺真实视图的 skip 与 ImportError 不应 skip 也有反例。

全量 pytest、路径扫描及卫生检查的最终退出码、计数与 SHA-256 见 [结构化验收摘要](docs/studio/validation-m4a.json)。

冻结源码 `a4cf8ef` 的全量结果为 **4178 passed、355 skipped、26 warnings，exit 0**；外层耗时 448.35 秒。JUnit 含子测试累计 6799 项、skipped 358、failures 0、errors 0，与终端主测试口径分列。跳过项主要是未配置的外部源码/完整数据和真实视图，不能计为通过。路径扫描 2159 个文本文件、**0 命中**；提交卫生与 `git diff --check` 通过。最终仅补文档与证据摘要，未改变已验证源码。

## 保留边界

- 所有真实交付 prepush exit 0，但本地验证快照没有 `out/routes/cn/asset.js`，原有 **kulo #35 检查保留“待验证”**。M1 本地版本边、seq、重复和前后摘要检查实际已执行；不将缺失的服务模块检查写成通过。
- v34 compat 使用能力与方法摘要做静态匹配；没有设备运行、真机视觉或服务端生效证明。实测字段保持“未执行”。
- 非末尾像素动作须保持总时长，可改变帧数及逐帧时长；会影响其它槽区间的请求明确拒绝。末槽可调整时长，其他槽不平移。
- 立绘说明 sheet 沿用已有近似 fit 构图；ATF 结构与尺寸经过检查，未作设备验证。
- 缺少三表 `tableBefore` 的旧立绘草稿须重新保存裁剪。技能挂接与后续文本编辑分请求；一次文本请求同格只出现一次并断言全部实际档位。
- 后端 CLI 已能生成交付；前端生成/导出按钮仍未接线。应用、发布及新增语音台词不在本任务范围。

## 本地提交

- `d9b1684`：来源配置 API 与便携测试 fixture。
- `b9dce61`：交付桥、CLI/API 接线及接口反证。
- `142f90b`：媒体编译、旧值和 atlas 检查。
- `8616012`：生成/导出操作元数据说明。
- `7c8002b`：词条、文本、技能档位和 schema。
- `a4cf8ef`：立绘精确 CDN 根读取与冲突根反证。

最终报告、接口说明和结构化验收摘要另作本地文档提交。没有 push、merge 或发布。
