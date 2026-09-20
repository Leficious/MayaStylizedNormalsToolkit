"""Maya cmds interface for Stylize Normals Toolkit."""

import time

import maya.cmds as cmds

from . import __version__
from . import generation
from . import inspection
from . import comparison
from . import operations
from . import reporting
from . import scene
from . import settings
from .state import STATE


WINDOW_NAME = "stylizedNormalToolkitUI"
TARGET_LIST = "normalToolkitTargetList"
TARGET_STATUS = "normalToolkitTargetStatus"
METHOD_MENU = "normalToolkitMethodMenu"

SOURCE_FIELD = "normalToolkitSourceField"
SOURCE_CAPTURE_BUTTON = "normalToolkitCaptureSourceButton"
SOURCE_CLEAR_BUTTON = "normalToolkitClearSourceButton"
FIT_MENU = "normalToolkitFitMenu"
SAMPLE_MENU = "normalToolkitSampleMenu"
SEARCH_MENU = "normalToolkitSearchMenu"
SCALE_SLIDER = "normalToolkitScaleSlider"
RESOLUTION_SLIDER = "normalToolkitResolutionSlider"
OFFSET_SLIDERS = {
    "X": "normalToolkitOffsetXSlider",
    "Y": "normalToolkitOffsetYSlider",
    "Z": "normalToolkitOffsetZSlider",
}
PREVIEW_BUTTON = "normalToolkitPreviewButton"

GENERATION_MENU = "normalToolkitGenerationMenu"
ORIGIN_FIELD = "normalToolkitOriginField"
ORIGIN_CAPTURE_BUTTON = "normalToolkitCaptureOriginButton"
ORIGIN_CLEAR_BUTTON = "normalToolkitClearOriginButton"
DIRECTION_FIELD = "normalToolkitDirectionField"
BLEND_SLIDER = "normalToolkitBlendSlider"
PRESERVE_SURFACE_SIDE = "normalToolkitPreserveSurfaceSide"
VECTOR_PREVIEW_BUTTON = "normalToolkitVectorPreviewButton"

INSPECTION_LIST = "normalToolkitInspectionList"
SOFT_EDGE_ANGLE = "normalToolkitSoftEdgeAngle"

COMPARISON_STATUS = "normalToolkitComparisonStatus"
REPORT_LIST = "normalToolkitReportList"

SCALE_SLIDER_RANGE = (0.1, 10.0)
SCALE_FIELD_RANGE = (0.0001, 1000000.0)
OFFSET_SLIDER_RANGE = (-1000.0, 1000.0)
OFFSET_FIELD_RANGE = (-1000000000.0, 1000000000.0)

METHOD_LABELS = {
    "Ovoid Projection": operations.METHOD_OVOID,
    "Custom Source": operations.METHOD_CUSTOM,
    "Generated Direction": generation.METHOD_GENERATED,
}
FIT_LABELS = {
    "Per Target": operations.FIT_PER_TARGET,
    "Combined Bounds": operations.FIT_COMBINED,
}
GENERATION_LABELS = {
    "Radial - Away": generation.MODE_RADIAL_AWAY,
    "Radial - Toward": generation.MODE_RADIAL_TOWARD,
    "Directional": generation.MODE_DIRECTIONAL,
}


def _show_issues(title, heading, issues):
    if not issues:
        return
    visible = issues[:8]
    message = heading + "\n\n" + "\n".join("- " + item for item in visible)
    if len(issues) > len(visible):
        message += "\n- ...and {} more".format(len(issues) - len(visible))
    cmds.confirmDialog(title=title, message=message, button=["OK"], icon="warning")


def _control_exists(control):
    return bool(cmds.control(control, exists=True))


def _set_enabled(controls, enabled):
    for control in controls:
        if _control_exists(control):
            cmds.control(control, edit=True, enable=enabled)


def _method_label():
    return cmds.optionMenu(METHOD_MENU, query=True, value=True)


def _refresh_targets():
    if not _control_exists(TARGET_LIST):
        return
    labels = []
    for target in STATE.targets:
        components = STATE.target_components.get(target)
        if components is None:
            labels.append(target + "  [whole mesh]")
        else:
            labels.append(
                "{}  [{} selected components]".format(
                    target, scene.component_count(components)
                )
            )
    cmds.textScrollList(TARGET_LIST, edit=True, removeAll=True)
    if labels:
        cmds.textScrollList(TARGET_LIST, edit=True, append=labels)
    count = len(STATE.targets)
    cmds.text(
        TARGET_STATUS,
        edit=True,
        label="{} target{} captured".format(count, "" if count == 1 else "s"),
    )


def _refresh_source():
    if _control_exists(SOURCE_FIELD):
        cmds.textField(SOURCE_FIELD, edit=True, text=STATE.source or "No source captured")


def _refresh_origin():
    if _control_exists(ORIGIN_FIELD):
        if not STATE.origin:
            text = "No origin captured"
        else:
            try:
                center = scene.bounds_center(STATE.origin)
                text = "{} object{} | center ({:.3f}, {:.3f}, {:.3f})".format(
                    len(STATE.origin),
                    "" if len(STATE.origin) == 1 else "s",
                    center[0],
                    center[1],
                    center[2],
                )
            except Exception:
                text = "Origin selection changed; recapture it"
        cmds.textField(ORIGIN_FIELD, edit=True, text=text)


