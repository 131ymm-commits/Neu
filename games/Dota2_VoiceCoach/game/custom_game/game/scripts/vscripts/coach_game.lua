-- Кастомка «тренер доты» (решения автора Д9–Д11, 07.10.2026).
--
-- Стандартная карта Доты и её механики. В каждой команде 5 героев и тренер без героя (его герой спрятан у
-- базы). Каждого героя ведёт свой агент Claude (Д11): раз в секунду игра шлёт наблюдения героев на сервер
-- агентов на ПК тренера (coach_link.lua → coach/voicecoach/agents.py) и забирает их решения; исполнитель
-- (coach_exec.lua) выполняет решения рефлексами раз в 0.25 с. Встроенный ИИ ботов Доты выключен: боты —
-- только места в командах. Тренер командует текстом в коротком формате (поле внизу экрана или командный
-- чат): приказ уходит агентам адресатов, агенты отвечают своими словами. Нет связи с сервером агентов —
-- запасной исполнитель выполняет приказы тренера сам, без агентов, и HUD об этом пишет.
--
-- Модули рядом: coach_exec.lua (исполнитель), coach_obs.lua (наблюдение), coach_link.lua (связь),
-- coach_world.lua (карта через API Доты); общие — установщик кладёт их как vc_intents.lua, vc_text.lua,
-- vc_text_data.lua, vc_json.lua.

local Intents = require("vc_intents")
local Text = require("vc_text")
Text.init(require("vc_text_data"))
local JSON = require("vc_json")
local Exec = require("coach_exec")
local Obs = require("coach_obs")
local Link = require("coach_link")
local World = require("coach_world")

CoachGame = CoachGame or {}
local G = CoachGame

-- герои с поддержкой встроенных ботов Valve (по памяти; бот, которого не удалось добавить, — в журнале).
-- Встроенный ИИ выключен, но герои добавляются как боты: так у героя есть место в команде без человека.
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
G.THINK = 0.25                -- с: шаг исполнителя
G.TICK = 1.0                  -- с: обмен с сервером агентов
G.AGENTS_URL = "http://127.0.0.1:8787/api/local/tick"
G.FALLBACK_AFTER = 6          -- с без ответа сервера → запасной исполнитель
G.CAMERA_DISTANCE = 1600      -- дальше обычного (в Доте 1134): тренер смотрит сверху
G.CHAT_REPLIES = true         -- реплики агентов — и в командный чат
G.COACH_KEEP = 3              -- сколько последних приказов тренера видит агент
G.EVENTS_KEEP = 5
G.teams = G.teams or {}
G.ready = false
G.mode = "нет связи с сервером агентов"

local function log(fmt, ...)
  print("[ТРЕНЕР] " .. string.format(fmt, ...))
end

local function clock_text(clock)
  local c = math.floor(math.abs(clock) + 0.5)
  return string.format("%s%d:%02d", clock < 0 and "-" or "", math.floor(c / 60), c % 60)
end

