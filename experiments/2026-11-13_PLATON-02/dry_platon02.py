#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02: сухой прогон на заглушках (ожидания записаны до прогона).
  prior  — при именах S голова называет X (знакомый закон), при буквах — Y: ждём FC_X(M) = n в обоих режимах,
           TC(MN) = n, TC(M) = 0 → P1, P2, P3 отвергнуты;
  reader — всегда Y: ждём TC = n везде, FC_X = 0 → P1, P2, P3 не отвергнуты, P2 «редко»."""
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
        p = json.load(open(out, encoding='utf-8'))['platon02']; s, t = p['summary'], p['tests']; n = len(SEEDS)
        if strat == 'prior':
            ok = (s['M_forced']['FC_X'] == n and s['M_free']['FC_X'] == n and s['MN_free']['TC_Y'] == n and s['M_free']['TC_Y'] == 0
                  and t['P1']['rejected'] and t['P2']['rejected'] and t['P3']['rejected'])
        else:
            ok = (all(s[k]['TC_Y'] == n and s[k]['FC_X'] == 0 for k in s) and not t['P1']['rejected'] and not t['P2']['rejected']
                  and not t['P3']['rejected'] and t['P2']['rare'])
        print(strat, '✓' if ok else '✗', {k: (v['TC_Y'], v['FC_X']) for k, v in s.items()}, {k: v.get('rejected') for k, v in t.items()})
        if not ok:
            bad.append(strat)
    json.dump({'bad': bad}, open(DRY / 'dry_summary.json', 'w')); print('несовпадений:', bad); sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
