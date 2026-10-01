--[[ Витрина Magnetics (FINAL_SPEC §6.3): поверхность "magnetics-showroom", на ней по одной каждой из 26 построек
и рядом — её ванильная основа, с энергией, боеприпасами, топливом и показательными рецептами.
Headless: только расстановка (тест G3 в cells/static.lua). В графическом клиенте, если есть игрок, делаются снимки
в script-output/magnetics/showroom*.png (общий план и крупный план каждой пары).

Использование:  local showroom = require("showroom")
                local r = showroom.build{player_index = <номер или nil>, force = <сила или имя; по умолчанию "player">,
                                         enable_recipes = <true по умолчанию: показательные рецепты открываются для силы>,
                                         teleport = <true: перенести игрока player_index на витрину>}
Если силы с таким именем нет, она создаётся (тест G3 строит на отдельной силе, чтобы не трогать силу player других ячеек).
Возвращает {surface = имя, placed = {{name, base, unit_ok, base_ok, x, y}}, count = число построек Magnetics,
            base_count = число ванильных, errors = {строки}, screenshots = число}.
Повторный вызов очищает участок и строит заново. Сетка: пары по 12 клеток (постройка Magnetics и в 6 клетках
справа ванильная основа), ряды через 9 клеток; подстанции между рядами. ]]
local M = {}

M.SURFACE = "magnetics-showroom"
M.COLS = 4                -- пар в ряду
M.DX = 6                  -- шаг сетки по x (постройка Magnetics и ванильная основа — соседние узлы)
M.DY = 9                  -- шаг рядов (генераторы 3×5 + подстанции между рядами)

-- {постройка Magnetics, ванильная основа (FINAL_SPEC §4, столбец «type ← base»)}
M.PAIRS = {
  { "magnetics-sintering-kiln", "stone-furnace" },
  { "magnetics-induction-furnace", "electric-furnace" },
  { "magnetics-coil-winder", "assembling-machine-2" },
  { "magnetics-cryo-chamber", "chemical-plant" },
  { "magnetics-flux-resonator", "centrifuge" },
  { "magnetics-magnetic-separator", "assembling-machine-3" },
  { "magnetics-magnetic-drill", "electric-mining-drill" },
  { "magnetics-maglev-transport-belt", "express-transport-belt" },
  { "magnetics-maglev-underground-belt", "express-underground-belt" },
  { "magnetics-maglev-splitter", "express-splitter" },
  { "magnetics-coil-capacitor", "accumulator" },
  { "magnetics-superconducting-accumulator", "accumulator" },
  { "magnetics-superconducting-pylon", "big-electric-pole" },
  { "magnetics-mhd-generator", "burner-generator" },
  { "magnetics-flux-dynamo", "burner-generator" },
  { "magnetics-geomagnetic-coil", "solar-panel" },
  { "magnetics-ferrite-wall", "stone-wall" },
  { "magnetics-magnet-wall", "stone-wall" },
  { "magnetics-superconducting-wall", "stone-wall" },
  { "magnetics-magnet-gate", "gate" },
  { "magnetics-superconducting-gate", "gate" },
  { "magnetics-mend-coil", "electric-energy-interface" },
  { "magnetics-coilgun-turret", "gun-turret" },
  { "magnetics-gauss-turret", "gun-turret" },
  { "magnetics-arc-emitter", "laser-turret" },
  { "magnetics-rail-cannon", "gun-turret" },
}

-- Показательная начинка: рецепт, предметы на вход, жидкость на вход, топливо, боеприпасы.
M.DEMO = {
  ["magnetics-sintering-kiln"] = { fuel = { "coal", 10 }, input = { { "iron-ore", 20 }, { "stone", 20 } } },
  ["stone-furnace"] = { fuel = { "coal", 10 }, input = { { "iron-ore", 20 } } },
  ["magnetics-induction-furnace"] = { recipe = "magnetics-magnet-alloy",
    input = { { "steel-plate", 10 }, { "magnetics-ferrite", 20 }, { "copper-plate", 10 } } },
  ["electric-furnace"] = { input = { { "iron-ore", 20 } } },
  ["magnetics-coil-winder"] = { recipe = "magnetics-coil", input = { { "magnetics-ferrite", 10 }, { "copper-cable", 40 } } },
  ["assembling-machine-2"] = { recipe = "iron-gear-wheel", input = { { "iron-plate", 40 } } },
  ["magnetics-cryo-chamber"] = { recipe = "magnetics-liquid-nitrogen" },
  ["chemical-plant"] = { recipe = "magnetics-ferrofluid", input = { { "magnetics-ferrite", 10 } }, fluid = "light-oil" },
  ["magnetics-flux-resonator"] = { input = { { "magnetics-flux-crystal-uncharged", 5 } } },
  ["centrifuge"] = { recipe = "uranium-processing", input = { { "uranium-ore", 20 } } },
  ["magnetics-magnetic-separator"] = { recipe = "magnetics-stone-separation", input = { { "stone", 40 } }, fluid = "magnetics-ferrofluid" },
  ["assembling-machine-3"] = { recipe = "iron-gear-wheel", input = { { "iron-plate", 40 } } },
  ["magnetics-mhd-generator"] = { fuel = { "coal", 20 } },
  ["magnetics-flux-dynamo"] = { fuel = { "magnetics-flux-crystal", 5 } },
  ["burner-generator"] = { fuel = { "coal", 20 } },
  ["magnetics-coilgun-turret"] = { ammo = { "magnetics-ferrite-slug", 10 } },
  ["magnetics-gauss-turret"] = { ammo = { "magnetics-gauss-slug", 10 } },
  ["magnetics-rail-cannon"] = { ammo = { "magnetics-rail-slug", 5 } },
  ["gun-turret"] = { ammo = { "firearm-magazine", 10 } },
}

