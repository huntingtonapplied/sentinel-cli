"""Sentinel CLI — scan codebases for corruption from your terminal."""
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("sentinel-cli")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
