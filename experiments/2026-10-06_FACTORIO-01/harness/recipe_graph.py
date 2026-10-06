# Граф рецептов (этап 0.Б.4): промежуточные продукты каждой задачи по прототипам самой игры; метки «ближняя/дальняя» для Q относительно P.
import json, sys
sys.path.insert(0, '/tmp/claude-0/fact'); from rcon import RCON
r = RCON(port=27100, pw='factorio'); r.cmd('/sc rcon.print(1)')
LUA = r'''/sc local function ing(item, seen, depth)
  if depth > 8 or seen[item] then return end; seen[item] = true
  local rec = prototypes.recipe[item]
  if not rec then return end
  for _, i in pairs(rec.ingredients) do ing(i.name, seen, depth + 1) end
end
local out = {}
for _, t in pairs({TARGETS}) do local s = {}; ing(t, s, 0); local l = {}; for k, _ in pairs(s) do table.insert(l, k) end; out[t] = l end
rcon.print(helpers.table_to_json(out))'''
T = ['iron-plate', 'iron-gear-wheel', 'electronic-circuit', 'inserter', 'automation-science-pack', 'logistic-science-pack', 'plastic-bar', 'sulfur', 'battery', 'steel-plate', 'engine-unit', 'military-science-pack']
g = json.loads(r.cmd(LUA.replace('{TARGETS}', '{' + ','.join(f'"{t}"' for t in T) + '}')))
P = T[:6]; Q = T[6:]; base = {'iron-plate', 'copper-plate', 'iron-ore', 'copper-ore', 'coal', 'stone', 'water', 'crude-oil'}   # руды и пластины — общий базис, не утечка
Pset = set().union(*[set(g[p]) for p in P])
lab = {q: sorted((set(g[q]) & Pset) - base - {q}) for q in Q}
out = dict(graph=g, P=P, Q=Q, shared_with_P=lab, label={q: ('ближняя' if lab[q] else 'дальняя') for q in Q})
json.dump(out, open('../stage0/recipe_graph.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out['shared_with_P'], ensure_ascii=False)); print(out['label'])
