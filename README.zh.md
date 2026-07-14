# pxygen

**DaVinci Resolve 自动化代理生成工具。**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![English](https://img.shields.io/badge/docs-English-blue)](README.md)

pxygen 将素材导入 DaVinci Resolve，按照文件夹层级自动建立媒体库 bin 结构，并批量排队转码任务——一条命令完成全部操作。

## 功能特性

- **两种模式** — 直接从文件夹树导入，或基于 [fcmp](https://github.com/geekshootjack/fcmp) 的 JSON 报告重新生成缺失代理
- **智能编码选择** — 音频通道 ≤ 4 用 H.265，> 4 用 ProRes Proxy（解决 Adobe Premiere 兼容性问题）
- **文件夹筛选** — 交互式选择拍摄日（`--select`）或按名称过滤（`--filter`）
- **跨平台支持** — Windows、macOS

## 环境要求

- Python ≥ 3.10，**必须是 64 位**官方 python.org 版本（Resolve 脚本接口不兼容 uv 托管的 Python）
- DaVinci Resolve ≥ 19.1.4（未运行时 pxygen 会自动启动它）
- Resolve 渲染预设：`fhd-h265-5mbps`、`fhd-prores-proxy`
- Resolve 数据烧录预设：`burn-in-vertical`（居中布局，横竖屏通用）

## 环境变量配置

标准安装的 Resolve **无需任何配置**——pxygen 会自动探测各平台的标准脚本路径（macOS 标准版和 App Store Studio 版、Windows、Linux），并自行处理 `sys.path` 和 DLL 查找。

只有 Resolve 装在非标准路径时才需要手动指定：

```sh
RESOLVE_SCRIPT_API=<指向 .../Developer/Scripting 的路径>
RESOLVE_SCRIPT_LIB=<指向 fusionscript.dll / .so / .dylib 的路径>
```

## 安装

推荐使用 [uv](https://docs.astral.sh/uv/) 以工具方式安装：

```sh
uv tool install git+https://github.com/geekshootjack/pxygen          # 最新 main
uv tool install git+https://github.com/geekshootjack/pxygen@v2.0.0   # 锁定发布版本
uv tool upgrade pxygen                                               # 跟随已安装的 ref 更新
```

切换到其他版本时 `uv tool upgrade` 不会改变 ref，需强制重装：

```sh
uv tool install --force git+https://github.com/geekshootjack/pxygen@v2.1.0
```

或者免安装单次运行：

```sh
uvx --from git+https://github.com/geekshootjack/pxygen pxygen -i ... -o ...
```

### 离线安装

对于连不上 GitHub 的电脑：在任何一台能联网的机器上从 [Releases 页面](https://github.com/geekshootjack/pxygen/releases)下载 `.whl` 文件，用 U 盘或局域网拷过去，然后：

```sh
uv tool install ./pxygen-3.0.0-py3-none-any.whl
uv tool install --force ./pxygen-4.0.0-py3-none-any.whl   # 升级到新版 wheel
```

目标机器上仍需装有 [uv](https://docs.astral.sh/uv/) 和官方 python.org 版 Python。完整的从零离线部署清单（U 盘带齐 Python + uv + pxygen + Resolve 预设）见 **[docs/installation.md](docs/installation.md)**。

开发环境：

```sh
git clone https://github.com/geekshootjack/pxygen.git
cd pxygen
uv sync --all-groups
uv run pxygen --help
```

## 快速上手

```sh
# 目录模式——导入素材并生成代理
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 4 -d 5

# JSON 模式——基于 fcmp 报告重新生成缺失代理
pxygen -i fcmp_report.json -o /Volumes/SSD/Proxy -g a -n 4 -d 5

# 只处理特定拍摄日
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 4 -d 5 \
  --filter Shooting_Day_2 Shooting_Day_3
```

典型素材目录结构：

```
<项目文件夹>/
├── 素材/
│   ├── <拍摄日>/                # 260710
│   │   └── <机位类型>/          # 多机位、纪录
│   │       └── <机位编号>/      # FX3#1、FX6#2
│   └── <...>/
└── 代理/
    └── <拍摄日>/
```

## 文档

完整 CLI 参数说明与进阶用法：**[docs/usage.md](docs/usage.md)**

## 许可证

[MIT](LICENSE) — 基于 User22 的 [DaVinci_Script_Proxy_Generator](https://github.com/UserProjekt/DaVinci_Script_Proxy_Generator) 进行重构。
