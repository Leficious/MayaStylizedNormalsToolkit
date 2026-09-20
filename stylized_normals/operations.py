"""Preview creation and undoable normal-transfer operations."""

import maya.cmds as cmds

from . import scene


METHOD_OVOID = "ovoid"
METHOD_CUSTOM = "custom"
FIT_PER_TARGET = "per_target"
FIT_COMBINED = "combined"

SAMPLE_SPACES = {
    "World": 0,
    "Model": 1,
    "Topology": 5,
}

SEARCH_METHODS = {
    "Along Normal": 0,
    "Closest Point": 3,
}

SOURCE_TARGETS_ATTRIBUTE = "normalToolTargets"
_SOURCE_CLEANUP_JOBS = {}


def tag_node(node, attribute):
    if not cmds.attributeQuery(attribute, node=node, exists=True):
        cmds.addAttr(node, longName=attribute, attributeType="bool")
    cmds.setAttr("{}.{}".format(node, attribute), True)


def create_ovoid(bounds, scale_multiplier, resolution, offset, preview=False):
    center = [
        (bounds[0] + bounds[3]) * 0.5 + offset[0],
        (bounds[1] + bounds[4]) * 0.5 + offset[1],
        (bounds[2] + bounds[5]) * 0.5 + offset[2],
    ]
    half_extent = [
        max((bounds[3] - bounds[0]) * 0.5, 0.001),
        max((bounds[4] - bounds[1]) * 0.5, 0.001),
        max((bounds[5] - bounds[2]) * 0.5, 0.001),
    ]

    sphere = cmds.polySphere(
        name="normalToolPreview#" if preview else "normalToolSource#",
        subdivisionsX=int(resolution),
        subdivisionsY=int(resolution),
        radius=1.0,
        constructionHistory=False,
    )[0]
    cmds.scale(
        half_extent[0] * scale_multiplier,
        half_extent[1] * scale_multiplier,
        half_extent[2] * scale_multiplier,
        sphere,
        absolute=True,
    )
    cmds.move(center[0], center[1], center[2], sphere, absolute=True, worldSpace=True)

    if preview:
        tag_node(sphere, "normalToolTemporaryPreview")
        cmds.setAttr(sphere + ".overrideEnabled", 1)
        cmds.setAttr(sphere + ".overrideShading", 0)
        cmds.setAttr(sphere + ".overrideColor", 18)
    else:
        tag_node(sphere, "normalToolTransferSource")
    return sphere


def duplicate_custom_source(source):
    duplicate = cmds.duplicate(
        source,
        name="normalToolCustomSource#",
        returnRootsOnly=True,
        renameChildren=True,
        upstreamNodes=False,
        inputConnections=False,
    )[0]
    tag_node(duplicate, "normalToolTransferSource")
    return duplicate


def create_source_group():
    group = cmds.group(empty=True, name="normalToolSources#")
    tag_node(group, "normalToolSourceGroup")
    cmds.setAttr(group + ".visibility", 0)
    return group


def cleanup_nodes(nodes):
    existing = [node for node in nodes if node and cmds.objExists(node)]
    if existing:
        cmds.delete(existing)


def cleanup_orphaned_previews():
    """Delete only nodes explicitly marked as temporary by this toolkit."""
    nodes = []
    for plug in cmds.ls("*.normalToolTemporaryPreview") or []:
        node = plug.rsplit(".", 1)[0]
        if cmds.objExists(node) and cmds.getAttr(plug):
            nodes.append(node)
    cleanup_nodes(list(set(nodes)))


def _source_nodes():
    nodes = []
    for plug in cmds.ls("*.normalToolTransferSource") or []:
        node = plug.rsplit(".", 1)[0]
        if cmds.objExists(node) and cmds.getAttr(plug):
            nodes.append(node)
    return list(set(nodes))


def _source_groups():
    nodes = []
    for plug in cmds.ls("*.normalToolSourceGroup") or []:
        node = plug.rsplit(".", 1)[0]
        if cmds.objExists(node) and cmds.getAttr(plug):
            nodes.append(node)
    return list(set(nodes))


def _legacy_source_is_live(source):
    nodes = [source]
    nodes.extend(cmds.listRelatives(source, shapes=True, fullPath=True) or [])
    for node in nodes:
        if cmds.listConnections(node, type="transferAttributes"):
            return True
    return False


def cleanup_orphaned_sources():
    """Remove retained transfer sources after their last target is deleted."""
    stale_sources = []
    for source in _source_nodes():
        if cmds.attributeQuery(SOURCE_TARGETS_ATTRIBUTE, node=source, exists=True):
            targets = cmds.listConnections(
                "{}.{}".format(source, SOURCE_TARGETS_ATTRIBUTE),
                source=True,
                destination=False,
            ) or []
            if not targets:
                stale_sources.append(source)
            else:
                watch_targets(targets)
        elif not _legacy_source_is_live(source):
            stale_sources.append(source)
    cleanup_nodes(stale_sources)

    empty_groups = []
    for group in _source_groups():
        children = cmds.listRelatives(group, children=True, fullPath=True) or []
        if not children:
            empty_groups.append(group)
    cleanup_nodes(empty_groups)


