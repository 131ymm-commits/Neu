-- Кастомка «голосовой тренер» — каркас (решения автора Д9 и Д10, 07.10.2026).
--
-- Стандартная карта Доты и её механики. В каждой команде 5 агентов-ботов и тренер без героя (его
-- герой спрятан у базы). Тренер командует текстом в коротком формате — в поле внизу экрана или в
-- командном чате: «1 фарм лес. 23 ганг мид. все рош». Агенты играют сами (встроенный ИИ ботов Доты),
-- приказы тренера сдвигают, что они делают (coach_agents.lua), и агенты отвечают своими словами.
--
-- Модули рядом: coach_agents.lua (решения), coach_world.lua (карта через API Доты); общие с прототипом
-- и страницей тренера — установщик кладёт их как vc_intents.lua, vc_voice.lua, vc_text.lua, vc_text_data.lua.

local Intents = require("vc_intents")
local Voice = require("vc_voice")
local Text = require("vc_text")
Text.init(require("vc_text_data"))
local Agents = require("coach_agents")
local World = require("coach_world")

CoachGame = CoachGame or {}
local G = CoachGame

-- герои с поддержкой встроенных ботов Valve (по памяти; бот, которого не удалось добавить, — в журнале)
G.BOT_HEROES = {
  [DOTA_TEAM_GOODGUYS] = { "npc_dota_hero_sniper", "npc_dota_hero_viper", "npc_dota_hero_axe",
                           "npc_dota_hero_lion", "npc_dota_hero_crystal_maiden",
                           "npc_dota_hero_drow_ranger", "npc_dota_hero_dragon_knight" },
  [DOTA_TEAM_BADGUYS] = { "npc_dota_hero_luna", "npc_dota_hero_lina", "npc_dota_hero_bristleback",
                          "npc_dota_hero_witch_doctor", "npc_dota_hero_jakiro",
                          "npc_dota_hero_skeleton_king", "npc_dota_hero_ogre_magi" },
}
-- угол базы, куда прячется герой тренера (приблизительно, по памяти)
G.CORNER = { [DOTA_TEAM_GOODGUYS] = Vector(-7300, -7000, 0), [DOTA_TEAM_BADGUYS] = Vector(7300, 6900, 0) }
G.THINK = 0.5                 -- с: цикл агентов
G.CAMERA_DISTANCE = 1600      -- дальше обычного (в Доте 1134): тренер смотрит сверху
G.CHAT_REPLIES = true         -- агенты отвечают и в командный чат (кроме ошибок формата)
G.teams = G.teams or {}
G.ready = false

local MORE_REFUSE = {
  no_target = "Не вижу цели", where = "Не знаю, куда", no_item = "Нет такого предмета",
  item_cd = "Предмет в откате, %d с",
}

local function log(fmt, ...)
  print("[ТРЕНЕР] " .. string.format(fmt, ...))
end

local function refuse_text(reason, value)
  local f = MORE_REFUSE[reason]
  if f then
    if f:find("%%d") then return string.format(f, math.max(0, math.floor((tonumber(value) or 0) + 0.5))) end
    return f
  end
  return Voice.refuse(reason, value)
end

function G:Init()
  GameRules:SetCustomGameTeamMaxPlayers(DOTA_TEAM_GOODGUYS, 6)     -- 5 агентов + тренер
  GameRules:SetCustomGameTeamMaxPlayers(DOTA_TEAM_BADGUYS, 6)
  GameRules:EnableCustomGameSetupAutoLaunch(true)
  GameRules:SetCustomGameSetupAutoLaunchDelay(5)
  GameRules:SetHeroSelectionTime(20)
  GameRules:SetStrategyTime(5)
  GameRules:SetShowcaseTime(0)
  GameRules:SetPreGameTime(30)
  pcall(function() Convars:SetBool("dota_bot_mode", true) end)
  local gm = GameRules:GetGameModeEntity()
  gm:SetCameraDistanceOverride(G.CAMERA_DISTANCE)
  ListenToGameEvent("game_rules_state_change", Dynamic_Wrap(G, "OnState"), G)
  ListenToGameEvent("npc_spawned", Dynamic_Wrap(G, "OnSpawn"), G)
  ListenToGameEvent("player_chat", Dynamic_Wrap(G, "OnChat"), G)
  CustomGameEventManager:RegisterListener("vc_command", function(_, ev) G:OnHudCommand(ev) end)
  CustomGameEventManager:RegisterListener("vc_ready", function(_, ev) G:OnReady(ev) end)
  LinkLuaModifier("modifier_voicecoach_commander", "modifiers/modifier_voicecoach_commander", LUA_MODIFIER_MOTION_NONE)
  gm:SetContextThink("vc_coach_think", function() return G:Think() end, 1)
  log("каркас загружен")
