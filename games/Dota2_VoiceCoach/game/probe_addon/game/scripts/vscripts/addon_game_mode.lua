-- Пробник кастомки «голосовой тренер»: отвечает на открытые вопросы research/00_SUMMARY.md.
-- Результаты — строки «[ПРОБНИК] …» в консоли (запуск с -condebug → game/dota/console.log).
require("probe")

function Precache(context)
end

function Activate()
  VoiceCoachProbe:Init()
end
