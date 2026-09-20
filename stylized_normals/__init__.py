"""Stylize Normals Toolkit for Autodesk Maya."""

__version__ = "3.0.0-alpha.12"


def launch():
    """Open the toolkit without creating UI as a side effect of importing it."""
    from .ui import launch_window

    return launch_window()
