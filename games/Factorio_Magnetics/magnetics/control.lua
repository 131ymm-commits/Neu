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
--   storage.queue         массив {entity, unit, cycle} повреждённых целей (cycle — тик последней обработки);
--   storage.queued        unit -> true для целей в очереди;
--   storage.cursor        с какой записи очереди начнётся следующий цикл (обход по кругу);
--   storage.seq           счётчик порядка вставки катушек ("первая по порядку вставки" = наименьший seq);
--   storage.coils_version растёт при каждом добавлении/удалении катушки и слиянии сил: записи очереди хранят список
--                         покрывающих катушек (cov, по возрастанию seq) с версией cov_v и пересчитывают его при смене версии.
-- Скорость (замер UPS 01.10.2026, tools/ups.py): прежний цикл заново обходил все катушки соседних клеток сетки и читал
-- у цели неизменные поля через API на каждой записи — 100 катушек при 50 уронах/с стоили ~0,16 мс/тик. Теперь
-- неизменные поля цели (позиция, поверхность, сила, макс. здоровье) читаются один раз при постановке в очередь.
-- Обработчик on_entity_damaged зарегистрирован только пока есть хоть одна катушка; on_load повторяет это решение
-- по storage (регистрация — чистая функция storage, как требует детерминизм мультиплеера).
--
-- Фильтр урона (PILOT-24): в фильтрах событий "and" связывает сильнее "or" (runtime-api.json,
-- LuaEntityDamagedEventFilter.mode), поэтому условие final-health > 0 стоит в паре с КАЖДЫМ типом:
-- (wall and fh>0) or (gate and fh>0) or ... Запись "типы через or, затем один fh>0 с and" относила бы условие
-- только к последнему типу (radar). Пилот на сервере 2.0.77 (30.09.2026, tools/magnetics-tests/mend_tests.lua)
-- подтвердил: при записи "типы, затем fh>0 с and" смертельный урон по стене доходит до обработчика, а по радару нет;
-- при парной записи не доходит ни тот, ни другой; кусаки и сборочные машины не доходят ни при какой записи.
-- PILOT-10: катушка (EEI secondary-input, energy_usage = 0) заряжается от сети ровно на 200 кВт
-- (3333.33 Дж/тик, полный буфер 1 МДж через 300 тиков), запасной путь не нужен.
-- Здоровье хранится с округлением float32 (запись 505 читается как 505.0000305), поэтому "полное" сравнивается >=.

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
  storage.coils_version = (storage.coils_version or 0) + 1
end

local function cell_key(x, y)
  return (floor(x / CELL) + 0) .. "," .. (floor(y / CELL) + 0)   -- "+ 0" превращает -0 в 0, как (cx + dx) в find_coil
end

---------------------------------------------------------------------------------------------------------------------
-- Очередь повреждённых целей

-- Запись очереди: цель и её неизменные поля (стены, ворота, турели и радары не двигаются).
local function new_item(entity, unit, force_index)
  local position = entity.position
  return {entity = entity, unit = unit, x = position.x, y = position.y, surface = entity.surface_index,
          force = force_index, max_health = entity.max_health}
end

