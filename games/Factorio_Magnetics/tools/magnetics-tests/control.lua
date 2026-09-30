--[[ Стенд автотестов Magnetics (только для headless-сервера, в игру не ставить).
Ячейки — модули cells/<группа>.lua, каждый возвращает список тестов:
  { id = "P1", configs = {"base","sa"} | nil (все), slots = 1,
    init  = function(ctx) end | nil,       -- в on_init (при --create), состояние — в ctx.state (storage)
    setup = function(ctx) end | nil,       -- на тике 1 бенчмарка
    tick  = function(ctx, t) end | nil,    -- каждый тик после setup (t — тиков от setup)
    check_at = <тиков после setup>, check = function(ctx) end }   -- проверки пишут L.eq/L.check
ctx: S (поверхность-лаборатория), origin {x,y} (левый верх участка 128×128), state (таблица в storage),
     L (lib.lua), sa (Space Age включён?), cfg ("base"/"bq"/"be"/"sa"), id.
Какие модули грузить — cells/_select.lua (пишет tools/run.py), по умолчанию все из cells/_all.lua.
Результат: script-output/magnetics-results.json ]]
local L = require("lib")
local ok_sel, SEL = pcall(require, "cells._select")
if not ok_sel then SEL = require("cells._all") end

local function cfg_name()
  local m = script.active_mods
  if m["space-age"] then return "sa" end
  if m["quality"] and m["elevated-rails"] then return "bqe" end
  if m["quality"] then return "bq" end
  if m["elevated-rails"] then return "be" end
  return "base"
end

local CELLS = {}
do
  local cfg = cfg_name()
  for _, modname in ipairs(SEL) do
    local ok, list = pcall(require, "cells." .. modname)
    if not ok then
      CELLS[#CELLS + 1] = { id = "LOAD:" .. modname, load_error = tostring(list) }
    else
      for _, c in ipairs(list) do
        local want = true
        if c.configs then
          want = false
          for _, x in ipairs(c.configs) do if x == cfg or (x == "bq" and (cfg == "bq" or cfg == "bqe" or cfg == "sa")) then want = true end end
        end
        if want then c.module = modname; CELLS[#CELLS + 1] = c end
      end
    end
  end
end

local function ctx_for(i, c)
  storage.cells = storage.cells or {}
  storage.cells[c.id] = storage.cells[c.id] or {}
  return { S = game.surfaces["magnetics-lab"], origin = storage.origins[c.id], state = storage.cells[c.id], L = L,
           sa = script.active_mods["space-age"] ~= nil, cfg = cfg_name(), id = c.id }
end

local function guarded(c, what, f, ...)
  local ok, err = pcall(f, ...)
  if not ok then
    L.check(c.module or "?", c.id .. ":" .. what, false, nil, nil, "ошибка Lua: " .. tostring(err))
    storage.broken = storage.broken or {}
    storage.broken[c.id] = true
  end
  return ok
end

script.on_init(function()
  L.lab(22)
  storage.origins = {}
  local slot = 0
  for i, c in ipairs(CELLS) do
    storage.origins[c.id] = L.slot(slot)
    slot = slot + (c.slots or 1)
  end
  storage.init_errors = {}
  for i, c in ipairs(CELLS) do
    if c.init then
      local ok, err = pcall(c.init, ctx_for(i, c))
      if not ok then storage.init_errors[#storage.init_errors + 1] = { id = c.id, err = tostring(err) } end
    end
  end
end)

local finish_tick = 1
script.on_event(defines.events.on_tick, function(e)
  local t = e.tick
  if not storage.started then
    storage.started = t
    for _, ie in ipairs(storage.init_errors or {}) do
      L.check("init", ie.id .. ":init", false, nil, nil, "ошибка Lua в init: " .. ie.err)
    end
    for i, c in ipairs(CELLS) do
      if c.load_error then
        L.check("load", c.id, false, nil, nil, c.load_error)
      elseif c.setup then
        guarded(c, "setup", c.setup, ctx_for(i, c))
      end
      if c.check_at and c.check_at + 1 > finish_tick then finish_tick = c.check_at + 1 end
    end
    storage.finish = storage.started + finish_tick
    return
  end
  local rel = t - storage.started
  for i, c in ipairs(CELLS) do
    if not (storage.broken and storage.broken[c.id]) and not c.load_error then
      if c.tick and rel <= (c.check_at or 0) then guarded(c, "tick", c.tick, ctx_for(i, c), rel) end
      if c.check and rel == c.check_at then guarded(c, "check", c.check, ctx_for(i, c)) end
    end
  end
  if t == storage.finish then
    L.write("magnetics-results.json")
    helpers.write_file("magnetics-done.txt", "done at tick " .. t, false)
  end
end)
