"""Tests for pxygen.i18n — the PXYGEN_LANG language switch."""
from __future__ import annotations

import ast
from pathlib import Path

import pxygen
from pxygen.i18n import _EN, _

_SRC_DIR = Path(pxygen.__file__).parent


def _wrapped_string_literals() -> set[str]:
    """Collect every string literal passed to `_()` across the package.

    Python folds adjacent string literals into a single ast.Constant, so
    multi-line concatenated messages come back as one key.
    """
    literals: set[str] = set()
    for source_file in _SRC_DIR.glob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                literals.add(node.args[0].value)
    return literals


class TestCatalogCompleteness:
    def test_every_wrapped_string_has_an_english_translation(self):
        missing = _wrapped_string_literals() - set(_EN)
        assert not missing, f"strings missing from _EN: {sorted(missing)}"

    def test_catalog_has_no_orphan_entries(self):
        orphans = set(_EN) - _wrapped_string_literals()
        assert not orphans, f"_EN entries no call site uses: {sorted(orphans)}"

    def test_translations_keep_the_same_placeholders(self):
        for key, value in _EN.items():
            assert key.count("{") == value.count("{"), key
            assert key.count("%s") == value.count("%s"), key


class TestLanguageSwitch:
    def test_defaults_to_chinese(self, monkeypatch):
        monkeypatch.delenv("PXYGEN_LANG", raising=False)
        assert _("渲染已开始") == "渲染已开始"

    def test_env_override_returns_english(self, monkeypatch):
        monkeypatch.setenv("PXYGEN_LANG", "en")
        assert _("渲染已开始") == "Rendering started"

    def test_env_value_is_case_insensitive_and_prefix_matched(self, monkeypatch):
        monkeypatch.setenv("PXYGEN_LANG", "en_US")
        assert _("渲染已开始") == "Rendering started"

    def test_unknown_string_falls_back_to_chinese(self, monkeypatch):
        monkeypatch.setenv("PXYGEN_LANG", "en")
        assert _("不存在的字符串") == "不存在的字符串"
