"""Tests for terminal table rendering helpers."""
from __future__ import annotations

from pxygen.table_output import output_table


def test_output_table_does_not_print_directly_to_stdout(capsys):
    output_lines: list[str] = []

    output_table(
        "Render jobs:",
        ("Resolution", "Audio", "Clips", "Target"),
        [("3840x2160", "standard", 2, "/proxy/Day1")],
        output_lines.append,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    output_text = "\n".join(output_lines)
    assert output_text.count("Render jobs:") == 1
    assert output_text.count("3840x2160") == 1
