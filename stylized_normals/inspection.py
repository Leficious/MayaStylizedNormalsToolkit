"""Fast mesh-normal inspection and undoable repair operations."""

import maya.api.OpenMaya as om
import maya.cmds as cmds


LOCK = "lock"
UNLOCK = "unlock"
RESET = "reset"
CONFORM = "conform"
REVERSE = "reverse"
HARDEN = "harden"
SOFTEN = "soften"
SOFTEN_ANGLE = "soften_angle"


def _dag_and_mesh(transform):
    selection = om.MSelectionList()
    selection.add(transform)
    dag_path = selection.getDagPath(0)
    return dag_path, om.MFnMesh(dag_path)


def inspect_mesh(transform):
    """Return a compact status record without expanding component strings."""
    dag_path, mesh = _dag_and_mesh(transform)
    unused_counts, normal_ids = mesh.getNormalIds()
    unique_normal_ids = set(normal_ids)
    locked_ids = {
        normal_id for normal_id in unique_normal_ids if mesh.isNormalLocked(normal_id)
    }
    locked_face_vertices = sum(
        1 for normal_id in normal_ids if normal_id in locked_ids
    )

    soft_edges = 0
    hard_edges = 0
    border_edges = 0
    edge_iterator = om.MItMeshEdge(dag_path)
    while not edge_iterator.isDone():
        if edge_iterator.onBoundary():
            border_edges += 1
        elif edge_iterator.isSmooth:
            soft_edges += 1
        else:
            hard_edges += 1
        edge_iterator.next()

    return {
        "transform": transform,
        "vertices": mesh.numVertices,
        "faces": mesh.numPolygons,
        "face_vertices": len(normal_ids),
        "custom": bool(locked_ids),
        "locked": locked_face_vertices,
        "soft_edges": soft_edges,
        "hard_edges": hard_edges,
        "border_edges": border_edges,
    }


def status_line(record):
    values = dict(record)
    values["custom"] = "yes" if record["custom"] else "no"
    return (
        "{transform} | {vertices}v {faces}f | Custom: {custom} | "
        "Locked: {locked}/{face_vertices} | Edges: {soft_edges} soft, "
        "{hard_edges} hard, {border_edges} border"
    ).format(**values)


def inspect_targets(targets):
    records = []
    errors = []
    for target in targets:
        try:
            records.append(inspect_mesh(target))
        except Exception as exc:
            errors.append("{}: {}".format(target, exc))
    return records, errors


def _flatten_conversion(components, **kwargs):
    converted = cmds.polyListComponentConversion(components, **kwargs) or []
    return cmds.ls(converted, flatten=True) or []


def _normal_scope(target, components):
    if components is None:
        return [target]
    result = _flatten_conversion(components, toVertexFace=True)
    if not result:
        raise ValueError("The component scope contains no editable normals.")
    return result


def _face_scope(target, components):
    if components is None:
        return [target]
    result = _flatten_conversion(components, toFace=True)
    if not result:
        raise ValueError("The component scope contains no faces.")
    return result


def _edge_scope(target, components):
    if components is None:
        return [target]
    result = _flatten_conversion(components, toEdge=True)
    if not result:
        raise ValueError("The component scope contains no edges.")
    return result


def _apply_one(target, components, operation, angle):
    if operation == LOCK:
        cmds.polyNormalPerVertex(_normal_scope(target, components), freezeNormal=True)
    elif operation == UNLOCK:
        cmds.polyNormalPerVertex(_normal_scope(target, components), unFreezeNormal=True)
    elif operation == RESET:
        cmds.polySetToFaceNormal(_normal_scope(target, components))
        cmds.polySoftEdge(
            _edge_scope(target, components),
            angle=max(0.0, min(180.0, float(angle))),
            constructionHistory=True,
        )
    elif operation == CONFORM:
        cmds.polyNormal(
            _face_scope(target, components),
            normalMode=2,
            userNormalMode=True,
            constructionHistory=True,
        )
    elif operation == REVERSE:
        cmds.polyNormal(
            _face_scope(target, components),
            normalMode=0,
            userNormalMode=True,
            constructionHistory=True,
        )
    elif operation in (HARDEN, SOFTEN, SOFTEN_ANGLE):
        edge_angle = {HARDEN: 0.0, SOFTEN: 180.0}.get(
            operation, max(0.0, min(180.0, float(angle)))
        )
        cmds.polySoftEdge(
            _edge_scope(target, components),
            angle=edge_angle,
            constructionHistory=True,
        )
    else:
        raise ValueError("Unknown repair operation: {}".format(operation))


def apply_repair(targets, component_scopes, operation, angle=30.0):
    """Apply one repair to every valid target as a single Maya Undo step."""
    previous_selection = cmds.ls(selection=True, long=True) or []
    successes = []
    failures = []
    cmds.undoInfo(openChunk=True, chunkName="Stylized Normal Repair")
    try:
        for target in targets:
            try:
                _apply_one(
                    target,
                    component_scopes.get(target),
                    operation,
                    angle,
                )
                successes.append(target)
            except Exception as exc:
                failures.append("{}: {}".format(target, exc))
    finally:
        if previous_selection:
            cmds.select(previous_selection, replace=True)
        else:
            cmds.select(clear=True)
        cmds.undoInfo(closeChunk=True)
    return {"successes": successes, "failures": failures}
