-- Короткий текстовый формат команд тренера — разбор на Lua (команды в чате игры).
-- Чистый Lua 5.1 / LuaJIT: работает и в скриптах ботов, и в vscripts кастомки.
--
-- Та же логика и те же сообщения об ошибках, что coach/voicecoach/textcmd.py; словарь —
-- coach_text_data.lua (собирается из Python: python -m voicecoach.textcmd --lua …).
-- Общие примеры для обеих версий — coach/data/text_cases.json (game/tests/test_coach_text.py).
--
--   local T = require("coach_text")          -- или dofile; словарь: T.init(require("coach_text_data"))
--   local r = T.parse("1 фарм лес. 23 ганг мид", ctx)
--   r.commands = { {action="farm", agents={1}, params={area="jungle_own"}, urgent=false, after_prev=false}, … }
--   r.errors   = { "«…»: не понял «…»" }       -- непусто → commands пуст (строка целиком или ничего)
-- ctx = { team = "radiant"|"dire", agents = { {pos=1, name="Петя", aliases={"петя"}, hero="npc_dota_hero_juggernaut"}, … },
--         enemy_heroes = { "npc_dota_hero_mars", … } }

local T = {}
local D = nil

function T.init(data)
  D = data
  T.data = data
  return T
end

-- --- UTF-8 ---------------------------------------------------------------------
local LOWER = {}
for b = 0x90, 0x9F do LOWER[string.char(0xD0, b)] = string.char(0xD0, b + 0x20) end   -- А..П → а..п
for b = 0xA0, 0xAF do LOWER[string.char(0xD0, b)] = string.char(0xD1, b - 0x20) end   -- Р..Я → р..я
LOWER["\208\129"] = "\208\181"     -- Ё → е
LOWER["\209\145"] = "\208\181"     -- ё → е

function T.lower(s)
  s = s:gsub("[\208\209][\128-\191]", function(ch) return LOWER[ch] end)
  return (s:lower())
end

