-- Тренер для ботов Open Hyper AI (OHA) в лобби «Local Host». Работает внутри bot scripts.
--
-- Что делает:
--   * опрашивает сервер тренера (coach/voicecoach/server.py) на localhost через CreateRemoteHTTPRequest
--     (так ходит в сеть сам OHA: bots/ts_libs/utils/http_utils/http_req.lua);
--   * превращает команды в намерения (coach_intents.lua) и сдвигает желания режимов ботов:
--     в конец каждого mode_*_generic.lua установщик дописывает обёртку GetDesire → M.desire(...);
--   * мгновенные приказы: купить (в начало очереди покупок OHA), выкупиться;
--   * отвечает тренеру: в командный чат игры и на сервер (озвучка на странице тренера).
--
-- Установка — game/prototype_oha/install.py; настройки — coach_config.lua (пишет установщик).
-- Всё, что зависит от API ботов, обёрнуто в pcall: ошибка тренера не должна ломать бота.

local DIR = GetScriptDirectory()
local Intents = require(DIR .. "/coach/coach_intents")
local json = require(DIR .. "/coach/json")
local okc, Config = pcall(require, DIR .. "/coach/coach_config")
if not okc or type(Config) ~= "table" then Config = {} end

local M = {}
M.base_url = Config.base_url or "http://127.0.0.1:8787"
M.room = Config.room or "local"
M.poll_interval = Config.poll_interval or 0.5
M.debug = Config.debug and true or false
M.teams = M.teams or {}          -- состояние по командам (общее, если модуль общий для ботов)
M.bots = M.bots or {}            -- состояние по ботам (ключ — PlayerID)

local function log(msg)
  if M.debug then print("[тренер] " .. tostring(msg)) end
end

local function clock()
  return GameTime()
end

local function team_name(team)
  if team == TEAM_RADIANT then return "radiant" end
  if team == TEAM_DIRE then return "dire" end
  return nil
end

local function team_state(team)
  local t = M.teams[team]
  if t == nil then
    local personas = (Config.personas and Config.personas[team]) or {}
    t = { intents = Intents.new(personas), last_seq = 0, next_poll = 0, in_flight = false,
          fail = 0, poller = nil, poller_seen = -1e9, state_sent = false }
    M.teams[team] = t
  end
  return t
end

-- позиция 1–5: роль OHA (FunLib/aba_role), иначе порядок слотов лобби (у OHA это одно и то же)
local function my_pos(bot)
  local id = bot:GetPlayerID()
  local b = M.bots[id]
  if b and b.pos then return b.pos end
  local pos = nil
  local okr, Role = pcall(require, DIR .. "/FunLib/aba_role")
  if okr and type(Role) == "table" and Role.GetPosition then
    local okp, p = pcall(Role.GetPosition, bot)
    if okp and type(p) == "number" and p >= 1 and p <= 5 then pos = p end
  end
  if pos == nil then
    for i, pid in ipairs(GetTeamPlayers(GetTeam())) do
      if pid == id then pos = i end
    end
  end
  M.bots[id] = M.bots[id] or { seen_seq = 0, next_say = 0, done = {} }
  M.bots[id].pos = pos
  return pos
end

-- --- HTTP ---

local function urlencode(s)
  return (string.gsub(s, "[^%w%-%._~]", function(c) return string.format("%%%02X", string.byte(c)) end))
end

local function http_get(url, cb)
  local okq, req = pcall(CreateRemoteHTTPRequest, url)
  if not okq or req == nil then
    cb(nil)
    return
  end
  req:Send(function(result)
    -- в API ботов ответ приходит строкой (так читает OHA); на всякий случай понимаем и таблицу
    if type(result) == "table" then
      cb(result.Body or result.body)
    else
      cb(result)
    end
  end)
end

-- запись через GET (?d=JSON): так же будет писать веб-панель кастомки, у неё нет POST
local function http_write(what, team, payload)
  local tn = team_name(team)
  if not tn then return end
  local url = M.base_url .. "/api/" .. M.room .. "/w/" .. what .. "?team=" .. tn .. "&d=" .. urlencode(json.encode(payload))
  http_get(url, function() end)
end

local function poll(team, now)
  local t = team_state(team)
  if t.in_flight or now < t.next_poll then return end
  t.in_flight = true
  t.next_poll = now + M.poll_interval
  local url = M.base_url .. "/api/" .. M.room .. "/commands?team=" .. team_name(team) .. "&after=" .. t.last_seq
  http_get(url, function(body)
    t.in_flight = false
    local ok, data = false, nil
    if body then ok, data = pcall(json.decode, body) end
    if not ok or type(data) ~= "table" then
      t.fail = t.fail + 1
      t.next_poll = clock() + math.min(10, 0.5 * 2 ^ (t.fail - 1))
      if t.fail == 1 then print("[тренер] нет связи с сервером тренера " .. M.base_url) end
      return
    end
    if t.fail > 0 then print("[тренер] связь с сервером тренера есть") end
    t.fail = 0
    for _, cmd in ipairs(data.commands or {}) do
      if type(cmd.seq) == "number" and cmd.seq > t.last_seq then
        t.last_seq = cmd.seq
        Intents.apply(t.intents, cmd, clock())
        log("команда " .. tostring(cmd.seq) .. " " .. tostring(cmd.action))
      end
    end
  end)
end

-- --- ответы тренеру ---

