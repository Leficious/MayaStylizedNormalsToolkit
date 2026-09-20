"""Radial and directional custom-normal generation for Maya meshes."""

import math
import os
import re
import uuid

import maya.api.OpenMaya as om
import maya.cmds as cmds

from . import operations
from . import scene


METHOD_GENERATED = "generated"
MODE_RADIAL_AWAY = "radial_away"
MODE_RADIAL_TOWARD = "radial_toward"
MODE_DIRECTIONAL = "directional"

VERTEX_FACE_PATTERN = re.compile(r"\.vtxFace\[(\d+)\]\[(\d+)\]$")
APPLY_COMMAND = "stylizedNormalApplyBatch"
_APPLY_PLANS = {}


def _normalized(vector, fallback=None):
    vector = om.MVector(vector)
    if vector.length() > 1.0e-10:
        return vector.normal()
    if fallback is not None:
        fallback = om.MVector(fallback)
        if fallback.length() > 1.0e-10:
            return fallback.normal()
    raise ValueError("A direction vector cannot have zero length.")


def _dag_and_mesh(transform):
    selection = om.MSelectionList()
    selection.add(transform)
    dag_path = selection.getDagPath(0)
    return dag_path, om.MFnMesh(dag_path)


def face_vertex_pairs(transform, components=None):
    """Return unique (face, vertex) pairs for a mesh or component scope."""
    if components is None:
        dag_path, unused_mesh = _dag_and_mesh(transform)
        pairs = []
        iterator = om.MItMeshPolygon(dag_path)
        while not iterator.isDone():
            face_id = iterator.index()
            pairs.extend((face_id, vertex_id) for vertex_id in iterator.getVertices())
            iterator.next()
        return pairs

    converted = cmds.polyListComponentConversion(components, toVertexFace=True) or []
    flattened = cmds.ls(converted, flatten=True) or []
    pairs, seen = [], set()
    for component in flattened:
        match = VERTEX_FACE_PATTERN.search(component)
        if not match:
            continue
        vertex_id = int(match.group(1))
        face_id = int(match.group(2))
        pair = (face_id, vertex_id)
        if pair not in seen:
            pairs.append(pair)
            seen.add(pair)
    if not pairs:
        raise ValueError("The captured component scope contains no face vertices.")
    return pairs


def _generated_world_normal(
    mode,
    position,
    origin,
    direction,
    existing,
    preserve_surface_side=False,
):
    if mode == MODE_DIRECTIONAL:
        return _normalized(direction)
    radial = om.MVector(position - om.MPoint(origin))
    if mode == MODE_RADIAL_TOWARD:
        radial *= -1.0
    generated = _normalized(radial, fallback=existing)
    if preserve_surface_side and generated * existing < 0.0:
        generated *= -1.0
    return generated


def build_normal_records(
    transform,
    components,
    mode,
    origin,
    direction,
    blend,
    max_records=None,
    preserve_surface_side=False,
):
    """Calculate component names plus object/world-space normal data."""
    blend = max(0.0, min(1.0, float(blend)))
    dag_path, mesh = _dag_and_mesh(transform)
    points = mesh.getPoints(om.MSpace.kWorld)
    counts, vertex_ids = mesh.getVertices()
    unused_normal_counts, normal_ids = mesh.getNormalIds()
    world_normal_values = mesh.getNormals(om.MSpace.kWorld)

    selected_pairs = None
    if components is not None:
        selected_pairs = set(face_vertex_pairs(transform, components))

    eligible_count = len(vertex_ids) if selected_pairs is None else len(selected_pairs)
    stride = 1
    if max_records and eligible_count > max_records:
        stride = int(math.ceil(float(eligible_count) / float(max_records)))

    world_to_object_normal = dag_path.inclusiveMatrix().transpose()
    records = []
    flat_index = 0
    eligible_index = 0
    for face_id, count in enumerate(counts):
        for unused_index in range(count):
            vertex_id = vertex_ids[flat_index]
            pair = (face_id, vertex_id)
            if selected_pairs is None or pair in selected_pairs:
                if eligible_index % stride == 0:
                    existing = _normalized(world_normal_values[normal_ids[flat_index]])
                    generated = _generated_world_normal(
                        mode,
                        points[vertex_id],
                        origin,
                        direction,
                        existing,
                        preserve_surface_side,
                    )
                    blended = _normalized(
                        existing * (1.0 - blend) + generated * blend,
                        fallback=generated,
                    )
                    object_normal = _normalized(blended * world_to_object_normal)
                    component = "{}.vtxFace[{}][{}]".format(
                        transform, vertex_id, face_id
                    )
                    records.append(
                        (
                            component,
                            (object_normal.x, object_normal.y, object_normal.z),
                            (
                                points[vertex_id].x,
                                points[vertex_id].y,
                                points[vertex_id].z,
                            ),
                            (blended.x, blended.y, blended.z),
                        )
                    )
                    if max_records and len(records) >= max_records:
                        return records
                eligible_index += 1
            flat_index += 1
    return records


