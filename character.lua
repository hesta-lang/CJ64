-- CJ64: replace only Mario's rendered model and, when a rigged actor is present,
-- drive its 20-node armature with converted GTA San Andreas animation clips.
-- MarioState, marioObj, movement, collision, camera and physics remain native.

CJ64 = CJ64 or {}
CJ64.character = CJ64.character or {
    modelName = "cj_geo",
    modelId = nil,
    ready = false,
    animationReady = false,
    retryFrames = 0,
    applied = {},
    warnedMissing = false,
    warnedApi = false,
    animationState = {},
}
local state = CJ64.character

local function valid_model_id(id)
    return type(id) == "number"
        and (E_MODEL_NONE == nil or id ~= E_MODEL_NONE)
        and (E_MODEL_ERROR_MODEL == nil or id ~= E_MODEL_ERROR_MODEL)
end

function state.try_register(force)
    if state.ready and valid_model_id(state.modelId) then return true end
    if state.retryFrames > 0 and not force then
        state.retryFrames = state.retryFrames - 1
        return false
    end
    state.retryFrames = 60

    if type(smlua_model_util_get_id) ~= "function" then
        if not state.warnedApi then
            print("[CJ64] ERROR: smlua_model_util_get_id is unavailable.")
            state.warnedApi = true
        end
        return false
    end

    local ok, id = pcall(smlua_model_util_get_id, state.modelName)
    if not ok or not valid_model_id(id) then
        if not state.warnedMissing then
            print("[CJ64] Waiting for DynOS actor '" .. state.modelName .. "'.")
            state.warnedMissing = true
        end
        return false
    end

    state.modelId = id
    state.ready = true
    state.warnedMissing = false
    print("[CJ64] Registered CJ model ID " .. tostring(id) .. ".")
    return true
end

local function action_is(action, ...)
    if action == nil then return false end
    for i = 1, select("#", ...) do
        local candidate = select(i, ...)
        if candidate ~= nil and action == candidate then return true end
    end
    return false
end

local function choose_loop_role(m)
    local a = m.action
    if action_is(a, ACT_WATER_IDLE, ACT_HOLD_WATER_IDLE, ACT_BREASTSTROKE,
        ACT_SWIMMING_END, ACT_FLUTTER_KICK, ACT_HOLD_BREASTSTROKE,
        ACT_HOLD_SWIMMING_END, ACT_HOLD_FLUTTER_KICK, ACT_WATER_SHELL_SWIMMING) then
        return "swim_tread"
    end

    if action_is(a, ACT_FREEFALL, ACT_BURNING_FALL, ACT_BURNING_JUMP, ACT_LAVA_BOOST, ACT_GETTING_BLOWN) then
        return "fall"
    end
    if action_is(a, ACT_HOLD_FREEFALL) then return "fall_air" end

    if action_is(a, ACT_JUMP, ACT_DOUBLE_JUMP, ACT_TRIPLE_JUMP, ACT_BACKFLIP,
        ACT_STEEP_JUMP, ACT_WALL_KICK_AIR, ACT_SIDE_FLIP, ACT_LONG_JUMP,
        ACT_WATER_JUMP, ACT_HOLD_JUMP, ACT_HOLD_WATER_JUMP, ACT_TWIRLING,
        ACT_FLYING_TRIPLE_JUMP, ACT_SPECIAL_TRIPLE_JUMP) then
        if m.vel ~= nil and m.vel.y ~= nil and m.vel.y < -25 then return "fall" end
        return "jump_air"
    end

    if action_is(a, ACT_WALKING, ACT_HOLD_WALKING, ACT_RIDING_SHELL_GROUND,
        ACT_HOLD_HEAVY_WALKING, ACT_CRAWLING) then
        local speed = math.abs(tonumber(m.forwardVel) or 0)
        if speed >= 28 then return "sprint_candidate" end
        if speed >= 16 then return "run" end
        return "walk"
    end

    if action_is(a, ACT_IDLE, ACT_PANTING, ACT_HOLD_IDLE, ACT_HOLD_HEAVY_IDLE,
        ACT_START_SLEEPING, ACT_SLEEPING, ACT_WAKING_UP, ACT_STANDING_AGAINST_WALL) then
        return "idle"
    end
    return nil