def _target_deleted_cleanup():
    cleanup_orphaned_previews()
    cleanup_orphaned_sources()
    try:
        from .state import STATE

        STATE.targets = [target for target in STATE.targets if cmds.objExists(target)]
        STATE.target_components = {
            target: STATE.target_components.get(target) for target in STATE.targets
        }
        STATE.origin = [origin for origin in STATE.origin if cmds.objExists(origin)]
        STATE.clear_previews()
        STATE.clear_comparison()
    except Exception:
        pass


def watch_targets(targets):
    """Attach lightweight scene cleanup jobs to target DAG nodes."""
    for target in targets:
        if not target or not cmds.objExists(target):
            continue
        uuids = cmds.ls(target, uuid=True) or []
        key = uuids[0] if uuids else target
        existing_job = _SOURCE_CLEANUP_JOBS.get(key)
        if existing_job and cmds.scriptJob(exists=existing_job):
            continue
        try:
            _SOURCE_CLEANUP_JOBS[key] = cmds.scriptJob(
                nodeDeleted=[target, _target_deleted_cleanup],
                runOnce=True,
                killWithScene=True,
                compressUndo=True,
            )
        except Exception:
            pass


def _connect_source_target(source, target):
    if not cmds.attributeQuery(SOURCE_TARGETS_ATTRIBUTE, node=source, exists=True):
        cmds.addAttr(
            source,
            longName=SOURCE_TARGETS_ATTRIBUTE,
            attributeType="message",
            multi=True,
        )
    indices = cmds.getAttr(
        "{}.{}".format(source, SOURCE_TARGETS_ATTRIBUTE), multiIndices=True
    ) or []
    next_index = max(indices) + 1 if indices else 0
    cmds.connectAttr(
        target + ".message",
        "{}.{}[{}]".format(source, SOURCE_TARGETS_ATTRIBUTE, next_index),
        force=True,
    )
    watch_targets([target])


def cleanup_orphaned_tool_nodes():
    cleanup_orphaned_previews()
    cleanup_orphaned_sources()


def build_ovoid_previews(targets, fit_mode, scale, resolution, offset):
    previous_selection = cmds.ls(selection=True, long=True) or []
    watch_targets(targets)
    try:
        if fit_mode == FIT_COMBINED:
            bounds_list = [scene.world_bounds(targets)]
        else:
            bounds_list = [scene.world_bounds([target]) for target in targets]
        return [
            create_ovoid(bounds, scale, resolution, offset, preview=True)
            for bounds in bounds_list
        ]
    finally:
        if previous_selection:
            cmds.select(previous_selection, replace=True)
        else:
            cmds.select(clear=True)


def transfer_attributes(source, target, sample_space, search_method):
    cmds.transferAttributes(
        source,
        target,
        transferPositions=0,
        transferNormals=1,
        transferUVs=0,
        transferColors=0,
        sampleSpace=sample_space,
        searchMethod=search_method,
        flipUVs=0,
        colorBorders=1,
    )


def _parent_source(source, group):
    result = cmds.parent(source, group) or [source]
    return result[0]


def _transfer_one(source, target, sample_space, search_method, failures, successes):
    try:
        transfer_attributes(source, target, sample_space, search_method)
        successes.append(target)
        return True
    except Exception as exc:
        failures.append("{}: {}".format(target, exc))
        return False


def apply_transfers(
    targets,
    method,
    fit_mode,
    custom_source,
    scale,
    resolution,
    offset,
    sample_space,
    search_method,
):
    """Apply a complete batch as one Maya undo step while preserving history."""
    successes, failures = [], []
    source_group = None

    cmds.undoInfo(openChunk=True, chunkName="Stylized Normal Transfer")
    try:
        source_group = create_source_group()

        if method == METHOD_CUSTOM:
            source_copy = _parent_source(duplicate_custom_source(custom_source), source_group)
            for target in targets:
                if target == custom_source:
                    failures.append("{}: cannot also be the custom source".format(target))
                    continue
                _transfer_one(
                    source_copy,
                    target,
                    sample_space,
                    search_method,
                    failures,
                    successes,
                )
            for target in successes:
                _connect_source_target(source_copy, target)

        elif fit_mode == FIT_COMBINED:
            source = create_ovoid(
                scene.world_bounds(targets), scale, resolution, offset, preview=False
            )
            source = _parent_source(source, source_group)
            for target in targets:
                _transfer_one(
                    source,
                    target,
                    sample_space,
                    search_method,
                    failures,
                    successes,
                )
            for target in successes:
                _connect_source_target(source, target)

        else:
            for target in targets:
                source = create_ovoid(
                    scene.world_bounds([target]), scale, resolution, offset, preview=False
                )
                source = _parent_source(source, source_group)
                if not _transfer_one(
                    source,
                    target,
                    sample_space,
                    search_method,
                    failures,
                    successes,
                ):
                    cleanup_nodes([source])
                else:
                    _connect_source_target(source, target)

        if not successes and source_group and cmds.objExists(source_group):
            cmds.delete(source_group)
            source_group = None
    except Exception as exc:
        failures.append("Could not prepare the transfer: {}".format(exc))
        if source_group and not successes and cmds.objExists(source_group):
            cmds.delete(source_group)
            source_group = None
    finally:
        cmds.undoInfo(closeChunk=True)

    return {
        "successes": successes,
        "failures": failures,
        "source_group": source_group,
    }
