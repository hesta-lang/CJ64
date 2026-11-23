-- CJ64 - Character Select DynOS actor baseline for SM64CoopDX
CJ64 = CJ64 or {}
CJ64.name = "CJ64"
CJ64.version = "0.1.8-alpha"
CJ64.csActor = true

-- Use the original Character Select DynOS actor, which was confirmed in-game
-- with native Mario animations. Do not substitute the experimental FBX export.
-- GTA playback remains disabled until the CS actor local rotation basis is calibrated.
CJ64.useGTAAnimations = false
CJ64.animationTablesLoaded = false
CJ64.animationStatus = "disabled_unverified_cs_node_order_and_rest_pose"

if CJ64.useGTAAnimations == true then
    local animationOk, animationError = pcall(require, "cj64_gta_animations")
    if type(CJ64_GTA_ANIMATIONS) == "table"
        and type(CJ64_GTA_ANIMATIONS.set_for_role) == "function" then
        CJ64.animationTablesLoaded = true
        CJ64.animationStatus = "loaded_experimental"
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
    print("[CJ64] Experimental GTA animation playback enabled.")
else
    print("[CJ64] GTA clips disabled: using SM64CoopDX native player animations until the CS node order and rest pose are verified.")
end