end

local function choose_transition_role(m, loopRole, anim)
    local a = m.action
    if action_is(a, ACT_JUMP_LAND, ACT_DOUBLE_JUMP_LAND, ACT_TRIPLE_JUMP_LAND,
        ACT_BACKFLIP_LAND, ACT_SIDE_FLIP_LAND, ACT_LONG_JUMP_LAND) then
        return "jump_land", 7, loopRole
    end
    if action_is(a, ACT_FREEFALL_LAND, ACT_HOLD_FREEFALL_LAND) then
        return "fall_land", 14, loopRole
    end
    if action_is(a, ACT_BRAKING, ACT_DECELERATING, ACT_HOLD_DECELERATING)
        and (anim.lastRole == "run" or anim.lastRole == "sprint_candidate") then
        return "run_stop", 26, loopRole
    end
    if loopRole == "walk" and anim.lastRole == "idle" then
        return "walk_start", 8, "walk"
    end
    if loopRole == "jump_air" and anim.lastRole ~= "jump_start"
        and anim.lastRole ~= "jump_air" then
        return "jump_start", 6, "jump_air"
    end
    return nil, 0, loopRole
end

function state.apply_animation(m)
    if not state.ready or CJ64.riggedActor ~= true or CJ64.animationTablesLoaded ~= true then
        state.animationReady = false
        return
    end
    if type(CJ64_GTA_ANIMATIONS) ~= "table"
        or type(CJ64_GTA_ANIMATIONS.set_for_role) ~= "function" then
        state.animationReady = false
        return
    end
    state.animationReady = true

    local index = m.playerIndex
    local anim = state.animationState[index]
    if anim == nil then
        anim = { lastRole = nil, transitionFrames = 0, transitionNextRole = nil }
        state.animationState[index] = anim
    end

    local loopRole = choose_loop_role(m)
    local role
    if anim.transitionFrames > 0 then
        anim.transitionFrames = anim.transitionFrames - 1
        role = anim.lastRole
        if anim.transitionFrames == 0 then
            role = anim.transitionNextRole or loopRole or "idle"
            anim.transitionNextRole = nil
        end
    else
        local transition, frames, nextRole = choose_transition_role(m, loopRole, anim)
        if transition ~= nil then
            role = transition
            anim.transitionFrames = frames
            anim.transitionNextRole = nextRole or "idle"
        else
            role = loopRole
        end
    end

    if role ~= nil and role ~= anim.lastRole then
        if CJ64_GTA_ANIMATIONS.set_for_role(m, role) then
            anim.lastRole = role
        end
    end
end

function state.apply(m)
    if m == nil or m.marioObj == nil or m.playerIndex == nil then return end
    if not state.ready and not state.try_register(false) then return end

    if type(obj_set_model_extended) ~= "function" then
        if not state.warnedApi then
            print("[CJ64] ERROR: obj_set_model_extended is unavailable.")
            state.warnedApi = true
        end
        return
    end

    local index = m.playerIndex
    local obj = m.marioObj
    local previous = state.applied[index]
    local apply = previous == nil or previous.obj ~= obj or previous.id ~= state.modelId

    if type(obj_get_model_id_extended) == "function" then
        local ok, current = pcall(obj_get_model_id_extended, obj)
        if ok and type(current) == "number" then
            apply = current ~= state.modelId
        end
    end

    if apply then
        local ok, err = pcall(obj_set_model_extended, obj, state.modelId)
        if not ok then
            print("[CJ64] Could not apply CJ model: " .. tostring(err))
            return
        end
        state.applied[index] = { obj = obj, id = state.modelId }
        state.animationState[index] = nil
    end

    state.apply_animation(m)
end

function state.reset()
    state.applied = {}
    state.retryFrames = 0
    state.animationState = {}
    state.animationReady = false
end

hook_event(HOOK_MARIO_UPDATE, state.apply)
if HOOK_ON_LEVEL_INIT ~= nil then
    hook_event(HOOK_ON_LEVEL_INIT, state.reset)
end

state.try_register(true)
print("[CJ64] Native Mario physics and collision retained.")
