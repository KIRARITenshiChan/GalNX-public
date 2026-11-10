# examples/nsp/ — NSP 自包含打包的输入模板

M3-a 实测用的 NPDM 配置模板（`npdmtool` 的 JSON 输入）。`scripts/build_nsp_demo.sh`
会读取本文件、把 `title_id` 替换成调用方给的 TitleID，再交给 `npdmtool`。

## 来源与许可

- 权限/服务/syscall 列表取自 **nx-hbloader** 的 `hbl.json`（ISC，switchbrew/nx-hbloader @ v2.4.5），
  因为它是「可安装 homebrew 应用」的已知可用配置。
- 结构对照 **hacBrewPack** 的 `template/npdm.json`（GPL-2.0，rlaphoenix/hacBrewPack @ v3.05）。
- 本文件是配置数据（不是代码），随本仓库文档一起分发；不含任何密钥。

## 与上游的差异（实测必须改）

`debug_flags` 三个布尔值在上游模板里同时为 true，devkitPro 2024 版 `npdmtool` 会拒绝：

```
Only one of allow_debug, force_debug, or force_debug_prod can be set!
Failed to parse descriptor json!
```

改成 `allow_debug=true`、其余两个 false 后 `npdmtool` 退出码 0。详见
`docs/builds/005-nsp-selfcontained.md`。

## title_id 约束

hacBrewPack 要求 `0x0100000000000000`–`0x0fffffffffffffff`（小写 16 位十六进制），
建议不超过 `0x01ffffffffffffff`（零售应用区）。同一个 TitleID 不要与已安装应用冲突。
