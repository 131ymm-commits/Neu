--[[ neu-play: обвязка опыта PLAY-01 (решение совета 24, docs/council/2026-10-01_PLAY-01_session24.md).
Один персонаж без игрока-человека на поверхности nauvis. Голова присылает список действий (JSON), мод исполняет их
по порядку тиками самой игры: ходьба через walking_state (без поиска пути и без телепорта), добыча через mining_state,
ручной крафт через begin_crafting; постройка, перенос предметов, рецепт, исследование, поворот — мгновенно, с проверкой
законности (дальность, наличие предметов, место). Незаконное действие отклоняется с причиной и ничего не меняет в мире.
Каждое действие, двигающее предметы, проверяет сохранение предметов (нулевой допуск) и пишет нарушение в журнал.
Вызовы снаружи — только remote.call("neu_play", ...) с данными в шестнадцатеричной записи (без склейки строк в Lua).
Состояние — только в storage; решения не зависят от порядка обхода хеш-таблиц (детерминизм). ]]
local ps = require("production-score")

local MAX_ACTIONS = 40
local STUCK_TICKS = 30          -- «застрял»: за 30 тиков сдвиг меньше STUCK_DIST (выбор совета, не замер)
local STUCK_DIST = 0.05
local NO_PROGRESS_TICKS = 60    -- «застрял» и так: 60 тиков лучшее расстояние до цели не сократилось на 0,05 (скольжение вдоль преграды;
                                -- сухой прогон 01.10.2026: персонаж скользил вдоль своих построек 10 000 тиков, правило 30 тиков не срабатывало)
local ARRIVE = 0.3              -- клетки: персонаж дошёл
local MINE_IDLE = 600           -- тиков без нового предмета при добыче — прекратить
local START_ITEMS = { { "iron-plate", 8 }, { "wood", 1 }, { "burner-mining-drill", 1 }, { "stone-furnace", 1 } }
-- стартовый набор freeplay (base) без пистолета и патронов: мирный режим, жуков нет
local DIRS = { north = defines.direction.north, east = defines.direction.east, south = defines.direction.south, west = defines.direction.west }
local DIR_NAME = {}
for k, v in pairs(DIRS) do DIR_NAME[v] = k end
local WALK = {   -- 8 направлений ходьбы и их единичные векторы (y вниз)
  { defines.direction.north, 0, -1 }, { defines.direction.northeast, 0.7071, -0.7071 }, { defines.direction.east, 1, 0 },
  { defines.direction.southeast, 0.7071, 0.7071 }, { defines.direction.south, 0, 1 }, { defines.direction.southwest, -0.7071, 0.7071 },
  { defines.direction.west, -1, 0 }, { defines.direction.northwest, -0.7071, -0.7071 },
}
local STATUS = {}
for k, v in pairs(defines.entity_status) do STATUS[v] = k end

---------------------------------------------------------------------------------------------------------------- данные
local function unhex(h)
  return (h:gsub("..", function(cc) return string.char(tonumber(cc, 16)) end))
end
local function decode(hex)
  if type(hex) ~= "string" or hex:find("[^0-9a-f]") or #hex % 2 == 1 then return nil end
  return helpers.json_to_table(unhex(hex))
