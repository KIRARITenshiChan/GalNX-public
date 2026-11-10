# 证据索引（docs/environment/evidence/）

| 文件 | 字节 | SHA-256 | 内容 |
| --- | ---: | --- | --- |
| `build.log` | 356 | `4692f60fb68aae291ee7e84b493628a114cda7b1ada4480d01ac935b18c8b737` | M0 构建日志原件（11 行，356 B；含主机名 GBK 字节，非 UTF-8） |
| `nro-sha256.txt` | 541 | `ece2503259ef7219f9814d9201fb321b513f2612fe97c9466cb7e59efefe0ce2` | 产物与 build.log 的 SHA-256/字节数 |
| `pacman-Q-switch.txt` | 5125 | `8d9f3d36d43a7278cc8007fa6206b2f2fe5c533136c5460b605a83c9375d5267` | pacman -Q 全量快照 + Switch 相关过滤 + switch-dev 组成员 |
| `pacman-qi-switch.txt` | 5083 | `99d7dbecfe45a89fb74aaf904211a28e71e762afdee0cd3cf424baeabf69879a` | pacman -Qi 元数据（版本/许可证/依赖/来源 URL/已安装大小） |
| `pacman-log-2026-10-29.txt` | 6527 | `ccbc72ca14b2c577161b5d37a196b56c98c2455571315a17cbef7dfe3e5d7542` | pacman.log 2026-10-29 关键时间线（含 15:36:07 switch-dev 静默失败与 22:07 成功事务） |
| `measure-2026-10-29.txt` | 18762 | `a3acb424ce45fcafc5ffb3cd634764146e2eb98876c14b7cc219947ccd439600` | 补测命令完整输出（gcc/ld/make/nxlink/pacman/缓存/du/fstab/profile.d/pacman.conf） |
| `cache-sha256-switch.txt` | 3606 | `48c6403e36e3c5a9b81863a79dc3f7dfb9eae35d6b0938a582a92623146e615e` | /var/cache/pacman/pkg 中 Switch 相关包与 SHA-256 |
| `env-snapshot-switch.txt` | 2322 | `70e868d0a82b05b64d2ecdff04a9999f8ec33922ebd3b185cfcb02ac1c3b8cb6` | raw_env_snapshot.txt 的 Switch 相关节选 |
