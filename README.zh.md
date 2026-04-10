# pxygen

**DaVinci Resolve 自动化代理生成工具。**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![English](https://img.shields.io/badge/docs-English-blue)](README.md)

pxygen 将素材导入 DaVinci Resolve，按照文件夹层级自动建立媒体库 bin 结构，并批量排队代理渲染任务——一条命令完成全部操作。

## 功能特性

- **两种模式** — 直接从文件夹树导入，或基于 [File_Compare](https://github.com/UserProjekt/File_Compare) 的 JSON 结果重新生成缺失代理
- **智能编码选择** — 音频通道 ≤ 4 用 H.265，> 4 用 ProRes Proxy（解决 Adobe Premiere 兼容性问题）
- **烧录叠加层** — 自动叠加源片段名称与时间码；可用 `-c` 关闭
- **文件夹筛选** — 交互式选择拍摄日（`--select`）或按名称过滤（`--filter`）
- **跨平台支持** — macOS、Windows、Linux

## 环境要求

- Python ≥ 3.9，**必须是 64 位**
- DaVinci Resolve ≥ 19.1.4（运行脚本前需保持 Resolve 开启）
- Resolve 渲染预设：`FHD_h.265_420_8bit_5Mbps`、`FHD_prores_proxy`
- Resolve 数据烧录预设：`burn-in`

## 环境变量配置

DaVinci Resolve 通过环境变量暴露脚本 API，运行前需要设置：

<details>
<summary>macOS（标准安装）</summary>

```sh
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```
</details>

<details>
<summary>macOS（App Store 安装版）</summary>

```sh
export RESOLVE_SCRIPT_API="/Applications/DaVinci Resolve Studio.app/Contents/Resources/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve Studio.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```
</details>

<details>
<summary>Windows</summary>

```bat
set RESOLVE_SCRIPT_API=%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting
set RESOLVE_SCRIPT_LIB=C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll
set PYTHONPATH=%PYTHONPATH%;%RESOLVE_SCRIPT_API%\Modules\
set PATH=%PATH%;C:\Program Files\Blackmagic Design\DaVinci Resolve
```
</details>

<details>
<summary>Linux</summary>

```sh
export RESOLVE_SCRIPT_API="/opt/resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/opt/resolve/libs/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```
</details>

## 安装

```sh
pip install git+https://github.com/thomjiji/pxygen.git
```

或克隆后以可编辑模式安装：

```sh
git clone https://github.com/thomjiji/pxygen.git
cd pxygen
pip install -e .
```

## 快速上手

```sh
# 目录模式——导入素材并生成代理
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 4 -d 5

# JSON 模式——基于 File_Compare 结果重新生成缺失代理
pxygen -i comparison.json -o /Volumes/SSD/Proxy -g 1 -n 4 -d 5

# 只处理特定拍摄日
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 4 -d 5 \
  --filter "Shooting_Day_2,Shooting_Day_3"
```

典型素材目录结构：

```
Production/
├── Footage/
│   ├── Shooting_Day_1/
│   │   ├── A001_C001/
│   │   └── B001_C001/
│   └── Shooting_Day_2/
└── Proxy/          ← 代理输出到这里
```

## 文档

完整 CLI 参数说明与进阶用法：**[docs/usage.md](docs/usage.md)**

## 许可证

[MIT](LICENSE) — 基于 User22 的 [DaVinci_Script_Proxy_Generator](https://github.com/UserProjekt/DaVinci_Script_Proxy_Generator) 进行重构。
