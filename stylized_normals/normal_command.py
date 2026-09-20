"""Undoable bulk normal application command used by the toolkit.

This module is loaded by Maya as a lightweight Python plug-in. The command data
stays in memory, avoiding command-line serialization for dense meshes.
"""

import importlib

import maya.api.OpenMaya as om


COMMAND_NAME = "stylizedNormalApplyBatch"
PLAN_FLAG = "-p"
PLAN_FLAG_LONG = "-planId"


def maya_useNewAPI():
    """Tell Maya to pass API 2.0 objects to this Python plug-in."""


def _mesh(transform):
    selection = om.MSelectionList()
    selection.add(transform)
    return om.MFnMesh(selection.getDagPath(0))


def _set_item_normals(item, key):
    mesh = _mesh(item["transform"])
    mesh.unlockFaceVertexNormals(
        item["face_ids"],
        item["vertex_ids"],
    )
    mesh.setFaceVertexNormals(
        item[key],
        item["face_ids"],
        item["vertex_ids"],
        om.MSpace.kObject,
    )
    mesh.updateSurface()


def _restore_item(item):
    _set_item_normals(item, "old_normals")
    if len(item["unlocked_face_ids"]):
        _mesh(item["transform"]).unlockFaceVertexNormals(
            item["unlocked_face_ids"],
            item["unlocked_vertex_ids"],
        )


class ApplyNormalsCommand(om.MPxCommand):
    def __init__(self):
        super(ApplyNormalsCommand, self).__init__()
        self._plan = []

    @staticmethod
    def creator():
        return ApplyNormalsCommand()

    @staticmethod
    def syntax_creator():
        syntax = om.MSyntax()
        syntax.addFlag(PLAN_FLAG, PLAN_FLAG_LONG, om.MSyntax.kString)
        return syntax

    def isUndoable(self):
        return True

    def doIt(self, arguments):
        parser = om.MArgParser(self.syntax(), arguments)
        if not parser.isFlagSet(PLAN_FLAG):
            raise RuntimeError("A normal-operation plan ID is required.")
        plan_id = parser.flagArgumentString(PLAN_FLAG, 0)
        generation = importlib.import_module("stylized_normals.generation")
        self._plan = generation._consume_apply_plan(plan_id)
        self.redoIt()

    def redoIt(self):
        applied = []
        try:
            for item in self._plan:
                _set_item_normals(item, "new_normals")
                applied.append(item)
        except Exception:
            for item in reversed(applied):
                _restore_item(item)
            raise

    def undoIt(self):
        for item in reversed(self._plan):
            _restore_item(item)


def initializePlugin(plugin_object):
    plugin = om.MFnPlugin(plugin_object, "Leficious", "3.0.0-alpha.12", "Any")
    plugin.registerCommand(
        COMMAND_NAME,
        ApplyNormalsCommand.creator,
        ApplyNormalsCommand.syntax_creator,
    )


def uninitializePlugin(plugin_object):
    om.MFnPlugin(plugin_object).deregisterCommand(COMMAND_NAME)
