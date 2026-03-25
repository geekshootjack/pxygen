"""Tests for pure functions extracted from the Resolve layer.

calculate_proxy_dimensions() was previously a nested function inside
process_files_in_resolve() and therefore untestable. Extraction during
refactoring made it directly testable — this is a concrete benefit of
the restructuring.
"""
import pytest

from davinci_proxy_generator.resolve import calculate_proxy_dimensions


class TestCalculateProxyDimensions:
    def test_4k_landscape(self):
        w, h = calculate_proxy_dimensions("4096x2160")
        assert h == "1080"
        assert int(w) % 2 == 0  # must be even

    def test_uhd_landscape(self):
        w, h = calculate_proxy_dimensions("3840x2160")
        assert h == "1080"
        assert w == "1920"

    def test_1080p_passthrough(self):
        w, h = calculate_proxy_dimensions("1920x1080")
        assert w == "1920"
        assert h == "1080"

    def test_2_39_cinemascope(self):
        # 2.39:1 aspect ratio
        w, h = calculate_proxy_dimensions("2048x858")
        assert h == "1080"
        assert int(w) % 2 == 0

    def test_portrait_orientation(self):
        # Vertical video (e.g. 1080x1920)
        w, h = calculate_proxy_dimensions("1080x1920")
        assert h == "1080"
        assert int(w) > 0
        assert int(w) % 2 == 0

    def test_square_aspect(self):
        w, h = calculate_proxy_dimensions("1080x1080")
        assert w == "1080"
        assert h == "1080"

    def test_odd_width_rounded_to_even(self):
        # Force a case where naive rounding gives an odd number
        # 2.35:1 → 1080 * 2.35 = 2538 (even) — need a ratio that gives odd
        # 1.33:1 → 1080 * (4/3) = 1440 (even)
        # Use a contrived ratio to guarantee odd intermediate:
        # 1437x1080 → aspect = 1437/1080 = 1.330555...
        # 1080 * 1.330555 ≈ 1437.0 → round = 1437 (odd) → should become 1438
        w, h = calculate_proxy_dimensions("1437x1080")
        assert int(w) % 2 == 0

    def test_returns_strings(self):
        w, h = calculate_proxy_dimensions("3840x2160")
        assert isinstance(w, str)
        assert isinstance(h, str)
