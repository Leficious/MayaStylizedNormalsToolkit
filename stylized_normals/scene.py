"""Maya scene discovery and validation helpers."""

import maya.cmds as cmds


SUPPORTED_COMPONENT_MARKERS = (".vtx[", ".f[", ".vtxFace[")


def mesh_shape(transform):
    shapes = cmds.listRelatives(
        transform,
        shapes=True,
        noIntermediate=True,
        fullPath=True,
        type="mesh",
    ) or []
    if not shapes:
        return None, "does not contain a visible polygon mesh"
    if len(shapes) > 1:
        return None, "contains multiple visible mesh shapes"
    return shapes[0], None


def resolve_mesh_transform(node, editable=True):
    """Resolve a transform, mesh shape, or component to a mesh transform."""
    if not node or not cmds.objExists(node):
        return None, "no longer exists"

    matches = cmds.ls(node, long=True, objectsOnly=True) or []
    if not matches:
        return None, "could not be resolved"

    resolved = matches[0]
    node_type = cmds.nodeType(resolved)
    if node_type == "mesh":
        parents = cmds.listRelatives(resolved, parent=True, fullPath=True) or []
        if not parents:
            return None, "has no transform parent"
        resolved = parents[0]
    elif node_type != "transform":
        return None, "is not a polygon mesh transform"

    shape, error = mesh_shape(resolved)
    if error:
        return None, error

    if editable:
        if cmds.referenceQuery(resolved, isNodeReferenced=True):
            return None, "is referenced and cannot be edited safely"
        if any(cmds.lockNode(item, query=True, lock=True)[0] for item in (resolved, shape)):
            return None, "is locked and cannot be edited safely"

    return resolved, None


def validate_nodes(nodes, editable=True):
    valid, errors, seen = [], [], set()
    for node in nodes:
        transform, error = resolve_mesh_transform(node, editable=editable)
        if error:
            errors.append("{}: {}".format(node, error))
        elif transform not in seen:
            valid.append(transform)
            seen.add(transform)
    return valid, errors


def selected_meshes(editable=True):
    selected = cmds.ls(selection=True, long=True, objectsOnly=True) or []
    return selected, validate_nodes(selected, editable=editable)


def capture_target_selection():
    """Capture mesh objects plus optional vertex/face component scopes."""
    selected = cmds.ls(selection=True, long=True) or []
    targets, scopes, errors = [], {}, []

    for item in selected:
        is_component = "." in item
        if is_component and not any(marker in item for marker in SUPPORTED_COMPONENT_MARKERS):
            errors.append("{}: only vertex and face components are supported".format(item))
            continue

        owner = item.split(".", 1)[0] if is_component else item
        transform, error = resolve_mesh_transform(owner, editable=True)
        if error:
            errors.append("{}: {}".format(item, error))
            continue

        if transform not in targets:
            targets.append(transform)
        if transform not in scopes:
            scopes[transform] = [item] if is_component else None
        elif scopes[transform] is not None:
            if is_component and item not in scopes[transform]:
                scopes[transform].append(item)
            elif not is_component:
                scopes[transform] = None

    return selected, targets, scopes, errors


def component_count(components):
    if components is None:
        return None
    return len(cmds.ls(components, flatten=True) or [])


def resolve_transform(node):
    """Resolve any DAG transform, including meshes, locators, and components."""
    if not node or not cmds.objExists(node):
        return None, "no longer exists"
    matches = cmds.ls(node, long=True, objectsOnly=True) or []
    if not matches:
        return None, "could not be resolved"
    resolved = matches[0]
    if cmds.nodeType(resolved) != "transform":
        parents = cmds.listRelatives(resolved, parent=True, fullPath=True) or []
        if not parents:
            return None, "has no transform parent"
        resolved = parents[0]
    return resolved, None


def world_bounds(transforms):
    if not transforms:
        raise ValueError("At least one mesh is required to calculate bounds.")
    boxes = [cmds.exactWorldBoundingBox(transform) for transform in transforms]
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        min(box[2] for box in boxes),
        max(box[3] for box in boxes),
        max(box[4] for box in boxes),
        max(box[5] for box in boxes),
    ]


def bounds_center(transforms):
    """Return the combined world bounding-box center without editing pivots."""
    bounds = world_bounds(transforms)
    return [
        (bounds[0] + bounds[3]) * 0.5,
        (bounds[1] + bounds[4]) * 0.5,
        (bounds[2] + bounds[5]) * 0.5,
    ]
