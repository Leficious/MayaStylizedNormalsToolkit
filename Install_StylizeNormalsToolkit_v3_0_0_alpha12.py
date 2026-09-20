"""Drag-and-drop installer for Stylize Normals Toolkit v3.0.0-alpha.12."""

import importlib
import os
import shutil
import sys
import traceback

import maya.cmds as cmds


INSTALLER_VERSION = "3.0.0-alpha.12"
LAUNCHER_FILENAME = "StylizeNormalsToolkit.py"
COMPATIBILITY_FILENAME = "TransferNormalsTool.py"
PACKAGE_NAME = "stylized_normals"
SHELF_NAME = "Custom"
BUTTON_LABEL = "StylizeNormals"
LEGACY_BUTTON_LABELS = ("StylizedNormals", "TransferNormals")
LOG_FILENAME = "StylizedNormalToolkit_install.log"


print("Stylize Normals Toolkit v{} installer loaded.".format(INSTALLER_VERSION))


def _source_directory():
    if "__file__" not in globals():
        raise RuntimeError("Maya did not provide the dropped installer path.")
    return os.path.dirname(os.path.abspath(__file__))


def _install_files(source_directory):
    scripts_directory = os.path.normpath(cmds.internalVar(userScriptDir=True))
    if not os.path.isdir(scripts_directory):
        os.makedirs(scripts_directory)

    launcher_source = os.path.join(source_directory, LAUNCHER_FILENAME)
    compatibility_source = os.path.join(source_directory, COMPATIBILITY_FILENAME)
    package_source = os.path.join(source_directory, PACKAGE_NAME)
    if not os.path.isfile(launcher_source):
        raise RuntimeError(
            "Missing {} beside the installer. Extract the complete ZIP first.".format(
                LAUNCHER_FILENAME
            )
        )
    if not os.path.isfile(compatibility_source):
        raise RuntimeError(
            "Missing {} beside the installer. Extract the complete ZIP first.".format(
                COMPATIBILITY_FILENAME
            )
        )
    if not os.path.isdir(package_source):
        raise RuntimeError(
            "Missing {} folder beside the installer. Extract the complete ZIP first.".format(
                PACKAGE_NAME
            )
        )

    package_destination = os.path.join(scripts_directory, PACKAGE_NAME)
    for source, filename in (
        (launcher_source, LAUNCHER_FILENAME),
        (compatibility_source, COMPATIBILITY_FILENAME),
    ):
        destination = os.path.join(scripts_directory, filename)
        if os.path.normcase(os.path.abspath(source)) != os.path.normcase(
            os.path.abspath(destination)
        ):
            shutil.copy2(source, destination)
    shutil.copytree(package_source, package_destination, dirs_exist_ok=True)
    obsolete_presets = os.path.join(package_destination, "presets.py")
    if os.path.isfile(obsolete_presets):
        os.remove(obsolete_presets)
    return scripts_directory, package_destination


def _create_shelf_button():
    if not cmds.shelfLayout(SHELF_NAME, exists=True):
        cmds.shelfLayout(SHELF_NAME, parent="ShelfLayout")

    for child in cmds.shelfLayout(SHELF_NAME, query=True, childArray=True) or []:
        try:
            label = cmds.shelfButton(child, query=True, label=True)
        except RuntimeError:
            continue
        if label == BUTTON_LABEL or label in LEGACY_BUTTON_LABELS:
            cmds.deleteUI(child)

    command = (
        "import StylizeNormalsToolkit\n"
        "StylizeNormalsToolkit.launch()"
    )
    cmds.shelfButton(
        label=BUTTON_LABEL,
        parent=SHELF_NAME,
        command=command,
        image="polySphere.png",
        imageOverlayLabel="Normals",
        overlayLabelColor=(1, 1, 1),
        overlayLabelBackColor=(0, 0, 0, 0.5),
        annotation="Launch Stylize Normals Toolkit",
        sourceType="python",
    )


def _reload_installed_tool(scripts_directory):
    if scripts_directory in sys.path:
        sys.path.remove(scripts_directory)
    sys.path.insert(0, scripts_directory)
    importlib.invalidate_caches()

    for module_name in list(sys.modules):
        if module_name in (
            "StylizeNormalsToolkit",
            "TransferNormalsTool",
            PACKAGE_NAME,
        ):
            sys.modules.pop(module_name, None)
        elif module_name.startswith(PACKAGE_NAME + "."):
            sys.modules.pop(module_name, None)

    return importlib.import_module("StylizeNormalsToolkit")


def _write_error_log(details):
    try:
        log_directory = os.path.normpath(cmds.internalVar(userTmpDir=True))
        log_path = os.path.join(log_directory, LOG_FILENAME)
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(details)
        return log_path
    except Exception:
        return None


def onMayaDroppedPythonFile(*args, **kwargs):
    print("Installing Stylize Normals Toolkit v{}...".format(INSTALLER_VERSION))
    try:
        cmds.inViewMessage(
            amg="Installing <hl>Stylize Normals Toolkit v{}</hl>...".format(
                INSTALLER_VERSION
            ),
            pos="topCenter",
            fade=True,
        )
    except Exception:
        pass

    try:
        scripts_directory, package_destination = _install_files(_source_directory())
        tool_module = _reload_installed_tool(scripts_directory)
        _create_shelf_button()
        tool_module.smart_launch_normal_tool()
    except Exception:
        details = traceback.format_exc()
        print(details)
        log_path = _write_error_log(details)
        message = "The toolkit could not be installed."
        if log_path:
            message += "\n\nDiagnostic log:\n{}".format(log_path)
        message += "\n\nOpen Maya's Script Editor for the full error."
        cmds.confirmDialog(
            title="Stylize Normals Toolkit Installation Failed",
            message=message,
            button=["OK"],
            icon="critical",
        )
        raise

    success_message = (
        "Stylize Normals Toolkit v{} installed successfully.\n\n"
        "Shelf: {}\nPackage: {}"
    ).format(INSTALLER_VERSION, SHELF_NAME, package_destination)
    print(success_message)
    cmds.inViewMessage(
        amg="<hl>Stylize Normals Toolkit v{}</hl> installed successfully.".format(
            INSTALLER_VERSION
        ),
        pos="topCenter",
        fade=True,
    )


if __name__ == "__main__":
    onMayaDroppedPythonFile()