local ORE_UNDER = { ["magnetics-magnetic-drill"] = true, ["electric-mining-drill"] = true }

-- Центр постройки в узле (cx, cy) с учётом чётности размеров (как у create_entity со snap_to_grid).
local function center(proto, cx, cy)
  local w, h = proto.tile_width, proto.tile_height
  return { x = cx + ((w % 2 == 1) and 0.5 or 0), y = cy + ((h % 2 == 1) and 0.5 or 0) }
end

local function surface()
  local S = game.surfaces[M.SURFACE]
  if not S then
    S = game.create_surface(M.SURFACE, { width = 256, height = 256, peaceful_mode = true, no_enemies_mode = true })
    S.generate_with_lab_tiles = true
    S.always_day = true
    S.request_to_generate_chunks({ 0, 0 }, 3)
    S.force_generate_chunk_requests()
  end
  return S
end

local function add_error(r, msg) r.errors[#r.errors + 1] = msg end

-- Начинка одной постройки; ошибки не прерывают расстановку, а записываются.
local function furnish(r, e)
  local d = M.DEMO[e.name]
  if not d then return end
  local function try(what, f)
    local ok, err = pcall(f)
    if not ok then add_error(r, e.name .. ": " .. what .. ": " .. tostring(err)) end
  end
  if d.recipe then try("recipe " .. d.recipe, function() e.set_recipe(d.recipe) end) end
  if d.fuel then
    try("fuel", function()
      local inv = e.get_inventory(defines.inventory.fuel)
      if not inv then error("нет топливного инвентаря") end
      inv.insert { name = d.fuel[1], count = d.fuel[2] }
    end)
  end
  if d.ammo then
    try("ammo", function()
      local inv = e.get_inventory(defines.inventory.turret_ammo)
      if not inv then error("нет инвентаря боеприпасов") end
      inv.insert { name = d.ammo[1], count = d.ammo[2] }
    end)
  end
  if d.input then
    try("input", function()
      local inv = e.get_inventory(defines.inventory.crafter_input)
      if not inv then error("нет входного инвентаря") end
      for _, it in ipairs(d.input) do inv.insert { name = it[1], count = it[2] } end
    end)
  end
  if d.fluid then
    try("fluid " .. d.fluid, function()
      local fb = e.fluidbox
      local filled = false
      for i = 1, #fb do
        local p = fb.get_prototype(i)   -- LuaFluidBoxPrototype или массив из них; индекс [1] у объекта API — ошибка
        local proto = (type(p) == "table") and p[1] or p
        local f = fb.get_filter(i)
        if proto.production_type == "input" and f and f.name == d.fluid then
          fb[i] = { name = d.fluid, amount = proto.volume }
          filled = true
        end
      end
      if not filled then error("нет входного бака для " .. d.fluid) end
    end)
  end
end

-- Снимки: только если есть игрок (headless их не делает — FINAL_SPEC §6.3, §10.4).
local function screenshots(r, S, player_index, bounds)
  local player = player_index and game.get_player(player_index)
  if not player then
    for _, p in pairs(game.connected_players) do player = p; break end
  end
  if not player then return 0 end
  local n = 0
  local cx = (bounds.x1 + bounds.x2) / 2
  local cy = (bounds.y1 + bounds.y2) / 2
  local ok, err = pcall(game.take_screenshot, { player = player, surface = S, position = { cx, cy },
    resolution = { 2560, 2560 }, zoom = 1, path = "magnetics/showroom.png", show_entity_info = true, daytime = 0 })
  if ok then n = n + 1 else add_error(r, "screenshot: " .. tostring(err)) end
  for i, rec in ipairs(r.placed) do
    local ok2, err2 = pcall(game.take_screenshot, { player = player, surface = S, position = { rec.x + M.DX / 2, rec.y },
      resolution = { 1024, 768 }, zoom = 2, path = string.format("magnetics/showroom-%02d-%s.png", i, rec.name),
      show_entity_info = true, daytime = 0 })
    if ok2 then n = n + 1 else add_error(r, "screenshot " .. rec.name .. ": " .. tostring(err2)) end
  end
  return n
end

function M.build(opts)
  opts = opts or {}
  local r = { surface = M.SURFACE, placed = {}, count = 0, base_count = 0, errors = {}, screenshots = 0 }
  local S = surface()
  local force = opts.force or "player"
  if type(force) == "string" and not game.forces[force] then game.create_force(force) end
  local force_obj = type(force) == "string" and game.forces[force] or force
  if opts.enable_recipes ~= false then
    local recipes = { "magnetics-ferrite", "magnetics-flux-crystal-charging" }
    for _, d in pairs(M.DEMO) do if d.recipe then recipes[#recipes + 1] = d.recipe end end
    for _, rn in ipairs(recipes) do
      local rec = force_obj.recipes[rn]
      if rec then rec.enabled = true else add_error(r, "нет рецепта " .. rn) end
    end
  end
  local rows = math.ceil(#M.PAIRS / M.COLS)
  local x0, y0 = -math.floor(M.COLS * M.DX), -math.floor(rows * M.DY / 2)
  local bounds = { x1 = x0 - 8, y1 = y0 - 8, x2 = x0 + M.COLS * 2 * M.DX + 8, y2 = y0 + rows * M.DY + 8 }

  -- очистить участок (повторный вызов)
  for _, e in pairs(S.find_entities_filtered { area = { { bounds.x1, bounds.y1 }, { bounds.x2, bounds.y2 } } }) do
    if e.valid and e.type ~= "character" then e.destroy() end
  end

  -- энергия: тестовый источник primary-output (есть в стенде), иначе ванильный EEI
  local src_name = prototypes.entity["magnetics-test-source"] and "magnetics-test-source" or "electric-energy-interface"
  local src = S.create_entity { name = src_name, position = { bounds.x1 + 2, bounds.y1 + 2 }, force = force }
  if src then
    src.power_production = 1e9 / 60
    src.electric_buffer_size = 1e9 / 60 * 2
  else
    add_error(r, "не создан источник энергии " .. src_name)
  end
  S.create_entity { name = "substation", position = { bounds.x1 + 5, bounds.y1 + 2 }, force = force }

  for i, pair in ipairs(M.PAIRS) do
    local k = i - 1
    local col, row = k % M.COLS, math.floor(k / M.COLS)
    local gx = x0 + col * 2 * M.DX
    local gy = y0 + row * M.DY
    local rec = { name = pair[1], base = pair[2], unit_ok = false, base_ok = false }
    for j, name in ipairs(pair) do
      local proto = prototypes.entity[name]
      if not proto then
        add_error(r, "нет прототипа " .. name)
      else
        local pos = center(proto, gx + (j - 1) * M.DX, gy)
        if ORE_UNDER[name] then
          for ox = -2, 2 do
            for oy = -2, 2 do
              S.create_entity { name = "iron-ore", position = { pos.x + ox, pos.y + oy }, amount = 100000 }
            end
          end
        end
        local params = { name = name, position = pos, force = force, create_build_effect_smoke = false }
        if proto.type == "underground-belt" then params.type = "input" end
        local ok, e = pcall(S.create_entity, params)
        if not ok then
          add_error(r, name .. ": create_entity: " .. tostring(e))
        elseif not (e and e.valid) then
          add_error(r, name .. ": create_entity вернул nil")
        else
          if name == "electric-energy-interface" then e.power_production = 0; e.power_usage = 0 end
          furnish(r, e)
          if j == 1 then
            rec.unit_ok = true; rec.x = pos.x; rec.y = pos.y; rec.entity = e
            r.count = r.count + 1
          else
            rec.base_ok = true; rec.base_entity = e
            r.base_count = r.base_count + 1
          end
        end
      end
    end
    r.placed[#r.placed + 1] = rec
    -- подстанция между парами, в промежутке между рядами: покрывает эту пару и следующий ряд
    S.create_entity { name = "substation", position = { gx + M.DX / 2, gy + math.floor(M.DY / 2) + 1 }, force = force }
  end
  -- подстанция над первым рядом, чтобы сеть дошла до источника энергии
  for col = 0, M.COLS - 1 do
    S.create_entity { name = "substation", position = { x0 + col * 2 * M.DX + M.DX / 2, y0 - 5 }, force = force }
  end

  r.screenshots = screenshots(r, S, opts.player_index, bounds)
  local player = opts.teleport and opts.player_index and game.get_player(opts.player_index)
  if player then player.teleport({ 0, bounds.y1 + 4 }, S) end
  return r
end

return M
