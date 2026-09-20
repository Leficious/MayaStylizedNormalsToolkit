"""Legacy compatibility entry point for StylizeNormalsToolkit."""

from StylizeNormalsToolkit import __version__
from StylizeNormalsToolkit import launch


def smart_launch_normal_tool():
    return launch()


def launch_smooth_normal_ui():
    """Retain the v1 public launch function for existing shelf buttons."""
    return launch()


# Importing this module intentionally does not create UI or modify the scene.
