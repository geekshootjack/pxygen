from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("pxygen")
except PackageNotFoundError:
    __version__ = "unknown"
