"""Persistent user preferences backed by Maya optionVars and JSON backups."""

import json

import maya.cmds as cmds


PREFIX = "LeficiousStylizedNormals_"
SETTINGS_SCHEMA = 1
PREFERENCES_VERSION = 2

DEFAULTS = {
    "method": "Ovoid Projection",
    "fit_mode": "Per Target",
    "scale": 1.0,
    "resolution": 25,
    "offset_x": 0.0,
    "offset_y": 0.0,
    "offset_z": 0.0,
    "sample_space": "World",
    "search_method": "Closest Point",
    "generation_mode": "Radial - Away",
    "direction_x": 0.0,
    "direction_y": 1.0,
    "direction_z": 0.0,
    "blend": 1.0,
    "preserve_surface_side": 0,
    "soft_edge_angle": 30.0,
}

OVOID_DEFAULT_KEYS = (
    "fit_mode",
    "scale",
    "resolution",
    "offset_x",
    "offset_y",
    "offset_z",
)

GENERATION_DEFAULT_KEYS = (
    "generation_mode",
    "direction_x",
    "direction_y",
    "direction_z",
    "blend",
    "preserve_surface_side",
)


def _name(key):
    return PREFIX + key


def load():
    values = dict(DEFAULTS)
    version_name = _name("preferences_version")
    stored_version = (
        int(cmds.optionVar(query=version_name))
        if cmds.optionVar(exists=version_name)
        else 0
    )
    for key, default in DEFAULTS.items():
        if key == "preserve_surface_side" and stored_version < PREFERENCES_VERSION:
            continue
        option_name = _name(key)
        if not cmds.optionVar(exists=option_name):
            continue
        value = cmds.optionVar(query=option_name)
        if isinstance(default, int) and not isinstance(default, bool):
            value = int(value)
        elif isinstance(default, float):
            value = float(value)
        else:
            value = str(value)
        values[key] = value
    cmds.optionVar(intValue=(version_name, PREFERENCES_VERSION))
    return values


def save(values):
    for key, default in DEFAULTS.items():
        if key not in values:
            continue
        value = values[key]
        option_name = _name(key)
        if isinstance(default, int) and not isinstance(default, bool):
            cmds.optionVar(intValue=(option_name, int(value)))
        elif isinstance(default, float):
            cmds.optionVar(floatValue=(option_name, float(value)))
        else:
            cmds.optionVar(stringValue=(option_name, str(value)))
    cmds.optionVar(intValue=(_name("preferences_version"), PREFERENCES_VERSION))


def factory_values():
    return dict(DEFAULTS)


def export_file(path, values):
    payload = {
        "schema": SETTINGS_SCHEMA,
        "tool": "StylizeNormalsToolkit",
        "settings": {key: values[key] for key in DEFAULTS if key in values},
    }
    with open(path, "w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, indent=2, sort_keys=True)


def import_file(path):
    with open(path, "r", encoding="utf-8") as input_file:
        payload = json.load(input_file)
    if payload.get("schema") != SETTINGS_SCHEMA:
        raise ValueError("This settings file uses an unsupported schema.")
    raw = payload.get("settings")
    if not isinstance(raw, dict):
        raise ValueError("The settings file does not contain a settings object.")
    values = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(default, int) and not isinstance(default, bool):
            values[key] = int(value)
        elif isinstance(default, float):
            values[key] = float(value)
        else:
            values[key] = str(value)
    return values
