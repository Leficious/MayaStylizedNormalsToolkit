"""Transient UI state. Scene object slots are intentionally not persisted."""


class ToolState(object):
    def __init__(self):
        self.targets = []
        self.target_components = {}
        self.source = None
        self.origin = []
        self.previews = []
        self.preview_visible = False
        self.before_samples = {}
        self.comparison_previews = []
        self.last_report = None

    def clear_previews(self):
        self.previews = []
        self.preview_visible = False

    def clear_comparison(self):
        self.before_samples = {}
        self.comparison_previews = []


STATE = ToolState()