def _cleanup_previews():
    operations.cleanup_nodes(STATE.previews)
    STATE.clear_previews()
    for button in (PREVIEW_BUTTON, VECTOR_PREVIEW_BUTTON):
        if _control_exists(button):
            cmds.button(button, edit=True, label="Show Preview")


def _cleanup_comparison(clear_samples=False):
    operations.cleanup_nodes(STATE.comparison_previews)
    STATE.comparison_previews = []
    if clear_samples:
        STATE.before_samples = {}
    if _control_exists(COMPARISON_STATUS):
        label = (
            "Before sample captured."
            if STATE.before_samples
            else "No before sample captured."
        )
        cmds.text(COMPARISON_STATUS, edit=True, label=label)


def capture_targets_from_selection(*args):
    selected, targets, scopes, errors = scene.capture_target_selection()
    if not selected:
        cmds.confirmDialog(
            title="No Selection",
            message="Select mesh objects, vertices, or faces, then click Capture Selection.",
            button=["OK"],
            icon="warning",
        )
        return
    _cleanup_previews()
    _cleanup_comparison(clear_samples=True)
    STATE.targets = targets
    STATE.target_components = scopes
    operations.watch_targets(targets)
    _refresh_targets()
    _show_issues("Some Targets Were Skipped", "These items were not captured:", errors)
    _show_preview_by_default()
    _mark_inspection_stale()


def clear_targets(*args):
    _cleanup_previews()
    _cleanup_comparison(clear_samples=True)
    STATE.targets = []
    STATE.target_components = {}
    _refresh_targets()
    _mark_inspection_stale("Capture mesh targets to inspect their normals.")


def capture_source_from_selection(*args):
    selected, result = scene.selected_meshes(editable=False)
    valid, errors = result
    if len(valid) != 1:
        details = list(errors)
        if len(valid) > 1:
            details.insert(0, "Select exactly one mesh to use as the source.")
        if not selected:
            details.insert(0, "Nothing is selected.")
        _show_issues("Source Not Captured", "A custom source could not be captured:", details)
        return
    STATE.source = valid[0]
    _refresh_source()


def clear_source(*args):
    STATE.source = None
    _refresh_source()


def capture_origin_from_selection(*args):
    selected = cmds.ls(selection=True, long=True, objectsOnly=True) or []
    if not selected:
        _show_issues(
            "Origin Not Captured",
            "A radial origin could not be captured:",
            ["Select one or more transform, locator, or mesh objects."],
        )
        return
    origins = []
    errors = []
    for item in selected:
        origin, error = scene.resolve_transform(item)
        if error:
            errors.append("{}: {}".format(item, error))
        elif origin not in origins:
            origins.append(origin)
    if errors or not origins:
        _show_issues(
            "Origin Not Captured",
            "The radial origin selection is invalid:",
            errors or ["No usable transforms were selected."],
        )
        return
    _cleanup_previews()
    STATE.origin = origins
    operations.watch_targets(origins)
    _refresh_origin()
    _show_preview_by_default()


def clear_origin(*args):
    _cleanup_previews()
    STATE.origin = []
    _refresh_origin()


def _ui_settings():
    return {
        "method": cmds.optionMenu(METHOD_MENU, query=True, value=True),
        "fit_mode": cmds.optionMenu(FIT_MENU, query=True, value=True),
        "scale": cmds.floatSliderGrp(SCALE_SLIDER, query=True, value=True),
        "resolution": cmds.intSliderGrp(RESOLUTION_SLIDER, query=True, value=True),
        "offset_x": cmds.floatSliderGrp(OFFSET_SLIDERS["X"], query=True, value=True),
        "offset_y": cmds.floatSliderGrp(OFFSET_SLIDERS["Y"], query=True, value=True),
        "offset_z": cmds.floatSliderGrp(OFFSET_SLIDERS["Z"], query=True, value=True),
        "sample_space": cmds.optionMenu(SAMPLE_MENU, query=True, value=True),
        "search_method": cmds.optionMenu(SEARCH_MENU, query=True, value=True),
        "generation_mode": cmds.optionMenu(GENERATION_MENU, query=True, value=True),
        "direction_x": cmds.floatFieldGrp(DIRECTION_FIELD, query=True, value1=True),
        "direction_y": cmds.floatFieldGrp(DIRECTION_FIELD, query=True, value2=True),
        "direction_z": cmds.floatFieldGrp(DIRECTION_FIELD, query=True, value3=True),
        "blend": cmds.floatSliderGrp(BLEND_SLIDER, query=True, value=True),
        "preserve_surface_side": int(
            cmds.checkBox(PRESERVE_SURFACE_SIDE, query=True, value=True)
        ),
        "soft_edge_angle": cmds.floatFieldGrp(
            SOFT_EDGE_ANGLE, query=True, value1=True
        ),
    }


