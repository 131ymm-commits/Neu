-- Тренер для ботов Open Hyper AI (OHA) в лобби «Local Host». Работает внутри bot scripts.
--
-- Что делает:
--   * опрашивает сервер тренера (coach/voicecoach/server.py) на localhost через CreateRemoteHTTPRequest
--     (так ходит в сеть сам OHA: bots/ts_libs/utils/http_utils/http_req.lua);
--   * превращает команды в намерения (coach_intents.lua) и сдвигает желания режимов ботов:
--     в конец каждого mode_*_generic.lua установщик дописывает обёртку GetDesire → M.desire(...);
--   * мгновенные приказы: купить (в начало очереди покупок OHA), выкупиться;
--   * отвечает тренеру: в командный чат игры и на сервер (озвучка на странице тренера);
--   * понимает команды короткого формата прямо из командного чата игры («1 фарм лес. все рош»):
--     разбор — coach_text.lua, тот же, что на странице тренера (решение автора 07.10.2026: голос
--     отложен, команды текстом). Сервер для этого не нужен. Обычный чат не трогается.
--
-- Установка — game/prototype_oha/install.py; настройки — coach_config.lua (пишет установщик).
-- Всё, что зависит от API ботов, обёрнуто в pcall: ошибка тренера не должна ломать бота.

local DIR = GetScriptDirectory()
local Intents = require(DIR .. "/coach/coach_intents")
local Voice = require(DIR .. "/coach/coach_voice")
local json = require(DIR .. "/coach/json")
local okc, Config = pcall(require, DIR .. "/coach/coach_config")
if not okc or type(Config) ~= "table" then Config = {} end
local okt, Text = pcall(require, DIR .. "/coach/coach_text")
local okx, TextData = pcall(require, DIR .. "/coach/coach_text_data")
if okt and okx and type(Text) == "table" and type(TextData) == "table" then Text.init(TextData) else Text = nil end

local M = {}
M.base_url = Config.base_url or "http://127.0.0.1:8787"
M.room = Config.room or "local"
M.poll_interval = Config.poll_interval or 0.5
-- канал команд: "http" — опрос сервера; "file" — файл-ящик, который пишет сервер (--inbox);
-- "auto" — HTTP, а после 3 неудач подряд — файл (и раз в 10 с снова пробуем HTTP)
M.channel = Config.channel or "auto"
M.inbox_prefix = Config.inbox_prefix or "bots/coach/inbox_"
M.debug = Config.debug and true or false
M.chat_commands = (Config.chat_commands ~= false) and Text ~= nil   -- команды из чата игры
M.teams = M.teams or {}          -- состояние по командам (общее, если модуль общий для ботов)
M.bots = M.bots or {}            -- состояние по ботам (ключ — PlayerID)
M.chat_installed = M.chat_installed or {}

local function log(msg)
  if M.debug then print("[тренер] " .. tostring(msg)) end
end

-- ключевые события пишутся всегда: по ним в console.log видно, где рвётся цепочка
local function note(msg)
  print("[тренер] " .. tostring(msg))
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
          fail = 0, poller = nil, poller_seen = -1e9, state_sent = false,
          chat_last = 0, chat_seen = {}, chat_error = nil }
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
  local okn, uname = pcall(function() return bot:GetUnitName() end)
  note(string.format("бот %s: позиция %s, команда %s, канал %s", okn and uname or "?", tostring(pos),
    tostring(team_name(GetTeam())), M.channel))
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

