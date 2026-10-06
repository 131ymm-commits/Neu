# Финальная мера FACTORIO-01 (этап 0, ветка «вычет запаса»): опустошить буферы (сундуки, входы/выходы печей и сборщиков, руки манипуляторов, ленты; топливо остаётся),
# прогрев W = 180 игровых секунд, затем два окна по 60 с; мера = min(окно1, окно2), с нормировкой на тики. Агент после конца эпизода не действует.
import json
from fle.env.utils.achievements import eval_program_with_achievements
CLEAR = r'''/sc local n=0
for _, e in pairs(game.surfaces[1].find_entities_filtered{force="player"}) do
  local t = e.type
  if t == "container" or t == "logistic-container" then local inv = e.get_inventory(defines.inventory.chest); if inv then n = n + inv.get_item_count(); inv.clear() end
  elseif t == "furnace" then for _, k in pairs({defines.inventory.furnace_source, defines.inventory.furnace_result}) do local inv = e.get_inventory(k); if inv then n = n + inv.get_item_count(); inv.clear() end end
  elseif t == "assembling-machine" then for _, k in pairs({defines.inventory.assembling_machine_input, defines.inventory.assembling_machine_output}) do local inv = e.get_inventory(k); if inv then n = n + inv.get_item_count(); inv.clear() end end
  elseif t == "inserter" then if e.held_stack and e.held_stack.valid_for_read then n = n + e.held_stack.count; e.held_stack.clear() end
  elseif t == "transport-belt" or t == "underground-belt" or t == "splitter" then for i = 1, e.get_max_transport_line_index() do local l = e.get_transport_line(i); n = n + #l; l.clear() end
  end
end
rcon.print(n)'''
def tick(inst): return int(inst.rcon_client.send_command('/sc rcon.print(game.tick)').strip())
def window(inst, entity):
    t0 = tick(inst); _, _, _, ach = eval_program_with_achievements(program='sleep(60)', instance=inst); dt = tick(inst) - t0
    raw = ach['dynamic'].get(entity, 0); return dict(raw=raw, dtick=dt, norm=raw * 3600 / dt if dt else 0)
def final_measure(inst, task, W=180):
    cleared = int(inst.rcon_client.send_command(CLEAR).strip() or 0)
    inst.eval(f'sleep({W})', agent_idx=0, timeout=900)
    w1 = window(inst, task.throughput_entity); w2 = window(inst, task.throughput_entity)
    m = min(w1['norm'], w2['norm'])
    return dict(cleared_items=cleared, warmup=W, w1=w1, w2=w2, measure=m, success=m >= task.quota)
