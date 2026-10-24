# 编辑台词条词汇表

效果卡、原始列的「含义」、按名选择和速查的「查类型」共用
`GET /api/studio/ability/glossary`。模板接口也使用相同的官方短名。
词汇表只读；选择枚举仍调用原有 `onCell`，不改变草稿请求或数值语义。
`action_skill` 不使用这份词汇表。

## 官方词来源

- `ability_enum_map.json` 和 `wf_describe.enum_options()` 提供值、英文构造名、直译和使用次数快照。
- `ability_official_map.json`（schemaVersion 2）保存每个值对应的客户端字符串键和相对 AS3 路径、行号。
  `as3` 表示主表解析器、内部枚举和取词分支之间存在静态证据；
  `guess` 只表示构造名转蛇形的候选，证据列表为空。一个值可对应多个条件分支的键。
  `bindings` 继续记录「外层模板 → env.push / getUiStringWithContext 参数 → 条件名词 / 固定属性」的链，
  支持条件名词内部再次插入属性；每条绑定保留相对路径和行号。
- 运行时从当前视图的 `master/string/ui_string.orderedmap` 读取原文，
  按枚举组限定主模板：效果使用 `condition_content_*` / `common_content_*` / `instant_content_*`，
  触发使用相应的 `trigger_kind_*`，开幕使用 `opening_kind_*`。
  `condition_target_*` 是插入的名词；合击前缀、目标串、分隔符、计数附加串不能充当效果类型名。
- AS3 已确定的条件和属性按绑定填入；构造名尾部的 Red / Blue / Yellow / Green / White / Black / AllElement
  分别补为火 / 水 / 雷 / 风 / 光 / 暗 / 全属性，也用于伤害模板的 `element_short`。
  敌方 Frozen 使用「迟缓」，队友对应效果使用「疲惫」。`Second` / `Third` 填入固定序号。
  条件的属性与效果的属性分别解析：例如 `ElementResistanceToResistanceRedUpEnemy` 的敌方条件确定为火抗性提升，
  其外层抗性属性仍依赖行数据，不能一起猜成火。
- 数值、对象及其他未确定的必填参数统一显示 `…`，相邻省略号合并。
  目标 / 来源显示块保留参数位置，例如「迟缓效果中的敌人对…造成的伤害减少…」。
  其余依赖行数据的可选条件块整体省略，不选定某一分支；HTML 图标标签清理掉。
  「技能槽在…以上时」「对敌人造成…威力的…伤害」保留缺失参数位置，不把句子删断。
- 类型级短名保持强度方向中性：391 为「…的攻击力…」，393 为「…的火抗性…」。
  效果卡也复用中性名，正负强度继续由数值列显示，不将负强度解释成提升。
  如果外层模板本身按正负切换且不存在中性版本（如 470 的逆境 / 萎缩），使用直译回退。
- 没有合适的主模板、主模板缺失或没有可读文字时，`official` 为 `null`，界面显示直译。
  629 `InvokeSkill` 只有目标辅助串，因此回退「发动技能动作」。
  响应的 `officialTemplate` / `officialKey` / `officialArguments` / `evidence` 保留原文及插入来源，鼠标悬停可查看。
- 缓存按 source 实例隔离，不按版本字符串合并；两个相同版本号、不同叠加内容的视图不会共享词汇表。

## 重建静态对照

在仓库根目录运行：

```powershell
py -3 scripts/generate_ability_official.py --as3 '<客户端反编译 scripts 根目录>'
```

默认输出仓库根目录的 `ability_official_map.json`；可用 `--out` 指定输出路径。
脚本只读 AS3，输出记录所引用源文件的 SHA256。运行时不依赖反编译树。
解析器只识别本客户端反编译格式中的枚举、switch、已知条件及说明辅助函数，
不执行 AS3。未知 selector 不被猜成某个分支；可选角色组保留有/无过滤两种候选。
开关、觉醒方式、无效果、动态文本表中的词和归档客户端没有的扩展值，可能没有静态 UI 字符串键。
角色组中的种族、性别、标签由其他主表取名，本接口继续保留描述器的直译。

## 官方短名回归统计

以下为同一份 UI 字符串快照的修前 / 修后对比，口径为「不同短名数 / 有官方短名的值数」。
仅统计非空 `official`，直译回退不计入；同义、目标不同而效果相同的值仍可能重名。
测试夹具只保存对照表引用的 411 条字符串，来源为
`pinball-1.4.187-1.4.188-3-liangyue-character-local.zip` 中的 `ui_string`，
原始数据 SHA256 为 `e59f4d48fb11d355840a81b45b5cb7482845886503808e3aa3a0d369b5e7d477`。

