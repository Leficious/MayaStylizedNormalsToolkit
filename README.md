# Stylize Normals Toolkit for Maya

**Author:** Leficious

**Version:** 1.0

**Compatible with:** Autodesk Maya 2024+

## Overview

Stylize Normals Toolkit transfers vertex normals from a generated ovoid or an
artist-selected source mesh, and can now generate radial or directional custom
normals directly. It is designed for foliage, hair cards, stylized rocks, and
other assets that benefit from deliberately controlled shading.

## Features

- Explicit target list that does not follow later selection changes
- Generated ovoid or custom source workflows
- Radial normals using the combined bounding-box center of one or more captured origin objects
- Directional normals using an artist-defined world-space vector
- Blend control between existing and generated normals
- Optional radial face-flip protection for thin shells and card meshes, off by default
- Whole-mesh, selected-vertex, and selected-face generation scopes
- Sampled vector-line preview capped to avoid excessive scene overhead
- Every slider refreshes its viewport preview only after mouse release
- Vector preview shapes are parented and cleaned up in batches
- Dense normal-lock queries are cached during generated-normal planning
- Mesh status inspection is user-triggered so capture and Apply stay responsive
- Per-mesh normal, lock, topology, and edge-smoothing status
- Component-aware lock, unlock, reset, conform, and reverse operations
- Harden-all, soften-all, and smoothing-angle edge controls
- Persistent last-operation report with successes, skips, failures, and timing
- JSON export/import plus factory settings restore
- Red/green sampled comparison without duplicating target meshes
- Per-target or combined-bounds fitting for generated ovoids
- World, model, and topology sampling options
- Closest-point and along-normal search methods
- Multi-object processing without combining target meshes
- Instance-aware batches that share compatible edits and reject conflicting instance transforms
- Isolated per-mesh generated-normal commits, grouped into one safe Undo step
- Consecutive generated operations explicitly unlock their scope before replacement
- Persistent UI preferences through Maya optionVars
- Scrollable, resizable interface for different display scales
- Generated-ovoid preview appears automatically when valid targets are captured
- Scale slider range of 0.1 to 10, with typed values allowed up to 1,000,000
- Offset slider range of -1,000 to 1,000, with much wider typed-value limits
- Existing construction history is preserved
- Each Apply batch is grouped into one Maya Undo step
- Live transfer sources are retained in a hidden, tool-owned group
- Temporary previews and retained sources clean up when their final target is deleted
- Per-object error reporting

## Installation

1. Keep `Install_StylizeNormalsToolkit_v3_0_0_alpha12.py`,
   `StylizeNormalsToolkit.py`, `TransferNormalsTool.py`, and the
   `stylized_normals` folder together.
2. Drag `Install_StylizeNormalsToolkit_v3_0_0_alpha12.py` from an extracted folder into
   the Maya viewport. Do not drag it directly from inside the ZIP archive.
3. Maya copies the wrapper and package into its user scripts directory, replaces
   the old **TransferNormals** shelf button if present, creates a
   **StylizeNormals** shelf button, and opens the toolkit.

Repeating installation updates the local installed copy. Importing the Python
package does not automatically create UI or modify the scene.

If Maya does not accept viewport drops, open a Python tab in the Script Editor
and run the following with the installer path replaced by its extracted location:

```python
import runpy
runpy.run_path(
    r"C:\path\to\Install_StylizeNormalsToolkit_v3_0_0_alpha12.py",
    run_name="__main__",
)
```

## Generated ovoid workflow

1. Select one or more target meshes and click **Capture Selection**.
2. Choose **Ovoid Projection**.
3. Choose **Per Target** to fit one source to each mesh, or **Combined Bounds**
   to fit one source around the complete target set.
4. Adjust scale, resolution, and world-space offset.
5. Preview and apply the transfer.

Topology sampling is intentionally unavailable for generated ovoids because the
generated source does not share target topology.

## Custom source workflow

1. Capture one or more target meshes.
2. Choose **Custom Source**.
3. Select exactly one source mesh and click **Capture Source from Selection**.
4. Choose the desired sample space and search method.
5. Apply the transfer.

The toolkit duplicates the custom source into its hidden source group before
creating transfer nodes. The user's original source remains untouched.

## Generated direction workflow

1. Select complete mesh objects, vertices, or faces and click
   **Capture Objects / Vertices / Faces**.
2. Choose **Generated Direction**.
3. Choose **Radial - Away**, **Radial - Toward**, or **Directional**.
4. For radial generation, select one or more transforms, locators, or meshes and
   click **Capture Radial Origin Object(s)**. The toolkit uses their combined
   world-space bounding-box center: the same position a combined center-pivot
   calculation would produce, without changing any object pivot.
5. For directional generation, enter a non-zero world-space XYZ direction.
6. Enable **Prevent Radial Face Flips** when cards or thin shells need to retain
   their existing surface side. It is off by default for literal radial vectors.
7. Adjust **Blend** from the existing normals toward the generated result.
8. Inspect the sampled yellow vector preview and apply.

Generated edits use Maya's undoable normal command, create locked custom normals,
and are grouped into one Undo step. Component scopes currently apply only to
Generated Direction; transfer-based methods require whole-mesh targets.

Each generated Apply explicitly unlocks its captured face-vertex scope before
writing the replacement normals, so consecutive operations do not depend on
Maya overwriting already-locked data. **Unlock Normals** keeps the current custom
direction but permits later recalculation; **Reset Normals** rebuilds the normals.

Generated normals are calculated with Maya's bulk mesh API and committed through
one custom undoable command, avoiding a separate Maya command for every vertex.
The vector preview is sampled independently and capped at 150 vectors, so its
scene-node cost does not grow with target density.

## Inspect and repair workflow

The status list reports vertex and face counts, custom/locked face-vertex
normals, and soft, hard, and border-edge counts for every captured target.

Repair actions use the same captured whole-mesh or component scope as normal
generation. **Reset Normals** removes user-normal overrides and rebuilds edge
normals using the current Edge Angle. Conform and reverse operate on
faces; vertex scopes are converted to their connected faces. Hard/soft actions
operate on connected edges. Every multi-target repair is grouped into one Undo
step and preserves the artist's active selection.

## Production workflow

The last batch report remains visible in the window and is also printed to
Maya's Script Editor with per-target success and failure lines.

For comparison, click **Capture Before**, apply or repair normals, then switch
between **Show Before (Red)** and **Show Current (Green)**. Only 150 normal
vectors are sampled across all targets, and no mesh duplicates are created.

Settings can be exported to and imported from a portable JSON file. Scene object
slots such as targets, custom sources, and radial origins are intentionally not
stored in settings files.

## Transfer behavior

Transfers remain live so existing target construction history does not need to
be deleted. Generated or duplicated transfer sources are stored under a hidden
`normalToolSources` group. Each source is linked to the targets that use it and
is removed automatically after its final target is deleted. Temporary vector
and ovoid previews are also removed when a watched target is deleted, while
launch-time cleanup removes orphaned nodes left by older toolkit versions. One
Undo reverses the full batch.

If a production pipeline requires baked normals, bake or clean history later
according to that pipeline's own approved workflow.

## Manual launch

After the package is placed on Maya's Python path:

```python
import StylizeNormalsToolkit
StylizeNormalsToolkit.launch()
```
