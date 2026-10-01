"""Таблица замеров для README из JSON результатов (числа не набираются руками; CLAUDE.md: каждое число — из json).
Вход: test_results.json, ups_results.json, tw_results_base.json. Выход: RESULTS.md (вставляется в README ссылкой).
Запуск: python3 tools/report.py [путь к RESULTS.md]"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'RESULTS.md')
R = json.load(open(os.path.join(HERE, 'test_results.json'), encoding='utf-8'))
U = json.load(open(os.path.join(HERE, 'ups_results.json'), encoding='utf-8'))
TW = json.load(open(os.path.join(HERE, 'tw_results_base.json'), encoding='utf-8'))

def got(cfg, test, name_start):
    for r in R['records']:
        if r.get('kind', 'mod') == 'mod' and r.get('config') == cfg and r.get('test') == test and str(r.get('name')).startswith(name_start):
            return r.get('got')
    raise KeyError((cfg, test, name_start))

def f(x, nd=2):
    if isinstance(x, (int, float)):
        x = round(float(x), nd)
        return ('%d' % x) if x == int(x) else (('%.' + str(nd) + 'f') % x).rstrip('0').rstrip('.')
    return str(x)

L = []
# в счёт идут только проверки мода (kind = "mod"); самопроверки стенда и справочные записи — отдельно (tests.py: KINDS)
T = R['totals']
mod_all = sum(v['mod_pass'] + v['mod_fail'] for v in T.values())
L.append('# Magnetics — замеры на сервере Factorio 2.0.77 (сгенерировано tools/report.py из JSON)\n')
L.append(f"Проверок мода всего: **{mod_all}**, провалов: **{sum(v['mod_fail'] for v in T.values())}** "
         f"(base {T['base']['mod_pass']}, base+quality {T['bq']['mod_pass']}, base+elevated-rails {T['be']['mod_pass']}, "
         f"Space Age {T['sa']['mod_pass']}, файлы {T['files']['mod_pass']}). Из них независимых (ожидание из FINAL_SPEC вручную, "
         f"из ванили или замер в игре) **{sum(v['mod_independent'] for v in T.values())}**, согласованность мода с expected.lua (тот же "
         f"файл spec.py) {sum(v['mod_consistency_expected_lua'] for v in T.values())}. Самопроверок стенда "
         f"{sum(v['harness_pass'] + v['harness_fail'] for v in T.values())} (провалов {sum(v['harness_fail'] for v in T.values())}), "
         f"справочных записей {sum(v['info'] for v in T.values())} — в счёт не входят.\n")
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
  ('Рельсовая пушка: урон по гиганту на линии (34 клетки) / за концом линии на 38,6', f(got('base', 'K9', 'K9 in-line behemoth at 34')), f(got('base', 'K9', 'K9 behemoth on the line at 38.6'))),
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
L.append(f"- Шум машины (наибольший разброс прогонов одного контрольного варианта: {', '.join(U.get('noise_from', []))}): {f(U['U1']['noise'], 3)} мс/тик.")
for k in ('U1', 'U2'):
    v = U[k]
    rule = (f"порог спецификации {f(v['limit'], 3)} различим (≥ 3× шума)" if v['resolvable'] else
            f"порог спецификации {f(v['limit'], 3)} меньше трёх шумов, по правилу PILOT-20 сравнение с 3× шума = {f(v['effective_limit'], 3)}")
    L.append(f"- {k}: Δ {f(v['delta'], 3)} мс/тик; {rule}: {'проходит' if v['ok'] else '**не проходит**'}.")
open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
