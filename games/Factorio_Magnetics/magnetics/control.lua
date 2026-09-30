-- Magnetics: ремонтная катушка (magnetics-mend-coil), FINAL_SPEC §6.1. Единственный скрипт времени игры в моде.
--
-- Катушка чинит стены, ворота, турели и радары своей силы в радиусе RADIUS, по TARGET_CAP HP на цель за цикл
-- (без сложения нескольких катушек) и не больше COIL_BUDGET HP на катушку за цикл; каждый HP стоит J_PER_HP джоулей
-- из буфера самой катушки (EEI secondary-input, 1 МДж, вход 200 кВт).
--
-- Устройство (всё состояние в storage, решения только по массивам, без pairs по хеш-ключам и без math.random):
--   storage.coils.list    массив записей катушек {entity, unit, surface, x, y, force, budget, budget_tick, seq};
--   storage.coils.index   unit_number -> номер записи в list;
--   storage.grid          [surface_index]["cx,cy"] -> массив unit_number катушек в клетке CELL×CELL (порядок вставки);
--   storage.force_coils   [force_index] -> число катушек силы;
--   storage.queue         массив {entity, unit} повреждённых целей;  storage.queued  unit -> true;
--   storage.cursor        позиция обхода очереди, когда в ней больше QUEUE_CAP записей;
--   storage.seq           счётчик порядка вставки катушек ("первая по порядку вставки" = наименьший seq).
-- Обработчик on_entity_damaged зарегистрирован только пока есть хоть одна катушка; on_load повторяет это решение
-- по storage (регистрация — чистая функция storage, как требует детерминизм мультиплеера).
--
-- Фильтр урона (PILOT-24): в фильтрах событий "and" связывает сильнее "or" (runtime-api.json,
-- LuaEntityDamagedEventFilter.mode), поэтому условие final-health > 0 стоит в паре с КАЖДЫМ типом:
-- (wall and fh>0) or (gate and fh>0) or ... Запись "типы через or, затем один fh>0 с and" относила бы условие
-- только к последнему типу (radar); пилот 30.09.2026 это подтвердил (см. tools/magnetics-tests/mend_tests.lua).

local COIL = "magnetics-mend-coil"
local RADIUS = 10                -- клеток, евклидово расстояние от позиции катушки до позиции цели
local RADIUS_SQ = RADIUS * RADIUS
local PERIOD = 30                -- тиков на цикл лечения
local TARGET_CAP = 5             -- HP на цель за цикл (10 HP/с), без сложения катушек
local COIL_BUDGET = 10           -- HP на катушку за цикл (20 HP/с)
local J_PER_HP = 5000            -- Дж на 1 HP (100 кВт при полном бюджете)
local QUEUE_CAP = 100            -- записей очереди за цикл
local CELL = 32                  -- клетка пространственной сетки (>= 2 * RADIUS)
local LINES_PER_CYCLE = 10       -- линий-лучей за цикл, не больше
local LINE_COLOR = {0.4, 1, 0.6, 0.8}
local LINE_WIDTH = 2
local LINE_TTL = 20
local HEAL_TYPES = {"wall", "gate", "ammo-turret", "electric-turret", "fluid-turret", "artillery-turret", "radar"}

local floor = math.floor