def _ui_is_ready():
    required = (
        METHOD_MENU,
        FIT_MENU,
        SCALE_SLIDER,
        RESOLUTION_SLIDER,
        OFFSET_SLIDERS["X"],
        OFFSET_SLIDERS["Y"],
        OFFSET_SLIDERS["Z"],
        SAMPLE_MENU,
        SEARCH_MENU,
        GENERATION_MENU,
        DIRECTION_FIELD,
        BLEND_SLIDER,
        PRESERVE_SURFACE_SIDE,
        SOFT_EDGE_ANGLE,
    )
    return all(_control_exists(control) for control in required)


def _save_preferences():
    if _ui_is_ready():
        settings.save(_ui_settings())


def _operation_settings():
    values = _ui_settings()
    return {
        "method": METHOD_LABELS[values["method"]],
        "fit_mode": FIT_LABELS[values["fit_mode"]],
        "scale": values["scale"],
        "resolution": values["resolution"],
        "offset": [values["offset_x"], values["offset_y"], values["offset_z"]],
        "sample_space": operations.SAMPLE_SPACES[values["sample_space"]],
        "search_method": operations.SEARCH_METHODS[values["search_method"]],
        "generation_mode": GENERATION_LABELS[values["generation_mode"]],
        "direction": [values["direction_x"], values["direction_y"], values["direction_z"]],
        "blend": values["blend"],
        "preserve_surface_side": bool(values["preserve_surface_side"]),
    }


def _update_generation_controls(*args):
    if not _control_exists(GENERATION_MENU):
        return
    is_radial = cmds.optionMenu(GENERATION_MENU, query=True, value=True) != "Directional"
    _set_enabled((ORIGIN_FIELD, ORIGIN_CAPTURE_BUTTON, ORIGIN_CLEAR_BUTTON), is_radial)
    _set_enabled((DIRECTION_FIELD,), not is_radial)
    _set_enabled((PRESERVE_SURFACE_SIDE,), is_radial)
    _save_preferences()
    if STATE.preview_visible:
        update_preview()
    else:
        _show_preview_by_default()


def _update_mode_controls(*args):
    if not _control_exists(METHOD_MENU):
        return
    label = _method_label()
    is_ovoid = label == "Ovoid Projection"
    is_custom = label == "Custom Source"
    is_generated = label == "Generated Direction"

    _cleanup_previews()
    _set_enabled((SOURCE_FIELD, SOURCE_CAPTURE_BUTTON, SOURCE_CLEAR_BUTTON), is_custom)
    _set_enabled(
        (
            FIT_MENU,
            SCALE_SLIDER,
            RESOLUTION_SLIDER,
            OFFSET_SLIDERS["X"],
            OFFSET_SLIDERS["Y"],
            OFFSET_SLIDERS["Z"],
            PREVIEW_BUTTON,
        ),
        is_ovoid,
    )
    _set_enabled((SAMPLE_MENU, SEARCH_MENU), is_ovoid or is_custom)
    _set_enabled(
        (GENERATION_MENU, BLEND_SLIDER, PRESERVE_SURFACE_SIDE, VECTOR_PREVIEW_BUTTON),
        is_generated,
    )
    if is_generated:
        _update_generation_controls()
    else:
        _set_enabled(
            (ORIGIN_FIELD, ORIGIN_CAPTURE_BUTTON, ORIGIN_CLEAR_BUTTON, DIRECTION_FIELD),
            False,
        )
        _set_enabled((PRESERVE_SURFACE_SIDE,), False)

    if (
        not is_custom
        and _control_exists(SAMPLE_MENU)
        and cmds.optionMenu(SAMPLE_MENU, query=True, value=True) == "Topology"
    ):
        cmds.optionMenu(SAMPLE_MENU, edit=True, value="World")
    _save_preferences()
    if is_ovoid or is_generated:
        _show_preview_by_default()


def _setting_changed(*args):
    _save_preferences()
    if STATE.preview_visible:
        update_preview()


def _preference_changed(*args):
    _save_preferences()


def _sample_space_changed(*args):
    if _method_label() != "Custom Source" and cmds.optionMenu(
        SAMPLE_MENU, query=True, value=True
    ) == "Topology":
        cmds.optionMenu(SAMPLE_MENU, edit=True, value="World")
        cmds.warning("Topology sampling is available only with a Custom Source.")
    _save_preferences()


def _current_targets():
    valid, errors = scene.validate_nodes(STATE.targets, editable=True)
    STATE.targets = valid
    STATE.target_components = {
        target: STATE.target_components.get(target) for target in valid
    }
    _refresh_targets()
    return valid, errors


def _generation_inputs(values):
    origin = None
    if values["generation_mode"] != generation.MODE_DIRECTIONAL:
        if not STATE.origin:
            raise ValueError("Capture one or more radial origin objects first.")
        origins = []
        for item in STATE.origin:
            origin_transform, error = scene.resolve_transform(item)
            if error:
                raise ValueError(
                    "A captured radial origin object changed or was deleted; recapture it."
                )
            if origin_transform not in origins:
                origins.append(origin_transform)
        STATE.origin = origins
        _refresh_origin()
        origin = scene.bounds_center(origins)
    return origin, values["direction"]


