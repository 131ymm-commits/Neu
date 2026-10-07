-- Кастомка «голосовой тренер» (каркас): стандартная карта, тренер без героя, 5 агентов на сторону,
-- приказы текстом. Логика — coach_game.lua; запуск: dota_launch_custom_game voicecoach dota
require("coach_game")

function Precache(context)
end

function Activate()
  CoachGame:Init()
end
