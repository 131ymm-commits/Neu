#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03: числа PREREG — только из json (ERRORS № 200), руками не переписываются. Печатает таблицы пилота (T_X19, вне теста),
мощности и ожиданий; пишет expect_d3.json (ожидание = 0,95 × наименьшая из четырёх моделей шума мощность при δ = D пилота, как в DISTILL-02).
  python3 prereg_numbers_d3.py [--write]"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ab  # noqa: E402

P1 = os.path.join(ROOT, 'gha_out/distill03_pilot')        # пилот, вторая попытка (64086bcb): решающие числа
P2 = os.path.join(ROOT, 'gha_out/distill03_power')        # пилот новым кодом (описательные срезы) и мощность
SHORT = {'Falcon3-1B-Instruct': 'Falcon 1B', 'OLMo-2-0425-1B-Instruct': 'OLMo 1B', 'Qwen2.5-0.5B-Instruct': 'Qwen 0,5B',
         'Qwen2.5-1.5B-Instruct': 'Qwen 1,5B', 'SmolLM2-1.7B-Instruct': 'SmolLM 1,7B', 'SmolLM2-360M-Instruct': 'SmolLM 360M',
         'TinyLlama-1.1B-Chat-v1.0': 'TinyLlama 1,1B'}


def f(x, n=4):
    return 'нет' if x is None else (f'{x:.{n}f}' if isinstance(x, float) else str(x))


