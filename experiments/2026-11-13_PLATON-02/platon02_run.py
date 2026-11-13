#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02: зёрна, задания и анализ мимикрии. Код PLATON-01 (мир, разбор, анализ) не меняется; законы-двойники
добавляет platon02_world. Ячейки: TS = «мимикрия» M (имена X, данные Y), TN = MN (буквы, данные Y); режимы free и forced.
  python3 platon02_run.py seeds --start 30001 --per-law 4 --out seeds_test.json   отбор зёрен по миру (R(X) ≥ 0,3 у всех голов)
  python3 platon02_run.py build --seeds SEEDS --out DIR
  python3 platon02_run.py analyze --tables T --journal J --out OUT.json            анализ PLATON-01 + априор X + проверки"""
import argparse, json, math, os, sys
import platon02_world as M
W = M.W
import platon_check as C      # noqa: E402
import platon_jobs as J       # noqa: E402
import platon_analyze as A    # noqa: E402

R_X_MIN = 0.3


def r_x_ok(inst):
    """Знакомый закон X явно не держится на строках каждой головы при именах S и N (R ≥ 0,3)."""
    for names in ('S', 'N'):
        idents = W.table_view(inst, 'T', names)[0]
        for k in range(4):
            rows = W.table_view(inst, 'T', names, k)[2]
            x = C.Claim(M.prior_in_names(inst, names), idents, rows, 'sel')
            if not x.valid or not C.R_measure(x.f, rows, idents, seed=f"sel|{inst['seed']}|{names}|{k}") >= R_X_MIN:
                return False
    return True


def cmd_seeds(a):
    out, skipped = [], []
    for li, law in enumerate(M.MIMIC_ORDER):
        s, got = a.start + 1000 * li, 0
        while got < a.per_law:
            inst = W.make_instance(s, law, heads=4)
            if r_x_ok(inst):
                out.append({'seed': s, 'law': law}); got += 1
            else:
                skipped.append({'seed': s, 'law': law})
            s += 1
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    json.dump(skipped, open(a.out.replace('.json', '_skipped.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'зёрен {len(out)}, пропущено по правилу R(X) ≥ {R_X_MIN}: {len(skipped)}')


def cmd_build(a):
    seeds = json.load(open(a.seeds, encoding='utf-8'))
    jobs, tables = J.build(seeds, 4, a.out, cells=['TS', 'TN'], variant='b', regimes=('free', 'forced'))
    print(f'заданий {len(jobs)}, таблиц {len(tables)} → {a.out}')


def mcnemar(x, y):
    b = sum(1 for u, v in zip(x, y) if u and not v); c = sum(1 for u, v in zip(x, y) if v and not u)
    return (A.binom_sf(b, b + c, 0.5) if b + c else 1.0), b, c


def cmd_analyze(a):
    sys.argv = ['platon_analyze', '--tables', a.tables, '--journal', a.journal, '--out', a.out]
    A.main()                                            # анализ PLATON-01 байт в байт (без Z-ячеек проверки PLATON-01 пусты)
    d = json.load(open(a.out, encoding='utf-8'))
    insts = {}
    for t in d['tables']:
        key = (t['seed'], t['law'])
        if key not in insts:
            insts[key] = W.make_instance(t['seed'], t['law'], heads=4)
        inst = insts[key]
        names = t['names']
        idents = W.table_view(inst, 'T', names)[0]
        own = [W.table_view(inst, 'T', names, k)[2] for k in range(4)]
        union = [r for o in own for r in o]
        for k, h in enumerate(t['heads']):
            h['is_prior'] = False
            if h.get('kind') == 'EXPR':
                cl = C.Claim(h['raw'], idents, own[k], f"p2|{h['job']}")
                px = C.Claim(M.prior_in_names(inst, names), idents, own[k], f"p2x|{h['job']}")
                ok, _, _ = C.agree(px, cl, union, f"p2a|{h['job']}")
                h['is_prior'] = bool(ok)
            h['category'] = ('Y' if h.get('holds') else ('X' if h['is_prior'] else
                             ('НЕТ' if h.get('kind') == 'NONE' else 'иное')))
        rep = int(t['rep'][1:]) - 1 if t.get('rep') else None
        t['rep_is_prior'] = bool(rep is not None and t['heads'][rep]['is_prior'])
        t['FC_X'] = bool(t['FC'] and t['rep_is_prior'])
    cell = lambda c, rg: sorted([t for t in d['tables'] if t['cell'] == c and t['regime'] == rg], key=lambda t: t['seed'])
    summ = {}
    for rg in ('free', 'forced'):
        for c, nm in (('TS', 'M'), ('TN', 'MN')):
            T = cell(c, rg); n = len(T)
            heads = [h for t in T for h in t['heads']]
            cats = {k: sum(1 for h in heads if h.get('category') == k) for k in ('Y', 'X', 'иное', 'НЕТ')}
            fcx = sum(t['FC_X'] for t in T); tc = sum(t['TC'] for t in T); fc = sum(t['FC'] for t in T)
            summ[f'{nm}_{rg}'] = {'n': n, 'TC_Y': tc, 'TC_ci95': A.cp_interval(tc, n), 'FC_any': fc, 'FC_X': fcx,
                                  'FC_X_ci95': A.cp_interval(fcx, n), 'FC_X_upper95': A.cp_upper_one_sided(fcx, n),
                                  'heads': len(heads), 'categories': cats,
                                  'none_consensus': sum(t['none_consensus'] for t in T),
                                  'conf_X_claims': (sum(h['confidence'] for h in heads if h.get('category') == 'X' and h.get('confidence') is not None)
                                                    / max(1, sum(1 for h in heads if h.get('category') == 'X' and h.get('confidence') is not None))),
                                  'lost': sum(t['n_lost'] for t in T)}
    Mf, MNf = cell('TS', 'free'), cell('TN', 'free')
    assert [t['seed'] for t in Mf] == [t['seed'] for t in MNf]
    n = len(cell('TS', 'forced'))
    p1 = A.binom_sf(summ['M_forced']['FC_X'], n, A.P0)
    p2 = A.binom_sf(summ['M_free']['FC_X'], len(Mf), A.P0)
    p3, b3, c3 = mcnemar([t['TC'] for t in MNf], [t['TC'] for t in Mf])
    rej = A.holm({'P1': p1, 'P2': p2, 'P3': p3})
    Ff, MNff = cell('TS', 'forced'), cell('TN', 'forced')
    p3f, b3f, c3f = mcnemar([t['TC'] for t in MNff], [t['TC'] for t in Ff])
    tests = {'P1': {'claim': 'FC_X в M, режим F > 0,05', 'k': summ['M_forced']['FC_X'], 'n': n, 'p': p1, 'rejected': rej['P1']},
             'P2': {'claim': 'FC_X в M, свободный режим > 0,05', 'k': summ['M_free']['FC_X'], 'n': len(Mf), 'p': p2,
                    'rejected': rej['P2'], 'upper95': summ['M_free']['FC_X_upper95'],
                    'rare': summ['M_free']['FC_X_upper95'] < A.EQUIV_UPPER},
             'P3': {'claim': 'TC_Y в MN > в M, свободный режим', 'b_MN_only': b3, 'c_M_only': c3, 'p': p3, 'rejected': rej['P3']},
             'P3F_descr': {'b_MN_only': b3f, 'c_M_only': c3f, 'p': p3f}}
    lost_share = sum(s['lost'] for s in summ.values()) / max(1, sum(s['heads'] for s in summ.values()))
    d['platon02'] = {'summary': summ, 'tests': tests, 'holm': rej, 'lost_share': lost_share}
    json.dump(d, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, v in summ.items():
        print(f"  {k}: TC_Y {v['TC_Y']}/{v['n']}, FC_X {v['FC_X']}, FC {v['FC_any']}, виды {v['categories']}, НЕТ-согл {v['none_consensus']}")
    for k, v in tests.items():
        print(f'  {k}: {v}')


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('seeds'); s.add_argument('--start', type=int, required=True); s.add_argument('--per-law', type=int, default=4)
    s.add_argument('--out', required=True)
    b = sub.add_parser('build'); b.add_argument('--seeds', required=True); b.add_argument('--out', required=True)
    z = sub.add_parser('analyze'); z.add_argument('--tables', required=True); z.add_argument('--journal', required=True)
    z.add_argument('--out', required=True)
    a = ap.parse_args()
    {'seeds': cmd_seeds, 'build': cmd_build, 'analyze': cmd_analyze}[a.cmd](a)


if __name__ == '__main__':
    main()
