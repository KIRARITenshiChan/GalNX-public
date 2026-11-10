# examples/batch —— galnx batch 演示项目

四个 manifest 演示 `galnx batch run` 的扫描、隔离与报告行为，以及 `galnx batch build` 的真实构建执行/缓存：

| 文件 | 项目 | adapter | 预期状态 | 说明 |
| --- | --- | --- | --- | --- |
| `demo-a.yaml` | batch-demo-a | krkrsdl2 | ok | 正常项目，`games/demo-a/data.xp3` 为占位文件；未声明 `build.commands`，`batch build` 下 build 阶段 skip |
| `demo-b.yaml` | batch-demo-b | brewser | ok | 正常项目，`games/demo-b/index.html` 为占位文件；同上 |
| `demo-broken.yaml` | batch-demo-broken | （缺失） | fail | 故意缺 `engine` 段且 title_id 非法，用于验证隔离 |
| `demo-build.yaml` | batch-demo-build | custom（内联描述符 `engines/custom-demo.yaml`） | ok | M6-b 构建演示：`build.commands` 调 `games/demo-build/build.py` 生成确定性产物 `out/demo.bin` |

`games/` 下是占位 fixture，不是真实游戏数据；`demo-build.yaml` 的构建只跑本仓库 Python 脚本，不调用 devkitPro/模拟器。

## 运行

在仓库根目录执行：

```bash
PYTHONPATH=src python -m galnx batch run --dir examples/batch
```

预期输出摘要：

```text
3 project(s): 2 ok, 0 warn, 1 fail, 0 skipped
  [FAIL] demo-broken.yaml  adapter=-
  [OK] demo-a.yaml  adapter=krkrsdl2
  [OK] demo-b.yaml  adapter=brewser
report: <repo>/examples/batch/.galnx/batch-report-<UTC时间戳>.json
```

退出码为 `2`（存在 fail 项目）。报告写在 `examples/batch/.galnx/`，该目录被 `.gitignore` 忽略；跑完可清理：

```bash
PYTHONPATH=src python -m galnx batch clean --dir examples/batch --yes
```

`demo-broken.yaml` 的失败原因（缺 `engine`、title_id 不匹配 `^01[0-9A-Fa-f]{14}$`）正是 `manifest` 阶段 schema 校验的输出示例。

## 构建演示（M6-b）

```bash
# 第一次：cache miss，执行 build.py（约 0.3s）
PYTHONPATH=src python -m galnx batch build --dir examples/batch

# 第二次：cache hit，不执行命令
PYTHONPATH=src python -m galnx batch build --dir examples/batch

# 强制重建 / 禁用缓存 / 依赖锁定
PYTHONPATH=src python -m galnx batch build --dir examples/batch --rebuild
PYTHONPATH=src python -m galnx batch build --dir examples/batch --no-cache
PYTHONPATH=src python -m galnx batch lock --dir examples/batch
PYTHONPATH=src python -m galnx batch build --dir examples/batch --locked

# 单个项目
PYTHONPATH=src python -m galnx build run --manifest examples/batch/demo-build.yaml
```

产物写入 `examples/batch/out/demo.bin`（被 `.gitignore` 忽略），缓存与日志在 `examples/batch/.galnx/`。`demo-build.yaml` 使用内联引擎描述符 `engines/custom-demo.yaml`（`adapter: custom`、`build_backend: none`），因此不需要任何外部引擎/工具链，适合作为 CI 冒烟样例。

预期：前两次运行 `demo-a` / `demo-b` / `demo-build` 为 ok（`demo-broken` 仍 fail），第一次 `cache: 0 hit(s), 1 miss(es); built 1`，第二次 `cache: 1 hit(s), 0 miss(es); built 0`，整批退出码 `2`（因为 `demo-broken`）。