def main(a):
    fits = json.load(open(os.path.join(P1, 'fits.json'), encoding='utf-8'))
    pil = json.load(open(os.path.join(P1, 'pilot.json'), encoding='utf-8'))
    pil2 = json.load(open(os.path.join(P2, 'pilot.json'), encoding='utf-8'))
    pw = json.load(open(os.path.join(P2, 'power.json'), encoding='utf-8'))
    print('## Программы: совпадение с DISTILL-02 (formulas в analysis.json)')
    for fam, v in fits['families'].items():
        print(f'- {fam}:', sum(all(x.values()) for x in v['same_as_distill02'].values() if x), 'из', len(v['same_as_distill02']))
    print('## Построение: числовых ответов на голову')
    for fam, v in pil['construction_n'].items():
        print(f'- {fam}:', ', '.join(f'{SHORT[h]} {n}' for h, n in sorted(v.items())))
    fm, fm2 = pil['families']['thousands'], pil2['families']['thousands']
    heads = fm['heads']
    print('## Пилот T_X19 (вне теста): решающие статистики')
    print('| вид | D | p (точное) | ранг из 5040 | различных D_π | голов, у которых своя лучше среднего чужих | голов, у которых своя лучше любой чужой | средний зазор к лучшей чужой |')
    print('|---|---|---|---|---|---|---|---|')
    for kind in ab.KINDS:
        r, r2 = fm[kind], fm2[kind]
        diag = [r['s'][i][i] for i in range(len(heads))]
        no = r['nearest_other']
        print(f"| {kind} | {r['D']:.4f} | {r['p']:.6f} | {r['rank']} | {r2['n_distinct']} | {sum(d > 0 for d in diag)} из {len(diag)} | "
              f"{no['heads_own_best']} из {len(heads)} | {no['mean']:+.4f} |")
    print('## Пилот T_X19: по головам (s[B, B] — своя минус среднее чужих; зазор — своя минус лучшая чужая)')
    print('| голова | точность построения | s программы | s формы | зазор программы | зазор формы | вклад входа | своя форма − своя программа |')
    print('|---|---|---|---|---|---|---|---|')
    for i, h in enumerate(heads):
        print(f"| {SHORT[h]} | {fm['accuracy_construction'][h]:.3f} | {fm['prog']['s'][i][i]:+.4f} | {fm['shape']['s'][i][i]:+.4f} | "
              f"{fm['prog']['nearest_other']['per_head'][i]:+.4f} | {fm['shape']['nearest_other']['per_head'][i]:+.4f} | "
              f"{fm['input_gain']['per_env_head'][0][i]:+.4f} | {fm['own_shape_minus_own_prog'][0][i]:+.4f} |")
    print(f"- вклад входа, среднее по головам: {fm['input_gain']['mean']:+.4f}; больше нуля у {sum(x > 0 for x in fm['input_gain']['per_env_head'][0])} голов из {len(heads)}")
    diag = [fm['prog']['s'][i][i] for i in range(len(heads))]
    top = max(range(len(heads)), key=lambda i: diag[i])
    print(f"- программа: сумма s(B, B) по головам {sum(diag):.4f}; наибольшая — {SHORT[heads[top]]} {diag[top]:.4f}, доля {diag[top] / sum(diag):.2f}")
    dc = fm2['decomposition']
    print('## Пилот T_X19 новым кодом: разбивка преимущества программы (описательно; порядок цепочки — PREREG §4)')
    print('| голова | всё | форма | уровень | прочие |')
    print('|---|---|---|---|---|')
    for h in heads:
        print(f"| {SHORT[h]} | {dc['total']['per_head'][h]:+.4f} | {dc['form']['per_head'][h]:+.4f} | {dc['level']['per_head'][h]:+.4f} | {dc['others']['per_head'][h]:+.4f} |")
    print(f"| среднее | {dc['total']['mean']:+.4f} | {dc['form']['mean']:+.4f} | {dc['level']['mean']:+.4f} | {dc['others']['mean']:+.4f} |")
    print(f"- доля «прочих» в D пилота (совет 76, п. 6): {dc['others']['mean'] / dc['total']['mean']:.4f}; формы — {dc['form']['mean'] / dc['total']['mean']:.4f}; "
          f"уровня — {dc['level']['mean'] / dc['total']['mean']:.4f}")
    an = json.load(open(os.path.join(ROOT, 'gha_out/distill02_sum_test/analysis.json'), encoding='utf-8'))
    ks = {n: len(v['heads']) for n, v in an['envs'].items()}
    want = [n for fam in ab.TEST_ENVS.values() for n in fam]
    new5 = [n for n, v in an['envs'].items() if v.get('phase') == 'new5']
    print(f"- k по analysis.json DISTILL-02 (правило ≥ {ab.MIN_NUMERIC} числовых ответов то же): среды теста — "
          f"{sorted(set(ks[n] for n in want))} голов в каждой из {len(want)}; new5 — {sorted(set(ks[n] for n in new5))} в каждой из {len(new5)}")
    print('## Пилот T_X19 новым кодом: родство (описательно)')
    print('| вид | голова | родич | своя − родич | родич − чужие | своя − чужие |')
    print('|---|---|---|---|---|---|')
    for kind in ab.KINDS:
        for h, v in fm2['kinship'][kind]['per_head'].items():
            print(f"| {kind} | {SHORT[h]} | {SHORT[v['relative']]} | {v['own_minus_relative']:+.4f} | {v['relative_minus_strangers']:+.4f} | {v['own_minus_strangers']:+.4f} |")
    same = all(fm[k]['D'] == fm2[k]['D'] and fm[k]['p'] == fm2[k]['p'] for k in ab.KINDS)
    print(f'- решающие D и p нового кода совпадают с пилотом 64086bcb: {same}')
    print(f"## Мощность (α = {pw['alpha']}, повторов {pw['reps']}, зерно {pw['seed']}; шум из пилота {pw['pilot_env']})")
    print('| вид | σ | остатки | D пилота | модель | δ при мощности 0,8 | мощность при δ = D пилота | доля «да» при δ = 0 |')
    print('|---|---|---|---|---|---|---|---|')
    expect = {}
    for kind, v in pw['kinds'].items():
        for name, r in v['results'].items():
            print(f"| {kind} | {v['sigma_offdiag']:.4f} | {v['resid_min']:+.3f} … {v['resid_max']:+.3f} | {v['pilot_D']:.4f} | {name} (сред {r['n_env']}) | "
                  f"{f(r['delta_80'])} | {f(r['power_at_pilot_D'], 3)} | {f(r['power_at_0'], 4)} |")
        print(f"- {kind}: «общий выше независимого более чем на 0,05» — {v['shared_le_independent']}")
    from scipy.stats import binom
    n0 = max(round(r['power_at_0'] * pw['reps']) for v in pw['kinds'].values() for r in v['results'].values())
    p_ex = 12 / 5040
    print(f"- при δ = 0: точная доля «да» при различных D_π — 12/5040 = {p_ex:.5f}; наибольшее число «да» из {pw['reps']} — {n0}; "
          f"P(не меньше {n0} из {pw['reps']}) = {binom.sf(n0 - 1, pw['reps'], p_ex):.3f}")
    for rule, (fam, kind) in ab.RULES.items():
        res = pw['kinds'][kind]['results']
        pows = {n: r['power_at_pilot_D'] for n, r in res.items() if n.startswith(fam + '_')}
        worst = min(pows, key=pows.get)
        al = pw['alpha']
        expect[rule] = dict(family=fam, kind=kind, power_min=pows[worst], model_min=worst, powers=pows, expect=round(0.95 * pows[worst], 4),
                            bits_yes=round(math.log2(pows[worst] / al), 2), bits_no=round(math.log2((1 - pows[worst]) / (1 - al)), 2))
    print('## Ожидания (0,95 × наименьшая мощность при δ = D пилота) и вес опоры (log₂ Λ: «да» — мощность/α, «нет» — (1 − мощность)/(1 − α))')
    for rule, e in expect.items():
        print(f"- {rule}: мощность {e['power_min']:.3f} ({e['model_min']}) → ожидание «да» {e['expect']:.4f}; вес «да» {e['bits_yes']:+.2f} бит, «нет» {e['bits_no']:+.2f} бит")
    k6p = os.path.join(ROOT, 'gha_out/distill03_power_k6/power_k6.json')
    if os.path.exists(k6p):
        k6 = json.load(open(k6p, encoding='utf-8'))
        print(f"## Мощность при k = 6 (совет 76, п. 3; α = {k6['alpha']}, повторов {k6['reps']}): наименьшая по 7 выпадениям и 4 моделям шума")
        for kind, v in k6['kinds'].items():
            mp = v['min_power']
            print(f"- {kind}: {mp:.4f} (без {SHORT[v['worst_drop']]}); по семействам: " +
                  ', '.join(f'{f} {x:.4f}' for f, x in v['min_power_by_family'].items()) +
                  f"; вес «да» {math.log2(mp / k6['alpha']):+.2f} бит, «нет» {math.log2((1 - mp) / (1 - k6['alpha'])):+.2f} бит")
    if '--write' in a:
        json.dump(dict(rule='0,95 × наименьшая из четырёх моделей шума мощность при δ = D пилота T_X19', alpha=pw['alpha'], rules=expect),
                  open(os.path.join(HERE, 'expect_d3.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('записано expect_d3.json')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
