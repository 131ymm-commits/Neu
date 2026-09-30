-- Тестовые источник и нагрузка энергии: у ванильного electric-energy-interface приоритет tertiary,
-- и аккумулятор (тоже tertiary) от него не заряжается (проверено пилотом 30.09.2026).
local function eei(name, priority)
  local e = table.deepcopy(data.raw["electric-energy-interface"]["electric-energy-interface"])
  e.name = name
  e.energy_source = { type = "electric", usage_priority = priority, buffer_capacity = "10GJ",
                      input_flow_limit = "10GW", output_flow_limit = "10GW" }
  e.energy_production = "0W"; e.energy_usage = "0W"
  e.minable = nil
  return e
end
data:extend{ eei("magnetics-test-source", "primary-output"), eei("magnetics-test-load", "secondary-input") }
