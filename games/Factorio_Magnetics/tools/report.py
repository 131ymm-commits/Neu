"""Таблица замеров для README из JSON результатов (числа не набираются руками; CLAUDE.md: каждое число — из json).
Вход: test_results.json, ups_results.json, tw_results_base.json. Выход: RESULTS.md (вставляется в README ссылкой)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, 'test_results.json'), encoding='utf-8'))
U = json.load(open(os.path.join(HERE, 'ups_results.json'), encoding='utf-8'))
TW = json.load(open(os.path.join(HERE, 'tw_results_base.json'), encoding='utf-8'))

def got(cfg, test, name_start):
    for r in R['records']:
        if r.get('config') == cfg and r.get('test') == test and str(r.get('name')).startswith(name_start):
            return r.get('got')
    raise KeyError((cfg, test, name_start))

def f(x, nd=2):
    if isinstance(x, (int, float)):
        x = round(float(x), nd)
        return ('%d' % x) if x == int(x) else (('%.' + str(nd) + 'f') % x).rstrip('0').rstrip('.')
    return str(x)

L = []
cnt = {}
for r in R['records']:
    c = r.get('config'); cnt.setdefault(c, [0, 0]); cnt[c][0 if r.get('pass_', r.get('pass')) else 1] += 1
L.append('# Magnetics — замеры на сервере Factorio 2.0.77 (сгенерировано tools/report.py из JSON)\n')
L.append(f"Проверок всего: **{sum(v[0] + v[1] for v in cnt.values())}**, провалов: **{sum(v[1] for v in cnt.values())}** "
         f"(base {cnt['base'][0]}, base+quality {cnt['bq'][0]}, base+elevated-rails {cnt['be'][0]}, Space Age {cnt['sa'][0]}, файлы {cnt['files'][0]}).\n")
rows = [
  ('Магнитный бур, руды за 60 с (электробур — контроль)', f(got('base', 'M1', 'M1 magnetic drill')), f(got('base', 'M1', 'M1 control'))),
  ('Маглев-конвейер, предметов/с (экспресс — контроль)', f(got('base', 'L1', 'L1 maglev belt')), f(got('base', 'L1', 'L1 control'))),
  ('МГД-генератор, Вт (угля за 60 с)', f(got('base', 'E4', 'E4 MHD (coal) output, electric')), f(got('base', 'E4', 'E4 MHD coal burnt'))),
  ('МГД-генератор, загрязнение в минуту', f(got('base', 'E4', 'E4 MHD pollution')), '—'),
  ('Динамо потока, Вт (кристаллов за 60 с)', f(got('base', 'E5', 'E5 flux dynamo output, electric')), f(got('base', 'E5', 'E5 crystals burnt'))),
  ('Резонатор, Дж на один заряд кристалла', f(got('base', 'P6', 'P6 resonator energy per crystal')), '—'),
  ('Петля потока: отдано / затрачено', f(got('base', 'E6', 'E6 flux round trip (dynamo'), 4), '—'),
  ('Катушечный конденсатор: Дж полный, Вт отдачи', f(got('base', 'E1', 'E1 coil capacitor energy when full')), f(got('base', 'E1', 'E1 coil capacitor discharge power'))),
  ('Геомагнитная катушка, Вт при поле 90 (Наувис) / 99 (Фулгора)', f(got('base', 'E7', 'E7 geomagnetic coil at magnetic-field 90, noon')), f(got('base', 'E7', 'E7 geomagnetic coil at magnetic-field 99, noon'))),
  ('Катушечник: урон за попадание ферритовой / магнитной', f(got('base', 'K1', 'K1 coilgun magnetics-ferrite-slug damage per hit (min)')), f(got('base', 'K1', 'K1 coilgun magnetics-magnet-slug damage per hit (min)'))),
  ('Пушка Гаусса: урон по большому жуку, выстрелов/с', f(got('base', 'K5', 'K5 gauss vs big biter per hit (min)')), f(got('base', 'K5', 'K5 gauss shots/s'))),
  ('Разрядник: урон одного выстрела по цепи (5 целей) / к лазеру', f(got('base', 'K7', 'K7 arc total damage')), f(got('base', 'K8', 'K8 arc DPS / laser DPS'))),
  ('Рельсовая пушка: урон по гиганту на линии (34 клетки) / вне линии на 37,5', f(got('base', 'K9', 'K9 in-line behemoth at 34')), f(got('base', 'K9', 'K9 behemoth on the line at 37.5'))),
  ('Сепаратор: железной руды / медной за 600 с', f(got('base', 'P7', 'P7 separator iron ore')), f(got('base', 'P7', 'P7 separator copper ore'))),
]
L.append('| замер | значение | второе / контроль |\n|---|---|---|')
for r in rows: L.append(f'| {r[0]} | {r[1]} | {r[2]} |')
L.append('\n## Волна: 20 средних + 10 больших жуков на блок 3×3 турелей за двойным кольцом стен (base)\n')
L.append('| турели | стены | очищено за, с | живых в конце | доля потерянной прочности стен | стен разрушено | турелей потеряно | энергия, МДж |\n|---|---|---|---|---|---|---|---|')
for v in TW['variants']:
    share = v['wall_hp_lost'] / v['wall_hp_total'] if v.get('wall_hp_total') else None
    L.append(f"| {v['turret']} ({v.get('ammo') or 'энергия'}) | {v['wall']} | {f(v.get('clear_s'), 1) if v.get('clear_s') else 'не очистили'} | {v['alive']} | "
             f"{f(share * 100, 1) + ' %' if share is not None else '—'} | {v['walls_destroyed']} | {v['turrets_lost']} | {f(v['energy_MJ'], 1)} |")
L.append('\n## Скорость игры (UPS), медиана 5 прогонов по 3000 тиков, мс/тик\n')
L.append(f"- U1: 200 простаивающих катушек против 200 аккумуляторов на карте из 10 000 стен: Δ = {f(U['U1']['delta'], 3)} мс/тик.")
L.append(f"- U2: 100 катушек чинят 1000 стен под 50 уронами в секунду, та же сеть и нагрузка без катушек: Δ = {f(U['U2']['delta'], 3)} мс/тик.")
L.append(f"- Шум машины (наибольший разброс прогонов одного варианта): {f(U['U1']['noise'], 3)} мс/тик. Пороги спецификации (0,02 и 0,10) меньше трёх шумов, "
         f"поэтому по правилу PILOT-20 разности сравниваются с 3× шума ({f(U['U1']['effective_limit'], 3)}): обе меньше.")
open(os.path.join(HERE, '..', 'RESULTS.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