def _show_preview_by_default():
    if not _ui_is_ready() or STATE.preview_visible or not STATE.targets:
        return
    label = _method_label()
    if label == "Custom Source":
        return
    if label == "Generated Direction":
        values = _operation_settings()
        try:
            _generation_inputs(values)
        except ValueError:
            return
    STATE.preview_visible = True
    update_preview()


def update_preview(*args):
    if not STATE.preview_visible:
        return
    targets, errors = _current_targets()
    if not targets:
        _cleanup_previews()
        return

    values = _operation_settings()
    method = values["method"]
    _cleanup_previews()
    try:
        if method == operations.METHOD_OVOID:
            STATE.previews = operations.build_ovoid_previews(
                targets,
                values["fit_mode"],
                values["scale"],
                values["resolution"],
                values["offset"],
            )
            active_button = PREVIEW_BUTTON
        elif method == generation.METHOD_GENERATED:
            origin, direction = _generation_inputs(values)
            STATE.previews = generation.build_vector_previews(
                targets,
                STATE.target_components,
                values["generation_mode"],
                origin,
                direction,
                values["blend"],
                preserve_surface_side=values["preserve_surface_side"],
            )
            active_button = VECTOR_PREVIEW_BUTTON
        else:
            return
        STATE.preview_visible = True
        cmds.button(active_button, edit=True, label="Hide Preview")
    except Exception as exc:
        _cleanup_previews()
        cmds.warning("Stylize Normals Toolkit preview failed: {}".format(exc))
    if errors:
        cmds.warning("Some captured targets are no longer valid; recapture the selection.")


def toggle_preview(*args):
    if STATE.preview_visible:
        _cleanup_previews()
        return
    targets, errors = _current_targets()
    if not targets:
        if errors:
            _show_issues("Invalid Targets", "No captured target can be used:", errors)
        else:
            cmds.confirmDialog(
                title="No Captured Targets",
                message="Capture one or more mesh targets first.",
                button=["OK"],
                icon="warning",
            )
        return
    STATE.preview_visible = True
    update_preview()


def _scoped_targets():
    return [
        target
        for target in STATE.targets
        if STATE.target_components.get(target) is not None
    ]


def apply_operation(*args):
    started = time.perf_counter()
    targets, validation_errors = _current_targets()
    if not targets:
        if validation_errors:
            _show_issues(
                "Cannot Apply", "No valid captured targets remain:", validation_errors
            )
        else:
            cmds.confirmDialog(
                title="No Captured Targets",
                message="Capture one or more mesh targets first.",
                button=["OK"],
                icon="warning",
            )
        return

    values = _operation_settings()
    method = values["method"]
    if method != generation.METHOD_GENERATED and _scoped_targets():
        cmds.confirmDialog(
            title="Component Scope Requires Generated Direction",
            message=(
                "Ovoid and Custom Source transfers currently require whole-mesh targets. "
                "Recapture the objects, or choose Generated Direction to edit selected "
                "vertices and faces."
            ),
            button=["OK"],
            icon="warning",
        )
        return

    _cleanup_previews()
    _cleanup_comparison(clear_samples=False)
    if method == generation.METHOD_GENERATED:
        try:
            origin, direction = _generation_inputs(values)
        except ValueError as exc:
            _show_issues("Cannot Generate Normals", "Generation settings are incomplete:", [str(exc)])
            return
        result = generation.apply_generated_normals(
            targets,
            STATE.target_components,
            values["generation_mode"],
            origin,
            direction,
            values["blend"],
            preserve_surface_side=values["preserve_surface_side"],
        )
        action_word = "Generated normals for"
    else:
        custom_source = None
        if method == operations.METHOD_CUSTOM:
            custom_source, source_error = scene.resolve_mesh_transform(
                STATE.source, editable=False
            )
            if source_error:
                cmds.confirmDialog(
                    title="Invalid Custom Source",
                    message="Capture one valid custom source mesh first.\n\n{}".format(
                        source_error
                    ),
                    button=["OK"],
                    icon="warning",
                )
                return
            STATE.source = custom_source
            _refresh_source()
        result = operations.apply_transfers(
            targets=targets,
            method=method,
            fit_mode=values["fit_mode"],
            custom_source=custom_source,
            scale=values["scale"],
            resolution=values["resolution"],
            offset=values["offset"],
            sample_space=values["sample_space"],
            search_method=values["search_method"],
        )
        action_word = "Transferred normals to"

    failures = list(validation_errors) + result["failures"]
    _record_report(
        action_word.rstrip(),
        result["successes"],
        failures,
        time.perf_counter() - started,
    )
    if failures:
        _show_issues(
            "Operation Completed with Warnings",
            "Updated {} target(s). Problems:".format(len(result["successes"])),
            failures,
        )
    elif result["successes"]:
        cmds.confirmDialog(
            title="Operation Complete",
            message="{} {} target(s). Use Undo once to revert the batch.".format(
                action_word, len(result["successes"])
            ),
            button=["OK"],
            icon="information",
        )
    _mark_inspection_stale()


