-- CJ64 - Character Select DynOS actor baseline for SM64CoopDX
CJ64 = CJ64 or {}
CJ64.name = "CJ64"
CJ64.version = "0.2.0-alpha"
CJ64.csActor = true

-- Use the original Character Select DynOS actor, which was confirmed in-game
-- with native Mario animations. Do not substitute the experimental FBX export.
-- GTA clips are calibrated for the native Mario rest frames used by the working CS actor.
-- Movement, collision, camera and player heading remain owned by SM64CoopDX.
CJ64.useGTAAnimations = true
CJ64.animationTablesLoaded = false
CJ64.animationStatus = "loading_native_mario_cs_rest_profile"

if CJ64.useGTAAnimations == true then
    local animationOk, animationError = pcall(require, "cj64_gta_animations")
    if type(CJ64_GTA_ANIMATIONS) == "table"
        and type(CJ64_GTA_ANIMATIONS.set_for_role) == "function" then
        CJ64.animationTablesLoaded = true
        CJ64.animationStatus = "loaded_native_mario_cs_rest_profile"
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
    print("[CJ64] GTA San Andreas animation playback enabled for the Character Select actor.")
else
    print("[CJ64] GTA clips unavailable: keeping the working Character Select actor and native SM64CoopDX animations.")
end
