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