local function on_damaged(event)
  if event.final_health <= 0 then return end          -- страховка; фильтр уже отсёк смертельный урон
  local entity = event.entity
  local force_index = entity.force_index
  if not storage.force_coils[force_index] then return end
  local unit = entity.unit_number
  if not unit then return end
  local queued = storage.queued
  if queued[unit] then return end
  queued[unit] = true
  local queue = storage.queue
  queue[#queue + 1] = new_item(entity, unit, force_index)
end

-- Поставить в очередь найденную поиском цель, если она повреждена.
local function enqueue_if_damaged(entity)
  local unit = entity.unit_number
  if not unit or storage.queued[unit] then return end
  local health = entity.health
  if not health or health <= 0 or health >= entity.max_health then return end
  storage.queued[unit] = true
  local queue = storage.queue
  queue[#queue + 1] = new_item(entity, unit, entity.force_index)
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
  storage.coils_version = (storage.coils_version or 0) + 1
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
  storage.coils_version = (storage.coils_version or 0) + 1
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
  storage.coils_version = (storage.coils_version or 0) + 1
  -- силы целей в очереди тоже могли смениться: перечитать
  local queue = storage.queue
  for i = 1, #queue do
    local item = queue[i]
    if item.entity.valid then item.force = item.entity.force_index end
  end
end

---------------------------------------------------------------------------------------------------------------------
-- Цикл лечения

-- Первая по порядку вставки подходящая катушка для цели; признак "цель вообще покрыта" (катушка своей силы,
-- на той же поверхности, в радиусе, существует — независимо от бюджета и энергии); признак "покрывающая катушка
-- уже истратила бюджет этого цикла" (значит, энергия у неё была — цель ждёт очереди, а не энергии).
local function by_seq(a, b) return a.seq < b.seq end

-- Список покрывающих катушек цели (своя сила, та же поверхность, в радиусе) по возрастанию seq; пересчёт по сетке
-- только при смене storage.coils_version.
local function covering(item)
  local version = storage.coils_version
  if item.cov_v == version then return item.cov end
  if item.x == nil then                                  -- запись из старой версии мода: дочитать поля
    local target = item.entity
    local position = target.position
    item.x, item.y, item.surface, item.force, item.max_health =
      position.x, position.y, target.surface_index, target.force_index, target.max_health
  end
  local recs = {}
  local grid = storage.grid[item.surface]
  if grid then
    local tx, ty, force_index = item.x, item.y, item.force
    local cx, cy = floor(tx / CELL), floor(ty / CELL)
    local list, index = storage.coils.list, storage.coils.index
    for dx = -1, 1 do
      for dy = -1, 1 do
        local cell = grid[(cx + dx) .. "," .. (cy + dy)]
        if cell then
          for i = 1, #cell do
            local slot = index[cell[i]]
            local rec = slot and list[slot]
            if rec and rec.force == force_index then
              local ddx, ddy = rec.x - tx, rec.y - ty
              if ddx * ddx + ddy * ddy <= RADIUS_SQ then recs[#recs + 1] = rec end
            end
          end
        end
      end
    end
  end
  table.sort(recs, by_seq)                               -- seq уникальны: порядок однозначен
  local cov = {}
  for i = 1, #recs do cov[i] = recs[i].unit end
  item.cov, item.cov_v = cov, version
  return cov
end

-- Первая по порядку вставки подходящая катушка для цели (бюджет цикла не исчерпан, энергии хватает на 1 HP);
-- признак "цель вообще покрыта" (существующая катушка своей силы на той же поверхности в радиусе — независимо от
-- бюджета и энергии); признак "покрывающая катушка уже истратила бюджет этого цикла" (энергия у неё была — цель ждёт
-- очереди, а не энергии). Тот же выбор, что и прежний полный обход клеток: первая по seq подходящая.
local function find_coil(item, tick)
  local cov = covering(item)
  local list, index = storage.coils.list, storage.coils.index
  local covered, spent, dead = false, false, nil
  local best = nil
  for i = 1, #cov do
    local slot = index[cov[i]]
    local rec = slot and list[slot]
    if rec then
      local coil = rec.entity
      if coil.valid then
        covered = true
        if rec.budget_tick ~= tick then rec.budget = COIL_BUDGET; rec.budget_tick = tick end
        if rec.budget <= 0 then
          spent = true
        elseif coil.energy >= J_PER_HP then
          best = rec
          break
        end
      else
        dead = dead or {}
        dead[#dead + 1] = rec.unit
      end
    end
  end
  if dead then
    for i = 1, #dead do remove_coil(dead[i]) end        -- ленивое удаление недействительных записей
  end
  return best, covered, spent
end

-- Одна запись очереди: вылечить цель первой подходящей катушкой.
-- Возвращает (убрать_из_очереди, вылечена, ждёт_бюджета): ждёт бюджета цель, которую покрывает катушка с энергией,
-- уже истратившая бюджет этого цикла на другие цели.
local function heal_one(item, tick, may_draw)
  local target = item.entity
  if not target.valid then return true, false, false end
  local health = target.health
  local max_health = item.max_health or target.max_health
  if not health or health >= max_health then return true, false, false end
  local rec, covered, spent = find_coil(item, tick)
  if not rec then
    return not covered, false, spent                   -- не покрыта никем: убрать; покрыта: ждать энергии или бюджета
  end
  local coil = rec.entity
  local energy = coil.energy
  local h = max_health - health
  if h > TARGET_CAP then h = TARGET_CAP end
  if h > rec.budget then h = rec.budget end
  local affordable = floor(energy / J_PER_HP)
  if h > affordable then h = affordable end
  target.health = health + h                           -- запись ограничивается [0, max_health] движком
  coil.energy = energy - h * J_PER_HP
  rec.budget = rec.budget - h
  if may_draw then
    rendering.draw_line{surface = rec.surface, from = coil, to = target, color = LINE_COLOR,
                        width = LINE_WIDTH, time_to_live = LINE_TTL}
  end
  return health + h >= max_health, true, false
end

-- Цикл: до QUEUE_CAP записей по кругу от cursor. Каждая запись за цикл обрабатывается не больше одного раза:
-- она помечается тиком цикла (item.cycle), а запись, подтянутая swap-remove из уже пройденного хвоста, пропускается.
-- Если за цикл пройдена вся очередь (она не длиннее QUEUE_CAP), следующий цикл начинается с первой записи этого
-- цикла, ждавшей бюджета (иначе — на одну запись дальше): бюджет катушки достаётся её целям по очереди, а не всегда
-- первым в массиве. Три стены у одной катушки лечатся 2 цикла из 3 каждая, и бюджет 10 HP расходуется весь.
-- Цели, ждущие энергии (катушка без питания), на порядок не влияют.
local function on_cycle(event)
  local queue = storage.queue
  if not queue then return end
  local n0 = #queue
  if n0 == 0 then return end
  local tick = event.tick
  local queued = storage.queued
  local limit = n0 < QUEUE_CAP and n0 or QUEUE_CAP
  local start = storage.cursor
  if start > n0 then start = 1 end
  local i = start
  local done, lines, steps, waiting = 0, 0, 0, nil
  while done < limit and steps < 2 * QUEUE_CAP do     -- шагов не больше limit + число удалений <= 2 * QUEUE_CAP
    local n = #queue
    if n == 0 then break end
    if i > n then i = 1 end
    steps = steps + 1
    local item = queue[i]
    if item.cycle == tick then
      i = i + 1
    else
      item.cycle = tick
      done = done + 1
      local may_draw = lines < LINES_PER_CYCLE
      local remove, healed, wants_budget = heal_one(item, tick, may_draw)
      if healed then
        if may_draw then lines = lines + 1 end
      elseif wants_budget and not remove and not waiting then
        waiting = item
      end
      if remove then
        queued[item.unit] = nil
        queue[i] = queue[n]
        queue[n] = nil
      else
        i = i + 1
      end
    end
  end
  if done >= n0 then
    i = start + 1
    if waiting then
      for k = 1, #queue do
        if queue[k] == waiting then i = k; break end
      end
    end
  end
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
-- Удалённая поверхность: убрать её катушки сразу, не полагаясь на on_object_destroyed (обход массива с конца;
-- swap-remove подтягивает на место i уже просмотренную запись).
script.on_event(defines.events.on_surface_deleted, function(event)
  local coils = storage.coils
  if not coils then return end
  local list = coils.list
  for i = #list, 1, -1 do
    local rec = list[i]
    if rec and rec.surface == event.surface_index then remove_coil(rec.unit) end
  end
  storage.grid[event.surface_index] = nil
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
