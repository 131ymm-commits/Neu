-- Тестовые источник и нагрузка энергии: у ванильного electric-energy-interface приоритет tertiary,
-- и аккумулятор (тоже tertiary) от него не заряжается (проверено пилотом 30.09.2026).
local function eei(name, priority, production)
  local e = table.deepcopy(data.raw["electric-energy-interface"]["electric-energy-interface"])
  e.name = name
  e.energy_source = { type = "electric", usage_priority = priority, buffer_capacity = "10GJ",
                      input_flow_limit = "10GW", output_flow_limit = "10GW" }
  e.energy_production = production; e.energy_usage = "0W"
  e.minable = nil
  return e
end
-- источник по умолчанию выдаёт 500 ГВт (FINAL_SPEC §11.1); ячейки могут менять power_production на ходу
data:extend{ eei("magnetics-test-source", "primary-output", "500GW"), eei("magnetics-test-load", "secondary-input", "0W") }

-- мишень без формул (FINAL_SPEC §11.1, PILOT-14). max_health 1e4, не 1e7: здоровье хранится во float32,
-- при 1e7 шаг 1 HP и урон за попадание округляется (замерено 9,8 → 10); при 1e4 шаг около 0,001.
do
  local t = table.deepcopy(data.raw["simple-entity-with-force"]["simple-entity-with-force"])
  t.name = "magnetics-test-target"
  t.max_health = 10000
  t.is_military_target = true
  t.resistances = nil
  t.flags = { "placeable-neutral", "placeable-player", "placeable-enemy", "not-on-map" }
  t.minable = nil
  t.hidden = true
  data:extend{ t }
end

-- Факты стадии данных для проверок, которых нет в API времени игры (§15.4, ревью 01.10.2026): гильзы и звук выстрела
-- турелей, дым генераторов, метка уровня предметов, окраска листьев chargable_graphics и инея Space Age, порядок
-- доставок цепи разрядника. Здесь только наблюдения (что лежит в data.raw после data.lua мода Magnetics — тестовый
-- мод зависит от него и грузится позже); ожидания набраны вручную в cells/static.lua (DOC.data_facts), не здесь.
do
  local raw = data.raw
  local function oggs(snd)                      -- все имена .ogg в таблице звука (варианты, filename)
    local out = {}
    local function walk(t)
      if type(t) == "string" then
        if t:sub(-4) == ".ogg" then out[#out + 1] = t end
      elseif type(t) == "table" then
        for _, v in pairs(t) do walk(v) end
      end
    end
    walk(snd)
    table.sort(out)
    return out
  end
  local function leaves(node, path, out, pred)  -- листья спрайтов (filename/filenames/stripes) под node
    if type(node) ~= "table" then return end
    if node.filename or node.filenames or node.stripes then
      if not pred or pred(path) then
        local t = node.tint
        out[#out + 1] = { path = path, file = node.filename or (node.filenames and node.filenames[1]) or "stripes",
          tint = t and { t[1] or t.r, t[2] or t.g, t[3] or t.b } or false,
          shadow = node.draw_as_shadow == true, glow = node.draw_as_glow == true }
      end
      return
    end
    local ks = {}
    for k in pairs(node) do ks[#ks + 1] = k end
    table.sort(ks, function(a, b) return tostring(a) < tostring(b) end)
    for _, k in ipairs(ks) do leaves(node[k], path .. "/" .. tostring(k), out, pred) end
  end
  local function get(t, path)                   -- значение по пути "/a/b/1" (для сверки с ванильным образцом)
    for part in path:gmatch("[^/]+") do
      if type(t) ~= "table" then return nil end
      t = t[part] ~= nil and t[part] or t[tonumber(part)]
    end
    return t
  end
  local facts = { turrets = {}, generators = {}, color_hint = {}, chargable = {}, frozen = {}, arc_chain_deliveries = {} }
  for _, n in ipairs { "magnetics-coilgun-turret", "magnetics-gauss-turret", "magnetics-rail-cannon", "gun-turret" } do
    local a = raw["ammo-turret"][n] and raw["ammo-turret"][n].attack_parameters or {}
    facts.turrets[n] = { shell_particle = a.shell_particle and a.shell_particle.name or false, sound = oggs(a.sound) }
  end
  facts.tank_cannon_sound = oggs(raw.gun["tank-cannon"] and raw.gun["tank-cannon"].attack_parameters.sound)
  for _, n in ipairs { "magnetics-flux-dynamo", "magnetics-mhd-generator" } do
    local g = raw["burner-generator"][n]
    facts.generators[n] = { smoke = g and g.burner and g.burner.smoke and #g.burner.smoke or 0 }
  end
  for n, it in pairs(raw.item) do
    if n:sub(1, 10) == "magnetics-" and it.place_result then
      facts.color_hint[n] = it.color_hint and it.color_hint.text or false
    end
  end
  for _, n in ipairs { "magnetics-superconducting-accumulator", "magnetics-coil-capacitor" } do
    local l = {}
    leaves(raw.accumulator[n] and raw.accumulator[n].chargable_graphics, "", l)
    facts.chargable[n] = l
  end
  -- иней: листья под любым ключом с «frozen» у построек Magnetics и тот же путь у ванильного образца
  local frozen_src = { ["magnetics-maglev-transport-belt"] = { "transport-belt", "express-transport-belt" },
                       ["magnetics-maglev-underground-belt"] = { "underground-belt", "express-underground-belt" },
                       ["magnetics-maglev-splitter"] = { "splitter", "express-splitter" } }
  for n, src in pairs(frozen_src) do
    local e, v = raw[src[1]][n], raw[src[1]][src[2]]
    local l = {}
    leaves(e, "", l, function(p) return p:find("frozen", 1, true) ~= nil end)
    for _, x in ipairs(l) do
      local vt = v and get(v, x.path)
      x.vanilla_tint = (type(vt) == "table" and vt.tint) and { vt.tint[1] or vt.tint.r, vt.tint[2] or vt.tint.g, vt.tint[3] or vt.tint.b } or false
      x.vanilla_found = type(vt) == "table"
    end
    facts.frozen[n] = l
  end
  local ch = raw["chain-active-trigger"] and raw["chain-active-trigger"]["magnetics-arc-chain"]
  local ad = ch and ch.action and ch.action.action_delivery or {}
  for i, d in ipairs(ad) do facts.arc_chain_deliveries[i] = d.type end
  data:extend { { type = "mod-data", name = "magnetics-test-data-facts", data = facts } }
end
