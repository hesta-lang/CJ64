-- CJ64 - Character Select DynOS actor with GTA movement animations
CJ64 = CJ64 or {}
CJ64.name = "CJ64"
CJ64.version = "0.2.11-alpha"
CJ64.csActor = true

-- Keep the original working Character Select actor; do not use the experimental FBX export.
-- GTA rotations are normalized to IDLE_stance motion and composed on all 20 native CS anim_00 XYZ joints.
-- SM64CoopDX retains world heading, movement, collision, camera and physics.
CJ64.useGTAAnimations = true
CJ64.animationTablesLoaded = false
CJ64.animationStatus = "loading_gta_xyz_native_anim00_pose"

if CJ64.useGTAAnimations == true then
    local animationOk, animationError = pcall(require, "cj64_gta_animations")
    if type(CJ64_GTA_ANIMATIONS) == "table"
        and type(CJ64_GTA_ANIMATIONS.set_for_role) == "function" then
        CJ64.animationTablesLoaded = true
        CJ64.animationStatus = "loaded_gta_xyz_native_anim00_pose"
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
    print("[CJ64] GTA animation motion composed on all 20 native CS anim_00 XYZ joints.")
else
    print("[CJ64] GTA clips unavailable: keeping the working Character Select actor and native SM64CoopDX animations.")
end
