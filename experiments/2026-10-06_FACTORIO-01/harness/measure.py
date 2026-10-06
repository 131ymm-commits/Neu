# Финальная мера FACTORIO-01, ред. 2 (06.10.2026, после слов автора «Изучи саму игру внимательнее там все можно автоматизировать»).
# Только RCON и статистика производства игры (без FLE: новое подключение FLE сбрасывает карту).
# 1) Опустошить буферы: сундуки, входы/выходы печей и сборщиков, руки манипуляторов, ленты — кроме топлива (топливо в топках и на лентах остаётся,
#    иначе честная угольная лента к котлу обрывается при очистке).
# 2) Горизонт H = 45 игровых минут без агента (50 угля в одном слоте хватает максимум на 37 мин — каменная печь; бур 22, котёл 2; по прототипам игры).
# 3) Два окна по 3600 тиков: выпуск цели = прирост в статистике производства (после конца эпизода руками никто не крафтит),
#    баланс сырья: для руд, угля, камня, дерева потреблено ≤ добыто·1,05 + 2 — завод живёт добычей, а не тающим запасом.
# 2а) На горизонте каждые 5 игровых минут и перед каждым окном опустошаются сундуки (продукцию «забирают»; деревянный сундук держит 1600 предметов —
#     без этого честный завод на 72/мин встаёт через ~22 мин; заодно запас топлива в сундуках не живёт дольше 5 мин).
# Успех = min(окно1, окно2) ≥ квоты и баланс в обоих окнах.
import json, time
RAW = ['coal', 'iron-ore', 'copper-ore', 'stone', 'wood', 'uranium-ore']
CLEAR = r'''/sc local fuel = {coal=true, wood=true, ["solid-fuel"]=true}
local n = 0
local function clr(inv) if inv then n = n + inv.get_item_count(); inv.clear() end end
for _, e in pairs(game.surfaces[1].find_entities_filtered{force="player"}) do
  local t = e.type
  if t == "container" or t == "logistic-container" then clr(e.get_inventory(defines.inventory.chest))
  elseif t == "furnace" then clr(e.get_inventory(defines.inventory.furnace_source)); clr(e.get_inventory(defines.inventory.furnace_result))
  elseif t == "assembling-machine" then clr(e.get_inventory(defines.inventory.assembling_machine_input)); clr(e.get_inventory(defines.inventory.assembling_machine_output))
  elseif t == "inserter" then if e.held_stack and e.held_stack.valid_for_read and not fuel[e.held_stack.name] then n = n + e.held_stack.count; e.held_stack.clear() end
  elseif t == "transport-belt" or t == "underground-belt" or t == "splitter" then
    for i = 1, e.get_max_transport_line_index() do local l = e.get_transport_line(i); local keep = {}
      for _, it in pairs(l.get_detailed_contents()) do
        if it.stack.valid_for_read and fuel[it.stack.name] then keep[#keep + 1] = {pos = it.position, name = it.stack.name, count = it.stack.count} end
      end
      n = n + #l; l.clear()
      for _, k in pairs(keep) do if l.insert_at(k.pos, {name = k.name, count = k.count}) then n = n - k.count end end
    end
  end
end
rcon.print(n)'''
CLEAR_CHESTS = '/sc local n=0 for _, e in pairs(game.surfaces[1].find_entities_filtered{force="player", type={"container","logistic-container"}}) do local inv=e.get_inventory(defines.inventory.chest); n=n+inv.get_item_count(); inv.clear() end rcon.print(n)'
def _stats(cmd, items):
    q = '/sc local st = game.forces.player.get_item_production_statistics(game.surfaces[1]); local o = {tick = game.tick}\n' + \
        ''.join(f'o["{k}"] = {{st.get_input_count("{k}"), st.get_output_count("{k}")}}\n' for k in items) + 'rcon.print(helpers.table_to_json(o))'
    return json.loads(cmd(q).strip())
def _tick(cmd): return int(cmd('/sc rcon.print(game.tick)').strip())
def _wait(cmd, ticks):
    t0 = _tick(cmd)
    while _tick(cmd) - t0 < ticks: time.sleep(0.5)
def window(cmd, target):
    cmd(CLEAR_CHESTS); items = RAW + [target]; s0 = _stats(cmd, items); _wait(cmd, 3600); s1 = _stats(cmd, items)
    dt = s1['tick'] - s0['tick']; out = s1[target][0] - s0[target][0]
    bal = {r: dict(mined=s1[r][0] - s0[r][0], used=s1[r][1] - s0[r][1]) for r in RAW}
    return dict(raw=out, dtick=dt, norm=out * 3600 / dt if dt else 0, balance=bal, balance_ok=all(b['used'] <= b['mined'] * 1.05 + 2 for b in bal.values()))
def final_measure_cmd(cmd, target, quota, H=2700):
    cmd('/sc rcon.print(1)')
    cleared = int(cmd(CLEAR).strip() or 0); chest_cleared = 0
    for _ in range(H // 300): _wait(cmd, 300 * 60); chest_cleared += int(cmd(CLEAR_CHESTS).strip() or 0)
    w1 = window(cmd, target); chest_cleared += int(cmd(CLEAR_CHESTS).strip() or 0); w2 = window(cmd, target)
    m = min(w1['norm'], w2['norm']); ok = w1['balance_ok'] and w2['balance_ok']
    return dict(cleared_items=cleared, chest_cleared_during=chest_cleared, horizon=H, w1=w1, w2=w2, measure=m, balance_ok=ok, success=(m >= quota) and ok, quota=quota, target=target)
def final_measure(inst, task, H=2700):
    ent = task.throughput_entity; ent = ent.value[0] if hasattr(ent, 'value') else str(ent)
    return final_measure_cmd(inst.rcon_client.send_command, ent, task.quota, H)
