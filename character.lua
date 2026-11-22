-- CJ64: replace the native Mario model with the CJ DynOS actor.
-- Expected model/GeoLayout name: cj_geo
--
-- No extra object is spawned. marioObj and MarioState remain engine-owned.
-- Native movement, collision, camera, actions and interactions are untouched.

CJ64 = CJ64 or {}
CJ64.character = CJ64.character or {
    modelName = "cj_geo",
    modelId = nil,
    ready = false,
    retryFrames = 0,
    applied = {},
    warnedMissing = false,
    warnedApi = false,
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
    end
end

function state.reset()
    state.applied = {}
    state.retryFrames = 0
end

hook_event(HOOK_MARIO_UPDATE, state.apply)
if HOOK_ON_LEVEL_INIT ~= nil then
    hook_event(HOOK_ON_LEVEL_INIT, state.reset)
end

state.try_register(true)
print("[CJ64] Native Mario physics and collision retained.")
