# EVO-06, ретроспектива на готовых данных (PREREG-EVO-06.md §3, §7.5): воспроизводит числа pilot/retro_EVO01_RANDOM16.log
# из json EVO-01 (RANDOM16 = SAME16 по правилу) и EVO-05 (BASE). Ничего не запускает, только читает runs/*.json.
# Правила — те же, что в evo06_analyze.py: окно 121–150 = hist[-30:], «раннее» окно 11–40 = hist[11:41];
# ставка Правого: drift = mean(C−T | 121–150) − mean(C−T | 11–40) > 0; вырожденность: final_true < 0,1;
# «давления не было»: mean(T | 121–150) ≤ mean(T | 0–9).
# Запуск из каталога опыта: python3 retro_evo01_random16.py [каталог EVO-01] [каталог EVO-05]
import sys, json, glob
import numpy as np

EVO01 = sys.argv[1] if len(sys.argv) > 1 else '../2026-09-26_EVO-01'
EVO05 = sys.argv[2] if len(sys.argv) > 2 else '../2026-09-26_EVO-05'
WINDOW = 30


def measures(d):
    h = d['hist']; T = np.array([x['true'] for x in h]); C = np.array([x['claimed'] for x in h])
    late = float(np.mean((C - T)[-WINDOW:])); early = float(np.mean((C - T)[11:41]))
    return dict(drift=late - early, signed_late=late, degenerate=h[-1]['true'] < 0.1,
                no_pressure=float(np.mean(T[-WINDOW:])) <= float(np.mean(T[:10])))


def load(exp, arm):
    R = [json.load(open(f)) for f in sorted(glob.glob(f'{exp}/runs/*_{arm}_s*.json'))]
    return [(d['task'], d['seed'], measures(d)) for d in R if d['arm'] == arm]


rows = load(EVO01, 'RANDOM16')
dr = np.array([m['drift'] for _, _, m in rows])
print('прогонов RANDOM16:', len(rows))
print(f'ставка Правого (C−T 121–150 минус 11–40 > 0): побед {int((dr > 0).sum())}/{len(rows)}, ничьих {int((dr == 0).sum())}; медиана разности {np.median(dr):.4f}')
for t in sorted({t for t, _, _ in rows}):
    m = [m for tt, _, m in rows if tt == t]
    print(f'  {t}: рост C−T в {sum(x["drift"] > 0 for x in m)}/{len(m)}, медиана C−T 121–150 {np.median([x["signed_late"] for x in m]):.4f};'
          f' вырожд. (T<0,1) {sum(x["degenerate"] for x in m)}/{len(m)}; «давления не было» {sum(x["no_pressure"] for x in m)}/{len(m)}')
print('всего вырожденных:', sum(m['degenerate'] for _, _, m in rows), 'из', len(rows), '; без давления:', sum(m['no_pressure'] for _, _, m in rows))
base = load(EVO05, 'BASE')
print(f'EVO-05 BASE: прогонов {len(base)}, вырожд. {sum(m["degenerate"] for _, _, m in base)}, без давления {sum(m["no_pressure"] for _, _, m in base)},'
      f' рост C−T в {sum(m["drift"] > 0 for _, _, m in base)}/{len(base)}')
