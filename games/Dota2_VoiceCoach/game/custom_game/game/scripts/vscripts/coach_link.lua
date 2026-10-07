-- Связь игры с сервером агентов Claude (coach/voicecoach/agents.py, путь POST /api/{room}/tick).
--
-- Раз в interval секунд игра отправляет наблюдения всех героев и получает последние решения агентов.
-- Запрос всегда один в полёте; при ошибке — пауза 1, 2, 4 … но не больше 10 с. HTTP, JSON и время
-- передаются снаружи, поэтому модуль проверяется вне игры (game/tests/test_custom_game.py).

local L = {}

-- HTTP через API Доты (CreateHTTPRequestScriptVM; поля ответа StatusCode и Body — как в коде Open Hyper AI,
-- FretBots/Chat.lua, и в game/shared/coach_bridge.lua). Вне игры не вызывается.
function L.dota_http(method, url, body, callback)
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

function L.new(opts)
  return {
    url = assert(opts.url, "нужен url"),
    http = assert(opts.http, "нужна функция http(method, url, body, callback)"),
    json = assert(opts.json, "нужна библиотека json"),
    now = assert(opts.now, "нужна функция now()"),
    log = opts.log or function() end,
    interval = opts.interval or 1.0,
    stale = opts.stale or 6,          -- с без ответа — связи нет
    lost = opts.lost or 10,           -- с без ответа на запрос — считаем его потерянным
    in_flight = false, sent_at = 0, next_try = 0, fails = 0, last_ok = nil, connected = false,
    sent = 0, ok = 0,
  }
end

function L.alive(k)
  return k.last_ok ~= nil and k.now() - k.last_ok <= k.stale
end

local function fail(k, t, why)
  k.fails = k.fails + 1
  k.next_try = t + math.min(10, k.interval * 2 ^ math.min(k.fails - 1, 4))
  if k.connected or k.fails == 1 then k.log("агенты: нет связи с сервером (" .. tostring(why) .. ")") end
  k.connected = false
end

-- build() → таблица запроса; on_reply(data) — ответ сервера. Возвращает true, если запрос ушёл.
function L.tick(k, build, on_reply)
  local now = k.now()
  if k.in_flight and now - k.sent_at > k.lost then
    k.in_flight = false
    fail(k, now, "ответ не пришёл за " .. k.lost .. " с")
  end
  if k.in_flight or now < k.next_try then return false end
  local okb, body = pcall(function() return k.json.encode(build()) end)
  if not okb then
    k.log("агенты: не собрал наблюдение: " .. tostring(body))
    k.next_try = now + k.interval
    return false
  end
  k.in_flight, k.sent_at, k.sent = true, now, k.sent + 1
  k.http("POST", k.url, body, function(code, resp)
    k.in_flight = false
    local t = k.now()
    if code ~= 200 or resp == nil then return fail(k, t, "HTTP " .. tostring(code)) end
    local okd, data = pcall(k.json.decode, resp)
    if not okd or type(data) ~= "table" then return fail(k, t, "плохой JSON") end
    if not k.connected then k.log("агенты: связь с сервером есть") end
    k.connected, k.fails, k.last_ok, k.next_try, k.ok = true, 0, t, t + k.interval, k.ok + 1
    local okr, err = pcall(on_reply, data)
    if not okr then k.log("агенты: ошибка в ответе сервера: " .. tostring(err)) end
  end)
  return true
end

return L
