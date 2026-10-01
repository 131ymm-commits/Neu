-- Общие помощники стенда Magnetics: лаборатория, энергия, подача и снятие продукции, запись результатов.
local L = {}

L.results = {}
-- крючки событий урона и смерти: ячейки добавляют function(e) при загрузке модуля; состояние — в storage
L.on_damaged, L.on_died = {}, {}
-- kind: "mod" (по умолчанию) — проверка мода; "harness" — самопроверка стенда (провал тоже валит прогон);
-- "info" — справочная запись без проверки (в счёт прошло/не прошло не входит)
function L.check(group, name, ok, got, expected, note, kind)
  L.results[#L.results + 1] = { group = group, name = name, pass = ok and true or false, got = got, expected = expected, note = note,
                                kind = kind or "mod" }
end
function L.near(got, exp, rel, abs)
  if type(got) ~= "number" or type(exp) ~= "number" then return got == exp end
  local tol = math.max((rel or 1e-9) * math.abs(exp), abs or 0)
  return math.abs(got - exp) <= tol
end
-- Сравнение числа с ожиданием и запись в результаты.
function L.eq(group, name, got, exp, rel, abs, note)
  L.check(group, name, L.near(got, exp, rel, abs), got, exp, note)
end

function L.write(file)
  local pass, fail = 0, 0
  for _, r in pairs(L.results) do if r.pass then pass = pass + 1 else fail = fail + 1 end end
  helpers.write_file(file, helpers.table_to_json({ pass = pass, fail = fail, results = L.results }), false)
end

-- Пустая лаборатория: плитки lab, без руды и врагов.
function L.lab(radius_chunks)
  local S = game.create_surface("magnetics-lab", { width = 2048, height = 2048, peaceful_mode = false })
  S.generate_with_lab_tiles = true
  S.always_day = true
  S.request_to_generate_chunks({ 0, 0 }, radius_chunks or 12)
  S.force_generate_chunk_requests()
  return S
end

-- Начало ячейки i (ячейки 128×128 клеток, чтобы опыты не мешали друг другу).
function L.slot(i)
  local cols = 10
  return { x = (i % cols) * 128 - 640, y = math.floor(i / cols) * 128 - 640 }
end

-- Энергия: тестовый источник (primary-output) и подстанции сеткой, покрывающей квадрат размером size клеток.
function L.power(S, origin, size, watts)
  local src = S.create_entity { name = "magnetics-test-source", position = { origin.x - 6, origin.y - 6 }, force = "player" }
  src.power_production = (watts or 1e9) / 60
  src.electric_buffer_size = (watts or 1e9) / 60 * 2
  local poles = {}
  for dx = -4, size + 4, 16 do
    for dy = -4, size + 4, 16 do
      poles[#poles + 1] = S.create_entity { name = "substation", position = { origin.x + dx, origin.y + dy }, force = "player" }
    end
  end
  return src, poles
end

-- Подать в машину всё, что просит рецепт (предметы — вдвое больше разовой нормы; жидкости — полный бак).
function L.topup(e, recipe)
  local inv = e.get_inventory(defines.inventory.crafter_input)
  recipe = recipe or e.get_recipe()
  if recipe then
    for _, ing in pairs(recipe.ingredients) do
      if ing.type == "item" then
        local need = ing.amount * 4 - inv.get_item_count(ing.name)
        if need > 0 then inv.insert { name = ing.name, count = need } end
      end
    end
  end
  local fb = e.fluidbox
  for i = 1, #fb do
    local proto = fb.get_prototype(i)
    if proto.object_name == nil then proto = proto[1] end   -- бывает один прототип или список
    if proto.production_type == "input" then
      local f = fb.get_filter(i)
      if f then fb[i] = { name = f.name, amount = proto.volume } end
    end
  end
end

-- Снять продукцию (предметы и жидкости) и прибавить к счётчику counter[name].
function L.drain(e, counter)
  local out = e.get_inventory(defines.inventory.crafter_output)
  if out then
    for _, it in pairs(out.get_contents()) do
      counter[it.name] = (counter[it.name] or 0) + it.count
      out.remove { name = it.name, count = it.count, quality = it.quality }
    end
  end
  local fb = e.fluidbox
  for i = 1, #fb do
    local proto = fb.get_prototype(i)
    if proto.object_name == nil then proto = proto[1] end
    if proto.production_type == "output" and fb[i] then
      counter[fb[i].name] = (counter[fb[i].name] or 0) + fb[i].amount
      fb[i] = nil
    end
  end
end

-- Топливо в горелку (для машин и генераторов на топливе).
function L.fuel(e, item, count)
  local inv = e.get_inventory(defines.inventory.fuel)
  if inv then
    local need = (count or 20) - inv.get_item_count(item)
    if need > 0 then inv.insert { name = item, count = need } end
  end
end

return L
