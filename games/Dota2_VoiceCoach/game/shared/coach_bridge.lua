-- Мост «сервер тренера ↔ игра» для серверных скриптов Доты (vscripts).
--
-- Опрашивает сервер тренера (coach/voicecoach/server.py) по HTTP, забирает новые команды
-- своей и чужой команды, отдаёт состав матча (для разбора имён) и ответы агентов.
-- HTTP и время передаются снаружи, поэтому модуль проверяется вне игры (game/tests).
--
-- В Доте:
--   local Bridge = require("coach_bridge")
--   local b = Bridge.new({ base_url = "http://127.0.0.1:8787", room = "local",
--     http = Bridge.dota_http, now = function() return GameRules:GetGameTime() end,
--     json = require("json"), on_command = function(team, cmd) ... end })
--   GameRules:GetGameModeEntity():SetContextThink("coach_bridge", function()
--     Bridge.tick(b) return b.poll_interval end, 0)

local Bridge = {}

Bridge.TEAMS = { "radiant", "dire" }

-- HTTP через API Доты (CreateHTTPRequestScriptVM; поля ответа StatusCode и Body —
-- как в коде Open Hyper AI, FretBots/Chat.lua). Вне игры не вызывается.
function Bridge.dota_http(method, url, body, callback)
  local req = CreateHTTPRequestScriptVM(method, url)
  if req == nil then
    callback(0, nil)
    return
  end
  req:SetHTTPRequestAbsoluteTimeoutMS(5000)
  if body ~= nil then
    req:SetHTTPRequestRawPostBody("application/json", body)
  end
  req:Send(function(res)
    callback(res.StatusCode, res.Body)
  end)
end

function Bridge.new(opts)
  local b = {
    base_url = opts.base_url or "http://127.0.0.1:8787",
    room = opts.room or "local",
    teams = opts.teams or Bridge.TEAMS,
    http = assert(opts.http, "нужна функция http(method, url, body, callback)"),
    now = assert(opts.now, "нужна функция now()"),
    json = assert(opts.json, "нужна библиотека json"),
    on_command = opts.on_command or function() end,
    log = opts.log or function() end,
    poll_interval = opts.poll_interval or 0.25,
    last_seq = {},
    in_flight = {},
    fail_count = 0,
    next_try = 0,
    connected = false,
    received = 0,
    outbox = {},
  }
  for _, t in ipairs(b.teams) do
    b.last_seq[t] = 0
    b.outbox[t] = {}
  end
  return b
end

local function url(b, path, team, query)
  local u = b.base_url .. "/api/" .. b.room .. "/" .. path .. "?team=" .. team
  if query then u = u .. "&" .. query end
  return u
end

local function on_fail(b, why)
  -- несколько запросов одного опроса (две команды, события) — одна неудача, не три
  if b.now() < b.next_try then return end
  b.fail_count = b.fail_count + 1
  -- 0.5, 1, 2, 4 … но не реже раза в 10 с
  local delay = math.min(10, 0.5 * 2 ^ (b.fail_count - 1))
  b.next_try = b.now() + delay
  if b.connected or b.fail_count == 1 then
    b.log("[тренер] нет связи с сервером: " .. tostring(why))
  end
  b.connected = false
end

local function on_ok(b)
  if not b.connected then b.log("[тренер] связь с сервером есть") end
  b.connected = true
  b.fail_count = 0
end

local function poll_team(b, team)
  b.in_flight[team] = true
  b.http("GET", url(b, "commands", team, "after=" .. b.last_seq[team]), nil, function(code, body)
    b.in_flight[team] = nil
    if code ~= 200 or body == nil then
      on_fail(b, "HTTP " .. tostring(code))
      return
    end
    local ok, data = pcall(b.json.decode, body)
    if not ok or type(data) ~= "table" then
      on_fail(b, "плохой JSON")
      return
    end
    on_ok(b)
    for _, cmd in ipairs(data.commands or {}) do
      if type(cmd.seq) == "number" and cmd.seq > b.last_seq[team] then
        b.last_seq[team] = cmd.seq
        b.received = b.received + 1
        local okc, err = pcall(b.on_command, team, cmd)
        if not okc then b.log("[тренер] ошибка обработки команды: " .. tostring(err)) end
      end
    end
  end)
end

local function flush(b, team)
  local box = b.outbox[team]
  if #box == 0 then return end
  b.outbox[team] = {}
  local body = b.json.encode({ team = team, events = box })
  b.http("POST", url(b, "events", team), body, function(code)
    if code ~= 200 then on_fail(b, "events HTTP " .. tostring(code)) end
  end)
end

-- Вызывать по таймеру (каждые poll_interval секунд).
function Bridge.tick(b)
  if b.now() < b.next_try then return end
  for _, team in ipairs(b.teams) do
    if not b.in_flight[team] then poll_team(b, team) end
    flush(b, team)
  end
end

-- Состав матча для разбора речи: agents = {{pos=1, name="Miracle-", aliases={"миракл"}, hero="npc_dota_hero_invoker"}, ...}
function Bridge.push_state(b, team, agents, enemy_heroes)
  local body = b.json.encode({ team = team, agents = agents, enemy_heroes = enemy_heroes or {} })
  b.http("POST", url(b, "state", team), body, function(code)
    if code ~= 200 then on_fail(b, "state HTTP " .. tostring(code)) end
  end)
end

-- Ответ агента тренеру («иду», «нет маны», доклад). Уходит пачкой на следующем tick.
function Bridge.say(b, team, pos, kind, text)
  local box = b.outbox[team]
  if box then box[#box + 1] = { pos = pos, kind = kind, text = text } end
end

return Bridge
