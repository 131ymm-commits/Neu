# Проверка состояния мира по игре после эпизода (оркестратор): ток, статусы машин, выпуск за 10 мин, потери от врагов.
#   /tmp/claude-0/flevenv/bin/python health.py [порт RCON, 27106]
import sys, json, factorio_rcon
r = factorio_rcon.RCONClient('localhost', int(sys.argv[1]) if len(sys.argv) > 1 else 27106, 'factorio')
q = r'''/sc local n={} for k,v in pairs(defines.entity_status) do n[v]=k end
local s=game.surfaces[1] local c={} for _,e in pairs(s.find_entities_filtered{force="player", type={"furnace","boiler","generator","assembling-machine","lab","mining-drill"}}) do local k=e.type.."/"..tostring(n[e.status] or e.status) c[k]=(c[k] or 0)+1 end
local st=game.forces.player.get_item_production_statistics(s) local p={} for _,it in pairs({"iron-plate","copper-plate","steel-plate","electronic-circuit","automation-science-pack","logistic-science-pack","chemical-science-pack","plastic-bar","sulfur"}) do p[it]=math.floor(st.get_flow_count{name=it,category="input",precision_index=defines.flow_precision_index.ten_minutes}) end
local k={} for nm,v in pairs(game.forces.enemy.get_kill_count_statistics(s).input_counts) do k[nm]=v end
rcon.print(helpers.table_to_json({tick=game.tick, statuses=c, made_10min=p, killed_by_enemy=k, enemies_near=s.count_entities_filtered{force="enemy", area={{-150,-100},{150,200}}}, research=game.forces.player.current_research and game.forces.player.current_research.name or ""}))'''
d = json.loads(r.send_command(q))
gen = sum(v for k, v in d['statuses'].items() if k.startswith('generator/'))
nopow = sum(v for k, v in d['statuses'].items() if k.endswith('/no_power'))
print(json.dumps(d, ensure_ascii=False))
print(f"ИТОГ: паровых машин {gen}, без тока {nopow}, железо за 10 мин {d['made_10min'].get('iron-plate')}, врагов у базы {d['enemies_near']}, исследование «{d['research']}»")
