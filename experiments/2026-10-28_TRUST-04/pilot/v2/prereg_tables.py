#!/usr/bin/env python3
"""TRUST-04: таблицы для PREREG §3 и §6 из pilot/v2/pilot_calib2.json — числа в предрегистрацию идут командой, не
перепечаткой (ворота 5). Запуск из папки опыта: python3 pilot/v2/prereg_tables.py 95 > pilot/v2/prereg_tables.md
(аргумент — выбранный уровень ДИ эквивалентности, 90 или 95)."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, EXP)
import exp_trust_04 as E  # noqa: E402

C = json.load(open(os.path.join(HERE, 'pilot_calib2.json')))
okey = lambda k: (k[0], int(re.sub(r'\D', '', k) or 0), k)
LEV = int(sys.argv[1]) if len(sys.argv) > 1 else 95
f = lambda x, d=3: (f'{x:.{d}f}'.replace('.', ',').replace('-', '−'))
g = lambda x: (f'{x:.2g}' if x < 0.001 else f'{x:.4f}').replace('.', ',')

print('### Пилот v2: руки (зёрна 1100–1109; `pilot/v2/pilot_calib2.json`, ключ desc)\n')
print('| Рука | u, среднее ± SD | SD шага среднего группы | R | срывов из 10 | внутригрупповая часть Прайса |')
print('|---|---|---|---|---|---|')
for a, v in C['desc'].items():
    nb = v['n_break'] if (E.ARMS[a]['sig'] == E.SIG and E.ARMS[a]['sig_g'] == E.SIG) else '—'
    print(f"| {a} | {f(v['u_mean'])} ± {f(v['u_sd'])} | {f(v['step_sd'], 4)} | {f(v['R'])} | {nb} | {f(v['price_within'], 5)} |")
print('\n- Срыв — по окну SD w_G между группами > 0,5 или V_внутри > 0,1. Порог V_внутри задан для σ = 0,04, поэтому у рук ×5 и COUNCIL_SIGN — «—».')
print('\n### Предсказания: порог, мощность, ложный уровень (20 тестовых зёрен)\n')
print('| | Вид | Порог | Мощность | При SD × 1,5 | Ложный уровень | В пилоте |')
print('|---|---|---|---|---|---|---|')
for k, v in sorted(C['confirm'].items(), key=lambda kv: okey(kv[0])):
    if v['kind'] == 'эквивалентность':
        print(f"| {k} | эквивалентность ±0,1, ДИ {LEV} % | — | {f(v[f'power_{LEV}'])} | {f(v[f'power_sd15_{LEV}'])} | "
              f"{g(v[f'false_level_{LEV}'])} | разность {f(v['diff'], 4)} |")
    else:
        thr = v['k'] if isinstance(v['k'], str) else f"{v['k']} из 20"
        print(f"| {k} | {v['kind']} | {thr} | {f(v['power'])} | {f(v['power_sd15'])} | {g(v['false_level'])} | "
              f"{v['pilot_count']} из {v.get('pilot_n_nb', 10)}{' — ' + v['flag'] if v.get('flag') else ''} |")
print('\n### Сводные исходы: вес в битах при подтверждении\n')
print('| Сводный | Части | Ложный уровень | Мощность | При SD × 1,5 | Вес |')
print('|---|---|---|---|---|---|')
for c, parts in C['composites'].items():
    b = C['bits'][str(LEV)][c]
    print(f"| {c} | {', '.join(parts)} | {g(b['false_level'])} | {f(b['power'])} | {f(b['power_sd15'])} | {f(b['bits'], 1)} бита |")
B = C['bits'][str(LEV)]
print(f"\n- Сумма ложных уровней (Бонферрони): по всем {len(C['confirm'])} частям основной семьи — {g(B['family_sum_parts'])}; "
      f"по шести сводным — {g(B['family_sum_composites'])}; по разведке (без EB6) — {g(B['expl_sum'])}.")
print('\n### Разведка (пилот)\n')
for k, v in C['explore'].items():
    if k == 'EB6':
        print(f"- **EB6** (правило — DEMES_MIG и DEMES_SIG5): |ū − (1 − R̄)| — {f(v['gap_MIG'], 4)} и {f(v['gap_SIG5'], 4)}; доля прохождений "
              f"при 20 зёрнах с возвращением из 10 пилотных — {f(v['boot_pass'])}. Описательно: в пределах 0,1 у {v['n_within_01']} из "
              f"{len(v['arms'])} рук; ρ Спирмена {f(v['spearman'])} (p двусторонний {g(v['spearman_p_two_sided'])}). По рукам: " +
              '; '.join(f"{a} {f(uu)} / {f(r)}" for a, uu, r in zip(v['arms'], v['u'], v['one_minus_R'])) + ' (u / 1 − R).')
    elif v['kind'] == 'эквивалентность':
        print(f"- **{k}:** разность {f(v['diff'], 4)}; мощность {f(v[f'power_{LEV}'])} ({f(v[f'power_sd15_{LEV}'])}); ложный уровень {g(v[f'false_level_{LEV}'])}.")
    elif k == 'EB1':
        print(f"- **EB1:** SD u {f(v['sd_IND'], 4)} против {f(v['sd_base'], 4)} (отношение {f(v['ratio'], 2)}); мощность {f(v['power'])} "
              f"(при отношении / 1,5 — {f(v['power_sd15'])}); ложный уровень {g(v['false_level'])}.")
    else:
        print(f"- **{k}:** {v['pair'][0]} < {v['pair'][1]} в ≥ {v['k']} из 20; мощность {f(v['power'])} ({f(v['power_sd15'])}); "
              f"ложный уровень {g(v['false_level'])}; в пилоте {v['pilot_count']} из 10.")

print('\n### Пилот: DEMES_NOWITHIN по зёрнам и независимая реализация\n')
print('- **DEMES_NOWITHIN по зёрнам** (`pilot/v2/results_trust_04_A.json`):\n')
A = {r['seed']: r['final'] for r in json.load(open(os.path.join(HERE, 'results_trust_04_A.json')))['runs'] if r['arm'] == 'DEMES_NOWITHIN'}
my, far = (0.9873, 0.6891)
print('| Зерно | u | SD w_G между группами | V_внутри | срыв |')
print('|---|---|---|---|---|')
for sd, fin in sorted(A.items()):
    br = fin['wG_sd_groups'] > 0.5 or fin['V_within'] > 0.1
    print(f"| {sd} | {f((fin['wG'] - far) / (my - far))} | {f(fin['wG_sd_groups'])} | {f(fin['V_within'], 4)} | {'да' if br else 'нет'} |")
ind = {a: v['u_indep'] for a, v in C['confirm'].items() if a.startswith('C_') and 'u_indep' in v}
print('\n- **Независимая реализация, пилот 1200–1209,** u по замороженной теории (среднее; по зёрнам): ' +
      '; '.join(f"{a[2:]} {f(sum(x) / len(x))} ({', '.join(f(y) for y in x)})" for a, x in ind.items()) + '.')
log = open(os.path.join(HERE, 'compare_v1.log'), encoding='utf-8').read().strip().splitlines()
print('- **Сверка пилота v1 с v2** (`pilot/v2/compare_v1.log`): ' + '; '.join(x.strip().rstrip('.') for x in log[:2]) + '. ' + log[-1].replace('ИТОГ: ', 'Итог: ').replace('нынешним кодом', 'кодом пилота v2 (602fa27)') + '.')

# ---- после третьей проверки по трём линзам: динамика пилота, шаг MYOPIC, расширенный пилот DEMES_NOWITHIN ----
import numpy as np  # noqa: E402
RUNS = {}
for part in ('A', 'B'):
    for r in json.load(open(os.path.join(HERE, f'results_trust_04_{part}.json')))['runs']:
        RUNS[(r['seed'], r['arm'])] = r
FZ = {'base': (0.9873, 0.6891), 'r075': (0.5768, 0.3897), 'r095': (1.7134, 1.1968), 'b03': (1.2221, 0.9622), 'b09': (0.8328, 0.5372)}
HALF = {}
print('\n### Пилот v2: динамика u (средние по 10 зёрнам; `pilot/v2/results_trust_04_*.json`, поле traj)\n')
print('| Рука | 0–500 | 500–1000 | 1000–1500 | 1500–2000 | 2000–2500 | 2500–3000 | 2-я минус 1-я половина окна, ср. ± SD | зёрен < 0 |')
print('|---|---|---|---|---|---|---|---|---|')
for a in E.ARMS:
    my_, far_ = FZ[E.ARMS[a]['world']]; seg = np.zeros((10, 6)); half = []
    for i, sd in enumerate(E.PILOT_SEEDS):
        tu = [(t['g'], (t['wG'] - far_) / (my_ - far_)) for t in RUNS[(sd, a)]['traj']]
        for j in range(6):
            seg[i, j] = np.mean([x for gg, x in tu if min(gg // 500, 5) == j])
        half.append(np.mean([x for gg, x in tu if gg >= 2000]) - np.mean([x for gg, x in tu if 1000 <= gg < 2000]))
    half = np.array(half); HALF[a] = half
    print(f"| {a} | " + ' | '.join(f(x) for x in seg.mean(0)) + f" | {f(half.mean())} ± {f(half.std(ddof=1))} | {int((half < 0).sum())} |")
big = [(a, h) for a, h in HALF.items() if abs(h.mean()) > 2 * h.std(ddof=1) / np.sqrt(len(h))]
print('\n- Средняя разность половин окна больше двух стандартных ошибок у: ' + '; '.join(
    f"{a} {f(h.mean())} (зёрен < 0: {int((h < 0).sum())} из 10)" for a, h in big) + '.')
print('\n### Шаг среднего у одной группы из 400 (пилот v2, снимки g ≥ 1000)\n')
print('| Рука | SD шага среднего | SD сдвига от отбора (s_within) | √((V_внутри + σ²)/400) |')
print('|---|---|---|---|')
for a in ('MYOPIC', 'MYOPIC_r075', 'MYOPIC_r095', 'MYOPIC_b03', 'MYOPIC_b09'):
    sw = [np.std([t['s_within'] for t in RUNS[(sd, a)]['traj'] if t['g'] >= 1000], ddof=1) for sd in E.PILOT_SEEDS]
    st = [RUNS[(sd, a)]['final']['step_sd'] for sd in E.PILOT_SEEDS]
    dr = [np.sqrt((RUNS[(sd, a)]['final']['V_within'] + E.SIG ** 2) / 400) for sd in E.PILOT_SEEDS]
    print(f"| {a} | {f(np.mean(st), 4)} | {f(np.mean(sw), 4)} | {f(np.mean(dr), 4)} |")
A15c = C['confirm']['A15']
print('\n### DEMES_NOWITHIN: расширенный пилот (1300–1319, `pilot/v2b/`) вместе с 1100–1109\n')
V2B = json.load(open(os.path.join(os.path.dirname(HERE), 'v2b', 'results_nowithin_1300.json')))['runs']
bk = [(r['seed'], r['final']) for r in V2B if r['final']['wG_sd_groups'] > 0.5 or r['final']['V_within'] > 0.1]
oku = [abs((r['final']['wG'] - 0.6891) / (0.9873 - 0.6891)) for r in V2B if not (r['final']['wG_sd_groups'] > 0.5 or r['final']['V_within'] > 0.1)]
print(f"- В 1300–1319 срывов {len(bk)} из 20: " + '; '.join(f"{sd} (u {f((fi['wG'] - 0.6891) / (0.9873 - 0.6891))}, SD между группами "
      f"{f(fi['wG_sd_groups'])}, V_внутри {f(fi['V_within'], 4)})" for sd, fi in bk) +
      f". У {len(oku)} зёрен без срыва наибольшее |u| — {f(max(oku), 4)}.")
print(f"- Всего {A15c['breakdowns']} срыва из {A15c['n_pilot']}: q̂ = {f(A15c['q'])}, верхняя 95 % граница Клоппера–Пирсона — {f(A15c['q_cp_upper'])}.")
print(f"- Мощность A15 (n_min = {A15c['n_min']}): при q̂ — {f(A15c['power'])}; при верхней границе q и SD × 1,5 — {f(A15c['power_sd15'])}; "
      f"предсказательная (q ~ Beta({1 + A15c['breakdowns']}; {1 + A15c['n_pilot'] - A15c['breakdowns']})) — {f(A15c['power_predictive'])}; "
      f"при q = 0,1 — {f(A15c['power_q01'])}, при q = 0,3 — {f(A15c['power_q03'])}.")
E6 = C['explore']['EB6']
print(f"- EB6 по новому правилу: |ū − (1 − R̄)| у DEMES_MIG {f(E6['gap_MIG'], 4)}, у DEMES_SIG5 {f(E6['gap_SIG5'], 4)}; "
      f"доля прохождений при 20 зёрнах с возвращением из 10 пилотных — {f(E6['boot_pass'])}.")
