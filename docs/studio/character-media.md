# 角色媒体与缓存契约

## 资产清单版本

`GET /api/characters/<id>/assets` 保留 `groups`、`speech`、`cutins` 等清单字段，增加：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `sourceVersion` | string | 当前链视图的资源版本，例如 `1.4.233` |
| `draftRevision` | integer 或 null | 当前角色草稿的修订号；没有草稿时为 null |
| `assetsVersion` | string | 64 位小写 SHA-256；作为前端资产缓存失效键 |
| `etag` | string | 带双引号的 `assetsVersion`，位于 JSON 响应体 |
| `groups[].items[].sha256` | string，可省略 | 清单所选资源根中的原始存储字节哈希；缺失资源不返回 |

同一视图和同一草稿重复读取时版本稳定。源文件内容（包括相同大小的不同内容）、
源版本、草稿编辑、撤销、删除后重新建立草稿都会参与版本计算。
`assetsVersion` 覆盖整个清单与草稿描述，不能只用 `sourceVersion` 或草稿修订号代替。

前端读取清单后比较 `assetsVersion`；变化时丢弃相关媒体缓存。当前接口只在 JSON 中返回
`etag`，没有 HTTP 条件请求或 `304 Not Modified` 契约。

清单仍描述当前视图；对于新角色，描述克隆候选的初始资产，并通过 `cloneAssets` 标识后续派生状态。
草稿像素合成结果使用 `/api/drafts/<id>/pixels` 读取。缓存键变化不表示资产清单已经合成所有媒体编辑。
Studio 的已配置源视图在进程内保持不变，外部改写源文件后需重启载入。

## 克隆角色的像素工坊

克隆角色的像素拆解、帧切片、动作画板输入、整族重映射与程序化动作生成，
使用该角色的克隆候选作为基线。保存后的整族文件记录克隆候选资产的旧值哈希；
生成交付时以同一候选验证，避免将新代码路径误判成「原来不存在」。

- `GET /api/characters/<id>/pixel-workshop`、`.../cell/<family>/<key>.png`、
  `.../action/<family>/<action>` 可读取克隆角色。
- `POST /api/drafts/<id>/pixel-remap`、`.../pixel-generate` 沿用已有请求结构。
- `GET /api/characters/<id>/pixels/<family>.rgba` 返回克隆候选的基线像素。
- `GET /api/drafts/<id>/pixels` 与 `.../<family>.rgba` 返回整族改动和逐动作改动编译后的草稿像素。

克隆候选与 scratch 的 RGBA、帧切片，以及草稿预览返回 `Cache-Control: no-store`。
RGBA 格式保持不变：8 字节小端 `uint32 width, height`，随后是 `width * height * 4` 字节 RGBA。
源视图仍被多个角色共享；构造候选不会把新 ID 或其资产写回源视图。

## 语音行与多行字幕

`character_speech` 每行是五列：`kind, constraint, evo_level, subtitle, voice_path`。
`subtitle`（c3）允许 CSV 引号内换行，读取、克隆、替换音频后保持完整。
`voice_path`（c4）是单个不带 `.mp3` 的相对路径，或 `(None)` 表示无声字幕。
编辑台不会把 c3 的换行拆成新的语音槽位，也不会将 c4 换行当成连续播放多个音频。
克隆建稿和交付复查均拒绝 c4 中的 CR/LF，并给出阻塞错误。

`GET /api/characters/<id>/voice` 每条已注册路径仍是一条可替换音频；
`POST /api/drafts/<id>/voice` 只替换已有路径的 MP3。此次没有新增字幕编辑协议，
`compile_voices` 不改 `character_speech` 表字节。主页两态的可见行检查只计算 `kind=0`，
入队或进化行不能替代主页行满足该条件。

上述单路径约定已对照本机客户端源码核验：
`CharacterSpeechValues.as` 从 c4 构造单个 `Option<String>`，`Speech.as` 调用
`GeneralCharacterLogic.resolveVoicePath` 拼接目录，`HomeView.playVoice` 将整个路径交给
`ProductionSoundSection.loadAndPlay` / `loadAndPlayWithDetail`，后者将同一个路径传给 `setVoice`。
审查稿所称的 c4 多段连续播放、`speech_mode=inherit/omit`、语音编译器改写字幕及 87 列结构，
与当前仓库及已核验客户端实现不符。