local function chars(s)
  local out = {}
  for ch in s:gmatch("[%z\1-\127\194-\244][\128-\191]*") do out[#out + 1] = ch end
  return out
end

local function ulen(s) return #chars(s) end

local VOWEL_END = {}
for ch in ("аяоеиыуюь"):gmatch("[%z\1-\127\194-\244][\128-\191]*") do VOWEL_END[ch] = true end

local function split_words(s)
  local out = {}
  for w in s:gmatch("%S+") do out[#out + 1] = w end
  return out
end

local function set_of(list)
  local s = {}
  for _, v in ipairs(list or {}) do s[v] = true end
  return s
end

local function is_positions_word(w)
  return w:match("^[1-5][1-5,]*$") ~= nil and not w:find(",,", 1, true) and w:sub(-1) ~= ","
end

-- --- нормализация ----------------------------------------------------------------
function T.normalize(text)
  local t = T.lower(text)
  t = t:gsub("\209\130%s*%-?%s*([1-4])", "\209\130%1")      -- «т-2», «т 2» → «т2»
  t = t:gsub("t%s*%-?%s*([1-4])", "\209\130%1")              -- латинская t
  t = t:gsub("!", " ! "):gsub("%?", " ? ")
  local n
  repeat t, n = t:gsub("(%d)%s*,%s*(%d)", "%1\001%2") until n == 0   -- «1,2» — список позиций
  local out = {}
  for part in t:gmatch("[^.;,\n]+") do
    part = part:gsub("\194\171", " "):gsub("\194\187", " "):gsub('[%"%(%)%[%]{}:]', " "):gsub("\001", ",")
    local words = split_words(part)
    if #words > 0 then out[#out + 1] = words end
  end
  return out
end

local function join_multi(words)
  local out, i = {}, 1
  while i <= #words do
    local hit = nil
    for _, m in ipairs(D.multi) do
      local mw = split_words(m)
      local ok = true
      for k = 1, #mw do
        if words[i + k - 1] ~= mw[k] then ok = false; break end
      end
      if ok then hit = { m, #mw }; break end
    end
    if hit then
      out[#out + 1] = hit[1]
      i = i + hit[2]
    else
      out[#out + 1] = words[i]
      i = i + 1
    end
  end
  return out
end

-- --- контекст матча --------------------------------------------------------------
local function make_ctx(ctx)
  local c = { team = ctx.team or "radiant", names = {}, own_heroes = {}, enemies = set_of(ctx.enemy_heroes) }
  for _, a in ipairs(ctx.agents or {}) do
    local list = {}
    for _, n in ipairs(a.aliases or {}) do list[#list + 1] = n end
    if a.name and a.name ~= "" then list[#list + 1] = a.name end
    for _, n in ipairs(list) do
      n = T.lower(n):gsub("^%s+", ""):gsub("%s+$", "")
      if n ~= "" then c.names[n] = a.pos end
    end
    if a.hero then c.own_heroes[a.hero] = a.pos end
  end
  -- порядок обхода имён для падежей — как в Python (порядок вставки)
  c.name_list = {}
  for _, a in ipairs(ctx.agents or {}) do
    local list = {}
    for _, n in ipairs(a.aliases or {}) do list[#list + 1] = n end
    if a.name and a.name ~= "" then list[#list + 1] = a.name end
    for _, n in ipairs(list) do
      n = T.lower(n):gsub("^%s+", ""):gsub("%s+$", "")
      if n ~= "" then c.name_list[#c.name_list + 1] = n end
    end
  end
  return c
end

local function agent_by_word(c, w)
  if c.names[w] then return c.names[w] end
  local wch = chars(w)
  for _, n in ipairs(c.name_list) do
    local nch = chars(n)
    local stem_len = #nch
    if VOWEL_END[nch[#nch]] and #nch > 3 then stem_len = #nch - 1 end
    if stem_len >= 3 and #wch - stem_len <= 2 and #wch >= stem_len then
      local same = true
      for k = 1, stem_len do
        if wch[k] ~= nch[k] then same = false; break end
      end
      if same then return c.names[n] end
    end
  end
  return nil
end

local function positions(words, start, c)
  local out, n = {}, 0
  for i = start, #words do
    local w = words[i]
    if is_positions_word(w) then
      for d in w:gmatch("%d") do out[#out + 1] = tonumber(d) end
    elseif D.addr_role[w] then
      for _, p in ipairs(D.addr_role[w]) do out[#out + 1] = p end
    elseif not D.action_words[w] and w ~= "не" and agent_by_word(c, w) then
      out[#out + 1] = agent_by_word(c, w)
    elseif D.heroes[w] and c.own_heroes[D.heroes[w]] and not D.action_words[w] then
      out[#out + 1] = c.own_heroes[D.heroes[w]]
    else
      break
    end
    n = n + 1
  end
  local seen, uniq = {}, {}
  for _, p in ipairs(out) do
    if not seen[p] then seen[p] = true; uniq[#uniq + 1] = p end
  end
  table.sort(uniq)
  return uniq, n
end

local ADDR_ALL = nil

local function addressee(words, c)
  if #words == 0 then return nil, 0, nil end
  local w = words[1]
  local head, ex = w:match("^(.-)%-([1-5,]+)$")
  if head and (head == "все" or head == "0") then
    local exs = {}
    for d in ex:gmatch("%d") do exs[tonumber(d)] = true end
    local out = {}
    for p = 1, 5 do if not exs[p] then out[#out + 1] = p end end
    return out, 1, nil
  end
  if ADDR_ALL[w] then
    if #words >= 3 and words[2] == "кроме" then
      local exl, n = positions(words, 3, c)
      if #exl == 0 then return nil, 2, "кроме кого? после «кроме» — номер или имя" end
      local exs = set_of(exl)
      local out = {}
      for p = 1, 5 do if not exs[p] then out[#out + 1] = p end end
      return out, 2 + n, nil
    end
    return { 1, 2, 3, 4, 5 }, 1, nil
  end
  local pos, n = positions(words, 1, c)
  if #pos > 0 then return pos, n, nil end
  return nil, 0, nil
end

local function rel_to_abs(rel, team)
  if team == "dire" then return rel == "safe" and "top" or "bot" end
  return rel == "safe" and "bot" or "top"
end

local function where_canon(kind, val)
  return D.where_canon[kind .. "/" .. tostring(val)] or tostring(val)
end

-- параметр → слово формата для сообщения об ошибке (как _param_word в Python)
local function param_word(k, v)
  if k == "tier" then return "т" .. tostring(v) end
  if k == "enemy" then return D.hero_canon[v] or tostring(v) end
  if k == "item" then return D.item_canon[v] or tostring(v) end
  if k == "lane" or k == "place" or k == "area" then return where_canon(k, v) end
  return tostring(v)
end

-- порядок проверки параметров — как порядок их появления в Python-словаре params
local PARAM_ORDER = { ["then"] = 1, tier = 2, enemy_pos = 3, kind = 4, item = 5, ally = 6, enemy = 7,
                      area = 8, lane = 9, place = 10, what = 11 }

local function slice(words, from)
  local out = {}
  for i = from, #words do out[#out + 1] = words[i] end
  return out
end

local function one(words, c)
  words = join_multi(words)
  local urgent, after = false, false
  if words[1] and set_of(D.after_words)[words[1]] then
    after = true
    words = slice(words, 2)
  end
  local urgent_set = set_of(D.urgent_words)
  local kept = {}
  for _, w in ipairs(words) do
    if urgent_set[w] then urgent = true else kept[#kept + 1] = w end
  end
  words = kept
  local agents, n, err = addressee(words, c)
  if err then return nil, err end
  local rest = slice(words, n + 1)
  local neg = false
  if rest[1] == "не" then
    neg = true
    rest = slice(rest, 2)
  end
  if #rest == 0 then return nil, "нет действия (фарм, пуш, рош, назад, …)" end
  local action = D.action_words[rest[1]]
  if not action then
    local hint = ""
    if D.where_words[rest[1]] and rest[2] and D.action_words[rest[2]] then
      hint = " — место пишется после действия: «" .. rest[2] .. " " .. rest[1] .. "»"
    elseif D.where_words[rest[1]] then
      hint = " — место пишется после действия, например «" .. D.action_canon.move .. " " .. rest[1] .. "»"
    end
    return nil, "не понял «" .. rest[1] .. "» на месте действия" .. hint
  end
  local spec = D.actions[action]
  local allowed = set_of(spec.params)
  local params, where = {}, {}
  local filler = (action == "save_ult") and { ["ульт"] = true, ["ульту"] = true } or {}
  for i = 2, #rest do
    local w = rest[i]
    if filler[w] then
      -- «держи ульт»
    elseif action == "smoke" and w == "ганг" then
      params["then"] = "gank"
    elseif D.where_words[w] then
      where[#where + 1] = D.where_words[w]
    elseif D.tier_words[w] then
      params.tier = D.tier_words[w]
    elseif D.enemy_pos_words[w] then
      params.enemy_pos = D.enemy_pos_words[w]
    elseif w == "сентри" and action == "ward" then
      params.kind = "sentry"
    elseif (action == "buy" or action == "use_item") and D.items[w] then
      params.item = D.items[w]
    elseif (action == "save" or action == "follow") and w:match("^[1-5]$") then
      params.ally = tonumber(w)
    elseif (action == "save" or action == "follow") and agent_by_word(c, w) then
      params.ally = agent_by_word(c, w)
    elseif D.heroes[w] then
      local hero = D.heroes[w]
      if action == "save" or action == "follow" then
        if not c.own_heroes[hero] then return nil, "«" .. w .. "» — не наш герой" end
        params.ally = c.own_heroes[hero]
      elseif c.own_heroes[hero] and not c.enemies[hero] then
        return nil, "«" .. w .. "» — наш герой, а не цель"
      else
        params.enemy = hero
      end
    else
      return nil, "не понял «" .. w .. "»"
    end
  end
  for _, kv in ipairs(where) do
    local kind, val = kv[1], kv[2]
    if kind == "rel" then kind, val = "lane", rel_to_abs(val, c.team) end
    if action == "farm" then
      if kind == "lane" then params.area, params.lane = "lane", val
      elseif kind == "area" then params.area = val
      else return nil, "фармить можно линию, лес, их лес или древних" end
    elseif kind == "lane" then
      params.lane = val
    elseif kind == "area" then
      if val == "lane" then return nil, "«линия» — только для фарма" end
      if not allowed.place then
        return nil, "«" .. where_canon(kind, val) .. "» не подходит к «" .. (D.action_canon[action] or action) .. "»"
      end
      params.place = val
    else
      params.place = val
    end
  end
  if action == "farm" and params.area == nil then params.area = "auto" end
  if (action == "push" or action == "defend" or action == "split") and params.lane == nil and params.place == nil then
    params.lane = "auto"
  end
  if action == "stack" and params.place ~= nil and params.place ~= "ancients" then
    return nil, "стакать — только лагеря или древних"
  end
  if neg then
    params = { what = action }
    action, spec = "hold", D.actions.hold
    allowed = set_of(spec.params)
  end
  if agents == nil then
    if spec.scope == "team" then
      agents = { 1, 2, 3, 4, 5 }
    else
      return nil, "кому? начните с номера (1–5), имени или «все»"
    end
  end
  local need = D.personal_needs[action]
  if need == "item" and params.item == nil then return nil, D.needs_text.item end
  if need == "ally" and params.ally == nil then return nil, D.needs_text.ally end
  if need == "where" and params.lane == nil and params.place == nil then return nil, D.needs_text.where end
  if need == "target" and params.enemy == nil and params.enemy_pos == nil then return nil, D.needs_text.target end
  local keys = {}
  for k in pairs(params) do keys[#keys + 1] = k end
  table.sort(keys, function(a, b) return (PARAM_ORDER[a] or 99) < (PARAM_ORDER[b] or 99) end)
  for _, k in ipairs(keys) do
    if not allowed[k] then
      return nil, "«" .. param_word(k, params[k]) .. "» не подходит к «" .. (D.action_canon[action] or action) .. "»"
    end
  end
  return { action = action, agents = agents, params = params, urgent = urgent, after_prev = after,
           text = table.concat(words, " ") }, nil
end

function T.parse(text, ctx)
  assert(D, "coach_text: сначала T.init(словарь)")
  ADDR_ALL = set_of(D.addr_all)
  local c = make_ctx(ctx or {})
  local res = { text = text, commands = {}, errors = {} }
  local parts, pending = {}, nil
  for _, words in ipairs(T.normalize(text)) do
    local agents, n = addressee(words, c)
    if agents ~= nil and n == #words then          -- «дима, фарм лес»: обращение отдельно
      pending = words
    else
      if pending then
        local merged = {}
        for _, w in ipairs(pending) do merged[#merged + 1] = w end
        for _, w in ipairs(words) do merged[#merged + 1] = w end
        words = merged
        pending = nil
      end
      parts[#parts + 1] = words
    end
  end
  if pending then parts[#parts + 1] = pending end
  for _, words in ipairs(parts) do
    local cmd, err = one(words, c)
    if err then
      res.errors[#res.errors + 1] = "«" .. table.concat(words, " ") .. "»: " .. err
    elseif cmd then
      res.commands[#res.commands + 1] = cmd
    end
  end
  if #res.errors > 0 then res.commands = {} end
  return res
end

-- строка похожа на команду тренера (а не на обычный чат)? — для ботов: на «обычный» чат не отвечать
function T.looks_like_command(text, ctx)
  assert(D, "coach_text: сначала T.init(словарь)")
  ADDR_ALL = set_of(D.addr_all)
  local parts = T.normalize(text)
  if #parts == 0 then return false end
  local words = parts[1]
  local c = make_ctx(ctx or {})
  local _, n = addressee(words, c)
  local first = words[n + 1]
  if first == "не" then first = words[n + 2] end
  if first and set_of(D.after_words)[first] then return true end
  return n > 0 or (first ~= nil and D.action_words[first] ~= nil)
end

return T