def reset_ovoid_settings(*args):
    defaults = settings.DEFAULTS
    cmds.optionMenu(FIT_MENU, edit=True, value=defaults["fit_mode"])
    cmds.floatSliderGrp(SCALE_SLIDER, edit=True, value=defaults["scale"])
    cmds.intSliderGrp(RESOLUTION_SLIDER, edit=True, value=defaults["resolution"])
    for axis, key in (("X", "offset_x"), ("Y", "offset_y"), ("Z", "offset_z")):
        cmds.floatSliderGrp(OFFSET_SLIDERS[axis], edit=True, value=defaults[key])
    _setting_changed()


def reset_generation_settings(*args):
    defaults = settings.DEFAULTS
    cmds.optionMenu(GENERATION_MENU, edit=True, value=defaults["generation_mode"])
    cmds.floatFieldGrp(
        DIRECTION_FIELD,
        edit=True,
        value1=defaults["direction_x"],
        value2=defaults["direction_y"],
        value3=defaults["direction_z"],
    )
    cmds.floatSliderGrp(BLEND_SLIDER, edit=True, value=defaults["blend"])
    cmds.checkBox(
        PRESERVE_SURFACE_SIDE,
        edit=True,
        value=bool(defaults["preserve_surface_side"]),
    )
    _update_generation_controls()


def refresh_inspection(*args):
    if not _control_exists(INSPECTION_LIST):
        return
    targets, validation_errors = _current_targets()
    records, inspection_errors = inspection.inspect_targets(targets)
    lines = [inspection.status_line(record) for record in records]
    cmds.textScrollList(INSPECTION_LIST, edit=True, removeAll=True)
    if lines:
        cmds.textScrollList(INSPECTION_LIST, edit=True, append=lines)
    else:
        cmds.textScrollList(
            INSPECTION_LIST,
            edit=True,
            append="Capture mesh targets to inspect their normals.",
        )
    errors = list(validation_errors) + inspection_errors
    if errors:
        cmds.warning("Some targets could not be inspected: {}".format("; ".join(errors)))


def _mark_inspection_stale(message="Status not scanned yet. Click Refresh Status."):
    if not _control_exists(INSPECTION_LIST):
        return
    cmds.textScrollList(INSPECTION_LIST, edit=True, removeAll=True, append=message)


def apply_repair(operation, *args):
    started = time.perf_counter()
    targets, validation_errors = _current_targets()
    if not targets:
        _show_issues(
            "Cannot Repair",
            "No valid captured targets remain:",
            validation_errors or ["Capture one or more mesh targets first."],
        )
        return
    _cleanup_comparison(clear_samples=False)
    angle = cmds.floatFieldGrp(SOFT_EDGE_ANGLE, query=True, value1=True)
    result = inspection.apply_repair(
        targets,
        STATE.target_components,
        operation,
        angle=angle,
    )
    _mark_inspection_stale()
    failures = list(validation_errors) + result["failures"]
    _record_report(
        "Repair: {}".format(operation.replace("_", " ").title()),
        result["successes"],
        failures,
        time.perf_counter() - started,
    )
    if failures:
        _show_issues(
            "Repair Completed with Warnings",
            "Updated {} target(s). Problems:".format(len(result["successes"])),
            failures,
        )
    elif result["successes"]:
        cmds.confirmDialog(
            title="Repair Complete",
            message="Updated {} target(s). Use Undo once to revert the batch.".format(
                len(result["successes"])
            ),
            button=["OK"],
            icon="information",
        )


def _apply_preferences(values):
    menu_values = (
        (METHOD_MENU, "method", METHOD_LABELS),
        (FIT_MENU, "fit_mode", FIT_LABELS),
        (SAMPLE_MENU, "sample_space", operations.SAMPLE_SPACES),
        (SEARCH_MENU, "search_method", operations.SEARCH_METHODS),
        (GENERATION_MENU, "generation_mode", GENERATION_LABELS),
    )
    for control, key, choices in menu_values:
        if _control_exists(control) and values.get(key) in choices:
            cmds.optionMenu(control, edit=True, value=values[key])
    if _control_exists(SCALE_SLIDER):
        cmds.floatSliderGrp(SCALE_SLIDER, edit=True, value=values["scale"])
        cmds.intSliderGrp(RESOLUTION_SLIDER, edit=True, value=values["resolution"])
        for axis, key in (("X", "offset_x"), ("Y", "offset_y"), ("Z", "offset_z")):
            cmds.floatSliderGrp(OFFSET_SLIDERS[axis], edit=True, value=values[key])
        cmds.floatFieldGrp(
            DIRECTION_FIELD,
            edit=True,
            value1=values["direction_x"],
            value2=values["direction_y"],
            value3=values["direction_z"],
        )
        cmds.floatSliderGrp(BLEND_SLIDER, edit=True, value=values["blend"])
        cmds.checkBox(
            PRESERVE_SURFACE_SIDE,
            edit=True,
            value=bool(values["preserve_surface_side"]),
        )
        cmds.floatFieldGrp(
            SOFT_EDGE_ANGLE, edit=True, value1=values["soft_edge_angle"]
        )
    _update_mode_controls()
    _save_preferences()


