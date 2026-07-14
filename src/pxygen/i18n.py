"""Minimal runtime language switch for user-facing text.

Chinese is the source language, hardcoded at every call site so the code
stays readable; :func:`_` returns the English translation when the
``PXYGEN_LANG`` environment variable starts with ``en``. The catalog keys
are the Chinese template strings themselves (gettext-style), so adding a
message means writing it once in the code and once in ``_EN`` below.

Untranslated strings fall back to Chinese; ``tests/test_i18n.py`` guards
the catalog against drifting out of sync with the call sites.
"""
from __future__ import annotations

import os


def _(text: str) -> str:
    """Return *text* in the active UI language (zh source, en override)."""
    if os.environ.get("PXYGEN_LANG", "").lower().startswith("en"):
        return _EN.get(text, text)
    return text


_EN: dict[str, str] = {
    # --- cli.py ---
    "把素材文件夹或 fcmp JSON 报告传给 --input, 自动识别模式":
        "Pass a footage folder or an fcmp JSON report to --input;"
        " the mode is detected automatically",
    "示例:": "Examples:",
    "素材文件夹或 fcmp JSON 报告": "Footage folder or fcmp JSON report",
    "代理输出文件夹": "Proxy output folder",
    "输入文件夹之下第几层作为一个素材分组":
        "Levels below the input folder to treat as one footage group",
    "输入文件夹之下第几层保留为子文件夹":
        "Levels below the input folder to preserve as subfolders",
    "JSON 模式: 渲染 fcmp 的哪一侧 (a = unique_in_a, b = unique_in_b)":
        "JSON mode: fcmp side to render (a = unique_in_a, b = unique_in_b)",
    "交互式选择要处理的文件夹": "Interactively select which folders to process",
    "只处理指定名称的文件夹 (如 Day1 Day2)":
        "Folder names to process (e.g. Day1 Day2)",
    "渲染编码 (≤4 音轨用 h265, 更多音轨用 ProRes)":
        "Render codec (h265 for ≤4 audio ch, ProRes otherwise)",
    "日志详细程度": "Logging verbosity",
    "可选: 详细运行日志的输出文件路径":
        "Optional file path for detailed runtime logs",
    "所有渲染任务已添加, 现在开始渲染? (y/n)":
        "All render jobs added. Start rendering now? (y/n)",
    "缺少 -o/--output 输出目录": "requires -o/--output",
    "已中止": "Aborted",
    "Resolve API 错误: %s": "Resolve API error: %s",
    "请确认 DaVinci Resolve 正在运行": "Make sure DaVinci Resolve is running",
    # --- modes.py ---
    "输入编号如 '1 3 8', 范围如 2-4, 'all' 全选, 'q' 退出":
        "Numbers like '1 3 8', range like 2-4, 'all', or 'q' to quit",
    "({} 项)": "({} items)",
    "文件夹 ({} 个):": "Folders ({}):",
    "无效的 side 值 '{}', 必须是 'a' 或 'b'":
        "Invalid side value '{}'; must be 'a' or 'b'",
    "读取 JSON 文件失败: {}": "Error reading JSON file: {}",
    "这是旧版 File_Compare 报告; pxygen 只支持 fcmp 的 JSON 报告"
    " (unique_in_a / unique_in_b), 请用 fcmp 重新比对":
        "This looks like a legacy File_Compare report; pxygen reads fcmp JSON"
        " reports (unique_in_a / unique_in_b). Re-run the comparison with fcmp",
    "已从 frame_mismatches 追加 {} 个文件 (side {})":
        "Added {} file(s) from frame_mismatches (side {})",
    "unique_in_{} 中没有文件": "No files found in unique_in_{}",
    "深度值 (-n/-d) 必须 ≥ 0": "Depth values (-n/-d) must be ≥ 0",
    "输出深度 (-d) 必须 ≥ 输入深度 (-n)":
        "Output depth (-d) must be ≥ input depth (-n)",
    "报告中没有素材根目录 ({}.directories 缺失或为空), 请用 fcmp 重新比对":
        "No footage root in the report ({}.directories missing or empty);"
        " re-run the comparison with fcmp",
    "报告文件": "json file",
    "比对侧": "side",
    "素材根目录": "root",
    "深度": "depths",
    "文件数": "files",
    "示例": "example",
    "分组文件夹": "folder name",
    "分组片段": "key fragment",
    "JSON 模式": "JSON mode",
    "不在 {} 目录之下": "outside the {} directories",
    "距素材根目录不足 {} 层, 无法按 -n {} 分组":
        "less than {} folder level(s) below the footage root"
        " (cannot group at -n {})",
    "警告: 跳过 {} 个文件 ({}):": "Warning: skipped {} file(s) ({}):",
    "没有文件能归入素材根目录之下的分组":
        "No files could be grouped below the footage root",
    "警告: 筛选无匹配文件夹: {}": "Warning: no folders match the filter: {}",
    "可选文件夹: {}": "Available folders: {}",
    "筛选后没有可处理的文件夹": "No folders to process after filtering",
    "素材文件夹不存在: {}": "Footage folder does not exist: {}",
    "'{}' 之下深度 {} 处没有文件夹": "No folders inside '{}' at depth {}",
    "目录模式": "Directory mode",
    "素材": "footage",
    "{} (深度 {})": "{} (depth {})",
    "代理": "proxy",
    "文件夹数": "folders",
    "筛选无匹配文件夹: {} (可选: {})":
        "No folders match the filter: {} (available: {})",
    "共处理 {} 个文件夹": "Total folders to process: {}",
    # --- resolve.py ---
    "找不到 DaVinci Resolve 脚本模块. 请手动设置 RESOLVE_SCRIPT_API 和"
    " RESOLVE_SCRIPT_LIB — 参见 README.md 的 Environment Setup 一节":
        "Could not find DaVinci Resolve scripting modules. Set"
        " RESOLVE_SCRIPT_API and RESOLVE_SCRIPT_LIB manually — see the"
        " Environment Setup section in README.md",
    "无法连接 DaVinci Resolve, 也找不到它的可执行文件来启动."
    " 请手动启动 Resolve, 并确认 Preferences → System → General 里"
    " 'External scripting using' 设为 Local":
        "Could not connect to DaVinci Resolve and could not locate its"
        " executable to launch it. Start Resolve manually, and check that"
        " 'External scripting using' is set to Local in Preferences →"
        " System → General",
    "Resolve 未运行, 正在启动...": "Resolve is not running — launching it...",
    "启动 Resolve 失败: {}": "Failed to launch Resolve: {}",
    "等待 Resolve 接受脚本连接 (最多 {} 秒)...":
        "Waiting for Resolve to accept scripting connections (up to {}s)...",
    "Resolve 已就绪": "Resolve is up",
    "Resolve 启动后 {} 秒内未接受脚本连接. 请确认 Preferences →"
    " System → General 里 'External scripting using' 设为 Local,"
    " 然后重新运行 pxygen":
        "Resolve did not accept scripting connections within {}s of"
        " launching. Check that 'External scripting using' is set to Local"
        " in Preferences → System → General, then re-run pxygen",
    "无法连接 DaVinci Resolve. 请确认 Resolve 正在运行, 且"
    " Preferences → System → General 里 'External scripting using'"
    " 设为 Local":
        "Could not connect to DaVinci Resolve. Make sure Resolve is running"
        " and 'External scripting using' is set to Local in Preferences →"
        " System → General",
    "与 DaVinci Resolve 的连接已断开 — 它可能崩溃了."
    " 请重启 Resolve 并重新运行 pxygen 处理剩余文件夹":
        "Lost connection to DaVinci Resolve — it may have crashed. Restart"
        " Resolve and re-run pxygen for the remaining folders",
    "已导入 {}/{}  {}": "imported {}/{}  {}",
    "无法从素材创建时间线 {!r}": "Failed to create timeline {!r} from clips",
    "无法切换当前时间线到 {!r}": "Failed to set current timeline to {!r}",
    "无法将时间线 {!r} 的设置 {!r} 设为 {!r}":
        "Failed to set timeline {!r} setting {!r} to {!r}",
    "时间线 {!r} 的设置 {!r} 未生效 (期望 {!r}, 实际 {!r})":
        "Timeline {!r} setting {!r} did not stick (expected {!r}, got {!r})",
    "渲染任务:": "Render jobs:",
    "{} 个片段": "{} clips",
    "正在处理 {} ({}/{})": "Processing {} ({}/{})",
    "Resolve 无法创建媒体池 bin {!r}":
        "Resolve failed to create media pool bin {!r}",
    "正在导入 {} 项到 Resolve (可能需要一些时间)...":
        "Importing {} item(s) into Resolve (may take a while)...",
    "所有渲染任务已添加, 现在开始渲染? (y/n/q)":
        "All render jobs added. Start rendering now? (y/n/q)",
    "已中止 — 渲染任务仍保留在已保存的 Resolve 项目中":
        "Aborted — render jobs remain queued in the saved Resolve project",
    "渲染已开始": "Rendering started",
    "项目已保存, 请在 DaVinci Resolve 中手动开始渲染":
        "Project saved. Start rendering manually in DaVinci Resolve",
}
