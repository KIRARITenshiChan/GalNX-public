# 第三方资源登记（docs/third_party）

本目录只登记**GalNX 仓库内合法再分发的第三方资源**（字体、图标、测试夹具等），并保存其许可原文。

## 机器可读清单与校验

- [inventory.yaml](inventory.yaml)：仓库全部第三方组件与产物的许可清单（33 个组件 / 4 个产物），字段说明见文件头。
- [../../scripts/check_license_inventory.py](../../scripts/check_license_inventory.py)：清单校验器，运行 `python scripts/check_license_inventory.py --json`（退出码 0/1）。
- 仓库级分发边界与合规结论（含 FFmpeg GPL 风险）见 [../../THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)。

## 硬性规则

1. **不放商业游戏数据**：任何商业游戏的脚本/图片/音频/ROM/存档一律不进本仓库，也不作为构建输入提交。
2. **不放密钥**：`prod.keys`/`title.keys` 等不进入仓库、不进日志、不进 CI（见计划 v0.4 §7.5 与审计 v1.3 §4.D.7）。
3. **每项必须可溯源**：记录来源 URL、获取方式、版本/日期、文件大小、SHA-256 与许可名称，并把许可原文一并保存。
4. **仅用于测试夹具**：这些资源用于构建可复现的测试用 NRO，不并入 GalNX 的对外发布物，除非单独评估。

## 已登记资源

| 资源 | 用途 | 许可 | 文件 | 大小 | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| IPAexGothic（IPAexゴシック）004.01 `ipaexg.ttf` | M1 KAG3 测试内容包的内嵌字体（`system_polyfill/font.ttf`） | IPA Font License 1.0（可再分发，需随附许可文本） | 不存二进制，见下方获取方式 | 6,099,900 B | `3b9955a5e437ffb24c41548e79296fa724822da21ee75dc1b94f6ccdb8f400dd` |
| IPA Font License 1.0 原文 | 上项许可 | - | `fonts/IPA_Font_License_Agreement_v1.0.txt` | 20,564 B | `4c84dd528ec3044638ec346fc1ee27cd1eb95dfc04cbc6a881b3ca7a7f517e54` |
| IPAexGothic Readme | 上项说明 | - | `fonts/Readme_ipaexg00401.txt` | 1,710 B | `567d253f2adb5bc6424fd2592550d225a39f919131e4a0cc0caa4d788e259a60` |

### IPAexGothic 004.01 获取方式

```
# 经本机代理下载（Cloudflare/地区限制少；直连也可以）
curl -x http://127.0.0.1:7897 -L -o ipaexg00401.zip https://moji.or.jp/wp-content/ipafont/IPAexfont/ipaexg00401.zip
unzip ipaexg00401.zip   # 得到 ipaexg00401/ipaexg.ttf + 两份文本
```

- 官方页面：https://moji.or.jp/ipafont/ （IPAexフォント）
- 实测：2026-10-30，zip 4,166,255 B，HTTP 200。
- 许可要点（详见原文）：允许再分发与嵌入，但再分发时必须随附 IPA Font License 1.0 文本；不得单独以字体文件形式销售；名称不得注册为商标。

## 候选但未采用

| 资源 | 许可 | 未采用原因 |
| --- | --- | --- |
| Noto Sans CJK JP Regular（`NotoSansCJKjp-Regular.otf`，16,467,736 B，OFL-1.1） | OFL-1.1 | 体积大（+16.5 MB RomFS）；若后续需要更广汉字覆盖再切换 |
| Noto Sans JP 变量字体（`NotoSansJP[wght].ttf`，9,589,900 B，OFL-1.1） | OFL-1.1 | 变量字体在 devkitPro FreeType 上的兼容性未验证 |
| KAG3 demo 自带「梅ゴシックO5」 | 未核实 | 许可不明确，不用作可分发夹具 |