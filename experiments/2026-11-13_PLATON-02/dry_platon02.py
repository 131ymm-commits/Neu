#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02: сухой прогон на заглушках (ожидания записаны до прогона).
  prior  — при именах S голова называет X, при буквах — Y: ждём в слое A FC_X(M) = nA в обоих режимах, TC(MN) = nA,
           P1A и P2A отвергнуты, вердикт «гипотеза подтверждена»;
  reader — всегда Y: ждём FC_X = 0 везде, P1A и P2A не отвергнуты; при nA = 14 «редко» недостижимо
           (граница при 0 из 14 — 0,193), поэтому вердикт «не показано» (совет 46: порог через cp_upper при фактическом n)."""
import json, shutil, subprocess, sys
from pathlib import Path
import platon02_world as M
W = M.W
HERE = Path(__file__).resolve().parent; DRY = HERE / 'dry'
SEEDS = [{'seed': 85001 + i, 'law': M.MIMIC_ORDER[i % 10]} for i in range(20)]
sys.argv = [sys.argv[0]]
import platon02_run as R        # noqa: E402


def main():
    if DRY.exists():
        shutil.rmtree(DRY)
    jobs, tables = R.J.build(SEEDS, 4, DRY / 'jobs', cells=['TS', 'TN'], variant='b', regimes=('free', 'forced'))
    tbs = {t['table']: t for t in tables}; bad = []
    for strat in ('prior', 'reader'):
        jd = DRY / strat / 'journal'; jd.mkdir(parents=True)
        by = {}
        for j in jobs:
            tb = tbs[j['id'].rsplit('|', 1)[0]]; inst = W.make_instance(tb['seed'], tb['law'], heads=4)
            ans = (M.prior_in_names(inst, 'S') if (strat == 'prior' and tb['names'] == 'S') else W.inv_in_names(inst, tb['names']))
            by.setdefault(j['task'], []).append({'task': j['task'], 'job': j['id'], 'arm': j['arm'], 'attempt': 1, 'role': 'основной',
                                                 'outcome': 'годный', 'final': 'годный', 'answer': {'invariant': ans, 'confidence': 0.8},
                                                 'usage': {'inp': 1, 'out': 1, 'cost_usd': 0.0}})
        for t, recs in by.items():
            (jd / f'{t}.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')
        out = DRY / strat / 'dry_out.json'
        r = subprocess.run([sys.executable, str(HERE / 'platon02_run.py'), 'analyze', '--tables', str(DRY / 'jobs' / 'tables.json'),
                            '--journal', str(jd), '--out', str(out)], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-2000:]); bad.append(strat); continue
        p = json.load(open(out, encoding='utf-8'))['platon02']; s, t = p['summary'], p['tests']
        nA = s['M_free_A']['n']
        if strat == 'prior':
            ok = (s['M_forced_A']['FC_X'] == nA and s['M_free_A']['FC_X'] == nA and s['MN_free_A']['TC_Y'] == nA
                  and t['P1A']['rejected'] and t['P2A']['rejected'] and t['verdict'].startswith('гипотеза подтверждена'))
        else:
            ok = (all(v['FC_X'] == 0 for v in s.values()) and t['rare_A_both'] is False and not t['P1A']['rejected']
                  and not t['P2A']['rejected'])
            # при nA = 14 «редко» недостижимо (граница при 0 из 14 — 0,193 > 0,15): ждём «не показано»
            ok = ok and t['verdict'] == 'не показано'
        print(strat, '✓' if ok else '✗', 'nA', nA, {k: (v['TC_Y'], v['FC_X']) for k, v in s.items() if k.endswith('_A')},
              t['P1A']['rejected'], t['P2A']['rejected'], t['rare_A_both'], t['verdict'][:40])
        if not ok:
            bad.append(strat)
    json.dump({'bad': bad}, open(DRY / 'dry_summary.json', 'w')); print('несовпадений:', bad); sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