def _build_apply_plan(
    transform,
    components,
    mode,
    origin,
    direction,
    blend,
    preserve_surface_side=False,
):
    """Build compact array data for one bulk, undoable mesh edit."""
    blend = max(0.0, min(1.0, float(blend)))
    dag_path, mesh = _dag_and_mesh(transform)
    points = mesh.getPoints(om.MSpace.kWorld)
    counts, vertex_ids = mesh.getVertices()
    unused_normal_counts, normal_ids = mesh.getNormalIds()
    world_normal_values = mesh.getNormals(om.MSpace.kWorld)
    object_normal_values = mesh.getNormals(om.MSpace.kObject)

    selected_pairs = None
    if components is not None:
        selected_pairs = set(face_vertex_pairs(transform, components))

    face_ids = om.MIntArray()
    scoped_vertex_ids = om.MIntArray()
    old_normals = om.MVectorArray()
    new_normals = om.MVectorArray()
    unlocked_face_ids = om.MIntArray()
    unlocked_vertex_ids = om.MIntArray()
    world_to_object_normal = dag_path.inclusiveMatrix().transpose()
    lock_states = {}

    flat_index = 0
    for face_id, count in enumerate(counts):
        for unused_index in range(count):
            vertex_id = vertex_ids[flat_index]
            pair = (face_id, vertex_id)
            normal_id = normal_ids[flat_index]
            if selected_pairs is None or pair in selected_pairs:
                locked = lock_states.get(normal_id)
                if locked is None:
                    locked = mesh.isNormalLocked(normal_id)
                    lock_states[normal_id] = locked
                if not locked:
                    unlocked_face_ids.append(face_id)
                    unlocked_vertex_ids.append(vertex_id)
                existing = _normalized(world_normal_values[normal_id])
                generated = _generated_world_normal(
                    mode,
                    points[vertex_id],
                    origin,
                    direction,
                    existing,
                    preserve_surface_side,
                )
                blended = _normalized(
                    existing * (1.0 - blend) + generated * blend,
                    fallback=generated,
                )
                object_normal = _normalized(blended * world_to_object_normal)
                face_ids.append(face_id)
                scoped_vertex_ids.append(vertex_id)
                old_normals.append(object_normal_values[normal_id])
                new_normals.append(object_normal)
            flat_index += 1

    if not face_ids:
        raise ValueError("The captured target scope contains no face vertices.")

    return {
        "transform": transform,
        "shape_id": cmds.ls(scene.mesh_shape(transform)[0], uuid=True)[0],
        "face_ids": face_ids,
        "vertex_ids": scoped_vertex_ids,
        "old_normals": old_normals,
        "new_normals": new_normals,
        "unlocked_face_ids": unlocked_face_ids,
        "unlocked_vertex_ids": unlocked_vertex_ids,
    }


def _plans_share_normals(left, right, tolerance=1.0e-8):
    """Return whether two paths to one instanced shape need identical edits."""
    if len(left["new_normals"]) != len(right["new_normals"]):
        return False
    if list(left["face_ids"]) != list(right["face_ids"]):
        return False
    if list(left["vertex_ids"]) != list(right["vertex_ids"]):
        return False
    for index in range(len(left["new_normals"])):
        if (left["new_normals"][index] - right["new_normals"][index]).length() > tolerance:
            return False
    return True


def _collapse_instance_plans(candidate_plans):
    """Collapse compatible instances and reject conflicting per-instance edits."""
    groups = {}
    order = []
    for plan in candidate_plans:
        shape_id = plan["shape_id"]
        if shape_id not in groups:
            groups[shape_id] = []
            order.append(shape_id)
        groups[shape_id].append(plan)

    plans = []
    successes = []
    failures = []
    for shape_id in order:
        group = groups[shape_id]
        first = group[0]
        if all(_plans_share_normals(first, plan) for plan in group[1:]):
            plans.append(first)
            successes.extend(plan["transform"] for plan in group)
            continue
        targets = ", ".join(plan["transform"] for plan in group)
        failures.append(
            "{} share one instanced mesh shape but require different normals. "
            "Make those mesh instances unique, recapture them, and apply again.".format(
                targets
            )
        )
    return plans, successes, failures


def _consume_apply_plan(plan_id):
    try:
        return _APPLY_PLANS.pop(plan_id)
    except KeyError:
        raise RuntimeError("The normal-operation plan expired before it could run.")


