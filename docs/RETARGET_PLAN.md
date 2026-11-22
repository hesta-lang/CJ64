# CJ to SM64CoopDX Mario retarget

## Why this stage exists

The GTA ped.ifp tracks belong to the GTA pedestrian skeleton, while the CJ FBX
has its own 58-bone rig and the SM64CoopDX character template uses a separate
Mario Armature. Matching bone names from GTA to the CJ FBX is not sufficient to
retarget a clip to Mario. Rest-pose matrices, parent hierarchy, bone roll,
lengths and target vertex groups must be checked first.

The official Coop Deluxe character-template instructions recommend Blender
3.6 LTS and Fast64, require CJ geometry to be parented to Mario's Armature with
matching vertex groups, and state that the game animation path only supports
bone rotations (limb translation/scale are not reproduced). The pipeline must
therefore bake the GTA motions onto the Mario rig and keep root movement as
SM64-compatible root translation only.

## Current automated step

The new GitHub Actions workflow downloads Blender 3.6.23 LTS and the official
Mario Coop Model Template.blend, imports the committed CJ FBX, and produces:

- cj_mario_rig_inspection.json: both armature hierarchies, rest matrices,
  bone endpoints, weighted mesh groups, dimensions and texture references.
- cj_mario_dual_rig_inspection.blend: editable project containing the official
  Mario template and the CJ source rig together for inspection.

The IFP is intentionally not copied into the public repository. The animation
JSON generated from the user-provided IFP remains a local input and is not
committed either.

## Retarget stages still required

1. Review the real Mario and CJ bone reports and define a validated semantic
   mapping; merge source joints only where the target skeleton has no equivalent.
2. Transfer CJ mesh weights to Mario vertex groups while preserving the visible
   proportions and bind pose.
3. Retarget each source pose using source and target rest matrices, then bake
   rotations at the SM64 animation frame rate. Do not copy GTA limb translations.
4. Validate idle, walk, run, jump, fall, land and swim in Blender before export.
5. Export the actor/animations with a compatible Fast64-Coop or Fast64-Gart
   build and generate the SM64 animation values/index tables.
6. Register the custom clips in Lua and test them in SM64CoopDX while retaining
   the vanilla Mario animation fallback.

No in-game-ready actor or custom SM64 animation tables are produced by the
inspection-only job. This is deliberate: an invented bone map would distort the
model and could cause broken animation in game.
