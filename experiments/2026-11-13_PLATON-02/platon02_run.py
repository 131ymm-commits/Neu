#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02: зёрна, задания и анализ мимикрии. Код PLATON-01 (мир, разбор, анализ) не меняется; законы-двойники
добавляет platon02_world. Ячейки: TS = «мимикрия» M (имена X, данные Y), TN = MN (буквы, данные Y); режимы free и forced.
  python3 platon02_run.py seeds --start 30001 --per-law 4 --out seeds_test.json   отбор зёрен по миру (R(X) ≥ 0,3 у всех голов)
  python3 platon02_run.py build --seeds SEEDS --out DIR
  python3 platon02_run.py analyze --tables T --journal J --out OUT.json            анализ PLATON-01 + априор X + проверки"""
import argparse, json, math, os, sys
import numpy as np
import platon02_world as M
W = M.W
import platon_check as C      # noqa: E402
import platon_jobs as J       # noqa: E402
import platon_analyze as A    # noqa: E402

R_X_MIN = 0.3


def layer_of(law):
    """Слой по форме канонического X (совет 46, п. б): A — одночлен (нет сложения или вычитания верхнего уровня
    в выражении после раскрытия корня ast), B — в X есть сумма. Вычисляется кодом из W.LAWS, без пилота."""
    import ast
    e = W.LAWS[law]['prior'](W.LAWS[law]['params'](__import__('random').Random(0)))
    def has_sum(n):
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)):
            return True
        return any(has_sum(c) for c in ast.iter_child_nodes(n))
    return 'B' if has_sum(ast.parse(e, mode='eval')) else 'A'


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
        need = a.per_law_a if (a.per_law_a and layer_of(law) == 'A') else a.per_law
        while got < need:
            inst = W.make_instance(s, law, heads=4)
            if r_x_ok(inst):
                out.append({'seed': s, 'law': law}); got += 1
            else:
                skipped.append({'seed': s, 'law': law})
            s += 1
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    json.dump(skipped, open(a.out.replace('.json', '_skipped.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'зёрен {len(out)}, пропущено по правилу R(X) ≥ {R_X_MIN}: {len(skipped)}')


def cmd_check(a):
    """Совет 46, п. в: X ≠ Y на тех же строках, что использует analyze (объединение строк четырёх голов ячейки)."""
    seeds = json.load(open(a.seeds, encoding='utf-8')); bad = []
    for e in seeds:
        inst = W.make_instance(e['seed'], e['law'], heads=4)
        for names in ('S', 'N'):
            idents = W.table_view(inst, 'T', names)[0]
            own = [W.table_view(inst, 'T', names, k)[2] for k in range(4)]
            union = [r for o in own for r in o]
            x = C.Claim(M.prior_in_names(inst, names), idents, own[0], 'chk')
            y = C.Claim(W.inv_in_names(inst, names), idents, own[0], 'chky')
            ok, _, _ = C.agree(x, y, union, f"chk|{e['seed']}|{names}")
            if ok:
                bad.append((e['seed'], e['law'], names))
    layers = {}
    for e in seeds:
        layers.setdefault(layer_of(e['law']), set()).add(e['law'])
    print('X равносилен Y на строках анализа:', bad or 'нигде', '| слои:', {k: sorted(v) for k, v in layers.items()})
    sys.exit(1 if bad else 0)


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
    for t in d['tables']:
        t['layer'] = layer_of(t['law'])
    cell = lambda c, rg, L=None: sorted([t for t in d['tables'] if t['cell'] == c and t['regime'] == rg and (L is None or t['layer'] == L)],
                                        key=lambda t: t['seed'])

    def boot(vals_by_inst, label):
        g = C.gen(f'p2boot|{label}'); n = len(vals_by_inst); out = []
        for _ in range(10000):
            idx = g.integers(0, n, size=n)
            out.append(sum(vals_by_inst[i] for i in idx) / n)
        return [round(float(A.np.percentile(out, 2.5)), 3), round(float(A.np.percentile(out, 97.5)), 3)]
    summ = {}
    for L in ('A', 'B', None):
        for rg in ('free', 'forced'):
            for c, nm in (('TS', 'M'), ('TN', 'MN')):
                T = cell(c, rg, L); n = len(T)
                if not n:
                    continue
                heads = [h for t in T for h in t['heads']]
                cats = {k: sum(1 for h in heads if h.get('category') == k) for k in ('Y', 'X', 'иное', 'НЕТ')}
                fcx = sum(t['FC_X'] for t in T); tc = sum(t['TC'] for t in T); fc = sum(t['FC'] for t in T)
                xs = [sum(1 for h in t['heads'] if h.get('category') == 'X') / 4 for t in T]
                summ[f"{nm}_{rg}{'_' + L if L else ''}"] = {
                    'n': n, 'TC_Y': tc, 'TC_ci95': A.cp_interval(tc, n), 'FC_any': fc, 'FC_any_ci95': A.cp_interval(fc, n),
                    'FC_X': fcx, 'FC_X_ci95': A.cp_interval(fcx, n), 'FC_X_upper95': A.cp_upper_one_sided(fcx, n),
                    'rare': A.cp_upper_one_sided(fcx, n) < A.EQUIV_UPPER, 'heads': len(heads), 'categories': cats,
                    'X_share_heads': sum(xs) / n, 'X_share_ci95_by_instance': boot(xs, f"x|{nm}|{rg}|{L}"),
                    'none_consensus': sum(t['none_consensus'] for t in T), 'lost': sum(t['n_lost'] for t in T)}
    # проверки: семья Холма — P1A, P2A (слой A; совет 46); P3 — описательно (одно- и двусторонний Макнемар)
    nA = len(cell('TS', 'forced', 'A'))
    p1 = A.binom_sf(summ['M_forced_A']['FC_X'], nA, A.P0)
    p2 = A.binom_sf(summ['M_free_A']['FC_X'], len(cell('TS', 'free', 'A')), A.P0)
    rej = A.holm({'P1A': p1, 'P2A': p2})
    p3 = {}
    for L in ('A', 'B', None):
        for rg in ('free', 'forced'):
            Mx, MNx = cell('TS', rg, L), cell('TN', rg, L)
            if not Mx:
                continue                                # пустой слой (например, пилот только из слоя A)
            assert [t['seed'] for t in Mx] == [t['seed'] for t in MNx]
            one, b, c = mcnemar([t['TC'] for t in MNx], [t['TC'] for t in Mx])
            two = min(1.0, 2 * min(A.binom_sf(b, b + c, 0.5), A.binom_sf(c, b + c, 0.5))) if b + c else 1.0
            diffs = [int(u['TC']) - int(v['TC']) for u, v in zip(MNx, Mx)]
            p3[f"{rg}{'_' + L if L else ''}"] = {'b_MN_only': b, 'c_M_only': c, 'p_one_sided': one, 'p_two_sided': two,
                                                 'diff_MN_minus_M': sum(diffs) / len(diffs),
                                                 'diff_ci95': boot(diffs, f"d|{rg}|{L}")}
    rareA = summ['M_free_A']['rare'] and summ['M_forced_A']['rare']        # пересечение двух условий (IUT): поправки не нужно
    validA = summ['MN_free_A']['TC_Y'] / summ['MN_free_A']['n'] >= 0.3
    # правило потерь (PREREG §5): в ячейке вердикта потеряно больше 5 % голов → «не определено»
    lost_bad = [k for k in ('M_forced_A', 'M_free_A', 'MN_free_A') if summ[k]['lost'] / summ[k]['heads'] > 0.05]
    tests = {'P1A': {'claim': 'FC_X в M, режим F, слой A > 0,05', 'k': summ['M_forced_A']['FC_X'], 'n': nA, 'p': p1, 'rejected': rej['P1A']},
             'P2A': {'claim': 'FC_X в M, свободный режим, слой A > 0,05', 'k': summ['M_free_A']['FC_X'], 'n': len(cell('TS', 'free', 'A')),
                     'p': p2, 'rejected': rej['P2A']},
             'rare_A_both': rareA, 'valid_A': validA, 'lost_bad_cells': lost_bad, 'P3_descr': p3}
    if lost_bad:
        verdict = 'не определено (потери больше 5 % голов: ' + ', '.join(lost_bad) + ')'
    elif not validA:
        verdict = 'не определено (условие осмысленности: TC_Y в MN свободного режима слоя A < 0,3)'
    elif rej['P1A']:
        verdict = 'гипотеза подтверждена в слое A: без права на отказ имена тянут согласие к X вопреки данным'
    elif rareA:
        verdict = 'гипотеза опровергнута узко: при видимой Y той же формы (слой A) имена не тянут согласие к X'
    else:
        verdict = 'не показано'
    tests['verdict'] = verdict
    tests['verdict_P2A'] = ('не определено' if (lost_bad or not validA) else
                            'P2A отвергнута: имена тянут согласие к X и при праве на отказ' if rej['P2A'] else 'P2A не отвергнута')
    lost_share = sum(s['lost'] for s in summ.values()) / max(1, sum(s['heads'] for s in summ.values()))
    d['platon02'] = {'summary': summ, 'tests': tests, 'holm': rej, 'lost_share': lost_share,
                     'layers': {L: sorted({t['law'] for t in d['tables'] if t['layer'] == L}) for L in ('A', 'B')}}
    json.dump(d, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, v in summ.items():
        print(f"  {k}: TC_Y {v['TC_Y']}/{v['n']}, FC_X {v['FC_X']}, FC {v['FC_any']}, виды {v['categories']}, НЕТ-согл {v['none_consensus']}")
    for k in ('P1A', 'P2A', 'rare_A_both', 'valid_A', 'lost_bad_cells', 'verdict', 'verdict_P2A'):
        print(f'  {k}: {tests[k]}')


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('seeds'); s.add_argument('--start', type=int, required=True); s.add_argument('--per-law', type=int, default=4)
    s.add_argument('--per-law-a', type=int, default=0, help='экземпляров на закон слоя A (совет 46: достижимость «редко»)')
    s.add_argument('--out', required=True)
    b = sub.add_parser('build'); b.add_argument('--seeds', required=True); b.add_argument('--out', required=True)
    z = sub.add_parser('analyze'); z.add_argument('--tables', required=True); z.add_argument('--journal', required=True)
    z.add_argument('--out', required=True)
    k = sub.add_parser('check'); k.add_argument('--seeds', required=True)
    a = ap.parse_args()
    {'seeds': cmd_seeds, 'build': cmd_build, 'analyze': cmd_analyze, 'check': cmd_check}[a.cmd](a)


if __name__ == '__main__':
    main()
