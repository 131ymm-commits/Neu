#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02: сухой прогон на заглушках (ожидания записаны до прогона).
  prior  — при именах S голова называет X, при буквах — Y: ждём в слое A FC_X(M) = nA в обоих режимах, TC(MN) = nA,
           P1A и P2A отвергнуты, вердикт «гипотеза подтверждена»;
  reader — всегда Y: ждём FC_X = 0 везде, P1A и P2A не отвергнуты; при nA = 14 «редко» недостижимо
           (граница при 0 из 14 — 0,193), поэтому вердикт «не показано» (совет 46: порог через cp_upper при фактическом n).
На раскладке теста (слой A — 6 на закон, 42 экземпляра; слой B — 4 на закон, 12; зёрна 87001+, вне теста и пилотов):
  reader42 — всегда Y: ждём «редко» в обоих режимах слоя A и вердикт «гипотеза опровергнута узко»;
  lossy    — как reader42, но у головы h1 во всех таблицах M режима F слоя A нет записи (потеря 25 %):
             ждём вердикт «не определено (потери …)»."""
import json, shutil, subprocess, sys
from pathlib import Path
import platon02_world as M
W = M.W
HERE = Path(__file__).resolve().parent; DRY = HERE / 'dry'
SEEDS = [{'seed': 85001 + i, 'law': M.MIMIC_ORDER[i % 10]} for i in range(20)]
sys.argv = [sys.argv[0]]
import platon02_run as R        # noqa: E402


SEEDS42 = [{'seed': 87001 + 100 * li + j, 'law': law} for li, law in enumerate(M.MIMIC_ORDER)
           for j in range(6 if R.layer_of(law) == 'A' else 4)]


def run_set(tag, seeds, strats, bad):
    base = DRY / tag
    jobs, tables = R.J.build(seeds, 4, base / 'jobs', cells=['TS', 'TN'], variant='b', regimes=('free', 'forced'))
    tbs = {t['table']: t for t in tables}
    for strat in strats:
        jd = base / strat / 'journal'; jd.mkdir(parents=True)
        by = {}
        for j in jobs:
            tb = tbs[j['id'].rsplit('|', 1)[0]]; inst = W.make_instance(tb['seed'], tb['law'], heads=4)
            if (strat == 'lossy' and tb['cell'] == 'TS' and tb['regime'] == 'forced' and R.layer_of(tb['law']) == 'A'
                    and j['id'].endswith('|h1')):
                continue                                   # потеря: записи нет (NO_RECORD)
            ans = (M.prior_in_names(inst, 'S') if (strat == 'prior' and tb['names'] == 'S') else W.inv_in_names(inst, tb['names']))
            by.setdefault(j['task'], []).append({'task': j['task'], 'job': j['id'], 'arm': j['arm'], 'attempt': 1, 'role': 'основной',
                                                 'outcome': 'годный', 'final': 'годный', 'answer': {'invariant': ans, 'confidence': 0.8},
                                                 'usage': {'inp': 1, 'out': 1, 'cost_usd': 0.0}})
        for t, recs in by.items():
            (jd / f'{t}.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')
        out = base / strat / 'dry_out.json'
        r = subprocess.run([sys.executable, str(HERE / 'platon02_run.py'), 'analyze', '--tables', str(base / 'jobs' / 'tables.json'),
                            '--journal', str(jd), '--out', str(out)], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-2000:]); bad.append(strat); continue
        p = json.load(open(out, encoding='utf-8'))['platon02']; s, t = p['summary'], p['tests']
        nA = s['M_free_A']['n']
        if strat == 'prior':
            ok = (s['M_forced_A']['FC_X'] == nA and s['M_free_A']['FC_X'] == nA and s['MN_free_A']['TC_Y'] == nA
                  and t['P1A']['rejected'] and t['P2A']['rejected'] and t['verdict'].startswith('гипотеза подтверждена'))
        elif strat == 'reader':
            ok = (all(v['FC_X'] == 0 for v in s.values()) and t['rare_A_both'] is False and not t['P1A']['rejected']
                  and not t['P2A']['rejected'])
            # при nA = 14 «редко» недостижимо (граница при 0 из 14 — 0,193 > 0,15): ждём «не показано»
            ok = ok and t['verdict'] == 'не показано'
        elif strat == 'reader42':
            ok = (nA == 42 and s['M_free_B']['n'] == 12 and all(v['FC_X'] == 0 for v in s.values()) and t['rare_A_both'] is True
                  and not t['P1A']['rejected'] and not t['P2A']['rejected'] and t['lost_bad_cells'] == []
                  and t['verdict'].startswith('гипотеза опровергнута узко') and t['verdict_P2A'] == 'P2A не отвергнута')
        else:   # lossy
            ok = (t['lost_bad_cells'] == ['M_forced_A'] and t['verdict'].startswith('не определено (потери')
                  and t['verdict_P2A'] == 'не определено')
        print(strat, '✓' if ok else '✗', 'nA', nA, {k: (v['TC_Y'], v['FC_X'], v['lost']) for k, v in s.items() if k.endswith('_A')},
              t['P1A']['rejected'], t['P2A']['rejected'], t['rare_A_both'], t['verdict'][:60])
        if not ok:
            bad.append(strat)


def main():
    if DRY.exists():
        shutil.rmtree(DRY)
    bad = []
    run_set('n14', SEEDS, ('prior', 'reader'), bad)
    run_set('n42', SEEDS42, ('reader42', 'lossy'), bad)
    json.dump({'bad': bad}, open(DRY / 'dry_summary.json', 'w')); print('несовпадений:', bad); sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
