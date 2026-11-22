# CJ64 Blender bridge

## What it does

CJ64 uses GitHub Actions as a remote, non-interactive Blender runner. This is the practical bridge for developing from Android: ChatGPT can update the Blender Python scripts and workflow in this repository, GitHub Actions executes Blender in the cloud, and the outputs are returned as downloadable artifacts.

This is a batch workflow, **not a live Blender MCP connection**. It does not keep Blender open between runs.

## Run it from Android

1. Open the [CJ64 Actions page](https://github.com/hesta-lang/CJ64/actions).
2. Select **CJ64 Blender bridge and DynOS export**.
3. Press **Run workflow** on the `main` branch.
4. Open the new run and wait until the job completes.
5. Download the `CJ64-static-model-test` artifact from the run's Artifacts section.

A push changing the model source, exporter, texture normalizer, or workflow also starts the build automatically.

## What the workflow executes

- Blender 4.5.16 imports the ASCII FBX source, prepares the static rest pose, and exports the textured GLB plus its reference preview.
- Blender 3.6.23 imports that GLB and runs Fast64-Coop to export a DynOS actor named `cj_geo`.
- The exporter clears Blender's factory-startup objects before importing CJ. This is important: the default `Cube` was previously joined to CJ, exported at 2×2×2 units, and appeared in-game as the gray block hiding the lower body.
- The exporter records per-mesh bounds, joined geometry dimensions, materials, and removed startup objects. It rejects geometry exceeding the expected 1.80-unit envelope.
- The texture normalizer replaces spaces in texture filenames and include paths, then verifies every referenced PNG exists inside the install ZIP.
- The Blender 3.6 scene is saved as `CJ64-Blender-Scene.blend`.

## Character scale reference

The export targets an estimated CJ height of 1.80 m (5 ft 11 in). Rockstar has not published an authoritative height for Carl Johnson; 1.80 m is a community/reference estimate, not a confirmed canon measurement.

SM64's in-game scale reference is 160 units tall for Mario. The Fast64 export uses 100 SM64 units per Blender unit, so this build targets CJ at 180 SM64 units (1.80 Blender units), or 1.125× Mario's 160-unit reference. The scaling factor is calculated from the imported mesh's measured height instead of being hard-coded.

Only the visible mesh is rescaled. CJ64 continues to use Mario's original `MarioState`, `marioObj`, hitboxes, collision and physics.

## Artifact contents

- `CJ64-Model-Test.zip`: installable SM64CoopDX mod folder.
- `CJ64-Blender-Scene.blend`: saved Blender scene after import and Fast64 export.
- `CJ64-model-preview.png`: reference render made during FBX preparation.
- `cj_model_test_report.json`: actor, materials, texture and geometry summary.
- `cj_scene_diagnostics.json`: startup object cleanup and mesh-bound diagnostics.
- `CJ-Static-Model.glb`: normalized intermediate model.

## Current limits

- The exported CJ mesh is still a static rest pose. This bridge does not yet transfer weights to Mario's armature or create the Mario-compatible animation hierarchy.
- A successful Blender/Fast64 export does not prove the build works in SM64CoopDX. The in-game result must still be checked on the Android installation.
- The `.blend` file is a diagnostic/editable project artifact. It is not required to install the mod.
