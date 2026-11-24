-- CJ64 - Character Select DynOS actor baseline for SM64CoopDX
CJ64 = CJ64 or {}
CJ64.name = "CJ64"
CJ64.version = "0.2.8-alpha"
CJ64.csActor = true

-- Keep the original Character Select actor; do not use the experimental FBX export.
-- GTA source-pose rotations are converted through quaternions and encoded in SM64 ZXY channel order.
-- No Mario anim_00/anim_C5 pose is applied over GTA. SM64CoopDX retains movement and world transforms.
CJ64.useGTAAnimations = true
CJ64.animationTablesLoaded = false
CJ64.animationStatus = "loading_gta_source_pose_sm64_zxy"

if CJ64.useGTAAnimations == true then
    local animationOk, animationError = pcall(require, "cj64_gta_animations")
    if type(CJ64_GTA_ANIMATIONS) == "table"
        and type(CJ64_GTA_ANIMATIONS.set_for_role) == "function" then
        CJ64.animationTablesLoaded = true
        CJ64.animationStatus = "loaded_gta_source_pose_sm64_zxy"
    elseif not animationOk then
        print("[CJ64] GTA animation module unavailable: " .. tostring(animationError))
    end
end

-- SM64CoopDX does not automatically execute every sibling Lua file.
local characterOk, characterError = pcall(require, "character")
if not characterOk then
    print("[CJ64] ERROR loading character controller: " .. tostring(characterError))
end

print("[CJ64] " .. CJ64.name .. " " .. CJ64.version .. " loaded.")
if CJ64.useGTAAnimations == true and CJ64.animationTablesLoaded then
    print("[CJ64] GTA source-pose animations loaded with SM64 ZXY channel encoding on the original CS actor.")
else
    print("[CJ64] GTA clips unavailable: keeping the working Character Select actor and native SM64CoopDX animations.")
end