def export_settings(*args):
    paths = cmds.fileDialog2(
        caption="Export Stylize Normals Settings",
        fileMode=0,
        fileFilter="JSON settings (*.json)",
    ) or []
    if not paths:
        return
    path = paths[0]
    if not path.lower().endswith(".json"):
        path += ".json"
    try:
        settings.export_file(path, _ui_settings())
    except Exception as exc:
        _show_issues("Settings Export Failed", "The settings could not be saved:", [str(exc)])


def import_settings(*args):
    paths = cmds.fileDialog2(
        caption="Import Stylize Normals Settings",
        fileMode=1,
        fileFilter="JSON settings (*.json)",
    ) or []
    if not paths:
        return
    try:
        values = settings.import_file(paths[0])
        _apply_preferences(values)
    except Exception as exc:
        _show_issues("Settings Import Failed", "The settings could not be loaded:", [str(exc)])


def restore_factory_settings(*args):
    _apply_preferences(settings.factory_values())


def capture_before_comparison(*args):
    targets, validation_errors = _current_targets()
    if not targets:
        _show_issues(
            "Cannot Capture Comparison",
            "No valid captured targets remain:",
            validation_errors or ["Capture one or more mesh targets first."],
        )
        return
    _cleanup_comparison(clear_samples=True)
    samples, failures = comparison.capture_samples(targets, STATE.target_components)
    STATE.before_samples = samples
    _cleanup_comparison(clear_samples=False)
    if failures:
        _show_issues("Comparison Capture Warnings", "Some samples were skipped:", failures)


def _show_comparison(samples, color, label):
    _cleanup_previews()
    _cleanup_comparison(clear_samples=False)
    try:
        STATE.comparison_previews = comparison.build_previews(samples, color)
        cmds.text(COMPARISON_STATUS, edit=True, label=label)
    except Exception as exc:
        _show_issues("Comparison Preview Failed", "The vectors could not be shown:", [str(exc)])


def show_before_comparison(*args):
    if not STATE.before_samples:
        _show_issues(
            "No Before Sample",
            "Capture a before sample prior to applying an operation:",
            ["Click Capture Before, apply an operation, then compare."],
        )
        return
    _show_comparison(STATE.before_samples, comparison.BEFORE_COLOR, "Showing before normals (red).")


def show_current_comparison(*args):
    targets, validation_errors = _current_targets()
    if not targets:
        _show_issues(
            "Cannot Compare Normals",
            "No valid captured targets remain:",
            validation_errors or ["Capture one or more mesh targets first."],
        )
        return
    samples, failures = comparison.capture_samples(targets, STATE.target_components)
    failures = list(validation_errors) + failures
    if failures:
        _show_issues("Comparison Warnings", "Some current samples were skipped:", failures)
    if samples:
        _show_comparison(samples, comparison.CURRENT_COLOR, "Showing current normals (green).")


def clear_comparison(*args):
    _cleanup_comparison(clear_samples=True)


def _record_report(title, successes, failures, elapsed):
    STATE.last_report = reporting.build(title, successes, failures, elapsed)
    _refresh_report()
    print("\n".join(reporting.lines(STATE.last_report)))


def _refresh_report():
    if not _control_exists(REPORT_LIST):
        return
    cmds.textScrollList(REPORT_LIST, edit=True, removeAll=True)
    if STATE.last_report:
        cmds.textScrollList(
            REPORT_LIST,
            edit=True,
            append=reporting.lines(STATE.last_report),
        )
    else:
        cmds.textScrollList(REPORT_LIST, edit=True, append="No operation run yet.")


def print_full_report(*args):
    if STATE.last_report:
        print("\n".join(reporting.lines(STATE.last_report)))


def _on_window_closed(*args):
    _save_preferences()
    _cleanup_previews()
    _cleanup_comparison(clear_samples=True)


def _option_menu(name, label, choices, value, callback):
    cmds.optionMenu(name, label=label, changeCommand=callback)
    for choice in choices:
        cmds.menuItem(label=choice)
    if value in choices:
        cmds.optionMenu(name, edit=True, value=value)


def _padded_slider(name, label, slider_type, **kwargs):
    cmds.columnLayout(adjustableColumn=True, columnOffset=("left", -75))
    slider_type(name, label=label, width=440, columnWidth=(1, 135), **kwargs)
    cmds.setParent("..")