def _ensure_apply_command():
    plugin_path = os.path.join(os.path.dirname(__file__), "normal_command.py")
    try:
        loaded = cmds.pluginInfo(plugin_path, query=True, loaded=True)
    except RuntimeError:
        loaded = False
    if not loaded:
        cmds.loadPlugin(plugin_path, quiet=True)
    command = getattr(cmds, APPLY_COMMAND, None)
    if command is None:
        raise RuntimeError("Maya did not register the bulk normal command.")
    return command


def apply_generated_normals(
    targets,
    component_scopes,
    mode,
    origin,
    direction,
    blend,
    preserve_surface_side=False,
):
    """Apply generated normals atomically as one Maya undo step."""
    if float(blend) <= 0.0:
        return {
            "successes": [],
            "failures": ["Blend is 0; no normal changes were requested."],
        }

    candidate_plans, failures = [], []
    for target in targets:
        try:
            candidate_plans.append(_build_apply_plan(
                target,
                component_scopes.get(target),
                mode,
                origin,
                direction,
                blend,
                preserve_surface_side,
            ))
        except Exception as exc:
            failures.append("{}: {}".format(target, exc))

    plans, successful_targets, instance_failures = _collapse_instance_plans(
        candidate_plans
    )
    failures.extend(instance_failures)

    if not plans:
        return {"successes": [], "failures": failures}

    command = None
    try:
        command = _ensure_apply_command()
    except Exception as exc:
        failures.append("Normal generation was canceled: {}".format(exc))
        return {"successes": [], "failures": failures}

    applied_count = 0
    active_plan_id = None
    chunk_open = False
    execution_failed = False
    try:
        cmds.undoInfo(openChunk=True, chunkName="Stylized Generated Normals")
        chunk_open = True
        for plan in plans:
            active_plan_id = uuid.uuid4().hex
            _APPLY_PLANS[active_plan_id] = [plan]
            command(planId=active_plan_id)
            active_plan_id = None
            applied_count += 1
            _dag_and_mesh(plan["transform"])[1].updateSurface()
    except Exception as exc:
        execution_failed = True
        if active_plan_id is not None:
            _APPLY_PLANS.pop(active_plan_id, None)
        failures.append("Normal generation was canceled: {}".format(exc))
    finally:
        if chunk_open:
            cmds.undoInfo(closeChunk=True)

    if execution_failed and applied_count:
        try:
            cmds.undo()
        except Exception as exc:
            failures.append("Automatic rollback failed: {}".format(exc))
    if execution_failed:
        return {"successes": [], "failures": failures}

    return {
        "successes": successful_targets,
        "failures": failures,
    }


def _preview_length(transform):
    bounds = scene.world_bounds([transform])
    diagonal = math.sqrt(
        (bounds[3] - bounds[0]) ** 2
        + (bounds[4] - bounds[1]) ** 2
        + (bounds[5] - bounds[2]) ** 2
    )
    return max(diagonal * 0.06, 0.01)


def create_vector_preview(transform, records, color=17):
    root = cmds.createNode("transform", name="normalToolkitVectorPreview#")
    operations.tag_node(root, "normalToolTemporaryPreview")
    cmds.setAttr(root + ".overrideEnabled", 1)
    cmds.setAttr(root + ".overrideColor", int(color))
    length = _preview_length(transform)
    temporary_curves = []
    shapes = []
    try:
        for unused_component, unused_object_normal, position, normal in records:
            end = (
                position[0] + normal[0] * length,
                position[1] + normal[1] * length,
                position[2] + normal[2] * length,
            )
            curve = cmds.curve(degree=1, point=[position, end])
            temporary_curves.append(curve)
            shapes.extend(cmds.listRelatives(curve, shapes=True, fullPath=True) or [])
        if shapes:
            cmds.parent(shapes, root, add=True, shape=True, relative=True)
        if temporary_curves:
            cmds.delete(temporary_curves)
        return root
    except Exception:
        operations.cleanup_nodes([root] + temporary_curves)
        raise


def build_vector_previews(
    targets,
    component_scopes,
    mode,
    origin,
    direction,
    blend,
    max_vectors=150,
    preserve_surface_side=False,
):
    previous_selection = cmds.ls(selection=True, long=True) or []
    operations.watch_targets(targets)
    roots = []
    per_target = max(1, int(max_vectors / max(1, len(targets))))
    try:
        for target in targets:
            records = build_normal_records(
                target,
                component_scopes.get(target),
                mode,
                origin,
                direction,
                blend,
                max_records=per_target,
                preserve_surface_side=preserve_surface_side,
            )
            roots.append(create_vector_preview(target, records))
        return roots
    except Exception:
        operations.cleanup_nodes(roots)
        raise
    finally:
        if previous_selection:
            cmds.select(previous_selection, replace=True)
        else:
            cmds.select(clear=True)
