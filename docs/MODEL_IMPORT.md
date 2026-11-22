# CJ model import

Source file: `CarlJohnson-GTASA.FBX`, accompanied by `head.png`, `upper body.png`, `legs.png` and `shoes.png`. The FBX contains a 58-bone rig and skin clusters. It is an authoring source, not a DynOS actor.

## Target for the first playable version

The first version uses the **existing SM64CoopDX Mario animations**. The CJ mesh therefore has to use the native Mario Armature rather than keeping its original GTA skeleton as the in-game rig.

The official [SM64CoopDX character template](https://github.com/coop-deluxe/character-template) documents the intended process: use the Mario Armature, parent the mesh to it, assign the correct vertex groups, and export the Armature GeoLayout with Fast64. Its README recommends Blender 3.6 LTS and a compatible Fast64 fork.

## Required conversion work

1. Open the SM64CoopDX character template in a compatible Blender/Fast64 setup.
2. Import the CJ FBX and preserve its mesh and texture material data.
3. Fit the CJ mesh to the Mario Armature. The GTA FBX's 58-bone hierarchy is not a drop-in replacement for Mario's skeleton.
4. Transfer/reassign skin weights to the matching Mario vertex groups. Check every body part for unweighted vertices, incorrect groups and duplicate armature modifiers.
5. Parent the CJ mesh to the Mario Armature and verify the mesh deforms correctly when testing Mario's idle, walk, run, jump and fall poses.
6. Export the **Mario Armature GeoLayout** into this actor folder, using the runtime model name `cj_geo` expected by `character.lua`.
7. Rebuild the actor in-game after deleting any stale generated `.bin` for the previous model export.

Do not solve rig mismatches by spawning a second CJ object or by replacing MarioState. That would break the chosen single-player-entity architecture.

## Future original animations

When the original GTA animation source becomes available, its tracks can be applied to the source rig, then retargeted and baked onto the Mario Armature. The model's first playable version does not depend on those clips. See [ANIMATIONS.md](ANIMATIONS.md).

Source credit: Carl Johnson (CJ), by Tsaphnat (Tsaphnat Mbuyi), Sketchfab, CC BY 4.0. See [assets/cj/source/README.md](../assets/cj/source/README.md).