| 枚举组 | 修前 | 修后 |
| --- | ---: | ---: |
| precondition | 87 / 204 | 158 / 206 |
| trigger | 111 / 259 | 239 / 259 |
| during_trigger | 94 / 229 | 175 / 230 |
| instant_content | 136 / 717 | 496 / 715 |
| during_content | 83 / 421 | 407 / 421 |
| target | 13 / 14 | 13 / 14 |
| instant_puller | 10 / 10 | 10 / 10 |
| during_puller | 11 / 11 | 11 / 11 |
| precontent | 4 / 4 | 4 / 4 |
| precontent_target | 4 / 4 | 4 / 4 |
| multiply | 3 / 3 | 3 / 3 |
| opening | 1 / 3 | 3 / 3 |
| mode | 0 / 0 | 0 / 0 |
| element | 7 / 7 | 7 / 7 |
| character_group | 6 / 6 | 6 / 6 |
| awake | 0 / 0 | 0 / 0 |
| boolean | 0 / 0 | 0 / 0 |
| cancelable | 0 / 0 | 0 / 0 |
| power_flip_levels | 0 / 0 | 0 / 0 |

瞬发效果有短名的值从 717 降至 715，是 629 和 470 的错误命名改为明确回退。
五个大组同时设置不同短名数、覆盖数和去重比例的下限，避免靠删掉重复值通过测试：
分别为 `150 / 200 / 70%`、`230 / 250 / 85%`、`165 / 225 / 70%`、
`475 / 705 / 65%`、`390 / 415 / 90%`，顺序与上表前五行一致。

| 枚举组 / 值 | 修后短名 |
| --- | --- |
| instant_content / 119 FrozenSlayer | …对迟缓效果中的敌人造成的伤害… |
| instant_content / 311 ResistanceToFrozenEnemy | 迟缓效果中的敌人对…造成的伤害减少… |
| instant_content / 410 EnemyConditionFrozen | 施加…迟缓效果 |
| instant_content / 2 ConditionResistanceAllElement | …的全属性抗性… |
| instant_content / 3 ConditionResistanceRed | …的火抗性… |
| instant_content / 391 EnemyConditionAttackPoint | …的攻击力… |
| instant_content / 629 InvokeSkill | 发动技能动作（直译；official 为 null） |
| opening / 0 MyselfExpBoost | 自身获得的经验值提升… |
| opening / 1 AllyExpBoost | 队伍全体获得的经验值提升… |
| opening / 2 ManaBoost | 玛纳获得数量提升… |

## 挑选框键盘规则与验证

Enter 和上下箭头只由搜索框、可聚焦列表处理；中文输入法组合输入期间忽略 Enter。
对话框只统一处理 Escape。关闭按钮上的 Enter 保留按钮原生激活行为，不调用 `onPick`。
Node 测试直接编译实际 TSX 组件并调用 VNode 处理器，覆盖搜索、列表、空结果、输入法、
关闭按钮冒泡及正负强度下的中性名称；这不是完整浏览器端到端测试。

```powershell
# 仓库根目录；沿用本工作区已有的隔离依赖
$env:PYTHONPATH = 'work/glossary-test-deps'
py -3 -m pytest tests/test_studio_ability.py tests/test_describe.py tests/test_studio_glossary.py -q

# studio/ 目录
node --test tests/*.test.mjs
npm.cmd run build
```

Python 测试无需本机反编译树或服务进程；用精简字符串夹具覆盖完整枚举，
并用临时 AS3 片段验证主模板、`env.push` 及嵌套属性链的提取。

## 数值规则

字段位置由现有 layout / block_fields 推导，两张原生表分别返回列号。
瞬发与持续来源不同；持续累积触发、倍增来源沿用瞬发来源表。
前置效果目标使用独立的五值表。

| 字段 | 显示规则 |
| --- | --- |
| 普通强度 | 除以 1000，显示百分比 |
| 计数型强度 | 沿用 `_desc_content` 的类型和双端点整除判断；十万为 1 |
| 帧数 | 除以 100000 得帧数，再除以 60 得秒数 |
| 冷却 | 原始帧数，除以 60 得秒数 |
| 次数 | 除以 100000 得次数 |
| 触发次数上限 | 原始次数 |
| 瞬发延迟 | 原始秒数 |
| 阈值 | 沿用 `_threshold`：正整数十万倍按次/层/个，其余按千分比 |

`time`、不明确的倍率、ID 等字段不猜换算。换算值为 0、空、`(None)` 时不显示提示。
枚举值 0 仍可能代表「自身」「瞬发」等有效类型。未识别的枚举值显示「未知值」。
这些提示用于解释原始值，不替代现有类型校验和实际运行验证。
