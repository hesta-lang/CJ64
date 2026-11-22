# CJ64

**Carl Johnson character replacement for SM64CoopDX.**

## 0.1.0-alpha — first implementation

CJ replaces Mario's visible model while the game continues to use its native player state and object.

- Keeps the original \`MarioState\` and \`marioObj\`.
- Does not create a second character entity.
- Does not replace movement, physics, collision, camera, actions or interactions.
- Looks for a DynOS model named \`cj_geo\`.
- Waits safely when the model asset is absent; Mario remains visible.

## Current limitation

This repository currently contains the Lua replacement framework only. **The CJ model and textures have not been added yet.** Consequently, downloading this version alone will not make CJ appear. Add a compatible DynOS actor under \`actors/cj/\`, registered with the model name \`cj_geo\`.

The model must be rigged to the native SM64CoopDX player skeleton/animation layout. A GTA San Andreas DFF/TXD is not directly usable as a DynOS actor; it must be converted and adapted. Only add assets you have permission to redistribute.

## Files

- \`main.lua\` — mod entry point.
- \`character.lua\` — safe native model replacement.
- \`actors/cj/README.md\` — required actor format and naming.
- \`tools/test_model_swap.lua\` — mocked Lua regression test.

## Install

Place the extracted \`CJ64\` folder inside the SM64CoopDX \`mods\` directory and enable it. The mod is Lua-only; it is not an APK.

## Validation

GitHub Actions checks Lua syntax and tests the replacement logic with a mocked SM64CoopDX API. This does not prove the actor loads or that the game works on Android; that requires an in-game test with the final CJ model.
