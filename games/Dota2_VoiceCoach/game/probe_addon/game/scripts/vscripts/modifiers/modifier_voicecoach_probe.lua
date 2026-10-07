-- Невидимый модификатор-метка: кастомка вешает его на героев ботов со stack count = номер команды.
-- Проверяется, видит ли его скрипт бота (GetModifierByName / GetModifierStackCount).
modifier_voicecoach_probe = class({})

function modifier_voicecoach_probe:IsHidden() return true end
function modifier_voicecoach_probe:IsPurgable() return false end
function modifier_voicecoach_probe:RemoveOnDeath() return false end
