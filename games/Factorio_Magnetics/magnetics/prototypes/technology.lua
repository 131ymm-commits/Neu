-- 14 технологий; «Маглев-логистика» под Space Age идёт после турбо-конвейеров и электромагнитной науки.
local U = require("prototypes.util")
local out = {}
for name, d in pairs(U.S.techs) do
  local prereq, count, time, packs = d.prereq, d.count, d.time, d.packs
  if U.SA and d.sa then
    prereq = table.deepcopy(prereq)
    for _, p in pairs(d.sa.extra_prereq) do prereq[#prereq + 1] = p end
    count, time, packs = d.sa.count, d.sa.time, d.sa.packs
  end
  local ing = {}
  for i, p in pairs(packs) do ing[i] = { p, 1 } end
  local eff = {}
  for i, r in pairs(d.unlocks) do eff[i] = { type = "unlock-recipe", recipe = r } end
  out[#out + 1] = { type = "technology", name = name, icon = "__magnetics__/graphics/technology/" .. name .. ".png", icon_size = 256,
                    prerequisites = prereq, effects = eff, unit = { count = count, time = time, ingredients = ing } }
end
data:extend(out)
