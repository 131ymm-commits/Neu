-- Пробник кастомки «голосовой тренер» (неделя 3 плана, docs/ROADMAP.md).
--
-- За один запуск в Workshop Tools на карте dota отвечает на вопросы, от которых зависит
-- итоговая кастомка (research/00_SUMMARY.md, «Открытые вопросы»):
--   1) ходит ли сервер кастомки по HTTP к серверу тренера (в Tools должен);
--   2) поднимаются ли 10 ботов через Tutorial:AddBot и думают ли они (схема Windy10v10AI);
--   3) работает ли канал «голос → веб-панель клиента → игровое событие → сервер» (как в аркаде);
--   4) видят ли скрипты ботов то, что кладёт кастомка (модификатор, чат, общая переменная);
--   5) перебивает ли встроенный ИИ наши приказы; 6) сколько стоит «думание» по 10 героям.
-- Каждый ответ — строка «[ПРОБНИК] имя  OK/НЕТ/??  подробности»; в конце — сводка «ИТОГ».

VoiceCoachProbe = VoiceCoachProbe or {}
local P = VoiceCoachProbe

P.SERVER = "http://127.0.0.1:8787"
P.ROOM = "probe"
-- герои с поддержкой встроенных ботов Valve (классический список ботов; ПРЕДПОЛОЖЕНИЕ, проверяется здесь же)
P.BOT_HEROES = {
  [DOTA_TEAM_GOODGUYS] = { "npc_dota_hero_sniper", "npc_dota_hero_viper", "npc_dota_hero_axe",
                           "npc_dota_hero_lion", "npc_dota_hero_crystal_maiden" },
  [DOTA_TEAM_BADGUYS] = { "npc_dota_hero_luna", "npc_dota_hero_lina", "npc_dota_hero_bristleback",
                          "npc_dota_hero_witch_doctor", "npc_dota_hero_jakiro" },
}

local results, order = {}, {}

local function say(name, ok, detail)
  local mark = (ok == true and "OK ") or (ok == false and "НЕТ") or "?? "
  print(string.format("[ПРОБНИК] %-24s %s %s", name, mark, tostring(detail or "")))
  if results[name] == nil then order[#order + 1] = name end
  results[name] = { ok = ok, detail = detail }
end

local function after(seconds, fn)
  GameRules:GetGameModeEntity():SetContextThink("vc_probe_" .. tostring(math.random(1e9)), function()
    local ok, err = pcall(fn)
    if not ok then print("[ПРОБНИК] ошибка в проверке: " .. tostring(err)) end
    return nil
  end, seconds)
end

-- JSON: game/shared/json.lua (rxi, MIT), установщик кладёт его рядом как vc_json.lua
local has_json, JSON = pcall(require, "vc_json")

local function json_decode(s)
  if not has_json then return nil end
  local ok, v = pcall(JSON.decode, s)
  if ok then return v end
  return nil
end

function P:Init()
  print("[ПРОБНИК] ===== голосовой тренер: пробник кастомки, " .. tostring(GetSystemTime()) .. " =====")
  say("lua", true, tostring(_VERSION) .. " jit=" .. tostring(jit and jit.version))
  say("tools_mode", IsInToolsMode(), "")
  say("dedicated_server", nil, tostring(IsDedicatedServer()))
  say("http_api", CreateHTTPRequestScriptVM ~= nil, "CreateHTTPRequestScriptVM")
  say("json", has_json, has_json and "vc_json загружен" or ("нет vc_json.lua: " .. tostring(JSON)))

  local gm = GameRules:GetGameModeEntity()
  pcall(function() Convars:SetBool("dota_bot_mode", true) end)
  pcall(function() Convars:SetBool("dota_bot_disable", false) end)
  GameRules:SetCustomGameTeamMaxPlayers(DOTA_TEAM_GOODGUYS, 5)
  GameRules:SetCustomGameTeamMaxPlayers(DOTA_TEAM_BADGUYS, 5)
  GameRules:EnableCustomGameSetupAutoLaunch(true)
  GameRules:SetCustomGameSetupAutoLaunchDelay(5)
  GameRules:SetHeroSelectionTime(30)
  GameRules:SetStrategyTime(5)
  GameRules:SetShowcaseTime(0)
  GameRules:SetPreGameTime(30)

  ListenToGameEvent("game_rules_state_change", Dynamic_Wrap(P, "OnState"), P)
  ListenToGameEvent("player_chat", Dynamic_Wrap(P, "OnChat"), P)
  CustomGameEventManager:RegisterListener("vc_probe_title", function(_, ev) P:OnTitle(ev) end)
  CustomGameEventManager:RegisterListener("vc_probe_report", function(_, ev) P:OnClientReport(ev) end)
  LinkLuaModifier("modifier_voicecoach_probe", "modifiers/modifier_voicecoach_probe", LUA_MODIFIER_MOTION_NONE)
  _G.VOICECOACH_PROBE = "vscripts"
  gm:SetContextThink("vc_probe_http", function() P:CheckHttp() return nil end, 1)
end

-- 1) HTTP сервера кастомки к серверу тренера
function P:CheckHttp()
  if CreateHTTPRequestScriptVM == nil then
    say("server_http", false, "функции нет")
    return
  end
  local t0 = GetSystemTimeMS()
  local req = CreateHTTPRequestScriptVM("GET", P.SERVER .. "/api/health")
  if req == nil then
    say("server_http", false, "CreateHTTPRequestScriptVM вернул nil (как в аркаде)")
    return
  end
  req:SetHTTPRequestAbsoluteTimeoutMS(5000)
  req:Send(function(res)
    local ms = math.floor(GetSystemTimeMS() - t0)
    say("server_http", res.StatusCode == 200, "код " .. tostring(res.StatusCode) .. ", " .. ms .. " мс, " .. tostring(res.Body))
  end)
