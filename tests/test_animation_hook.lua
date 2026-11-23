-- Regression test: HOOK_MARIO_UPDATE runs after native Mario action animation selection.
-- The GTA clip must be restored only if native animation selection replaced it,
-- without restarting an already-active custom clip every frame.

local callbacks = {}
HOOK_MARIO_UPDATE = 1
HOOK_ON_LEVEL_INIT = 2
E_MODEL_NONE = 0
E_MODEL_ERROR_MODEL = -1
ACT_FREEFALL = 10
ACT_IDLE = 11

local currentAnimation = "mario_anim_fall"
local setterCalls = {}

function hook_event(event, callback)
    callbacks[event] = callback
end

function smlua_model_util_get_id(_name)
    return 123
end

function obj_set_model_extended(_obj, _modelId)
end

function smlua_anim_util_get_current_animation_name(_obj)
    return currentAnimation
end

CJ64 = {
    useGTAAnimations = true,
    animationTablesLoaded = true,
}
CJ64_GTA_ANIMATIONS = {
    names = {
        fall = "cj64_anim_fall",
        idle = "cj64_anim_idle",
    },
    set_for_role = function(_m, role)
        local name = CJ64_GTA_ANIMATIONS.names[role]
        if not name then return false end
        currentAnimation = name
        setterCalls[#setterCalls + 1] = name
        return true
    end,
}

dofile("character.lua")

assert(type(callbacks[HOOK_MARIO_UPDATE]) == "function", "CJ64 did not register HOOK_MARIO_UPDATE")

local mario = {
    playerIndex = 0,
    marioObj = {},
    action = ACT_FREEFALL,
    vel = { y = -40 },
    forwardVel = 0,
}

-- First update chooses the GTA fall clip.
callbacks[HOOK_MARIO_UPDATE](mario)
assert(currentAnimation == "cj64_anim_fall", "GTA fall clip was not selected")
assert(#setterCalls == 1, "Initial GTA fall clip should be set once")

-- Simulate native SM64 choosing another animation ID before the next end-of-update hook.
-- The same GTA role is still desired, but the current clip is no longer CJ's.
currentAnimation = "mario_anim_fall"
callbacks[HOOK_MARIO_UPDATE](mario)
assert(currentAnimation == "cj64_anim_fall", "CJ64 failed to restore GTA clip after native override")
assert(#setterCalls == 2, "GTA clip should be restored once when the current clip differs")

-- If the custom clip is already active, do not call the setter again;
-- this preserves the clip's advancing animation frame.
callbacks[HOOK_MARIO_UPDATE](mario)
assert(#setterCalls == 2, "Active GTA clip was unnecessarily reset on the next frame")

-- Switching to a new Mario action must select the mapped GTA role.
mario.action = ACT_IDLE
currentAnimation = "mario_anim_idle"
callbacks[HOOK_MARIO_UPDATE](mario)
assert(currentAnimation == "cj64_anim_idle", "CJ64 failed to select GTA idle after action change")
assert(#setterCalls == 3, "GTA idle should be selected exactly once")

print("PASS: CJ64 restores overridden GTA clips without resetting active clips.")
