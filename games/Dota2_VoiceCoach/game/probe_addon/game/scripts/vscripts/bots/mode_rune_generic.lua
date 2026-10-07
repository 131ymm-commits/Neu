-- Пробник в среде ботов: если эти строки есть в консоли — папка bots аддона работает в кастомке.
-- Режим руны не трогаем (желание 0): остальное поведение бота — встроенное.
local bot = GetBot()
local name = bot and bot:GetUnitName() or "?"
print("[ПРОБНИК-БОТ] папка bots аддона загружена для " .. name)

local next_report = -1000
local chat_ok = false

function GetDesire()
  local t = DotaTime()
  if not chat_ok then
    chat_ok = true
    local ok, err = pcall(InstallChatCallback, function(a)
      print("[ПРОБНИК-БОТ] " .. name .. " услышал чат: " .. tostring(a.string) .. " (игрок " .. tostring(a.player_id) .. ")")
    end)
    print("[ПРОБНИК-БОТ] InstallChatCallback: " .. (ok and "есть" or ("ошибка " .. tostring(err))))
  end
  if t - next_report >= 15 then
    next_report = t
    local idx = bot:GetModifierByName("modifier_voicecoach_probe")
    local stack = (idx and idx > -1) and bot:GetModifierStackCount(idx) or nil
    print(string.format("[ПРОБНИК-БОТ] %s t=%.0f модификатор=%s стак=%s общая_переменная=%s http=%s",
      name, t, tostring(idx), tostring(stack), tostring(rawget(_G, "VOICECOACH_PROBE")),
      tostring(CreateRemoteHTTPRequest ~= nil)))
  end
  return 0
end
