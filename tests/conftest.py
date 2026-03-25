"""Pytest configuration for the test suite.

DaVinciResolveScript is mocked here as a precaution, but after the refactor
it is only imported lazily inside process_files_in_resolve(), so unit tests for
paths / organize / resolve (pure functions) don't need the mock at all.
"""
import sys
from unittest.mock import MagicMock

_mock_dvr = MagicMock()
_mock_dvr.scriptapp.return_value = MagicMock()
sys.modules["DaVinciResolveScript"] = _mock_dvr
