"""Shared terminal table rendering helpers."""
from __future__ import annotations

import shutil
from collections.abc import Callable

from rich import box
from rich.console import Console
from rich.table import Table

OutputFn = Callable[[str], None]


def output_table(
    title: str,
    headers: tuple[str, ...],
    rows: list[tuple[object, ...]],
    output: OutputFn,
) -> None:
    """Render a plain-text rich table through the provided output callback."""
    output(f"\n{title}")
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="", expand=False)
    for index, header in enumerate(headers):
        kwargs = {}
        if index == 0:
            kwargs["justify"] = "right"
            kwargs["no_wrap"] = True
        elif header in {"Items", "Sub-folders", "Clips"}:
            kwargs["justify"] = "right"
            kwargs["no_wrap"] = True
        elif header == "Parameter":
            kwargs["no_wrap"] = True
        table.add_column(str(header), **kwargs)

    for row in rows:
        table.add_row(*(str(cell).replace("\n", " ") for cell in row))

    terminal_width = max(shutil.get_terminal_size(fallback=(160, 20)).columns, 120)
    console = Console(
        record=True,
        width=terminal_width,
        color_system=None,
        force_terminal=False,
        soft_wrap=False,
        legacy_windows=False,
    )
    console.print(table)
    for line in console.export_text(styles=False).splitlines():
        output(line)
