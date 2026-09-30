local U = require("prototypes.util")
local out = {}
for name, d in pairs(U.S.fluids) do
  out[#out + 1] = { type = "fluid", name = name, icons = U.icon(name), subgroup = "fluid", order = d.order,
                    default_temperature = d.default_temperature, base_color = d.base_color, flow_color = d.flow_color,
                    auto_barrel = false }
end
data:extend(out)
