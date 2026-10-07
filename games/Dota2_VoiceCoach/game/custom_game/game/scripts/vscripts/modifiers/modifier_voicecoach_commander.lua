-- Тренер без героя: его герой спрятан у базы — невидим, неуязвим, вне игры, не на миникарте,
-- без приказов. Тренер командует пятью агентами (решение автора 07.10.2026: «игра сразу за 5 агентов»).
modifier_voicecoach_commander = class({})

function modifier_voicecoach_commander:IsHidden() return true end
function modifier_voicecoach_commander:IsPurgable() return false end
function modifier_voicecoach_commander:RemoveOnDeath() return false end

function modifier_voicecoach_commander:CheckState()
  return {
    [MODIFIER_STATE_INVULNERABLE] = true,
    [MODIFIER_STATE_OUT_OF_GAME] = true,
    [MODIFIER_STATE_NO_HEALTH_BAR] = true,
    [MODIFIER_STATE_NOT_ON_MINIMAP] = true,
    [MODIFIER_STATE_STUNNED] = true,
    [MODIFIER_STATE_COMMAND_RESTRICTED] = true,
    [MODIFIER_STATE_NO_UNIT_COLLISION] = true,
  }
end
