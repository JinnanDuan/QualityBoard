# -*- coding: utf-8 -*-
"""
OH 平台「日报数据」导出 — 表格格式定义（唯一权威来源）。

仓库不依赖「数据导出模板.xlsx」；若需调整列名、行顺序或主模块归属，只改本文件。

**逻辑布局（与 Excel 粘贴后一致，共 7 行 × 6 列）**

- 第 1 行（表头）：`OH_DAILY_EXPORT_HEADER_ROW` — 组件、Total、Success、Fail、NewFail、通过率。
- 第 2~7 行：A 列为组件分类中文名；B~F 列为该分类的 total、success、fail、newFail、通过率（文本）。

**导出形态**：制表符分隔（TSV），每行 6 个字段。

**统计口径**（由 Service 实现，与本文件分工）：单批次 + OH 平台白名单 + 本文件列出的 main_module；
按 case_name 去重聚合。**NewFail**：在「小于当前批次且最大的上一批次 B」中该用例为成功，在当前批次 A 中为失败的去重用例数（无满足条件的 B 时为 0）。
"""

from typing import List, Tuple

# ----- 表头：第 1 行 A1~F1 -----
OH_DAILY_EXPORT_HEADER_ROW: Tuple[str, ...] = (
    "组件",
    "Total",
    "Success",
    "Fail",
    "NewFail",
    "通过率",
)

# ----- 数据行：A 列展示名 + 纳入该行的 main_module 精确匹配列表（顺序即导出行序） -----
OH_DAILY_EXPORT_ROWS: List[Tuple[str, Tuple[str, ...]]] = [
    ("后端 & DFX", ("App", "Terminal", "LOG", "Git", "GIT", "TrustWorkspace")),
    ("编辑器 & 前端组件", ("Problem", "Hover", "Other", "Settings", "Editor", "Explorer", "FileExplorer")),
    ("IDE框架", ("Workbench", "Window", "webview", "Scaffold", "Notification")),
    (
        "插件生态 & 调试",
        (
            "AIChatView",
            "LSP",
            "PluginLSP",
            "PluginDebug",
            "PluginAPI",
            "PluginE",
            "PluginC",
            "Output",
            "Debug",
        ),
    ),
    ("智能辅助编写", ("AIFE",)),
    ("智能辅助阅读", ("AIPI",)),
]
