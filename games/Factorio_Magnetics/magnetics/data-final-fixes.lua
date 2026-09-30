-- 1) Исследования урона и скорострельности пуль копируются на болванки Magnetics (добавлением в конец списка,
--    после правок Space Age), а бонус турели-пулемёта — на три турели Magnetics.
-- 2) Резонатор потока не ускоряется качеством (замок петли энергии).
local CATS = { "magnetics-slug", "magnetics-gauss", "magnetics-rail" }
local TURRETS = { "magnetics-coilgun-turret", "magnetics-gauss-turret", "magnetics-rail-cannon" }
for _, tech in pairs(data.raw.technology) do
  local effs = tech.effects
  if effs then
    local snap = table.deepcopy(effs)
    for _, e in ipairs(snap) do
      if (e.type == "ammo-damage" or e.type == "gun-speed") and e.ammo_category == "bullet" then
        for _, c in ipairs(CATS) do effs[#effs + 1] = { type = e.type, ammo_category = c, modifier = e.modifier } end
      elseif e.type == "turret-attack" and e.turret_id == "gun-turret" then
        for _, t in ipairs(TURRETS) do effs[#effs + 1] = { type = "turret-attack", turret_id = t, modifier = e.modifier } end
      end
    end
  end
end

local res = data.raw["assembling-machine"]["magnetics-flux-resonator"]
if res and data.raw.quality then
  local m = {}
  for q, _ in pairs(data.raw.quality) do m[q] = 1 end
  res.crafting_speed_quality_multiplier = m
end
