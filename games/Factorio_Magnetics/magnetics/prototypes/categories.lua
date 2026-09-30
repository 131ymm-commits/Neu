local U = require("prototypes.util")
local S = U.S
local out = {}
for _, name in pairs(S.recipe_categories) do out[#out + 1] = { type = "recipe-category", name = name } end
for name, c in pairs(S.ammo_categories) do
  out[#out + 1] = { type = "ammo-category", name = name, bonus_gui_order = c.bonus_gui_order,
                    icon = "__magnetics__/graphics/icons/ammo-category-" .. name .. ".png", icon_size = 64 }
end
for _, name in pairs(S.fuel_categories) do out[#out + 1] = { type = "fuel-category", name = name } end
out[#out + 1] = { type = "item-subgroup", name = "magnetics-intermediate", group = "intermediate-products", order = "gm" }
data:extend(out)