end

local function humans()
  local out = {}
  for pid = 0, 23 do
    if PlayerResource:IsValidPlayerID(pid) and not PlayerResource:IsFakeClient(pid) then out[#out + 1] = pid end
  end
  return out
end

function G:OnState()
  local s = GameRules:State_Get()
  local gm = GameRules:GetGameModeEntity()
  if s == DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP then
    -- тренеры — по одному в команду: первый за Свет, второй за Тьму
    for i, pid in ipairs(humans()) do
      PlayerResource:SetCustomTeamAssignment(pid, (i % 2 == 1) and DOTA_TEAM_GOODGUYS or DOTA_TEAM_BADGUYS)
    end
  elseif s == DOTA_GAMERULES_STATE_HERO_SELECTION then
    gm:SetContextThink("vc_add_bots", function() G:AddBots() return nil end, 2)
  elseif s == DOTA_GAMERULES_STATE_PRE_GAME then
    gm:SetContextThink("vc_setup_agents", function() G:SetupAgents() return nil end, 1)
  end
end

local function taken_heroes()
  local taken = {}
  for pid = 0, 23 do
    if PlayerResource:IsValidPlayerID(pid) then
      local name = PlayerResource:GetSelectedHeroName(pid)
      if name and name ~= "" then taken[name] = true end
    end
  end
  return taken
end

local function bots_on_team(team)
  local n = 0
  for pid = 0, 23 do
    if PlayerResource:IsValidPlayerID(pid) and PlayerResource:IsFakeClient(pid) and PlayerResource:GetTeam(pid) == team then
      n = n + 1
    end
  end
  return n
end

function G:AddBots()
  local taken, added, failed = taken_heroes(), 0, {}
  for _, team in ipairs({ DOTA_TEAM_GOODGUYS, DOTA_TEAM_BADGUYS }) do
    local need = 5 - bots_on_team(team)
    for _, hero in ipairs(G.BOT_HEROES[team]) do
      if need <= 0 then break end
      if not taken[hero] then
        if Tutorial:AddBot(hero, "", "unfair", team == DOTA_TEAM_GOODGUYS) then
          added, need, taken[hero] = added + 1, need - 1, true
        else
          failed[#failed + 1] = hero
        end
      end
    end
  end
  GameRules:GetGameModeEntity():SetBotThinkingEnabled(true)
  Tutorial:StartTutorialMode()
  log("агенты добавлены: %d%s", added, #failed > 0 and (", не вышло: " .. table.concat(failed, " ")) or "")
end

-- тренер без героя: его герой прячется у своей базы (Д10)
function G:OnSpawn(ev)
  local unit = EntIndexToHScript(ev.entindex)
  if unit == nil or not unit:IsRealHero() then return end
  local pid = unit:GetPlayerOwnerID()
  if pid == nil or pid < 0 or PlayerResource:IsFakeClient(pid) then return end
  G.commander_heroes = G.commander_heroes or {}
  if G.commander_heroes[pid] then return end
  G.commander_heroes[pid] = unit
  local team = PlayerResource:GetTeam(pid)
  unit:AddNewModifier(unit, nil, "modifier_voicecoach_commander", {})
  unit:AddNoDraw()
  if G.CORNER[team] then FindClearSpaceForUnit(unit, G.CORNER[team], true) end
  log("тренер %d (команда %d): герой спрятан", pid, team)
end

-- агенты команды: боты в порядке номеров игроков — позиции 1–5
function G:SetupAgents()
  local towers, fountains = World.init()
  G.teams = {}
  for _, team in ipairs({ DOTA_TEAM_GOODGUYS, DOTA_TEAM_BADGUYS }) do
    local T = { agents = {}, last = {}, status = {}, seq = 0, personas = {}, commanders = {} }
    for pid = 0, 23 do
      if PlayerResource:IsValidPlayerID(pid) and PlayerResource:GetTeam(pid) == team then
        local hero = PlayerResource:GetSelectedHeroEntity(pid)
        if PlayerResource:IsFakeClient(pid) then
          if hero and #T.agents < 5 then T.agents[#T.agents + 1] = hero end
        else
          T.commanders[#T.commanders + 1] = pid
        end
      end
    end
    T.intents = Intents.new(T.personas)
    World.agents[team] = T.agents
    G.teams[team] = T
  end
  G.ready = true
  log("карта: вышек %d, фонтаны %s; агентов: Свет %d, Тьма %d", towers, tostring(fountains),
    #G.teams[DOTA_TEAM_GOODGUYS].agents, #G.teams[DOTA_TEAM_BADGUYS].agents)
  for team in pairs(G.teams) do G:SendAgents(team) end
end

local ORDER = nil
local function order_type(kind)
  ORDER = ORDER or { move = DOTA_UNIT_ORDER_MOVE_TO_POSITION, attack_move = DOTA_UNIT_ORDER_ATTACK_MOVE,
                     attack = DOTA_UNIT_ORDER_ATTACK_TARGET, hold = DOTA_UNIT_ORDER_HOLD_POSITION }
  return ORDER[kind]
end

function G:Issue(hero, order)
  local t = { UnitIndex = hero:entindex(), OrderType = order_type(order.kind), Queue = false }
  if order.point then t.Position = order.point end
  if order.target then t.TargetIndex = order.target:entindex() end
  ExecuteOrderFromTable(t)
end

function G:Cast(hero, act)
  local t = { UnitIndex = hero:entindex(), AbilityIndex = act.ability:entindex(), Queue = false }
  if act.behavior == "target" then
    t.OrderType, t.TargetIndex = DOTA_UNIT_ORDER_CAST_TARGET, act.target:entindex()
  elseif act.behavior == "point" then
    t.OrderType, t.Position = DOTA_UNIT_ORDER_CAST_POSITION, act.point
  else
    t.OrderType = DOTA_UNIT_ORDER_CAST_NO_TARGET
  end
  ExecuteOrderFromTable(t)
end

function G:Think()
  if not G.ready then return G.THINK end
  local now = GameRules:GetGameTime()
  for team, T in pairs(G.teams) do
    for pos, hero in pairs(T.agents) do
      local ok, err = pcall(G.ThinkAgent, G, team, T, pos, hero, now)
      if not ok then log("ошибка агента %d: %s", pos, tostring(err)) end
    end
    if now >= (T.next_hud or 0) then
      T.next_hud = now + 1
      G:SendAgents(team)
    end
  end
  return G.THINK
end

function G:ThinkAgent(team, T, pos, hero, now)
  local ag = { pos = pos, hero = hero, team = team }
  for _, it in ipairs(Intents.pending_instant(T.intents, pos, now)) do
    local act = Agents.instant(it, ag, World)
    if act.kind == "cast" then
      G:Cast(hero, act)
    elseif act.kind == "buyback" then
      hero:Buyback()
    elseif act.kind == "move" then
      G:Issue(hero, { kind = "move", point = act.point })
    elseif act.kind == "skip" then
      G:Reply(T, pos, "refuse", refuse_text(act.reason, act.value))
    end
    Intents.done_instant(T.intents, pos, it.seq)
  end
  local it = Intents.current(T.intents, pos, now)
  local order = Agents.decide(it, ag, World)
  if order then
    T.status[pos] = order.why
  elseif it then
    T.status[pos] = "сам (" .. (Text.data.action_canon[it.action] or it.action) .. " пока не умею)"
  else
    T.status[pos] = "играет сам"
  end
  if Agents.should_issue(T.last[pos], order, now, World) then
    G:Issue(hero, order)
    order.t = now
    T.last[pos] = order
  elseif order == nil then
    T.last[pos] = nil
  end
end

-- --- приказы тренера ---

function G:TextCtx(team)
  local T = G.teams[team]
  local agents, enemies = {}, {}
  for pos, hero in pairs(T and T.agents or {}) do
    agents[#agents + 1] = { pos = pos, name = "", aliases = {}, hero = hero:GetUnitName() }
  end
  local other = team == DOTA_TEAM_GOODGUYS and DOTA_TEAM_BADGUYS or DOTA_TEAM_GOODGUYS
  for _, hero in pairs((G.teams[other] or {}).agents or {}) do enemies[#enemies + 1] = hero:GetUnitName() end
  return { team = team == DOTA_TEAM_GOODGUYS and "radiant" or "dire", agents = agents, enemy_heroes = enemies }
end

function G:AgentState(hero)
  local s = { alive = World.alive(hero), busy = 0 }
  local pid = hero:GetPlayerID()
  s.gold = PlayerResource:GetGold(pid)
  s.has_buyback = s.gold >= hero:GetBuybackCost()
  if not s.alive then s.respawn_left = hero:GetTimeUntilRespawn() end
  local ab = World.ult(hero)
  s.has_ult = ab ~= nil
  s.ult_cd = ab and ab:GetCooldownTimeRemaining() or 0
  return s
end

-- ответ агента (pos) или системы (pos = 0) тренерам команды: в HUD и, по желанию, в чат
function G:Reply(T, pos, kind, text)
  local hero = pos and pos > 0 and T.agents[pos] or nil
  local name = hero and hero:GetUnitName():gsub("npc_dota_hero_", "") or ""
  for _, pid in ipairs(T.commanders) do
    local player = PlayerResource:GetPlayer(pid)
    if player then
      CustomGameEventManager:Send_ServerToPlayer(player, "vc_reply", { pos = pos or 0, hero = name, kind = kind, text = text })
    end
  end
  if G.CHAT_REPLIES and hero and kind ~= "error" then Say(hero, text, true) end
  log("%s%s: %s", pos and pos > 0 and (tostring(pos) .. " ") or "", name, text)
end

function G:Command(pid, text)
  local team = PlayerResource:GetTeam(pid)
  local T = G.teams[team]
  if not T then
    local player = PlayerResource:GetPlayer(pid)
    if player then
      CustomGameEventManager:Send_ServerToPlayer(player, "vc_reply",
        { pos = 0, hero = "", kind = "error", text = "Агенты ещё не готовы — подождите начала игры" })
    end
    return
  end
  local r = Text.parse(text, G:TextCtx(team))
  if #r.errors > 0 then
    G:Reply(T, 0, "error", "Не понял: " .. r.errors[1])
    return
  end
  local now = GameRules:GetGameTime()
  for _, cmd in ipairs(r.commands) do
    T.seq = T.seq + 1
    cmd.seq = T.seq
    Intents.apply(T.intents, cmd, now)
    for _, pos in ipairs(cmd.agents) do
      local hero = T.agents[pos]
      if hero then
        if cmd.action == "report" then
          G:Reply(T, pos, "report", string.format("%s, %d%% здоровья, %d золота",
            T.status[pos] or "играет сам", hero:GetHealthPercent(), PlayerResource:GetGold(hero:GetPlayerID())))
        else
          local resp = Intents.respond(T.intents, pos, cmd, now, G:AgentState(hero))
          if resp.kind == "delay" then
            Intents.delay(T.intents, pos, cmd.seq, resp.delay, now)
            G:Reply(T, pos, "delay", refuse_text(resp.reason, resp.value))
          elseif resp.kind == "refuse" or resp.kind == "short" then
            G:Reply(T, pos, "refuse", refuse_text(resp.reason, resp.value))
          else
            G:Reply(T, pos, "ack", Voice.ack(T.personas[pos], cmd.action, cmd.seq))
          end
        end
      end
    end
  end
  G:SendAgents(team)
end

function G:OnHudCommand(ev)
  local pid = tonumber(ev.PlayerID) or -1
  if pid < 0 then return end
  G:Command(pid, tostring(ev.text or ""))
end

function G:OnChat(ev)
  local pid = tonumber(ev.playerid) or -1
  if pid < 0 or PlayerResource:IsFakeClient(pid) then return end
  local team = PlayerResource:GetTeam(pid)
  local text = tostring(ev.text or "")
  if Text.looks_like_command(text, G:TextCtx(team)) then G:Command(pid, text) end
end

-- состояние агентов для HUD тренера (раз в секунду и после приказа)
function G:SendAgents(team)
  local T = G.teams[team]
  if not T then return end
  local list = {}
  for pos = 1, 5 do
    local hero = T.agents[pos]
    if hero then
      list[#list + 1] = { pos = pos, hero = hero:GetUnitName():gsub("npc_dota_hero_", ""),
                          alive = World.alive(hero) and 1 or 0, hp = hero:GetHealthPercent(),
                          status = T.status[pos] or "играет сам" }
    end
  end
  CustomGameEventManager:Send_ServerToTeam(team, "vc_agents", { agents = list })
end

-- интерфейс загрузился (шлёт, пока не получит ответ: ранние события приходят с PlayerID = -1)
function G:OnReady(ev)
  local pid = tonumber(ev.PlayerID) or -1
  if pid < 0 then return end
  local player = PlayerResource:GetPlayer(pid)
  if player then CustomGameEventManager:Send_ServerToPlayer(player, "vc_ack", { camera = G.CAMERA_DISTANCE }) end
  local team = PlayerResource:GetTeam(pid)
  if G.teams[team] then G:SendAgents(team) end
end

return G
