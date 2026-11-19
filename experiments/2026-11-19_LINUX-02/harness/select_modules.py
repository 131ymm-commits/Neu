#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-02: отбор модулей в тест по правилу плана пилота (PLAN-PILOT.md, «Правило отбора модулей в тест») и условию 5
(DEVIATIONS.md, п. 4) — механически, без разбора по одному. Плюс описательные числа пилота для мощности и цены (на пилоте
ничего не проверяется).
Условия для модуля:
  1–2. проверка обвязки: оригинал проходит KUnit и против себя даёт 0 расхождений — в обычной сборке и под UBSan (check.json);
  3.   правда сильнее оценщика (mutants_<модуль>.json, total.rule3);
  4.   хотя бы один перевод пилота с кодом неверен (eval.json; отказ площадки — не перевод, DEVIATIONS п. 1);
  5.   KUnit может провалить перевод (mutants_<модуль>.json, rule5).
Меньше двух модулей — тест в этом виде не ставится (решение по слову автора).
Фаза модуля (DEVIATIONS п. 9): errseq — pilot (поручение v1 по сути то же), остальные — pilot2 (повтор под поручениями test).
Условие 4 и числа мощности берутся из оценки фазы модуля; мутанты mutants_<модуль>.json посчитаны на той же фазе.
  python3 harness/select_modules.py CHECK.json MUT_DIR OUT.json --eval pilot=E1.json [--eval pilot2=E2.json]
                                    [--phase-of errseq=pilot] [--default-phase pilot2]"""
import glob
import json
import os
import sys

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
MODULES = ['errseq', '842_decompress', 'md5', 'random32', 'min_heap', 'string_helpers']


def load(p):
    try:
        return json.load(open(p, encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


def calls(phase):
    """Вызовы голов фазы: модуль → голова → запись (цена, есть ли код, отказ)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(X, 'translations', phase, '*', '*.json'))):
        r = load(f)
        if not r or 'module' not in r:
            continue
        out.setdefault(r['module'], {})[f"{r['head']}/r{r.get('rep')}"] = dict(
            cost=r.get('total_cost_usd') or 0.0, code=bool(r.get('code_extracted')),
            refused='safeguards flagged' in (r.get('result') or ''), output_tokens=(r.get('usage') or {}).get('output_tokens'))
    return out


def main(a):
    chk, mdir, dst = load(a[0]), a[1], a[2]
    evals = {k: load(v) for k, v in (x.split('=', 1) for i, x in enumerate(a) if i > 0 and a[i - 1] == '--eval')}
    phase_of = dict(x.split('=', 1) for i, x in enumerate(a) if i > 0 and a[i - 1] == '--phase-of')
    default = a[a.index('--default-phase') + 1] if '--default-phase' in a else 'pilot'
    res = dict(inputs=dict(check=a[0], mutants_dir=mdir, evals=sorted(evals), phase_of=phase_of, default_phase=default), modules={})
    used_phases = set()
    for m in MODULES:
        ph = phase_of.get(m, default)
        used_phases.add(ph)
        cl = calls(ph)
        c = (chk or {}).get('modules', {}).get(m, {})
        e = (evals.get(ph) or {}).get('modules', {}).get(m, {})
        mu = load(os.path.join(mdir, f'mutants_{m}.json'))
        tr = e.get('translations', {})
        rows = {k: dict(compiled=v.get('compiled'), kunit_pass=v.get('kunit_pass'), mismatches=v.get('mismatches'), correct=v.get('correct'),
                        kunit_failed=(v.get('kunit') or {}).get('failed'), kunit_total=(v.get('kunit') or {}).get('total'))
                for k, v in sorted(tr.items())}
        t = (mu or {}).get('total', {})
        cond = {
            '1_2_harness': bool(c.get('ok_plain') and c.get('ok_ubsan')),
            '3_truth_stronger': bool(mu and mu.get('orig_ok') and mu.get('phase') == ph and t.get('rule3')),
            '4_some_wrong': any(r['correct'] is False for r in rows.values()),
            '5_kunit_can_fail': bool(mu and mu.get('phase') == ph and mu.get('rule5')),
        }
        passed = [r for r in rows.values() if r['kunit_pass']]
        res['modules'][m] = dict(
            phase=ph, conditions=cond, selected=all(cond.values()), translations=rows, calls=cl.get(m, {}),
            c_lines=e.get('c_lines'),
            n_translations=len(rows), n_correct=sum(bool(r['correct']) for r in rows.values()), n_kunit_pass=len(passed),
            n_false_pass=sum(not r['correct'] for r in passed),
            mutants=None if not mu else dict(phase=mu.get('phase'), base_kind=mu.get('base_kind'),
                                             clean_bases=[b['base'] for b in mu.get('bases', []) if b.get('clean')],
                                             kunit_refs=len(mu.get('kunit_refs', [])), exported=len(mu.get('exported', [])),
                                             **{k: t.get(k) for k in ('generated', 'stillborn', 'not_linked', 'harness_errors', 'alive', 'changed',
                                                                      'changed_killed_kunit', 'changed_killed_main', 'killed_kunit',
                                                                      'kunit_caught_main_missed', 'main_killed_not_changed', 'survived_all',
                                                                      'share_changed_killed_kunit', 'share_changed_killed_main',
                                                                      'share_kunit_caught_main_missed', 'timeouts')}))
    sel = [m for m in MODULES if res['modules'][m]['selected']]
    res['selected'] = sel
    res['test_possible'] = len(sel) >= 2
    if not res['test_possible']:
        res['note'] = 'в тест проходит меньше двух модулей — тест в этом виде не ставится: решение по слову автора, с докладом'
    allc = [r for mm in res['modules'].values() for r in mm['translations'].values()]
    allp = [r for r in allc if r['kunit_pass']]
    spend = {ph: round(sum(v['cost'] for mm in calls(ph).values() for v in mm.values()), 4) for ph in sorted(used_phases | set(evals))}
    sel_calls = {m: res['modules'][m]['calls'] for m in MODULES}
    cost_sel = sum(v['cost'] for mm in sel_calls.values() for v in mm.values())
    lines_sel = sum((res['modules'][m]['c_lines'] or 0) * len(sel_calls[m]) for m in MODULES)
    res['pilot'] = dict(calls=sum(len(v) for v in sel_calls.values()), translations=len(allc),
                        refused=sum(v['refused'] for mm in sel_calls.values() for v in mm.values()),
                        correct=sum(bool(r['correct']) for r in allc), kunit_pass=len(allp), false_pass=sum(not r['correct'] for r in allp),
                        cost_usd_by_phase=spend, cost_usd_used_calls=round(cost_sel, 4), c_lines_called=lines_sel,
                        cost_per_c_line=round(cost_sel / lines_sel, 6) if lines_sel else None)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for m in MODULES:
        r = res['modules'][m]
        print(m, f"[{r['phase']}]", '|', ' '.join(f"{k}={'да' if v else 'нет'}" for k, v in r['conditions'].items()), '| в тест:',
              'да' if r['selected'] else 'нет')
    print('в тест:', sel, '| тест возможен:', res['test_possible'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