function G:Init()
  GameRules:SetCustomGameTeamMaxPlayers(DOTA_TEAM_GOODGUYS, 6)     -- 5 героев + тренер
  GameRules:SetCustomGameTeamMaxPlayers(DOTA_TEAM_BADGUYS, 6)
  GameRules:EnableCustomGameSetupAutoLaunch(true)
  GameRules:SetCustomGameSetupAutoLaunchDelay(5)
  GameRules:SetHeroSelectionTime(20)
  GameRules:SetStrategyTime(5)
  GameRules:SetShowcaseTime(0)
  GameRules:SetPreGameTime(30)
  pcall(function() Convars:SetBool("dota_bot_mode", true) end)    -- так добавляет ботов Windy10v10AI (research/01)
  local gm = GameRules:GetGameModeEntity()
  gm:SetCameraDistanceOverride(G.CAMERA_DISTANCE)
  ListenToGameEvent("game_rules_state_change", Dynamic_Wrap(G, "OnState"), G)
  ListenToGameEvent("npc_spawned", Dynamic_Wrap(G, "OnSpawn"), G)
  ListenToGameEvent("player_chat", Dynamic_Wrap(G, "OnChat"), G)
  ListenToGameEvent("entity_killed", Dynamic_Wrap(G, "OnKilled"), G)
  CustomGameEventManager:RegisterListener("vc_command", function(_, ev) G:OnHudCommand(ev) end)
  CustomGameEventManager:RegisterListener("vc_ready", function(_, ev) G:OnReady(ev) end)
  LinkLuaModifier("modifier_voicecoach_commander", "modifiers/modifier_voicecoach_commander", LUA_MODIFIER_MOTION_NONE)
  G.link = Link.new({ url = G.AGENTS_URL, http = Link.dota_http, json = JSON,
                      now = function() return GameRules:GetGameTime() end,
                      log = function(s) log("%s", s) end, interval = G.TICK, stale = G.FALLBACK_AFTER })
  gm:SetContextThink("vc_coach_think", function() return G:Think() end, 1)
  log("кастомка загружена: героев ведут агенты Claude, сервер агентов %s", G.AGENTS_URL)
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
  GameRules:GetGameModeEntity():SetBotThinkingEnabled(false)       -- Д11: героев ведут агенты, не ИИ Доты
  Tutorial:StartTutorialMode()
  log("герои добавлены: %d%s; встроенный ИИ ботов выключен", added,
    #failed > 0 and (", не вышло: " .. table.concat(failed, " ")) or "")
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

-- герои команды: боты в порядке номеров игроков — позиции 1–5
function G:SetupAgents()
  local towers, fountains = World.init()
  G.teams = {}
  for _, team in ipairs({ DOTA_TEAM_GOODGUYS, DOTA_TEAM_BADGUYS }) do
    local T = { agents = {}, exec = {}, status = {}, seq = 0, commanders = {}, coach = {}, events = {},
                dec_seq = {}, said = {}, thinking = {} }
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
    for pos in pairs(T.agents) do
      T.exec[pos], T.coach[pos], T.events[pos], T.dec_seq[pos] = Exec.new(), {}, {}, 0
    end
    T.intents = Intents.new({})
    World.agents[team] = T.agents
    G.teams[team] = T
  end
  G.ready = true
  log("карта: вышек %d, фонтаны %s; героев: Свет %d, Тьма %d", towers, tostring(fountains),
    #G.teams[DOTA_TEAM_GOODGUYS].agents, #G.teams[DOTA_TEAM_BADGUYS].agents)
  for team in pairs(G.teams) do G:SendAgents(team) end
end

-- --- приказы героям ---

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

-- покупка у фонтана: предмет в инвентарь, золото списывается по цене магазина
function G:Buy(hero, name, cost)
  local item = hero:AddItemByName(name)
  if item == nil then
    log("не купил %s для %s", name, hero:GetUnitName())
    return
  end
  PlayerResource:SpendGold(hero:GetPlayerID(), cost, DOTA_ModifyGold_PurchaseItem)
end

function G:Apply(hero, a)
  if a.kind == "order" then
    G:Issue(hero, a.order)
  elseif a.kind == "cast" then
    G:Cast(hero, a)
  elseif a.kind == "level" then
    ExecuteOrderFromTable({ UnitIndex = hero:entindex(), OrderType = DOTA_UNIT_ORDER_TRAIN_ABILITY,
                            AbilityIndex = a.ability:entindex(), Queue = false })
  elseif a.kind == "buy" then
    G:Buy(hero, a.item, a.cost)
  elseif a.kind == "buyback" then
    hero:Buyback()
  end
end

-- --- цикл ---

function G:Think()
  if not G.ready then return G.THINK end
  local now = GameRules:GetGameTime()
  local linked = Link.alive(G.link)
  G:UpdateMode(linked)
  for team, T in pairs(G.teams) do
    for pos, hero in pairs(T.agents) do
      local ok, err = pcall(G.ThinkHero, G, team, T, pos, hero, now, linked)
      if not ok then log("ошибка героя %d: %s", pos, tostring(err)) end
    end
    if now >= (T.next_hud or 0) then
      T.next_hud = now + 1
      G:SendAgents(team)
    end
  end
  if now >= (G.next_tick or 0) then
    G.next_tick = now + G.TICK
    for team in pairs(G.teams) do World.update_seen(team, now) end
    Link.tick(G.link, function() return G:TickPayload(now) end, function(data) G:OnAgents(data) end)
  end
  return G.THINK
end

local function enemy_namer(team)
  return function(pos)
    local e = (World.agents[World.other(team)] or {})[pos]
    return e and World.short(e:GetUnitName()) or ""
  end
end

function G:ThinkHero(team, T, pos, hero, now, linked)
  local st = T.exec[pos]
  if linked then
    -- мгновенные приказы (ульт, тп, предмет) агент получил сообщением — запасному они не нужны
    for _, it in ipairs(Intents.pending_instant(T.intents, pos, now)) do Intents.done_instant(T.intents, pos, it.seq) end
  else
    G:Fallback(team, T, pos, now)
  end
  local acts = Exec.step(st, { team = team, pos = pos, hero = hero }, World, now)
  for _, a in ipairs(acts) do G:Apply(hero, a) end
  T.status[pos] = st.status
end

-- без связи с агентами: решение из приказа тренера (или «фарм своей линии»), без характера и без выбора
function G:Fallback(team, T, pos, now)
  local st = T.exec[pos]
  local names = enemy_namer(team)
  local it = Intents.current(T.intents, pos, now)
  local key = it and it.seq or 0
  if st.source ~= "fallback" or st.fb_key ~= key then
    Exec.set(st, Exec.from_intent(it, team, pos, names), now, "fallback")
    st.fb_key = key
  end
  for _, inst in ipairs(Intents.pending_instant(T.intents, pos, now)) do
    local add = Exec.from_instant(inst, names)
    if add == nil then
      G:Reply(T, pos, "refuse", "Без агента не умею: " .. (Text.data.action_canon[inst.action] or inst.action))
    else
      if add.buyback then st.buyback = true end
      for _, item in ipairs(add.buy or {}) do st.buy[#st.buy + 1] = item end
      for _, c in ipairs(add.cast or {}) do
        st.casts[#st.casts + 1] = { ability = c.ability, target = c.target, until_t = now + Exec.CAST_TTL }
      end
    end
    Intents.done_instant(T.intents, pos, inst.seq)
  end
end

-- --- сервер агентов ---

function G:CoachFor(T, pos, now)
  local out = {}
  for _, c in ipairs(T.coach[pos] or {}) do
    out[#out + 1] = { seq = c.seq, ago = math.floor(now - c.t + 0.5), text = c.text, urgent = c.urgent }
  end
  return out
end

function G:TickPayload(now)
  local clock = GameRules:GetDOTATime(false, true)
  local heroes, coached = {}, {}
  for team, T in pairs(G.teams) do
    if #T.commanders > 0 then coached[#coached + 1] = Obs.team_name(team) end
    for pos = 1, 5 do
      local hero = T.agents[pos]
      if hero then
        heroes[#heroes + 1] = Obs.build({ team = team, pos = pos, hero = hero }, World,
          { clock = clock, now = now, st = T.exec[pos], coach = G:CoachFor(T, pos, now), events = T.events[pos],
            statuses = T.status })
      end
    end
  end
  return { clock = math.floor(clock + 0.5), heroes = heroes, coached = coached }
end

local function team_of(name)
  if name == "radiant" then return DOTA_TEAM_GOODGUYS end
  if name == "dire" then return DOTA_TEAM_BADGUYS end
  return nil
end

-- ответ сервера: { decisions = { {team, pos, seq, decision}, … }, agents = { {team, pos, state}, … },
--                  backend = { radiant = "…", dire = "…" }, run = "номер запуска сервера" }
function G:OnAgents(data)
  G.backend = type(data.backend) == "table" and data.backend or {}
  local now = GameRules:GetGameTime()
  if data.run ~= nil and data.run ~= G.agents_run then          -- сервер перезапущен: его номера решений снова с 1
    if G.agents_run ~= nil then log("агенты: сервер перезапущен, жду новых решений") end
    G.agents_run = data.run
    for _, T in pairs(G.teams) do
      for pos in pairs(T.dec_seq) do T.dec_seq[pos] = 0 end
    end
  end
  for _, d in ipairs(data.decisions or {}) do
    local T = G.teams[team_of(d.team) or -1]
    local pos, seq = tonumber(d.pos), tonumber(d.seq) or 0
    if T and pos and T.exec[pos] and type(d.decision) == "table" and seq > T.dec_seq[pos] then
      T.dec_seq[pos] = seq
      Exec.set(T.exec[pos], d.decision, now, "agent")
      local say = d.decision.say
      if type(say) == "string" and say ~= "" and say ~= T.said[pos] then G:Reply(T, pos, "say", say) end
    end
  end
  for _, a in ipairs(data.agents or {}) do
    local T = G.teams[team_of(a.team) or -1]
    local pos = tonumber(a.pos)
    if T and pos then T.thinking[pos] = a.state end
  end
end

function G:UpdateMode(linked)
  local mode
  if linked then
    local parts = {}
    for _, name in ipairs({ "radiant", "dire" }) do
      local b = (G.backend or {})[name]
      if b then parts[#parts + 1] = (name == "radiant" and "Свет: " or "Тьма: ") .. tostring(b) end
    end
    mode = "агенты на связи" .. (#parts > 0 and (" (" .. table.concat(parts, ", ") .. ")") or "")
  else
    mode = "нет связи с сервером агентов — героев ведёт запасной исполнитель по приказам тренера"
  end
  if mode ~= G.mode then
    G.mode = mode
    log("%s", mode)
  end
end

-- события для агентов: убийства, вышки, Рошан
local function push_event(T, pos, text)
  local list = T.events[pos]
  if not list then return end
  list[#list + 1] = text
  while #list > G.EVENTS_KEEP do table.remove(list, 1) end
end

function G:OnKilled(ev)
  if not G.ready then return end
  local killed = EntIndexToHScript(ev.entindex_killed)
  if killed == nil then return end
  local killer = ev.entindex_attacker and EntIndexToHScript(ev.entindex_attacker) or nil
  local stamp = clock_text(GameRules:GetDOTATime(false, true))
  local kname = World.short(killed:GetUnitName())
  local by = killer and World.short(killer:GetUnitName()) or "?"
  for team, T in pairs(G.teams) do
    for pos, hero in pairs(T.agents) do
      local text = nil
      if killed:IsRealHero() then
        if hero == killed then text = "тебя убил " .. by
        elseif hero == killer then text = "ты убил " .. kname
        elseif killed:GetTeamNumber() == team then text = "у нас погиб " .. kname
        else text = "у них погиб " .. kname end
      elseif killed:IsTower() then
        text = (killed:GetTeamNumber() == team and "снесли нашу вышку " or "снесли их вышку ") .. kname
      elseif kname == "npc_dota_roshan" then
        text = "убит Рошан" .. (killer and (" (" .. by .. ")") or "")
      end
      if text then push_event(T, pos, stamp .. " " .. text) end
    end
  end
end

-- --- приказы тренера ---

function G:TextCtx(team)
  local T = G.teams[team]
  local agents, enemies = {}, {}
  for pos, hero in pairs(T and T.agents or {}) do
    agents[#agents + 1] = { pos = pos, name = "", aliases = {}, hero = hero:GetUnitName() }
  end
  for _, hero in pairs((G.teams[World.other(team)] or {}).agents or {}) do enemies[#enemies + 1] = hero:GetUnitName() end
  return { team = team == DOTA_TEAM_GOODGUYS and "radiant" or "dire", agents = agents, enemy_heroes = enemies }
end

-- ответ агента (pos) или системы (pos = 0) тренерам команды: в HUD и, для реплик агентов, в чат
function G:Reply(T, pos, kind, text)
  local hero = pos and pos > 0 and T.agents[pos] or nil
  local name = hero and World.short(hero:GetUnitName()) or ""
  if hero and kind == "say" then T.said[pos] = text end
  for _, pid in ipairs(T.commanders) do
    local player = PlayerResource:GetPlayer(pid)
    if player then
      CustomGameEventManager:Send_ServerToPlayer(player, "vc_reply", { pos = pos or 0, hero = name, kind = kind, text = text })
    end
  end
  if G.CHAT_REPLIES and hero and (kind == "say" or kind == "report" or kind == "refuse") then Say(hero, text, true) end
  log("%s%s: %s", pos and pos > 0 and (tostring(pos) .. " ") or "", name, text)
end

function G:Command(pid, text)
  local team = PlayerResource:GetTeam(pid)
  local T = G.teams[team]
  if not T then
    local player = PlayerResource:GetPlayer(pid)
    if player then
      CustomGameEventManager:Send_ServerToPlayer(player, "vc_reply",
        { pos = 0, hero = "", kind = "error", text = "Герои ещё не готовы — подождите начала игры" })
    end
    return
  end
  local r = Text.parse(text, G:TextCtx(team))
  if #r.errors > 0 then
    G:Reply(T, 0, "error", "Не понял: " .. r.errors[1])
    return
  end
  local now = GameRules:GetGameTime()
  local linked = Link.alive(G.link)
  for _, cmd in ipairs(r.commands) do
    T.seq = T.seq + 1
    cmd.seq = T.seq
    Intents.apply(T.intents, cmd, now)
    local who = {}
    for _, pos in ipairs(cmd.agents) do
      local hero = T.agents[pos]
      if hero then
        who[#who + 1] = tostring(pos)
        local list = T.coach[pos]
        list[#list + 1] = { seq = cmd.seq, t = now, text = cmd.text, urgent = cmd.urgent and true or false }
        while #list > G.COACH_KEEP do table.remove(list, 1) end
        if cmd.action == "report" then
          G:Reply(T, pos, "report", string.format("%s, %d%% здоровья, %d золота", T.status[pos] or "ждёт",
            hero:GetHealthPercent(), PlayerResource:GetGold(hero:GetPlayerID())))
        end
      end
    end
    if #who > 0 and cmd.action ~= "report" then
      G:Reply(T, 0, "order", "→ " .. table.concat(who, "") .. ": " .. tostring(cmd.text)
        .. (linked and "" or " (агентов нет на связи — выполняет запасной исполнитель)"))
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

-- состояние героев для HUD тренера (раз в секунду и после приказа)
function G:SendAgents(team)
  local T = G.teams[team]
  if not T then return end
  local list = {}
  for pos = 1, 5 do
    local hero = T.agents[pos]
    if hero then
      local st = T.exec[pos]
      list[#list + 1] = { pos = pos, hero = World.short(hero:GetUnitName()),
                          alive = World.alive(hero) and 1 or 0, hp = hero:GetHealthPercent(),
                          status = T.status[pos] or st.status, source = st.source or "",
                          agent = T.thinking[pos] or "", said = T.said[pos] or "" }
    end
  end
  CustomGameEventManager:Send_ServerToTeam(team, "vc_agents", { agents = list, mode = G.mode })
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
