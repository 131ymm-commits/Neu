#!/usr/bin/env python3
"""TRUST-02: сводка пилота или сухого прогона (results_trust_02.json в указанной папке) — для калибровки порогов.
Запуск: python3 pilot_summary.py pilot"""
import json
import os
import sys

import numpy as np

import exp_trust_02 as E

d = json.load(open(os.path.join(E.HERE, sys.argv[1] if len(sys.argv) > 1 else 'pilot', 'results_trust_02.json')))
th = d['theory']
for k in ('A', 'B', 'G'):
    t = th[k]
    print(f"мир {k}: точные {np.round(t['w_exact'], 4)}; ML−точн. {t['max_abs_ml_minus_exact']:.4f}; "
          f"масштаб {t['scale_exact']:.4f}; точн. {t['exact_exact']['acc']:.4f}; наивн. самообман "
          f"{t['exact_naive']['self_dec']:+.4f}, точн. {t['exact_naive']['acc']:.4f}")
    print(f"   опознаваемые точные {np.round(t['identifiable_exact'], 4)}; наивные {np.round(t['identifiable_naive'], 4)}")
g = th['G']
print(f"мир G: b* {g['b_star']:.4f}; w_G* {g['wG_star']:.4f} при честном {g['w_ref']:.4f} (доля {g['wG_star'] / g['w_ref']:.3f}); "
      f"честная формула при b*: самообман {g['exact_honest_formula_at_bstar']['self_dec']:+.4f}, "
      f"точность {g['exact_honest_formula_at_bstar']['acc']:.4f}")
for r in d['runs']:
    a = r['arm']; spec = E.ARMS[a]; world = E.WORLDS[spec['world']].with_b(r['b_final'])
    wex = np.array(th[spec['world']]['w_exact']) if spec['world'] != 'G' else world.exact_weights()
    idf = world.identifiable(r['w_final']); ide = world.identifiable(wex)
    print(f"\n{a} (зерно {r['seed']}): самообман {r['exact']['self_dec']:+.4f} (снимки {r['self_dec_snap_mean']:+.4f}); "
          f"точность {r['exact']['acc']:.4f}; ECE {r['exact']['ece']:.4f}; масштаб/точный {world.scale(r['w_final']) / world.scale(wex):.3f}; "
          f"N_eff {r['neff_late']:.1f}; SD(logF) {r['sdF_late']:.2f}; b {r['b_final']:.4f}")
    print(f"   опознаваемые {np.round(idf, 3)} против точных {np.round(ide, 3)}; MAD {np.abs(idf - ide).mean():.4f}")
    if r['exact_shifted']:
        print(f"   после сдвига: самообман {r['exact_shifted']['self_dec']:+.4f}")
    tr = r['traj']
    print('   ход:', ' '.join(f"{t['g']}:{t['self_dec']:+.4f}/b{t['b']:.2f}/s{world.scale(t['w']) / world.scale(wex):.2f}"
                            for t in tr[::15] + [tr[-1]]))
