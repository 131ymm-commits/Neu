# EVO-06: кривые T_g и C_g по поколениям (ворота 1 CLAUDE.md — динамика, не только итог). Использование: python3 evo06_curves.py [каталог] [шаг]
import sys, json, glob
RUNS = sys.argv[1] if len(sys.argv) > 1 else 'pilot'; STEP = int(sys.argv[2]) if len(sys.argv) > 2 else 10
for f in sorted(glob.glob(f'{RUNS}/*.json')):
    d = json.load(open(f))
    if 'hist' not in d: continue
    h = d['hist']; gs = list(range(0, len(h), STEP)) + ([len(h) - 1] if (len(h) - 1) % STEP else [])
    print(f"{d['task']} {d['arm']:10s} s{d['seed']}" + (f" tour{d['tour']}" if d.get('tour', 5) != 5 else '') + f"  {d['sec']} с")
    print('  g   ' + ' '.join(f'{g:5d}' for g in gs))
    print('  T   ' + ' '.join(f'{h[g]["true"]:5.2f}' for g in gs))
    print('  C   ' + ' '.join(f'{h[g]["claimed"]:5.2f}' for g in gs))
    print('  Cf  ' + ' '.join(f'{h[g]["claimed_fresh"]:5.2f}' for g in gs))
    print('  age ' + ' '.join(f'{h[g]["elite_age"]:5d}' for g in gs))
