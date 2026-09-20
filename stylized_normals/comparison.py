"""Memory-bounded before/current normal comparison previews."""

import math

import maya.api.OpenMaya as om
import maya.cmds as cmds

from . import generation
from . import operations


BEFORE_COLOR = 13
CURRENT_COLOR = 14
DEFAULT_MAX_VECTORS = 150


def _dag_and_mesh(transform):
    selection = om.MSelectionList()
    selection.add(transform)
    dag_path = selection.getDagPath(0)
    return dag_path, om.MFnMesh(dag_path)


def sample_normals(transform, components=None, max_records=150):
    """Sample current world normals without creating dense component strings."""
    unused_dag, mesh = _dag_and_mesh(transform)
    points = mesh.getPoints(om.MSpace.kWorld)
    counts, vertex_ids = mesh.getVertices()
    unused_normal_counts, normal_ids = mesh.getNormalIds()
    world_normals = mesh.getNormals(om.MSpace.kWorld)

    selected_pairs = None
    if components is not None:
        selected_pairs = set(generation.face_vertex_pairs(transform, components))
    eligible_count = len(vertex_ids) if selected_pairs is None else len(selected_pairs)
    stride = max(1, int(math.ceil(float(eligible_count) / max(1, max_records))))

    records = []
    flat_index = 0
    eligible_index = 0
    for face_id, count in enumerate(counts):
        for unused_index in range(count):
            vertex_id = vertex_ids[flat_index]
            if selected_pairs is None or (face_id, vertex_id) in selected_pairs:
                if eligible_index % stride == 0:
                    normal = om.MVector(world_normals[normal_ids[flat_index]]).normal()
                    point = points[vertex_id]
                    records.append(
                        (
                            "{}.vtxFace[{}][{}]".format(
                                transform, vertex_id, face_id
                            ),
                            (normal.x, normal.y, normal.z),
                            (point.x, point.y, point.z),
                            (normal.x, normal.y, normal.z),
                        )
                    )
                    if len(records) >= max_records:
                        return records
                eligible_index += 1
            flat_index += 1
    return records


def capture_samples(targets, component_scopes, max_vectors=DEFAULT_MAX_VECTORS):
    samples = {}
    failures = []
    per_target = max(1, int(max_vectors / max(1, len(targets))))
    for target in targets:
        try:
            samples[target] = sample_normals(
                target,
                component_scopes.get(target),
                max_records=per_target,
            )
        except Exception as exc:
            failures.append("{}: {}".format(target, exc))
    return samples, failures


def build_previews(samples, color):
    previous_selection = cmds.ls(selection=True, long=True) or []
    operations.watch_targets(samples.keys())
    roots = []
    try:
        for target, records in samples.items():
            if cmds.objExists(target) and records:
                roots.append(
                    generation.create_vector_preview(target, records, color=color)
                )
        return roots
    except Exception:
        operations.cleanup_nodes(roots)
        raise
    finally:
        if previous_selection:
            cmds.select(previous_selection, replace=True)
        else:
            cmds.select(clear=True)
