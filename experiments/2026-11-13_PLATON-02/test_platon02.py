#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02: тесты мира мимикрии (до пилота). Для каждого двойника и зерна 76000+:
Y держится на строках каждой головы и на новых строках (in, out); X (априор по имени) не держится (R ≥ 0,3 на строках
голов, «держится» = нет); X и Y не равносильны на объединении строк. Запуск: python3 test_platon02.py [зёрен на закон]"""
import sys
import platon02_world as M
W = M.W
import platon_check as C      # noqa: E402
FAIL = []


def check(c, msg):
    if not c:
        FAIL.append(msg); print('  ✗', msg)


def test(law, seed):
    inst = W.make_instance(seed, law, heads=4)
    out = {}
    for names in ('S', 'N'):
        idents, _, _, mp = W.table_view(inst, 'T', names)
        own = [W.table_view(inst, 'T', names, k)[2] for k in range(4)]
        union = [r for t in own for r in t]
        hin = W.rename_rows(inst['hold']['T']['in'], mp); hout = W.rename_rows(inst['hold']['T']['out'], mp)
        y = C.Claim(W.inv_in_names(inst, names), idents, own[0], f'y|{law}|{seed}|{names}')
        x = C.Claim(M.prior_in_names(inst, names), idents, own[0], f'x|{law}|{seed}|{names}')
        check(y.valid and x.valid, f'{law}/{seed}/{names}: выражения не годны')
        ry = max(C.R_measure(y.f, o, idents, seed=f'ry|{law}|{seed}|{k}') for k, o in enumerate(own))
        rx = min(C.R_measure(x.f, o, idents, seed=f'rx|{law}|{seed}|{k}') for k, o in enumerate(own))
        hy = C.holds(y, hin, hout, f'hy|{law}|{seed}|{names}'); hx = C.holds(x, hin, hout, f'hx|{law}|{seed}|{names}')
        ag, r21, r12 = C.agree(x, y, union, f'ag|{law}|{seed}|{names}')
        check(ry < 0.05, f'{law}/{seed}/{names}: Y на строках R {ry:.3f}')
        check(hy['holds'], f'{law}/{seed}/{names}: Y не держится на новых строках')
        check(rx >= 0.3, f'{law}/{seed}/{names}: X на строках R {rx:.3f} < 0,3')
        check(not hx['holds'], f'{law}/{seed}/{names}: X держится на данных Y')
        check(not ag, f'{law}/{seed}/{names}: X и Y равносильны ({r21:.3f}, {r12:.3f})')
        out[names] = (round(ry, 4), round(rx, 3))
    return out


if __name__ == '__main__':
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    mins = {}
    for law in M.MIMIC_ORDER:
        for s in range(k):
            o = test(law, 76000 + 100 * M.MIMIC_ORDER.index(law) + s)
            mins.setdefault(law, []).append(o['S'])
    for law, v in mins.items():
        print(f'  {law}: R(Y) макс {max(a for a, _ in v)}, R(X) мин {min(b for _, b in v)}')
    print('ПРОВАЛОВ:', len(FAIL))
    sys.exit(1 if FAIL else 0)