local function apply_data(t, data)
  for _, cmd in ipairs(data.commands or {}) do
    if type(cmd.seq) == "number" and cmd.seq > t.last_seq then
      t.last_seq = cmd.seq
      Intents.apply(t.intents, cmd, clock())
      local who = {}
      for _, p in ipairs(cmd.agents or {}) do who[#who + 1] = tostring(p) end
      note(string.format("команда %s: %s → позиции %s", tostring(cmd.seq), tostring(cmd.action),
        table.concat(who, ",")))
    end
  end
end

-- файл-ящик (запасной канал): return { seq = N, commands = {...} }; так боты bota (2025)
-- читают свои bots/action_<team> — loadfile без расширения, на всякий случай пробуем и с ним
local function read_inbox(team)
  local name = M.inbox_prefix .. team_name(team)
  local okl, f = pcall(loadfile, name)
  if not okl or not f then okl, f = pcall(loadfile, name .. ".lua") end
  if not okl or not f then return nil end
  local ok, data = pcall(f)
  if ok and type(data) == "table" then return data end
  return nil
end

local function poll(team, now)
  local t = team_state(team)
  if now < t.next_poll then return end
  t.next_poll = now + M.poll_interval
  local use_file = M.channel == "file" or (M.channel == "auto" and t.fail >= 3)
  if use_file then
    local data = read_inbox(team)
    if data then
      if not t.file_ok then
        print("[тренер] читаю команды из файла " .. M.inbox_prefix .. team_name(team))
        t.file_ok = true
      end
      apply_data(t, data)
    end
    if M.channel == "file" then return end
  end
  if t.in_flight or now < (t.next_http or 0) then return end
  t.in_flight = true
  local url = M.base_url .. "/api/" .. M.room .. "/commands?team=" .. team_name(team) .. "&after=" .. t.last_seq
  http_get(url, function(body)
    t.in_flight = false
    local ok, data = false, nil
    if body then ok, data = pcall(json.decode, body) end
    if not ok or type(data) ~= "table" then
      t.fail = t.fail + 1
      local wait = math.min(10, 0.5 * 2 ^ (t.fail - 1))
      if M.channel == "auto" and t.fail >= 3 then wait = 10 end      -- файл уже работает
      t.next_http = clock() + wait
      if t.fail == 1 then print("[тренер] нет связи с сервером тренера " .. M.base_url) end
      return
    end
    if t.fail > 0 then print("[тренер] связь с сервером тренера есть") end
    t.fail = 0
    apply_data(t, data)
  end)
end

-- --- ответы тренеру ---

local function reply(bot, team, pos, kind, text)
  local b = M.bots[bot:GetPlayerID()]
  local now = clock()
  if b and now < b.next_say and kind == "ack" then return end
  if b then b.next_say = now + 2 end
  pcall(function() bot:ActionImmediate_Chat(text, false) end)
  note(string.format("ответ позиции %s: %s", tostring(pos), text))
  http_write("events", team, { team = team_name(team), events = { { pos = pos, kind = kind, text = text } } })
end

local function status_text(bot)
  local hp = math.floor(100 * bot:GetHealth() / math.max(1, bot:GetMaxHealth()))
  local mp = math.floor(100 * bot:GetMana() / math.max(1, bot:GetMaxMana()))
  if not bot:IsAlive() then return "Мёртв" end
  return string.format("Здоровье %d%%, мана %d%%, золото %d", hp, mp, bot:GetGold())
end

-- состояние бота для решения «принять / оговорить / отказать / отложить» (Intents.respond)
local function bot_state(bot, action, params)
  local s = { alive = bot:IsAlive(), gold = bot:GetGold() }
  pcall(function() s.has_buyback = bot:HasBuyback() end)
  pcall(function() s.busy = bot:GetActiveModeDesire() end)
  if action == "buy" and params and params.item then
    pcall(function() s.item_cost = GetItemCost(params.item) end)
  end
  if action == "use_ult" then
    pcall(function()
      s.has_ult = false
      for i = 0, 6 do
        local a = bot:GetAbilityInSlot(i)
        if a and a:IsUltimate() then
          s.has_ult = true
          s.ult_cd = a:GetCooldownTimeRemaining()
          break
        end
      end
    end)
  end
  return s
end

local function say_result(bot, team, pos, persona, it, r)
  if r.kind == "ack" then
    reply(bot, team, pos, "ack", Voice.ack(persona, it.action, it.seq))
  elseif r.kind == "short" then
    reply(bot, team, pos, "ack", Voice.refuse("short_gold", r.value))
  elseif r.kind == "delay" then
    reply(bot, team, pos, "delay", Voice.refuse("busy", r.value))
  else
    reply(bot, team, pos, "refuse", Voice.refuse(r.reason, r.value))
  end
end

-- новые намерения этого бота → ответ; мгновенные приказы → исполнение
local function handle_new(bot, team, pos, now)
  local t = team_state(team)
  local b = M.bots[bot:GetPlayerID()]
  local persona = t.intents.persona[pos]
  local it = Intents.current(t.intents, pos, now)
  if it and it.seq > b.seen_seq then
    b.seen_seq = it.seq
    local r = Intents.respond(t.intents, pos, it, now, bot_state(bot, it.action, it.params))
    if r.kind == "delay" then
      Intents.delay(t.intents, pos, it.seq, r.delay, now)
    end
    say_result(bot, team, pos, persona, it, r)
  end
  for _, ins in ipairs(Intents.pending_instant(t.intents, pos, now)) do
    if not b.done[ins.seq] then
      local r = Intents.respond(t.intents, pos, ins, now, bot_state(bot, ins.action, ins.params))
      if ins.action == "buy" then
        local item = ins.params and ins.params.item
        if item and bot.purchaseListInReverseOrder then
          table.insert(bot.purchaseListInReverseOrder, item)   -- верх стека покупок OHA
          say_result(bot, team, pos, persona, ins, r)
        else
          reply(bot, team, pos, "refuse", Voice.refuse("cant"))
        end
      elseif ins.action == "buyback" then
        if r.kind == "ack" then bot:ActionImmediate_Buyback() end
        say_result(bot, team, pos, persona, ins, r)
      elseif r.kind == "refuse" then
        say_result(bot, team, pos, persona, ins, r)          -- «ульта в откате»
      else
        -- ульта, предмет, тп — неделя 2 (ROADMAP): пока только подтверждаем
        reply(bot, team, pos, "ack", Voice.ack(persona, ins.action, ins.seq) .. " (пока не умею)")
      end
      b.done[ins.seq] = true
      Intents.done_instant(t.intents, pos, ins.seq)
    end
  end
  -- доклад приходит как команда report: отвечаем состоянием (по seq команды)
  if t.last_report_seq and t.last_report_seq > (b.report_seq or 0) and t.report_agents[pos] then
    b.report_seq = t.last_report_seq
    reply(bot, team, pos, "report", status_text(bot))
  end
end

-- главный вход: вызывается из обёрток режимов
-- --- команды из чата игры (короткий формат) ---

local function other_team(team)
  if team == TEAM_RADIANT then return TEAM_DIRE end
  return TEAM_RADIANT
end

local function hero_of(pid)
  local okh, h = pcall(GetSelectedHeroName, pid)
  if okh and type(h) == "string" and h ~= "" then return h end
  return nil
end

-- состав для разбора: имена из настроек (coach_config, по позициям); герой позиции — по роли бота,
-- если она уже известна (M.bots[pid].pos), иначе по слоту лобби
local function text_ctx(team)
  local personas = (Config.personas and Config.personas[team]) or {}
  local hero_by_pos = {}
  for slot, pid in ipairs(GetTeamPlayers(team) or {}) do
    local pos = (M.bots[pid] and M.bots[pid].pos) or slot
    hero_by_pos[pos] = hero_of(pid)
  end
  local agents = {}
  for pos = 1, 5 do
    local p = personas[pos] or {}
    agents[#agents + 1] = { pos = pos, name = p.name or "", aliases = p.aliases or {}, hero = hero_by_pos[pos] }
  end
  local enemies = {}
  for _, pid in ipairs(GetTeamPlayers(other_team(team)) or {}) do
    local h = hero_of(pid)
    if h then enemies[#enemies + 1] = h end
  end
  return { team = team_name(team), agents = agents, enemy_heroes = enemies }
end

local function is_bot_player(pid)
  local okb, isbot = pcall(IsPlayerBot, pid)
  return okb and isbot == true
end

-- отвечает на ошибки формата один бот команды: с наименьшим PlayerID среди ботов
local function is_spokesbot(bot, team)
  local best = nil
  for _, pid in ipairs(GetTeamPlayers(team) or {}) do
    if is_bot_player(pid) and (best == nil or pid < best) then best = pid end
  end
  return best == bot:GetPlayerID()
end

function M._on_chat(team, chat)
  if not M.chat_commands or type(chat) ~= "table" then return end
  local pid, text = chat.player_id, chat.string
  if type(text) ~= "string" or text == "" then return end
  if is_bot_player(pid) then return end                     -- боты не командуют
  local mine = false
  for _, p in ipairs(GetTeamPlayers(team) or {}) do
    if p == pid then mine = true end
  end
  if not mine then return end                               -- только человек своей команды
  local t = team_state(team)
  local key = tostring(pid) .. "|" .. text .. "|" .. tostring(math.floor(clock()))
  if t.chat_seen[key] then return end                       -- колбэк есть у каждого бота: разбор один раз
  t.chat_seen[key] = true
  local ctx = text_ctx(team)
  if not Text.looks_like_command(text, ctx) then return end -- обычный чат — молча
  local r = Text.parse(text, ctx)
  if #r.errors > 0 then
    t.chat_error = { text = "Не понял: " .. r.errors[1], said = false }
    note("чат: ошибка формата: " .. r.errors[1])
    return
  end
  for _, cmd in ipairs(r.commands) do
    cmd.seq = math.max(t.last_seq, t.chat_last or 0) + 0.001   -- между номерами команд сервера
    t.chat_last = cmd.seq
    Intents.apply(t.intents, cmd, clock())
    local who = {}
    for _, p in ipairs(cmd.agents or {}) do who[#who + 1] = tostring(p) end
    note(string.format("чат: %s → позиции %s", tostring(cmd.action), table.concat(who, ",")))
  end
end

local function chat_setup(bot, team)
  local id = bot:GetPlayerID()
  if not M.chat_commands or M.chat_installed[id] then return end
  M.chat_installed[id] = true
  local ok = pcall(InstallChatCallback, function(chat)
    local okc2, err = pcall(M._on_chat, team, chat)
    if not okc2 then note("чат: ошибка разбора: " .. tostring(err)) end
  end)
  note("чат: команды короткого формата " .. (ok and "включены" or "недоступны (нет InstallChatCallback)"))
end

local function chat_reply_error(bot, team)
  local t = team_state(team)
  if t.chat_error and not t.chat_error.said and is_spokesbot(bot, team) then
    t.chat_error.said = true
    pcall(function() bot:ActionImmediate_Chat(t.chat_error.text, false) end)
  end
end

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

  pcall(chat_setup, bot, team)
  pcall(chat_reply_error, bot, team)
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
