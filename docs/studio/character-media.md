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
