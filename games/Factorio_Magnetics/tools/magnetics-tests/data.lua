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