-- Фильтр on_entity_damaged: (тип and итоговое здоровье > 0) для каждого типа.
local DAMAGE_FILTER = {}
for i = 1, #HEAL_TYPES do
  DAMAGE_FILTER[#DAMAGE_FILTER + 1] = {filter = "type", type = HEAL_TYPES[i]}
  DAMAGE_FILTER[#DAMAGE_FILTER + 1] = {filter = "final-health", comparison = ">", value = 0, mode = "and"}
end

local COIL_FILTER = {{filter = "name", name = COIL}}

---------------------------------------------------------------------------------------------------------------------
-- Состояние

local function fresh_state()
  storage.coils = {list = {}, index = {}}
  storage.grid = {}
  storage.force_coils = {}
  storage.queue = {}
  storage.queued = {}
  storage.cursor = 1
  storage.seq = 0
end

local function cell_key(x, y)
  return floor(x / CELL) .. "," .. floor(y / CELL)
end

---------------------------------------------------------------------------------------------------------------------
-- Очередь повреждённых целей

local function on_damaged(event)
  if event.final_health <= 0 then return end          -- страховка; фильтр уже отсёк смертельный урон
  local entity = event.entity
  if not storage.force_coils[entity.force_index] then return end
  local unit = entity.unit_number
  if not unit then return end
  local queued = storage.queued
  if queued[unit] then return end
  queued[unit] = true
  local queue = storage.queue
  queue[#queue + 1] = {entity = entity, unit = unit}
end

-- Поставить в очередь найденную поиском цель, если она повреждена.
local function enqueue_if_damaged(entity)
  local unit = entity.unit_number
  if not unit or storage.queued[unit] then return end
  local health = entity.health
  if not health or health <= 0 or health >= entity.max_health then return end
  storage.queued[unit] = true
  local queue = storage.queue
  queue[#queue + 1] = {entity = entity, unit = unit}
end

---------------------------------------------------------------------------------------------------------------------
-- Условная регистрация on_entity_damaged: зарегистрирован тогда и только тогда, когда список катушек не пуст.

local damage_registered = false   -- зеркало (#storage.coils.list > 0) в этом Lua-состоянии; не решение, а кэш

local function update_registration()
  local want = storage.coils ~= nil and #storage.coils.list > 0
  if want == damage_registered then return end
  if want then
    script.on_event(defines.events.on_entity_damaged, on_damaged, DAMAGE_FILTER)
  else
    script.on_event(defines.events.on_entity_damaged, nil)
  end
  damage_registered = want
end

---------------------------------------------------------------------------------------------------------------------
-- Катушки: добавление и удаление

local function add_coil(entity)
  if not (entity and entity.valid and entity.name == COIL) then return end
  local unit = entity.unit_number
  if not unit then return end
  local coils = storage.coils
  if coils.index[unit] then return end                  -- уже учтена (повторное событие)

  local position = entity.position
  local surface_index = entity.surface_index
  local force_index = entity.force_index
  storage.seq = storage.seq + 1
  local list = coils.list
  list[#list + 1] = {
    entity = entity, unit = unit, surface = surface_index, x = position.x, y = position.y, force = force_index,
    budget = COIL_BUDGET, budget_tick = -1, seq = storage.seq,
  }
  coils.index[unit] = #list

  local grid = storage.grid[surface_index]
  if not grid then grid = {}; storage.grid[surface_index] = grid end
  local key = cell_key(position.x, position.y)
  local cell = grid[key]
  if not cell then cell = {}; grid[key] = cell end
  cell[#cell + 1] = unit

  storage.force_coils[force_index] = (storage.force_coils[force_index] or 0) + 1
  script.register_on_object_destroyed(entity)
  update_registration()

  -- Разовый поиск: цели, повреждённые до появления катушки.
  local found = entity.surface.find_entities_filtered{position = position, radius = RADIUS, force = entity.force, type = HEAL_TYPES}
  for i = 1, #found do enqueue_if_damaged(found[i]) end
end

local function remove_coil(unit)
  local coils = storage.coils
  local slot = coils.index[unit]
  if not slot then return end
  local list = coils.list
  local rec = list[slot]
  local last = #list
  if slot ~= last then
    local moved = list[last]
    list[slot] = moved
    coils.index[moved.unit] = slot
  end
  list[last] = nil
  coils.index[unit] = nil

  local grid = storage.grid[rec.surface]
  if grid then
    local key = cell_key(rec.x, rec.y)
    local cell = grid[key]
    if cell then
      for i = 1, #cell do
        if cell[i] == unit then table.remove(cell, i); break end   -- клетки малы; порядок вставки сохраняется
      end
      if #cell == 0 then grid[key] = nil end
    end
  end

  local count = (storage.force_coils[rec.force] or 1) - 1
  storage.force_coils[rec.force] = count > 0 and count or nil
  update_registration()
end

-- Полная перестройка: поверхности по возрастанию index, катушки на поверхности по возрастанию unit_number
-- (номера выдаются по порядку постройки, так что порядок вставки после перестройки совпадает с порядком постройки).
local function rebuild()
  fresh_state()
  update_registration()
  local surfaces = {}
  for _, surface in pairs(game.surfaces) do surfaces[#surfaces + 1] = surface end
  table.sort(surfaces, function(a, b) return a.index < b.index end)
  for s = 1, #surfaces do
    local found = surfaces[s].find_entities_filtered{name = COIL}
    local keyed = {}
    for i = 1, #found do keyed[i] = {unit = found[i].unit_number or 0, entity = found[i]} end
    table.sort(keyed, function(a, b) return a.unit < b.unit end)
    for i = 1, #keyed do add_coil(keyed[i].entity) end
  end
end

-- После слияния сил индексы сил в записях устарели: обновить их и пересчитать force_coils (обход массива).
local function refresh_forces()
  local counts = {}
  local list = storage.coils.list
  for i = 1, #list do
    local rec = list[i]
    if rec.entity.valid then rec.force = rec.entity.force_index end
    counts[rec.force] = (counts[rec.force] or 0) + 1
  end
  storage.force_coils = counts
end

---------------------------------------------------------------------------------------------------------------------
-- Цикл лечения

-- Первая по порядку вставки подходящая катушка для цели и признак "цель вообще покрыта" (катушка своей силы,
-- на той же поверхности, в радиусе, существует — независимо от бюджета и энергии).
local function find_coil(target, tick)
  local grid = storage.grid[target.surface_index]
  if not grid then return nil, false end
  local force_index = target.force_index
  local position = target.position
  local tx, ty = position.x, position.y
  local cx, cy = floor(tx / CELL), floor(ty / CELL)
  local list, index = storage.coils.list, storage.coils.index
  local best, covered, dead = nil, false, nil
  for dx = -1, 1 do
    for dy = -1, 1 do
      local cell = grid[(cx + dx) .. "," .. (cy + dy)]
      if cell then
        for i = 1, #cell do
          local slot = index[cell[i]]
          local rec = slot and list[slot]
          if rec and rec.force == force_index then
            local ddx, ddy = rec.x - tx, rec.y - ty
            if ddx * ddx + ddy * ddy <= RADIUS_SQ then
              local coil = rec.entity
              if coil.valid then
                covered = true
                if not best or rec.seq < best.seq then
                  if rec.budget_tick ~= tick then rec.budget = COIL_BUDGET; rec.budget_tick = tick end
                  if rec.budget > 0 and coil.energy >= J_PER_HP then best = rec end
                end
              else
                dead = dead or {}
                dead[#dead + 1] = rec.unit
              end
            end
          end
        end
      end
    end
  end
  if dead then
    for i = 1, #dead do remove_coil(dead[i]) end        -- ленивое удаление недействительных записей
  end
  return best, covered
end

local function on_cycle(event)
  local queue = storage.queue
  if not queue or #queue == 0 then return end
  local tick = event.tick
  local queued = storage.queued
  -- Если очередь помещается в QUEUE_CAP, обходим её всю с начала. Иначе продолжаем с cursor до конца массива,
  -- не заворачивая в этом же цикле: так ни одна запись не обрабатывается дважды за цикл (swap-remove подтягивает
  -- на место i запись из хвоста, ещё не обработанную).
  local i = storage.cursor
  if #queue <= QUEUE_CAP or i > #queue then i = 1 end
  local done, lines = 0, 0
  while done < QUEUE_CAP and i <= #queue do
    done = done + 1
    local item = queue[i]
    local target = item.entity
    local remove = false
    if not target.valid then
      remove = true
    else
      local health, max_health = target.health, target.max_health
      if not health or health >= max_health then
        remove = true
      else
        local rec, covered = find_coil(target, tick)
        if rec then
          local coil = rec.entity
          local energy = coil.energy
          local h = max_health - health
          if h > TARGET_CAP then h = TARGET_CAP end
          if h > rec.budget then h = rec.budget end
          local affordable = floor(energy / J_PER_HP)
          if h > affordable then h = affordable end
          target.health = health + h
          coil.energy = energy - h * J_PER_HP
          rec.budget = rec.budget - h
          if lines < LINES_PER_CYCLE then
            lines = lines + 1
            rendering.draw_line{surface = rec.surface, from = coil, to = target, color = LINE_COLOR,
                                width = LINE_WIDTH, time_to_live = LINE_TTL}
          end
          if health + h >= max_health then remove = true end
        elseif not covered then
          remove = true                                 -- ни одна катушка не покрывает цель
        end                                             -- иначе покрыта, но катушке не хватает энергии или бюджета
      end
    end
    if remove then
      queued[item.unit] = nil
      local last = #queue
      queue[i] = queue[last]
      queue[last] = nil
    else
      i = i + 1
    end
  end
  if i > #queue then i = 1 end
  storage.cursor = i
end

---------------------------------------------------------------------------------------------------------------------
-- События

local function on_built(event)
  add_coil(event.entity or event.destination)
end

local function on_object_destroyed(event)
  if event.type ~= defines.target_type.entity then return end
  local coils = storage.coils
  if not coils then return end
  local slot = coils.index[event.useful_id]
  if not slot then return end
  if coils.list[slot].entity.valid then return end
  remove_coil(event.useful_id)
end

local function on_teleported(event)
  local entity = event.entity
  if not (entity and entity.valid and entity.unit_number) then return end
  remove_coil(entity.unit_number)
  add_coil(entity)
end

local build_events = {
  defines.events.on_built_entity,
  defines.events.on_robot_built_entity,
  defines.events.script_raised_built,
  defines.events.script_raised_revive,
  defines.events.on_entity_cloned,
}
if defines.events.on_space_platform_built_entity ~= nil then
  build_events[#build_events + 1] = defines.events.on_space_platform_built_entity
end
for i = 1, #build_events do
  script.on_event(build_events[i], on_built, COIL_FILTER)
end
script.on_event(defines.events.script_raised_teleported, on_teleported, COIL_FILTER)
script.on_event(defines.events.on_object_destroyed, on_object_destroyed)
script.on_event(defines.events.on_forces_merged, function()
  if storage.coils then refresh_forces() end
end)
script.on_nth_tick(PERIOD, on_cycle)

script.on_init(rebuild)
script.on_configuration_changed(rebuild)
script.on_load(update_registration)   -- storage только читается

---------------------------------------------------------------------------------------------------------------------
-- Удалённый интерфейс (только чтение)

remote.add_interface("magnetics", {
  constants = function()
    local types = {}
    for i = 1, #HEAL_TYPES do types[i] = HEAL_TYPES[i] end
    return {
      RADIUS = RADIUS, PERIOD = PERIOD, TARGET_CAP = TARGET_CAP, COIL_BUDGET = COIL_BUDGET, J_PER_HP = J_PER_HP,
      QUEUE_CAP = QUEUE_CAP, CELL = CELL, HEAL_TYPES = types, LINES_PER_CYCLE = LINES_PER_CYCLE,
    }
  end,
  state = function()
    return {
      coils = storage.coils and #storage.coils.list or 0,
      queue = storage.queue and #storage.queue or 0,
      handler_registered = script.get_event_handler(defines.events.on_entity_damaged) ~= nil,
    }
  end,
})