end

function P:OnState()
  local s = GameRules:State_Get()
  if s == DOTA_GAMERULES_STATE_HERO_SELECTION then
    after(3, function() P:AddBots("bots_added") end)
  elseif s == DOTA_GAMERULES_STATE_STRATEGY_TIME then
    -- вторая попытка, если в выборе героев добавились не все (когда звать AddBot — тоже вопрос пробника)
    if (P.bots_total or 0) < 9 then after(1, function() P:AddBots("bots_added_retry") end) end
  elseif s == DOTA_GAMERULES_STATE_PRE_GAME then
    after(5, function() P:CheckHeroes() end)
    after(8, function() P:ChannelsToBots() end)
  elseif s == DOTA_GAMERULES_STATE_GAME_IN_PROGRESS then
    P.start_positions = P:HeroPositions()
    after(20, function() P:OrderOverride() end)
    after(30, function() P:ThinkCost() end)
    after(60, function() P:BotsMoved() end)
    after(90, function() P:Summary() end)
  end
end

-- 2) 10 ботов
function P:AddBots(check)
  local added, failed = 0, {}
  for _, team in ipairs({ DOTA_TEAM_GOODGUYS, DOTA_TEAM_BADGUYS }) do
    local need = 5 - PlayerResource:GetPlayerCountForTeam(team)
    for i = 1, need do
      local hero = P.BOT_HEROES[team][i]
      if hero and Tutorial:AddBot(hero, "", "unfair", team == DOTA_TEAM_GOODGUYS) then
        added = added + 1
      else
        failed[#failed + 1] = tostring(hero)
      end
    end
  end
  P.bots_total = (P.bots_total or 0) + added
  GameRules:GetGameModeEntity():SetBotThinkingEnabled(true)
  Tutorial:StartTutorialMode()
  say(check, P.bots_total >= 9, "добавлено " .. added .. ", всего " .. P.bots_total ..
    (#failed > 0 and (", не вышло: " .. table.concat(failed, " ")) or ""))
end

function P:Heroes()
  local list = {}
  for pid = 0, 23 do
    if PlayerResource:IsValidPlayerID(pid) then
      local h = PlayerResource:GetSelectedHeroEntity(pid)
      if h then
        list[#list + 1] = { pid = pid, hero = h, fake = PlayerResource:IsFakeClient(pid),
                            team = PlayerResource:GetTeam(pid) }
      end
    end
  end
  return list
end

function P:HeroPositions()
  local pos = {}
  for _, e in ipairs(P:Heroes()) do pos[e.pid] = e.hero:GetAbsOrigin() end
  return pos
end

function P:CheckHeroes()
  local list, fake, lines = P:Heroes(), 0, {}
  for _, e in ipairs(list) do
    if e.fake then fake = fake + 1 end
    lines[#lines + 1] = string.format("%d:%s%s(%d)", e.pid, e.hero:GetUnitName():gsub("npc_dota_hero_", ""),
      e.fake and "*" or "", e.team)
  end
  say("heroes", #list >= 10, #list .. " героев, ботов " .. fake .. ": " .. table.concat(lines, " "))
  -- тренер: кто человек и на какой он стороне
  for pid = 0, 23 do
    if PlayerResource:IsValidPlayerID(pid) and not PlayerResource:IsFakeClient(pid) then
      say("commander", nil, string.format("игрок %d, команда %d, герой %s", pid, PlayerResource:GetTeam(pid),
        tostring(PlayerResource:GetSelectedHeroName(pid))))
    end
  end
end

-- 4) что кастомка может положить ботам: модификатор со стаком, чат, общая переменная
function P:ChannelsToBots()
  local n = 0
  for _, e in ipairs(P:Heroes()) do
    if e.fake then
      local buff = e.hero:AddNewModifier(e.hero, nil, "modifier_voicecoach_probe", {})
      if buff then
        buff:SetStackCount(7)
        n = n + 1
      end
    end
  end
  say("modifier_on_bots", n > 0, "повешено на " .. n .. " ботов (стак 7); что увидели боты — строки [ПРОБНИК-БОТ]")
  for _, e in ipairs(P:Heroes()) do
    if e.fake and e.team == DOTA_TEAM_GOODGUYS then
      Say(e.hero, "#vc проба чата", true)
      break
    end
  end
  say("say_to_bots", nil, "отправлено «#vc проба чата»; дошло ли — строки [ПРОБНИК-БОТ] … услышал чат")
end

-- 5) перебивает ли встроенный ИИ наш приказ «идти в центр карты»
function P:OrderOverride()
  for _, e in ipairs(P:Heroes()) do
    if e.fake and e.team == DOTA_TEAM_GOODGUYS then
      local target = Vector(0, 0, 0)
      local d0 = (e.hero:GetAbsOrigin() - target):Length2D()
      for k = 0, 4 do
        after(k * 0.5, function()
          ExecuteOrderFromTable({ UnitIndex = e.hero:entindex(), OrderType = DOTA_UNIT_ORDER_MOVE_TO_POSITION,
                                  Position = target, Queue = false })
        end)
      end
      after(4, function()
        local d1 = (e.hero:GetAbsOrigin() - target):Length2D()
        say("order_vs_native_ai", d0 - d1 > 600, string.format("%s: до центра было %d, стало %d",
          e.hero:GetUnitName(), math.floor(d0), math.floor(d1)))
      end)
      return
    end
  end
  say("order_vs_native_ai", false, "нет героя-бота Света")
end

-- 6) цена «думания»: обход 10 героев с позициями и здоровьем, 40 раз
function P:ThinkCost()
  local t0 = GetSystemTimeMS()
  local sum = 0
  for _ = 1, 40 do
    for _, e in ipairs(P:Heroes()) do
      local p = e.hero:GetAbsOrigin()
      sum = sum + p.x * 0 + e.hero:GetHealth() * 0
    end
  end
  local per = (GetSystemTimeMS() - t0) / 40
  say("think_cost_ms", per < 2, string.format("%.3f мс на обход 10 героев", per))
end

function P:BotsMoved()
  local start, moved, total = P.start_positions or {}, 0, 0
  for _, e in ipairs(P:Heroes()) do
    if e.fake and start[e.pid] then
      total = total + 1
      if (e.hero:GetAbsOrigin() - start[e.pid]):Length2D() > 1000 then moved = moved + 1 end
    end
  end
  say("bots_think", total > 0 and moved >= total - 1, moved .. " из " .. total .. " ботов ушли от фонтана за 60 с")
end

-- 3) канал аркады: веб-панель клиента получила команду тренера и переслала её сюда
function P:OnTitle(ev)
  local data = json_decode(tostring(ev.data or "")) or {}
  local cmds = data.commands or {}
  if not P.title_ok then
    P.title_ok = true
    say("html_panel_channel", true, "первый ответ через DOTAHTMLPanel за " .. tostring(ev.ms) .. " мс")
  end
  for _, c in ipairs(cmds) do
    local who = {}
    for _, p in ipairs(c.agents or {}) do who[#who + 1] = tostring(p) end
    print(string.format("[ПРОБНИК] голос → клиент → сервер: %s → позиции %s (за %s мс)", tostring(c.action),
      table.concat(who, ","), tostring(ev.ms)))
    if c.action == "retreat" then P:RetreatRadiant() end
  end
end

function P:RetreatRadiant()
  local fountain = Vector(-7000, -6500, 0)
  for _, e in ipairs(P:Heroes()) do
    if e.fake and e.team == DOTA_TEAM_GOODGUYS then
      ExecuteOrderFromTable({ UnitIndex = e.hero:entindex(), OrderType = DOTA_UNIT_ORDER_MOVE_TO_POSITION,
                              Position = fountain, Queue = false })
    end
  end
  print("[ПРОБНИК] приказ «назад» отдан ботам Света (видно ли, что они пошли к фонтану?)")
end

function P:OnClientReport(ev)
  say("client_" .. tostring(ev.key), ev.ok == 1 or ev.ok == true, tostring(ev.detail))
  -- ранние события клиента приходят с PlayerID = -1 (так в коде Windy10v10AI): клиент шлёт
  -- «ui_loaded», пока сервер не ответит подтверждением
  local pid = tonumber(ev.PlayerID) or -1
  if ev.key == "ui_loaded" and pid >= 0 then
    local player = PlayerResource:GetPlayer(pid)
    if player then CustomGameEventManager:Send_ServerToPlayer(player, "vc_probe_ack", {}) end
  end
end

function P:OnChat(ev)
  print("[ПРОБНИК] чат игрока " .. tostring(ev.playerid) .. ": " .. tostring(ev.text))
end

function P:Summary()
  print("[ПРОБНИК] ===== ИТОГ (скопируйте этот блок) =====")
  for _, name in ipairs(order) do
    local r = results[name]
    local mark = (r.ok == true and "OK ") or (r.ok == false and "НЕТ") or "?? "
    print(string.format("[ПРОБНИК] ИТОГ %-24s %s %s", name, mark, tostring(r.detail or "")))
  end
  if not results.html_panel_channel then
    print("[ПРОБНИК] ИТОГ html_panel_channel       НЕТ ответов от веб-панели (сервер тренера запущен? комната probe?)")
  end
end