end
local function sorted_keys(t)
  local ks = {}
  for k in pairs(t) do ks[#ks + 1] = k end
  table.sort(ks, function(a, b) return tostring(a) < tostring(b) end)
  return ks
end
local function S() return game.surfaces["nauvis"] end
local function C() return storage.c end
local function force() return game.forces.player end
local function num(v) return type(v) == "number" and v == v and v > -1e6 and v < 1e6 end
local function dist(a, b) local dx, dy = a.x - b.x, a.y - b.y; return math.sqrt(dx * dx + dy * dy) end

local function inv_table(inv)
  local t = {}
  if inv and inv.valid then
    for _, it in pairs(inv.get_contents()) do t[it.name] = (t[it.name] or 0) + it.count end
  end
  return t
end

local function log_result(r)
  local L = storage.log
  L[#L + 1] = r
end
local function violation(what)
  storage.violations[#storage.violations + 1] = { tick = game.tick, what = what }
end

---------------------------------------------------------------------------------------------------------------- поиск целей
-- Цель по координатам: постройка, чья рамка содержит точку (допуск 0,25 клетки); из нескольких — ближайшая по центру,
-- затем по имени (детерминизм). Руда: ближайшая клетка в радиусе 1.
local function pick(found, pos, tol, ok)
  local best, bd
  for _, e in ipairs(found) do
    if e.valid and ok(e) then
      local b = e.bounding_box
      if pos.x >= b.left_top.x - tol and pos.x <= b.right_bottom.x + tol and pos.y >= b.left_top.y - tol and pos.y <= b.right_bottom.y + tol then
        local d = dist(pos, e.position)
        if not best or d < bd or (d == bd and e.name < best.name) then best, bd = e, d end
      end
    end
  end
  return best
end
local function entity_at(pos, opts)
  local found = S().find_entities_filtered { area = { { pos.x - 3, pos.y - 3 }, { pos.x + 3, pos.y + 3 } }, force = opts and opts.force }
  return pick(found, pos, 0.25, function(e)
    return e ~= C() and e.type ~= "character" and e.type ~= "resource" and (not (opts and opts.minable) or e.minable)
  end)
end
local function resource_at(pos)
  local found = S().find_entities_filtered { position = pos, radius = 1, type = "resource" }
  return pick(found, pos, 0.5, function() return true end)
end

---------------------------------------------------------------------------------------------------------------- ручной крафт
-- Статистика производства у персонажа без игрока пишет расход ингредиентов ручного крафта, но не выход (замер
-- 01.10.2026). Выход считаем сами: крафт идёт с головы очереди, за тик завершается не больше одного (рецепты base ≥ 0,5 с).
local function qsig()
  local t = {}
  for i, e in ipairs(C().crafting_queue or {}) do t[i] = { recipe = e.recipe, count = e.count, pre = e.prerequisite or false } end
  return t
end
-- Удержано очередью ручного крафта (для сверки баланса): begin_crafting сразу снимает сырьё с инвентаря, промежуточные
-- предметы (шестерни под бур) живут внутри очереди, а статистика пишет расход только по завершении крафта (замер 01.10.2026).
local function qheld_add(name, k)
  storage.qheld = storage.qheld or {}
  local v = (storage.qheld[name] or 0) + k
  storage.qheld[name] = v ~= 0 and v or nil
end
local function inv_delta(a, b)   -- b − a по предметам
  local d = {}
  for n, k in pairs(b) do if k ~= (a[n] or 0) then d[n] = k - (a[n] or 0) end end
  for n, k in pairs(a) do if b[n] == nil then d[n] = -k end end
  return d
end
-- Триггер «craft-item» технологий 2.0 (например, automation-science-pack: скрафтить лабораторию) у персонажа без игрока
-- от ручного крафта не срабатывает (замер 01.10.2026; от выплавки в печи срабатывает). Мод считает ручной крафт сам:
-- предмет, скрафтенный руками, когда все требования технологии изучены, идёт в её счёт; набрался счёт — технология изучена.
local function hand_trigger(item, k)
  local f = force()
  for _, name in ipairs(sorted_keys(f.technologies)) do
    local t = f.technologies[name]
    local tr = t.prototype.research_trigger
    if not t.researched and tr and tr.type == "craft-item" and tr.item and (tr.item.name or tr.item) == item then
      local ok = true
      for _, p in pairs(t.prerequisites) do if not p.researched then ok = false; break end end
      if ok then
        storage.trig = storage.trig or {}
        storage.trig[name] = (storage.trig[name] or 0) + k
        if storage.trig[name] >= (tr.count or 1) then
          t.researched = true
          log_result { a = "trigger", ok = true, detail = "технология " .. name .. " изучена (скрафтено " .. item .. ")", tick = game.tick }
        end
      end
    end
  end
end
local function hand_add(recipe, k, pre)
  local rp = prototypes.recipe[recipe]
  for _, ing in ipairs(rp.ingredients) do
    if ing.type == "item" then qheld_add(ing.name, -ing.amount * k) end      -- расход записан статистикой
  end
  for _, pr in ipairs(rp.products) do
    if pr.type == "item" then
      if pr.amount == nil or (pr.probability or 1) ~= 1 then violation("ручной крафт с вероятностным выходом: " .. recipe) end
      storage.hand[pr.name] = (storage.hand[pr.name] or 0) + (pr.amount or 0) * k
      if pre then qheld_add(pr.name, (pr.amount or 0) * k) end               -- промежуточный предмет остаётся в очереди
      hand_trigger(pr.name, (pr.amount or 0) * k)
    end
  end
end
local function track_crafting()
  local prev, now = storage.prev_q or {}, qsig()
  local same = #prev == #now
  if same then
    for i = 1, #now do
      if prev[i].recipe ~= now[i].recipe or prev[i].count ~= now[i].count then same = false; break end
    end
  end
  if same then return end
  local ok = false
  if #prev >= 1 then
    if #now == #prev and now[1].recipe == prev[1].recipe and now[1].count == prev[1].count - 1 then ok = true
    elseif #now == #prev - 1 and prev[1].count == 1 then ok = true; for i = 1, #now do
      if prev[i + 1].recipe ~= now[i].recipe or prev[i + 1].count ~= now[i].count then ok = false; break end end
    end
  end
  if ok then hand_add(prev[1].recipe, 1, prev[1].pre) else violation("очередь крафта изменилась не по правилам") end
  storage.prev_q = now
end

---------------------------------------------------------------------------------------------------------------- мгновенные действия
local I = {}

function I.craft(a)
  local c = C()
  if type(a.recipe) ~= "string" or not prototypes.recipe[a.recipe] then return false, "нет такого рецепта" end
  local n = (num(a.n) and a.n >= 1) and math.floor(a.n) or 1
  local r = force().recipes[a.recipe]
  if not r.enabled then return false, "рецепт не открыт" end
  local inv0 = inv_table(c.get_main_inventory())
  local ok, started = pcall(c.begin_crafting, { recipe = a.recipe, count = n, silent = true })
  for name, k in pairs(inv_delta(inv0, inv_table(c.get_main_inventory()))) do qheld_add(name, -k) end   -- снято в очередь
  storage.prev_q = qsig()
  if not ok then return false, "крафт невозможен: " .. tostring(started) end
  if started == 0 then return false, "не хватает ингредиентов или рецепт не для ручного крафта" end
  return true, "поставлено в очередь " .. started
end

function I.place(a)
  local c = C()
  if type(a.item) ~= "string" or not prototypes.item[a.item] then return false, "нет такого предмета" end
  local proto = prototypes.item[a.item]
  local ent = proto.place_result
  if not ent then return false, "предмет не ставится" end
  if not (num(a.x) and num(a.y)) then return false, "нет координат" end
  local have = c.get_item_count(a.item)
  if have < 1 then return false, "нет в инвентаре" end
  local pos = { x = a.x, y = a.y }
  if dist(c.position, pos) > c.build_distance then return false, "дальше " .. c.build_distance .. " клеток" end
  local dir = DIRS[a.dir or "north"]
  if not dir then return false, "направление: north/east/south/west" end
  if not S().can_place_entity { name = ent.name, position = pos, direction = dir, force = "player", build_check_type = defines.build_check_type.manual } then
    -- причина отказа (для всех участников одинаково): что мешает в прямоугольнике постройки
    local w, h = ent.tile_width, ent.tile_height
    if dir == defines.direction.east or dir == defines.direction.west then w, h = h, w end
    local box = { { pos.x - w / 2 + 0.05, pos.y - h / 2 + 0.05 }, { pos.x + w / 2 - 0.05, pos.y + h / 2 - 0.05 } }
    local why = {}
    for _, o in ipairs(S().find_entities_filtered { area = box }) do
      if o.valid and o.type ~= "resource" and o ~= C() then why[#why + 1] = string.format("%s в (%.1f, %.1f)", o.name, o.position.x, o.position.y) end
      if #why >= 3 then break end
    end
    if C().valid then
      local cp = C().position
      if cp.x > box[1][1] - 0.2 and cp.x < box[2][1] + 0.2 and cp.y > box[1][2] - 0.2 and cp.y < box[2][2] + 0.2 then why[#why + 1] = "персонаж стоит на месте постройки" end
    end
    if S().count_tiles_filtered { area = box, collision_mask = "water_tile" } > 0 then why[#why + 1] = "вода" end
    if ent.type == "mining-drill" and S().count_entities_filtered { area = box, type = "resource" } == 0 then why[#why + 1] = "под буром нет руды" end
    if ent.type == "offshore-pump" then why[#why + 1] = "насос ставится на край воды, dir — сторона воды" end
    return false, "нельзя поставить: " .. (#why > 0 and table.concat(why, "; ") or "место непригодно")
  end
  local e = S().create_entity { name = ent.name, position = pos, direction = dir, force = "player", raise_built = true }
  if not e then return false, "не удалось поставить" end
  local removed = c.remove_item { name = a.item, count = 1 }
  if removed ~= 1 then violation("place: снято " .. removed .. " вместо 1 (" .. a.item .. ")") end
  return true, string.format("%s в (%.1f, %.1f)", e.name, e.position.x, e.position.y)
end

local function reach_entity(a, minable)
  local c = C()
  if not (num(a.x) and num(a.y)) then return nil, "нет координат" end
  local e = entity_at({ x = a.x, y = a.y }, { force = "player" })
  if not e then return nil, "здесь нет вашей постройки" end
  if not c.can_reach_entity(e) then return nil, "не дотянуться" end
  return e
end

function I.insert(a)
  local c = C()
  local e, why = reach_entity(a)
  if not e then return false, why end
  if type(a.item) ~= "string" or not prototypes.item[a.item] then return false, "нет такого предмета" end
  local have = c.get_item_count(a.item)
  local n = (num(a.n) and a.n >= 1) and math.floor(a.n) or have
  n = math.min(n, have)
  if n < 1 then return false, "нет в инвентаре" end
  local before_c, before_e = have, e.get_item_count(a.item)
  local put = e.insert { name = a.item, count = n }
  if put < 1 then return false, "постройка не принимает" end
  local removed = c.remove_item { name = a.item, count = put }
  if removed ~= put or c.get_item_count(a.item) + e.get_item_count(a.item) ~= before_c + before_e then
    violation("insert: нарушение сохранения " .. a.item)
  end
  return true, "положено " .. put
end

function I.take(a)
  local c = C()
  local e, why = reach_entity(a)
  if not e then return false, why end
  if type(a.item) ~= "string" or not prototypes.item[a.item] then return false, "нет такого предмета" end
  local avail = e.get_item_count(a.item)
  local n = (num(a.n) and a.n >= 1) and math.floor(a.n) or avail
  n = math.min(n, avail)
  if n < 1 then return false, "в постройке нет" end
  local before_c, before_e = c.get_item_count(a.item), avail
  local got = e.remove_item { name = a.item, count = n }
  local put = c.insert { name = a.item, count = got }
  if put < got then e.insert { name = a.item, count = got - put } end
  if c.get_item_count(a.item) + e.get_item_count(a.item) ~= before_c + before_e then
    violation("take: нарушение сохранения " .. a.item)
  end
  if put < 1 then return false, "инвентарь полон" end
  return true, "взято " .. put
end

function I.recipe(a)
  local c = C()
  local e, why = reach_entity(a)
  if not e then return false, why end
  if e.type ~= "assembling-machine" then return false, "это не сборочная машина" end
  if type(a.recipe) ~= "string" or not force().recipes[a.recipe] then return false, "нет такого рецепта" end
  if not force().recipes[a.recipe].enabled then return false, "рецепт не открыт" end
  local ok, returned = pcall(e.set_recipe, a.recipe)
  if not ok then return false, "рецепт не подходит машине" end
  for _, st in pairs(returned or {}) do
    local put = c.insert { name = st.name, count = st.count, quality = st.quality }
    if put < st.count then S().spill_item_stack { position = c.position, stack = { name = st.name, count = st.count - put } } end
  end
  return true, "рецепт " .. a.recipe
end

function I.research(a)
  local f = force()
  if type(a.tech) ~= "string" or not f.technologies[a.tech] then return false, "нет такой технологии" end
  local t = f.technologies[a.tech]
  if t.researched then return false, "уже изучено" end
  for _, p in pairs(t.prerequisites) do
    if not p.researched then return false, "не изучено требование " .. p.name end
  end
  if not t.enabled then return false, "технология недоступна" end
  if t.prototype.research_trigger then return false, "эта технология открывается триггером, а не лабораторией" end
  local ok, res = pcall(f.add_research, t)
  if not ok or res == false then return false, "не удалось поставить в очередь" end
  return true, "исследуется " .. a.tech
end

function I.rotate(a)
  local e, why = reach_entity(a)
  if not e then return false, why end
  if not e.rotatable then return false, "не поворачивается" end
  e.rotate()
  return true, "направление " .. tostring(DIR_NAME[e.direction] or e.direction)
end

---------------------------------------------------------------------------------------------------------------- длительные действия
local D = {}

function D.walk_start(a)
  if not (num(a.x) and num(a.y)) then return false, "нет координат" end
  return true
end
function D.walk_tick(a, st)
  local c = C()
  local p = c.position
  local dx, dy = a.x - p.x, a.y - p.y
  local d = math.sqrt(dx * dx + dy * dy)
  if d <= ARRIVE then c.walking_state = { walking = false }; return "done", string.format("дошёл до (%.1f, %.1f)", p.x, p.y) end
  local best, bv = nil, -2
  for _, w in ipairs(WALK) do
    local v = (w[2] * dx + w[3] * dy) / d
    if v > bv then bv, best = v, w[1] end
  end
  c.walking_state = { walking = true, direction = best }
  if not st.best or d < st.best - STUCK_DIST then st.best, st.since = d, 0 else st.since = st.since + 1 end
  if st.since > NO_PROGRESS_TICKS then
    c.walking_state = { walking = false }
    return "fail", string.format("застрял в (%.1f, %.1f): нет продвижения к цели", p.x, p.y)
  end
  st.hist = st.hist or {}
  st.hist[#st.hist + 1] = { p.x, p.y }
  if #st.hist > STUCK_TICKS then
    local o = st.hist[#st.hist - STUCK_TICKS]
    if math.abs(o[1] - p.x) + math.abs(o[2] - p.y) < STUCK_DIST then
      c.walking_state = { walking = false }
      return "fail", string.format("застрял в (%.1f, %.1f): путь прегражден", p.x, p.y)
    end
    table.remove(st.hist, 1)
  end
  return "go"
end

function D.mine_start(a, st)
  local c = C()
  if not (num(a.x) and num(a.y)) then return false, "нет координат" end
  local pos = { x = a.x, y = a.y }
  local target = resource_at(pos)
  local is_res = target ~= nil
  if not target then target = entity_at(pos, { minable = true }) end
  if not target then return false, "здесь нечего добывать" end
  if is_res then
    if dist(c.position, target.position) > c.resource_reach_distance + 0.5 then return false, "руда дальше " .. c.resource_reach_distance .. " клеток" end
  elseif not c.can_reach_entity(target) then
    return false, "не дотянуться"
  end
  st.target, st.is_res, st.pos = target, is_res, target.position
  st.want = (num(a.n) and a.n >= 1) and math.floor(a.n) or 1
  st.items0 = inv_table(c.get_main_inventory())
  st.got, st.idle = 0, 0
  st.prev_total = 0
  for _, v in pairs(st.items0) do st.prev_total = st.prev_total + v end
  return true
end
function D.mine_tick(a, st)
  local c = C()
  local t = st.target
  if not (t and t.valid) then
    c.mining_state = { mining = false }
    return "done", "добыто предметов: " .. st.got .. " (цель исчерпана или убрана)"
  end
  c.update_selected_entity(st.pos)
  c.mining_state = { mining = true, position = st.pos }
  local total = 0
  for _, v in pairs(inv_table(c.get_main_inventory())) do total = total + v end
  if total > st.prev_total then st.got = st.got + (total - st.prev_total); st.idle = 0 else st.idle = st.idle + 1 end
  st.prev_total = total
  if st.is_res and st.got >= st.want then c.mining_state = { mining = false }; return "done", "добыто " .. st.got end
  if st.idle > MINE_IDLE then c.mining_state = { mining = false }; return "fail", "добыча встала (инвентарь полон?), добыто " .. st.got end
  return "go"
end

function D.wait_start(a, st)
  st.left = (num(a.ticks) and a.ticks >= 1) and math.floor(a.ticks) or 60
  return true
end
function D.wait_tick(a, st)
  st.left = st.left - 1
  if st.left <= 0 then return "done", "ждал" end
  return "go"
end

local LONG = { walk = true, mine = true, wait = true }

---------------------------------------------------------------------------------------------------------------- цикл
local function step()
  local c = C()
  if not (c and c.valid) then return end
  track_crafting()
  if storage.frozen or not storage.queue then return end
  local cur = storage.cur
  if cur then
    local a = storage.queue[cur.i]
    local res, detail = D[a.a .. "_tick"](a, cur.st)
    if res ~= "go" then
      log_result { i = cur.i, a = a.a, ok = res == "done", detail = detail, tick = game.tick }
      storage.cur = nil
      storage.next = cur.i + 1
    end
    return
  end
  local i = storage.next or 1
  local a = storage.queue[i]
  if not a then return end
  if type(a) ~= "table" or type(a.a) ~= "string" or not (I[a.a] or LONG[a.a]) then
    log_result { i = i, a = type(a) == "table" and tostring(a.a) or "?", ok = false, detail = "неизвестное действие", tick = game.tick }
    storage.next = i + 1
    return
  end
  if LONG[a.a] then
    local st = {}
    local ok, why = D[a.a .. "_start"](a, st)
    if not ok then
      log_result { i = i, a = a.a, ok = false, detail = why, tick = game.tick }
      storage.next = i + 1
    else
      storage.cur = { i = i, st = st }
    end
  else
    local ok, why = I[a.a](a)
    log_result { i = i, a = a.a, ok = ok, detail = why, tick = game.tick }
    storage.next = i + 1
  end
end
-- Диспетчер очереди действий; остановка игры — game.ticks_to_run (решение совета 24), не on_tick.
script.on_event(defines.events.on_tick, step)

---------------------------------------------------------------------------------------------------------------- наблюдение
local function short_inv(e, id)
  local inv = e.get_inventory(id)
  if not inv then return nil end
  local t = inv_table(inv)
  if next(t) == nil then return nil end
  return t
end

local function observe()
  local c = C()
  local f = force()
  local o = { tick = game.tick, minutes = math.floor(game.tick / 3600 * 10) / 10 }
  o.character = { x = math.floor(c.position.x * 10) / 10, y = math.floor(c.position.y * 10) / 10,
                  build_distance = c.build_distance, reach_distance = c.reach_distance, resource_reach_distance = c.resource_reach_distance }
  o.inventory = inv_table(c.get_main_inventory())
  o.crafting_queue = {}
  for _, q in ipairs(c.crafting_queue or {}) do o.crafting_queue[#o.crafting_queue + 1] = { recipe = q.recipe, count = q.count } end
  local r = f.current_research
  o.research = { current = r and r.name or nil, progress = r and math.floor(f.research_progress * 100) / 100 or nil, researched = {}, available = {} }
  for _, name in ipairs(sorted_keys(f.technologies)) do
    local t = f.technologies[name]
    if t.researched then
      o.research.researched[#o.research.researched + 1] = name
    elseif t.enabled then
      local ok = true
      for _, p in pairs(t.prerequisites) do if not p.researched then ok = false; break end end
      if ok then
        local tr = t.prototype.research_trigger
        if tr then
          local what = tr.type .. " " .. tostring(tr.item and (tr.item.name or tr.item) or tr.entity or "") .. (tr.count and (" x" .. tr.count) or "")
          o.research.available[#o.research.available + 1] = { name = name, trigger = what }
        else
          local packs = {}
          for _, ing in ipairs(t.research_unit_ingredients) do packs[#packs + 1] = ing.name end
          o.research.available[#o.research.available + 1] = { name = name, count = t.research_unit_count, packs = packs,
            unit_seconds = t.research_unit_energy / 60 }
        end
      end
    end
  end
  -- свои постройки (по удалённости)
  local ents = S().find_entities_filtered { force = "player" }
  local list = {}
  for _, e in ipairs(ents) do
    if e.valid and e.type ~= "character" then
      local d = { name = e.name, x = e.position.x, y = e.position.y, dir = DIR_NAME[e.direction], status = STATUS[e.status] }
      if e.type == "assembling-machine" or e.type == "furnace" then
        local rr = e.get_recipe and e.get_recipe() or (e.type == "furnace" and e.previous_recipe)
        d.recipe = rr and (rr.name or rr) or nil
        d.input = short_inv(e, defines.inventory.crafter_input)
        d.output = short_inv(e, defines.inventory.crafter_output)
      elseif e.type == "container" then
        d.contents = short_inv(e, defines.inventory.chest)
      elseif e.type == "lab" then
        d.contents = short_inv(e, defines.inventory.lab_input)
      elseif e.type == "mining-drill" then
        local tgt = e.mining_target
        d.mining = tgt and tgt.valid and tgt.name or nil
      end
      if e.burner then d.fuel = short_inv(e, defines.inventory.fuel) end
      d.d = dist(c.position, e.position)
      list[#list + 1] = d
    end
  end
  table.sort(list, function(a, b) if a.d ~= b.d then return a.d < b.d end; if a.x ~= b.x then return a.x < b.x end return a.y < b.y end)
  o.entities = {}
  for k = 1, math.min(#list, 150) do list[k].d = nil; o.entities[k] = list[k] end
  o.entities_total = #list
  -- руда рядом: по каждому виду ближайшая клетка и запас в радиусе 48
  local res = S().find_entities_filtered { type = "resource", position = c.position, radius = 48 }
  local agg = {}
  for _, e in ipairs(res) do
    local a = agg[e.name]
    local d = dist(c.position, e.position)
    if not a then a = { tiles = 0, amount = 0, d = 1e9 }; agg[e.name] = a end
    a.tiles = a.tiles + 1
    a.amount = a.amount + e.amount
    if d < a.d or (d == a.d and (e.position.x < a.x or (e.position.x == a.x and e.position.y < a.y))) then a.d, a.x, a.y = d, e.position.x, e.position.y end
  end
  o.resources_within_48 = {}
  for _, name in ipairs(sorted_keys(agg)) do
    local a = agg[name]
    -- участок у ближайшей клетки: клетки этой руды в радиусе 10 от неё, полосами [y, x_от, x_до] (центры клеток)
    local cells = S().find_entities_filtered { name = name, position = { a.x, a.y }, radius = 10 }
    local rows = {}
    for _, e in ipairs(cells) do
      local y, x = e.position.y, e.position.x
      rows[y] = rows[y] or {}
      rows[y][#rows[y] + 1] = x
    end
    local runs = {}
    local ys = {}
    for y in pairs(rows) do ys[#ys + 1] = y end
    table.sort(ys)
    for _, y in ipairs(ys) do
      local xs = rows[y]
      table.sort(xs)
      local x0, prev = xs[1], xs[1]
      for k = 2, #xs + 1 do
        local x = xs[k]
        if x == nil or x ~= prev + 1 then runs[#runs + 1] = { y, x0, prev }; x0 = x end
        prev = x
      end
    end
    o.resources_within_48[#o.resources_within_48 + 1] = { name = name, nearest = { x = a.x, y = a.y }, distance = math.floor(a.d * 10) / 10,
      tiles = a.tiles, amount = a.amount, patch_near = runs }
  end
  -- ближайшие руды дальше 48 (по одной клетке на вид, в радиусе 160)
  local far = S().find_entities_filtered { type = "resource", position = c.position, radius = 160 }
  local seen = {}
  o.resources_far = {}
  for _, e in ipairs(far) do
    if not agg[e.name] then
      local d = dist(c.position, e.position)
      local s = seen[e.name]
      if not s or d < s.d then seen[e.name] = { d = d, x = e.position.x, y = e.position.y } end
    end
  end
  for _, name in ipairs(sorted_keys(seen)) do
    local s = seen[name]
    o.resources_far[#o.resources_far + 1] = { name = name, nearest = { x = s.x, y = s.y }, distance = math.floor(s.d) }
  end
  -- препятствия рядом: деревья и камни в радиусе 12, ближайшие 15
  local obs = S().find_entities_filtered { type = { "tree", "simple-entity" }, position = c.position, radius = 12 }
  local ol = {}
  for _, e in ipairs(obs) do ol[#ol + 1] = { name = e.name, x = e.position.x, y = e.position.y, d = dist(c.position, e.position) } end
  table.sort(ol, function(a, b) if a.d ~= b.d then return a.d < b.d end; if a.x ~= b.x then return a.x < b.x end return a.y < b.y end)
  o.obstacles_near = {}
  for k = 1, math.min(#ol, 15) do o.obstacles_near[k] = { name = ol[k].name, x = math.floor(ol[k].x * 10) / 10, y = math.floor(ol[k].y * 10) / 10 } end
  o.obstacles_within_12 = #ol
  -- ближайшая вода (радиус до 96)
  o.water_nearest = nil
  for _, rad in ipairs { 16, 32, 64, 96 } do
    local tiles = S().find_tiles_filtered { name = { "water", "deepwater", "water-green", "deepwater-green", "water-shallow", "water-mud" }, position = c.position, radius = rad }
    if #tiles > 0 then
      local best, bd
      for _, t in ipairs(tiles) do
        local p = { x = t.position.x + 0.5, y = t.position.y + 0.5 }
        local d = dist(c.position, p)
        if not best or d < bd or (d == bd and (p.x < best.x or (p.x == best.x and p.y < best.y))) then best, bd = p, d end
      end
      o.water_nearest = { x = best.x, y = best.y, distance = math.floor(bd * 10) / 10 }
      break
    end
  end
  o.last_actions = storage.log
  return o
end

---------------------------------------------------------------------------------------------------------------- счёт и сверки
local function stat_counts()
  local f = force()
  local out = { item_in = {}, item_out = {}, fluid_in = {}, fluid_out = {} }
  local is = f.get_item_production_statistics(S())
  local fs = f.get_fluid_production_statistics(S())
  for k, v in pairs(is.input_counts) do out.item_in[k] = v end
  for k, v in pairs(is.output_counts) do out.item_out[k] = v end
  for k, v in pairs(fs.input_counts) do out.fluid_in[k] = v end
  for k, v in pairs(fs.output_counts) do out.fluid_out[k] = v end
  return out
end

-- Предметы мира: постройки игрока (сама постройка как её предмет + все её инвентари по номеру, без повторов), ленты,
-- руки манипуляторов, предметы на земле; с include_character — и все инвентари персонажа. Для сверки баланса и S′.
local function add_inventories(e, add)
  for id = 1, e.get_max_inventory_index() do
    local inv = e.get_inventory(id)
    if inv then for n, k in pairs(inv_table(inv)) do add(n, k) end end
  end
end
local function world_items(include_character)
  local t = {}
  local function add(n, k) t[n] = (t[n] or 0) + k end
  for _, e in ipairs(S().find_entities_filtered { force = "player" }) do
    if e.valid and e.type ~= "character" then
      local place = e.prototype.items_to_place_this
      if place and place[1] then add(place[1].name, place[1].count or 1) else add("entity:" .. e.name, 1) end
      add_inventories(e, add)
      if e.type == "transport-belt" or e.type == "underground-belt" or e.type == "splitter" then
        for li = 1, e.get_max_transport_line_index() do
          for _, it in pairs(e.get_transport_line(li).get_contents()) do add(it.name, it.count) end
        end
      end
      if e.type == "inserter" and e.held_stack and e.held_stack.valid_for_read then add(e.held_stack.name, e.held_stack.count) end
      -- бур, которому некуда выложить добытое (статус «ждёт места»), держит один цикл добычи во внутреннем буфере:
      -- статистика его уже засчитала, инвентаря у буфера нет (дымовой прогон 01.10.2026: расхождение −1 руды)
      if e.type == "mining-drill" and e.status == defines.entity_status.waiting_for_space_in_destination then
        local t = e.mining_target
        if t and t.valid and t.prototype.mineable_properties.products then
          for _, pr in ipairs(t.prototype.mineable_properties.products) do
            if pr.type == "item" then add(pr.name, pr.amount or pr.amount_min or 1) end
          end
        end
      end
    end
  end
  for _, ie in ipairs(S().find_entities_filtered { type = "item-entity" }) do
    if ie.stack and ie.stack.valid_for_read then add(ie.stack.name, ie.stack.count) end
  end
  if include_character then
    add_inventories(C(), add)
    for n, k in pairs(storage.qheld or {}) do add(n, k) end
  end
  return t
end
local function value(items)
  local v = 0
  for _, n in ipairs(sorted_keys(items)) do v = v + (storage.prices[n] or 0) * items[n] end
  return v
end

local function fnv(s)
  local h = 2166136261
  for i = 1, #s do
    h = bit32.bxor(h, s:byte(i))
    h = (h * 16777619) % 4294967296
  end
  return string.format("%08x", h)
end
local function state_hash()
  local parts = { tostring(game.tick) }
  local ents = S().find_entities_filtered { force = "player" }
  local rows = {}
  for _, e in ipairs(ents) do
    if e.valid then rows[#rows + 1] = string.format("%s@%.3f,%.3f:%s:%.2f", e.name, e.position.x, e.position.y, tostring(e.direction), e.health or 0) end
  end
  table.sort(rows)
  parts[#parts + 1] = table.concat(rows, ";")
  local inv = inv_table(C().get_main_inventory())
  local iv = {}
  for _, n in ipairs(sorted_keys(inv)) do iv[#iv + 1] = n .. "=" .. inv[n] end
  parts[#parts + 1] = table.concat(iv, ",")
  local wi = world_items(false)
  local wv = {}
  for _, n in ipairs(sorted_keys(wi)) do wv[#wv + 1] = n .. "=" .. wi[n] end
  parts[#parts + 1] = table.concat(wv, ",")
  local f = force()
  parts[#parts + 1] = tostring(f.current_research and f.current_research.name) .. ":" .. string.format("%.4f", f.research_progress)
  return fnv(table.concat(parts, "|"))
end

---------------------------------------------------------------------------------------------------------------- интерфейс
local function json(t) return helpers.table_to_json(t) end

remote.add_interface("neu_play", {
  setup = function(hex)
    local p = decode(hex) or {}
    S().peaceful_mode = p.peaceful ~= false
    for _, e in ipairs(S().find_entities_filtered { force = "enemy" }) do if p.remove_enemies ~= false then e.destroy() end end
    local pos = S().find_non_colliding_position("character", { 0, 0 }, 64, 0.5)
    storage.c = S().create_entity { name = "character", position = pos, force = "player" }
    for _, it in ipairs(START_ITEMS) do storage.c.insert { name = it[1], count = it[2] } end
    storage.prices = ps.generate_price_list()
    storage.log, storage.violations, storage.frozen = {}, {}, false
    storage.hand, storage.prev_q, storage.qheld = {}, {}, {}
    storage.start_items = world_items(true)
    return json { ok = true, x = pos.x, y = pos.y }
  end,
  submit = function(hex)
    local q = decode(hex)
    if type(q) ~= "table" then return json { ok = false, reason = "не JSON-массив" } end
    local list = {}
    for k = 1, math.min(#q, MAX_ACTIONS) do list[k] = q[k] end
    storage.queue, storage.cur, storage.next, storage.log = list, nil, 1, {}
    return json { ok = true, accepted = #list, dropped = math.max(0, #q - MAX_ACTIONS) }
  end,
  -- в конце раунда: что не успело — помечается; ходьба и добыча прекращаются (очередь крафта идёт дальше)
  end_round = function()
    local c = C()
    if storage.cur then
      local a = storage.queue[storage.cur.i]
      log_result { i = storage.cur.i, a = a.a, ok = false, detail = "не завершено к концу раунда", tick = game.tick }
      storage.next = storage.cur.i + 1
      storage.cur = nil
    end
    local n = #(storage.queue or {})
    for i = storage.next or 1, n do
      log_result { i = i, a = tostring(type(storage.queue[i]) == "table" and storage.queue[i].a), ok = false, detail = "не начато: раунд кончился", tick = game.tick }
    end
    storage.queue = {}
    c.walking_state = { walking = false }
    c.mining_state = { mining = false }
    return json { ok = true }
  end,
  observe = function() return json(observe()) end,
  freeze = function()
    local c = C()
    storage.queue, storage.cur = {}, nil
    c.walking_state = { walking = false }
    c.mining_state = { mining = false }
    local inv0 = inv_table(c.get_main_inventory())
    local q = c.crafting_queue
    while q and #q > 0 do
      c.cancel_crafting { index = #q, count = q[#q].count }
      q = c.crafting_queue
    end
    for name, k in pairs(inv_delta(inv0, inv_table(c.get_main_inventory()))) do qheld_add(name, -k) end   -- возвращено из очереди
    if next(storage.qheld or {}) then violation("после отмены очереди крафта осталось удержанным: " .. serpent.line(storage.qheld)) end
    storage.prev_q = qsig()
    storage.frozen = true
    storage.freeze_stats = stat_counts()
    storage.freeze_stock = world_items(false)
    storage.freeze_tick = game.tick
    return json { ok = true, queue_empty = (c.crafting_queue == nil or #c.crafting_queue == 0) }
  end,
  score = function()
    local now, was = stat_counts(), storage.freeze_stats
    local d = { item = {}, fluid = {} }
    local s = 0
    for _, kind in ipairs { "item", "fluid" } do
      local names = {}
      for n in pairs(now[kind .. "_in"]) do names[n] = true end
      for n in pairs(now[kind .. "_out"]) do names[n] = true end
      for _, n in ipairs(sorted_keys(names)) do
        local din = (now[kind .. "_in"][n] or 0) - (was[kind .. "_in"][n] or 0)
        local dout = (now[kind .. "_out"][n] or 0) - (was[kind .. "_out"][n] or 0)
        if din ~= 0 or dout ~= 0 then
          d[kind][n] = { produced = din, consumed = dout, price = storage.prices[n] }
          s = s + (storage.prices[n] or 0) * (din - dout)
        end
      end
    end
    local stock_end = world_items(false)
    local v0, v1 = value(storage.freeze_stock), value(stock_end)
    return json { ok = true, ticks = game.tick - storage.freeze_tick, s_auto = s, stock_value_freeze = v0, stock_value_end = v1,
                  s_prime = s - math.max(0, v0 - v1), deltas = d }
  end,
  totals = function()   -- сводка для отчёта: полный счёт за партию, вехи
    local f = force()
    local researched = 0
    for _, t in pairs(f.technologies) do if t.researched then researched = researched + 1 end end
    local st = stat_counts()
    return json { ok = true, tick = game.tick, researched = researched, stats = st, entities = S().count_entities_filtered { force = "player" } - 1,
                  violations = storage.violations, world_items = world_items(true) }
  end,
  hash = function() return state_hash() end,
  -- снимок для сверки баланса: Δмир = Δпроизведено − Δпотреблено + Δручной крафт, по каждому предмету, допуск 0
  snapshot = function()
    track_crafting()   -- крафт, завершённый в обновлении этого тика, учесть сейчас, а не в следующем on_tick
    local st = stat_counts()
    -- допуск сверки: бур может держать один цикл добычи в момент снимка (выгрузка и запись статистики — в разные моменты
    -- цикла; трасса пилота, раунд 3): по продукту добычи |расхождение| ≤ числу буров, добывающих его
    local tol = {}
    for _, e in ipairs(S().find_entities_filtered { type = "mining-drill", force = "player" }) do
      local t = e.mining_target
      if t and t.valid then
        for _, pr in ipairs(t.prototype.mineable_properties.products or {}) do
          if pr.type == "item" then tol[pr.name] = (tol[pr.name] or 0) + (pr.amount or pr.amount_max or 1) end
        end
      end
    end
    return json { tick = game.tick, world = world_items(true), item_in = st.item_in, item_out = st.item_out, hand = storage.hand,
                  fluid_in = st.fluid_in, fluid_out = st.fluid_out, violations = #storage.violations, drill_tol = tol }
  end,
  -- прогнать n тиков с ускорением: игра на паузе крутит ticks_to_run тиков и снова встаёт
  run = function(n)
    n = math.max(0, math.floor(tonumber(n) or 0))
    game.speed = 64
    game.tick_paused = true
    game.ticks_to_run = n
    return json { ok = true, from_tick = game.tick, ticks = n }
  end,
  status = function() return json { tick = game.tick, paused = game.tick_paused, ticks_to_run = game.ticks_to_run } end,
  -- сохранить на паузе (после загрузки игра стоит на паузе, если tick_paused сохраняется — проверяется пилотом)
  save = function(hexname)
    local name = type(hexname) == "string" and not hexname:find("[^0-9a-f]") and unhex(hexname) or ""
    if not name:match("^neu_[0-9a-f]+$") then return json { ok = false, reason = "имя сейва" } end
    game.tick_paused = true
    game.server_save(name)
    return json { ok = true, tick = game.tick }
  end,
  prices = function() return json(storage.prices) end,
  stock = function() return json(world_items(false)) end,   -- запасы мира без персонажа
  -- Контрфактическое окно для S′ (только на копии сейва при заморозке): убрать входные запасы — входы машин, сундуки,
  -- входы лабораторий, ленты, руки манипуляторов, предметы на земле; топливо и выходы машин остаются.
  strip_stock = function()
    assert(storage.frozen, "strip_stock только после freeze")
    local removed = {}
    local function rm(n, k) removed[n] = (removed[n] or 0) + k end
    for _, e in ipairs(S().find_entities_filtered { force = "player" }) do
      if e.valid and e.type ~= "character" then
        local id = (e.type == "furnace" or e.type == "assembling-machine") and defines.inventory.crafter_input
                   or (e.type == "container" or e.type == "logistic-container") and defines.inventory.chest
                   or e.type == "lab" and defines.inventory.lab_input or nil
        local inv = id and e.get_inventory(id)
        if inv then
          for n, k in pairs(inv_table(inv)) do rm(n, k) end
          inv.clear()
        end
        if e.type == "transport-belt" or e.type == "underground-belt" or e.type == "splitter" then
          for li = 1, e.get_max_transport_line_index() do
            local L = e.get_transport_line(li)
            for _, it in pairs(L.get_contents()) do rm(it.name, it.count) end
            L.clear()
          end
        end
        if e.type == "inserter" and e.held_stack and e.held_stack.valid_for_read then rm(e.held_stack.name, e.held_stack.count); e.held_stack.clear() end
      end
    end
    for _, ie in ipairs(S().find_entities_filtered { type = "item-entity" }) do
      if ie.stack and ie.stack.valid_for_read then rm(ie.stack.name, ie.stack.count) end
      ie.destroy()
    end
    return json { ok = true, removed = removed }
  end,
})
