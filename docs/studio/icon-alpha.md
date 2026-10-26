# 派生图标透明区检查

编辑台保存立绘派生时立即检查；交付时重新读取草稿图标和源立绘，再核对一次。
共享 `wf.chars.support.images.make_icons` 的默认底色行为保持不变。

检查复用生产 `crop_at` 的脸锚、组取景倍数、主槽尺寸和两次 LANCZOS 缩放。
源 alpha 小于 128 且形状蒙版 alpha 至少 128 的像素组成分母；其中图标 alpha
至少 128 的像素组成分子。比例严格大于 0.02 时记录
`ICON_BACKDROP_FILLS_TRANSPARENCY`。`skill_cutin` 不参与。

`template.backdrop` 为 null 时是 `warning` / `level=warn`；显式选择底色时是
`info` / `level=info`，消息写明“作者选择了底色”。两者均不阻断交付。
保存阶段沿用草稿 schema 的 `portrait.icon_alpha` 检查码，消息带上述完整告警码。

交付写 `delivery/icon-alpha.json`，详情接口字段为 `iconAlpha`（旧交付无文件为 null）：

```json
{"status":"warning","threshold":0.02,"slots":[
  {"slot":"square","form":"0","threshold":0.02,"authorBackdrop":false,
   "sourceTransparentPixels":100,"filledPixels":10,"ratio":0.1,
   "status":"warning","level":"warn","code":"ICON_BACKDROP_FILLS_TRANSPARENCY",
   "blocking":false,"message":"square：源透明区被填充 10.00%（阈值 2%）"}
]}
```

`status` 为 `ok`、`warning`、`info` 或 `skipped`；没有派生图标时 `skipped` 带 `reason`。
槽位检查同样进入 `draft-checks.json`。形状蒙版仅使用编辑台生成并有 SHA-256 校验的缓存。
旧草稿缺模板或缺蒙版时明确记录 `ICON_ALPHA_NOT_CHECKED`，缺蒙版的槽位 `ratio=null`，
没有蒙版的方形槽仍可完成检查；损坏的蒙版缓存报错，需要重新派生。