def launch_window():
    preferences = settings.load()
    operations.cleanup_orphaned_tool_nodes()
    _cleanup_previews()
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(
        WINDOW_NAME,
        title="Stylize Normals Toolkit v{}".format(__version__),
        widthHeight=(500, 780),
        sizeable=True,
        closeCommand=_on_window_closed,
    )
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnOffset=("both", 18))

    cmds.separator(style="none", height=4)
    cmds.text(label="Stylize Normals Toolkit", align="center", font="boldLabelFont")
    cmds.text(
        label="Transfer, generate, blend, and preview custom vertex normals.",
        align="center",
    )
    cmds.separator(style="in", height=5)

    cmds.text(label="Targets", align="left", font="boldLabelFont")
    cmds.textScrollList(TARGET_LIST, height=82, allowMultiSelection=False)
    cmds.text(TARGET_STATUS, label="0 targets captured", align="left")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(350, 100))
    cmds.button(
        label="Capture Objects / Vertices / Faces",
        height=30,
        command=capture_targets_from_selection,
    )
    cmds.button(label="Clear", height=30, command=clear_targets)
    cmds.setParent("..")

    cmds.separator(style="in", height=5)
    cmds.text(label="Method", align="left", font="boldLabelFont")
    _option_menu(
        METHOD_MENU,
        "Method",
        list(METHOD_LABELS.keys()),
        preferences["method"],
        _update_mode_controls,
    )

    cmds.text(label="Custom Transfer Source", align="left", font="boldLabelFont")
    cmds.textField(SOURCE_FIELD, editable=False, text="No source captured")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(350, 100))
    cmds.button(
        SOURCE_CAPTURE_BUTTON,
        label="Capture Source from Selection",
        height=30,
        command=capture_source_from_selection,
    )
    cmds.button(SOURCE_CLEAR_BUTTON, label="Clear", height=30, command=clear_source)
    cmds.setParent("..")

    cmds.separator(style="in", height=5)
    cmds.text(label="Generated Ovoid", align="left", font="boldLabelFont")
    _option_menu(
        FIT_MENU,
        "Ovoid Fit",
        list(FIT_LABELS.keys()),
        preferences["fit_mode"],
        _setting_changed,
    )
    _padded_slider(
        SCALE_SLIDER,
        "Scale",
        cmds.floatSliderGrp,
        field=True,
        minValue=SCALE_SLIDER_RANGE[0],
        maxValue=SCALE_SLIDER_RANGE[1],
        fieldMinValue=SCALE_FIELD_RANGE[0],
        fieldMaxValue=SCALE_FIELD_RANGE[1],
        value=preferences["scale"],
        changeCommand=_setting_changed,
    )
    _padded_slider(
        RESOLUTION_SLIDER,
        "Resolution",
        cmds.intSliderGrp,
        field=True,
        minValue=8,
        maxValue=64,
        value=preferences["resolution"],
        changeCommand=_setting_changed,
    )
    for axis, key in (("X", "offset_x"), ("Y", "offset_y"), ("Z", "offset_z")):
        _padded_slider(
            OFFSET_SLIDERS[axis],
            "{} Offset".format(axis),
            cmds.floatSliderGrp,
            field=True,
            minValue=OFFSET_SLIDER_RANGE[0],
            maxValue=OFFSET_SLIDER_RANGE[1],
            fieldMinValue=OFFSET_FIELD_RANGE[0],
            fieldMaxValue=OFFSET_FIELD_RANGE[1],
            value=preferences[key],
            changeCommand=_setting_changed,
        )
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(350, 100))
    cmds.button(
        PREVIEW_BUTTON,
        label="Show Preview",
        height=34,
        backgroundColor=(0.2, 0.5, 0.8),
        command=toggle_preview,
    )
    cmds.button(label="Defaults", height=34, command=reset_ovoid_settings)
    cmds.setParent("..")

    cmds.separator(style="in", height=5)
    cmds.text(label="Generated Direction", align="left", font="boldLabelFont")
    _option_menu(
        GENERATION_MENU,
        "Generation",
        list(GENERATION_LABELS.keys()),
        preferences["generation_mode"],
        _update_generation_controls,
    )
    cmds.textField(ORIGIN_FIELD, editable=False, text="No origin captured")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(350, 100))
    cmds.button(
        ORIGIN_CAPTURE_BUTTON,
        label="Capture Radial Origin Object(s)",
        height=30,
        command=capture_origin_from_selection,
    )
    cmds.button(ORIGIN_CLEAR_BUTTON, label="Clear", height=30, command=clear_origin)
    cmds.setParent("..")
    cmds.floatFieldGrp(
        DIRECTION_FIELD,
        numberOfFields=3,
        label="World Direction",
        value1=preferences["direction_x"],
        value2=preferences["direction_y"],
        value3=preferences["direction_z"],
        changeCommand=_setting_changed,
        columnWidth4=(135, 95, 95, 95),
    )
    _padded_slider(
        BLEND_SLIDER,
        "Blend",
        cmds.floatSliderGrp,
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=preferences["blend"],
        changeCommand=_setting_changed,
    )
    cmds.checkBox(
        PRESERVE_SURFACE_SIDE,
        label="Prevent Radial Face Flips",
        value=bool(preferences["preserve_surface_side"]),
        annotation=(
            "Keeps radial normals on the same visible side as the mesh's current "
            "face-vertex normals. Disable for literal inward or outward vectors."
        ),
        changeCommand=_update_generation_controls,
    )
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(350, 100))
    cmds.button(
        VECTOR_PREVIEW_BUTTON,
        label="Show Preview",
        height=34,
        backgroundColor=(0.55, 0.45, 0.15),
        command=toggle_preview,
    )
    cmds.button(label="Defaults", height=34, command=reset_generation_settings)
    cmds.setParent("..")

    cmds.separator(style="in", height=5)
    cmds.text(label="Transfer Settings", align="left", font="boldLabelFont")
    _option_menu(
        SAMPLE_MENU,
        "Sample Space",
        list(operations.SAMPLE_SPACES.keys()),
        preferences["sample_space"],
        _sample_space_changed,
    )
    _option_menu(
        SEARCH_MENU,
        "Search",
        list(operations.SEARCH_METHODS.keys()),
        preferences["search_method"],
        _preference_changed,
    )

    cmds.text(
        label="Each Apply is one Undo step. Generated edits create locked custom normals.",
        align="center",
    )
    cmds.button(
        label="Apply Normal Operation",
        height=42,
        backgroundColor=(0.2, 0.7, 0.3),
        command=apply_operation,
    )

    cmds.separator(style="in", height=5)
    cmds.text(label="Inspect & Repair", align="left", font="boldLabelFont")
    cmds.textScrollList(
        INSPECTION_LIST,
        height=92,
        allowMultiSelection=False,
        append=["Capture mesh targets to inspect their normals."],
    )
    cmds.button(label="Refresh Status", height=28, command=refresh_inspection)

    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3)
    cmds.button(
        label="Lock Normals",
        height=30,
        command=lambda *unused: apply_repair(inspection.LOCK),
    )
    cmds.button(
        label="Unlock Normals",
        height=30,
        command=lambda *unused: apply_repair(inspection.UNLOCK),
    )
    cmds.button(
        label="Reset Normals",
        height=30,
        command=lambda *unused: apply_repair(inspection.RESET),
    )
    cmds.setParent("..")
    cmds.text(
        label="Unlock keeps the current custom direction; Reset rebuilds the normals.",
        align="center",
    )

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.button(
        label="Conform Faces",
        height=30,
        command=lambda *unused: apply_repair(inspection.CONFORM),
    )
    cmds.button(
        label="Reverse Faces",
        height=30,
        command=lambda *unused: apply_repair(inspection.REVERSE),
    )
    cmds.setParent("..")

    cmds.floatFieldGrp(
        SOFT_EDGE_ANGLE,
        numberOfFields=1,
        label="Edge Angle",
        value1=preferences["soft_edge_angle"],
        precision=2,
        changeCommand=_preference_changed,
        columnWidth2=(135, 120),
    )
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3)
    cmds.button(
        label="Harden All",
        height=30,
        command=lambda *unused: apply_repair(inspection.HARDEN),
    )
    cmds.button(
        label="Soften All",
        height=30,
        command=lambda *unused: apply_repair(inspection.SOFTEN),
    )
    cmds.button(
        label="Set by Angle",
        height=30,
        command=lambda *unused: apply_repair(inspection.SOFTEN_ANGLE),
    )
    cmds.setParent("..")
    cmds.text(
        label="Reset uses Edge Angle. Repairs honor scopes and use one Undo step.",
        align="center",
    )

    cmds.separator(style="in", height=5)
    cmds.text(label="Before / Current Comparison", align="left", font="boldLabelFont")
    cmds.text(
        COMPARISON_STATUS,
        label="No before sample captured.",
        align="left",
    )
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.button(label="Capture Before", height=30, command=capture_before_comparison)
    cmds.button(label="Clear", height=30, command=clear_comparison)
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.button(label="Show Before (Red)", height=30, command=show_before_comparison)
    cmds.button(label="Show Current (Green)", height=30, command=show_current_comparison)
    cmds.setParent("..")
    cmds.text(
        label="Comparison samples at most 150 vectors and does not duplicate meshes.",
        align="center",
    )

    cmds.separator(style="in", height=5)
    cmds.text(label="Last Batch Report", align="left", font="boldLabelFont")
    cmds.textScrollList(
        REPORT_LIST,
        height=88,
        allowMultiSelection=False,
        append=["No operation run yet."],
    )
    cmds.button(label="Print Full Report", height=28, command=print_full_report)

    cmds.separator(style="in", height=5)
    cmds.text(label="Settings", align="left", font="boldLabelFont")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3)
    cmds.button(label="Export", height=30, command=export_settings)
    cmds.button(label="Import", height=30, command=import_settings)
    cmds.button(label="Factory Defaults", height=30, command=restore_factory_settings)
    cmds.setParent("..")
    cmds.separator(style="none", height=10)
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.showWindow(WINDOW_NAME)

    selected, targets, scopes, unused_errors = scene.capture_target_selection()
    STATE.targets = targets
    STATE.target_components = scopes
    operations.watch_targets(targets)
    _refresh_targets()
    _refresh_source()
    _refresh_origin()
    _update_mode_controls()
    _mark_inspection_stale(
        "Status not scanned yet. Click Refresh Status."
        if STATE.targets
        else "Capture mesh targets to inspect their normals."
    )
    _refresh_report()
    return WINDOW_NAME
