"""Canonical entry point for Stylize Normals Toolkit."""

from stylized_normals import __version__
from stylized_normals import launch as _launch


def launch():
    return _launch()


def smart_launch_normal_tool():
    """Compatibility-friendly shelf launch function."""
    return launch()


# Importing this module intentionally does not create UI or modify the scene.