local SAY = {
  farm = "Фармлю", push = "Иду пушить", defend = "Иду защищать", gank = "Иду на ганг",
  group = "Иду к своим", roshan = "Иду на Рошана", tormentor = "Иду на Торментора",
  smoke = "Смок, иду", retreat = "Отхожу", focus = "Бью цель", engage = "Захожу",
  hold = "Жду", split = "Сплитую", ward = "Иду ставить вард", stack = "Стакну",
  follow = "Иду с тобой", move = "Иду", save = "Иду спасать", save_ult = "Держу ульту",
  buy = "Куплю", buyback = "Выкупаюсь", use_ult = "Ульту понял", use_item = "Понял",
  tp = "Тпшусь", free = "Играю сам", cancel = "Отбой",
}

local function reply(bot, team, pos, kind, text)
  local b = M.bots[bot:GetPlayerID()]
  local now = clock()
  if b and now < b.next_say and kind == "ack" then return end
  if b then b.next_say = now + 2 end
  pcall(function() bot:ActionImmediate_Chat(text, false) end)
  http_write("events", team, { team = team_name(team), events = { { pos = pos, kind = kind, text = text } } })
end

local function status_text(bot)
  local hp = math.floor(100 * bot:GetHealth() / math.max(1, bot:GetMaxHealth()))
  local mp = math.floor(100 * bot:GetMana() / math.max(1, bot:GetMaxMana()))
  if not bot:IsAlive() then return "Мёртв" end
  return string.format("Здоровье %d%%, мана %d%%, золото %d", hp, mp, bot:GetGold())
end

-- новые намерения этого бота → ответ; мгновенные приказы → исполнение
local function handle_new(bot, team, pos, now)
  local t = team_state(team)
  local b = M.bots[bot:GetPlayerID()]
  local it = Intents.current(t.intents, pos, now)
  if it and it.seq > b.seen_seq then
    b.seen_seq = it.seq
    if not bot:IsAlive() and it.action ~= "buyback" then
      reply(bot, team, pos, "refuse", "Я мёртв, приду после возрождения")
    else
      reply(bot, team, pos, "ack", SAY[it.action] or "Понял")
    end
  end
  for _, ins in ipairs(Intents.pending_instant(t.intents, pos, now)) do
    if not b.done[ins.seq] then
      if ins.action == "buy" then
        local item = ins.params and ins.params.item
        if item and bot.purchaseListInReverseOrder then
          table.insert(bot.purchaseListInReverseOrder, item)   -- верх стека покупок OHA
          reply(bot, team, pos, "ack", SAY.buy)
        else
          reply(bot, team, pos, "refuse", "Не могу купить")
        end
        b.done[ins.seq] = true
        Intents.done_instant(t.intents, pos, ins.seq)
      elseif ins.action == "buyback" then
        if not bot:IsAlive() and bot:HasBuyback() then
          bot:ActionImmediate_Buyback()
          reply(bot, team, pos, "ack", SAY.buyback)
        else
          reply(bot, team, pos, "refuse", bot:IsAlive() and "Я жив" or "Нет денег на байбэк")
        end
        b.done[ins.seq] = true
        Intents.done_instant(t.intents, pos, ins.seq)
      else
        -- ульта, предмет, тп — неделя 2 (ROADMAP); пока только подтверждаем
        reply(bot, team, pos, "ack", (SAY[ins.action] or "Понял") .. " (пока не умею)")
        b.done[ins.seq] = true
        Intents.done_instant(t.intents, pos, ins.seq)
      end
    end
  end
  -- доклад приходит как команда report: отвечаем состоянием (по seq команды)
  if t.last_report_seq and t.last_report_seq > (b.report_seq or 0) and t.report_agents[pos] then
    b.report_seq = t.last_report_seq
    reply(bot, team, pos, "report", status_text(bot))
  end
end

-- главный вход: вызывается из обёрток режимов
function M.desire(mode, base)
  local okb, bot = pcall(GetBot)
  if not okb or bot == nil then return base end
  local team = GetTeam()
  if team_name(team) == nil then return base end
  local pos = my_pos(bot)
  if pos == nil then return base end
  local t = team_state(team)
  local now = clock()

  -- опрашивает один бот команды (если модуль общий для ботов) или каждый сам (если нет)
  local id = bot:GetPlayerID()
  if t.poller == nil or now - t.poller_seen > 3 then t.poller = id end
  if t.poller == id then
    t.poller_seen = now
    poll(team, now)
    if not t.state_sent and t.fail == 0 and t.last_seq >= 0 then
      t.state_sent = true
      local agents = {}
      for i, pid in ipairs(GetTeamPlayers(team)) do
        local hero = GetSelectedHeroName and GetSelectedHeroName(pid) or nil
        agents[#agents + 1] = { pos = i, hero = hero }
      end
      http_write("state", team, { team = team_name(team), agents = agents })
    end
  end

  local okh, err = pcall(handle_new, bot, team, pos, now)
  if not okh then log("ошибка ответа: " .. tostring(err)) end

  local okd, d = pcall(Intents.desire, t.intents, pos, mode, base, now)
  if okd and type(d) == "number" then return d end
  return base
end

-- для тестов: отметить, что пришла команда «доклад»
function M._on_report(team, seq, agents)
  local t = team_state(team)
  t.last_report_seq = seq
  t.report_agents = {}
  for _, p in ipairs(agents or {}) do t.report_agents[p] = true end
end

-- доклад: Intents.apply его не хранит, поэтому перехватываем здесь
local apply_orig = Intents.apply
Intents.apply = function(st, cmd, now)
  if cmd.action == "report" then
    for team, t in pairs(M.teams) do
      if t.intents == st then M._on_report(team, cmd.seq or 0, cmd.agents) end
    end
  end
  return apply_orig(st, cmd, now)
end

return M
