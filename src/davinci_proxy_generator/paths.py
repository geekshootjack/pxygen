"""Path manipulation utilities.

All functions here are pure Python with no external dependencies.
Pathlib is used throughout for cross-platform correctness (Windows / macOS / Linux).
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


def clean_path_input(path: str) -> str:
    """Sanitize a path string from terminal drag-drop or manual entry.

    Handles:
    - Shell-escaped spaces and hashes (backslash-prefixed)
    - Surrounding double quotes and whitespace
    - Windows drive-letter normalisation to uppercase (e.g. 'c:' → 'C:')
    """
    path = path.replace("\\ ", " ").replace("\\#", "#")
    path = path.strip('" ').strip()
    # Normalise Windows drive letter: 'c:/...' → 'C:/...'
    if len(path) >= 2 and path[1] == ":":
        path = path[0].upper() + path[1:]
    return path


def path_parts(path: str | Path) -> list[str]:
    """Return depth-countable path components (no root separator, normalised drive).

    Equivalent to ``[p for p in str(path).split(os.sep) if p]`` on the host OS,
    but uses pathlib so it is correct on both Windows and Unix.

    Examples (macOS/Linux):
        '/Volumes/SSD/Footage/Day1' → ['Volumes', 'SSD', 'Footage', 'Day1']

    Examples (Windows):
        'C:\\Footage\\Day1' → ['C:', 'Footage', 'Day1']
    """
    path_str = str(path)
    path_cls = PureWindowsPath if _looks_windows_path(path_str) else PurePosixPath
    parts = path_cls(path_str).parts
    if not parts:
        return []
    result: list[str] = []
    for i, part in enumerate(parts):
        if i == 0:
            if part == "/":
                continue  # strip Unix root
            # Normalise Windows drive root: 'C:\\' → 'C:'
            result.append(part.rstrip("\\") if part.endswith("\\") else part)
        else:
            result.append(part)
    return result


def _looks_windows_path(path_str: str) -> bool:
    """Return True when *path_str* should use Windows path semantics."""
    return len(path_str) >= 2 and path_str[1] == ":" or "\\" in path_str


def _looks_windows_parts(parts: list[str]) -> bool:
    """Return True when *parts* represent a Windows drive-based path."""
    return bool(parts) and parts[0].endswith(":")


def compute_key_path(
    parts: list[str],
    in_depth: int,
    *,
    leading_sep: bool | None = None,
) -> str | None:
    """Build the grouping key for items at *in_depth* path components deep.

    Args:
        parts: Output of :func:`path_parts` (no root separator).
        in_depth: Number of components to include (must be ≥ 1).
        leading_sep: Prepend ``os.sep`` to the result. Defaults to *True* on
            Unix (to reconstruct absolute paths) and *False* on Windows (the
            drive letter already anchors the path).

    Returns:
        The joined path string, or *None* if *parts* is shorter than *in_depth*.

    Raises:
        ValueError: If *in_depth* is ≤ 0.
    """
    if in_depth <= 0:
        raise ValueError("in_depth must be a positive integer")
    if len(parts) < in_depth:
        return None
    key_components = parts[:in_depth]

    if leading_sep is None:
        leading_sep = not _looks_windows_parts(key_components)

    if _looks_windows_parts(key_components):
        drive = f"{key_components[0]}\\"
        windows_path = PureWindowsPath(drive, *key_components[1:])
        return str(windows_path)

    if leading_sep:
        return str(PurePosixPath("/", *key_components))
    return str(PurePosixPath(*key_components))


def is_json_file(path: str) -> bool:
    """Return *True* if *path* looks like a JSON file (by extension or by being a real file)."""
    path_obj = Path(path)
    return path_obj.suffix.lower() == ".json" or (path_obj.is_file() and not path_obj.is_dir())
