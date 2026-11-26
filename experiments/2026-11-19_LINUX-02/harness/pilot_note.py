#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-02: числа записки пилота — только из json прогона GitHub Actions (gha_out/linux02_pilot/), без округления руками
(ERRORS № 200). Пишет pilot_note.json рядом с PILOT.md.
  python3 harness/pilot_note.py GHA_OUT_DIR OUT.json"""
import json
import os
import sys

MODS = ['errseq', '842_decompress', 'md5', 'random32', 'min_heap', 'string_helpers']


def main(a):
    g, dst = a[0], a[1]
    J = lambda n: json.load(open(os.path.join(g, n), encoding='utf-8'))   # noqa: E731
    chk, sel, ev1, ev2 = J('check.json'), J('select.json'), J('eval_pilot.json'), J('eval_pilot2.json')
    res = dict(source=g, selected=sel['selected'], test_possible=sel['test_possible'], check_ok=chk['ok'], phases={}, modules={})
    for name, ev in (('pilot', ev1), ('pilot2', ev2)):
        rows = []
        for m in MODS:
            for k, r in ev['modules'].get(m, {}).get('translations', {}).items():
                fns = (r.get('diff') or {}).get('fns', {})
                bfns = (r.get('diff_boundary') or {}).get('fns', {})
                rows.append(dict(module=m, key=k, compiled=r.get('compiled'), linked=r.get('linked'), kunit_pass=r.get('kunit_pass'),
                                 main_mismatches=r.get('main_mismatches'), bnd_mismatches=r.get('bnd_mismatches'), correct=r.get('correct'),
                                 fns_with_mismatch={f: v['mismatches'] for f, v in fns.items() if v['mismatches']},
                                 bnd_fns_with_mismatch={f: v['mismatches'] for f, v in bfns.items() if v['mismatches']},
                                 crashed_chunks=sum(v.get('crashed_chunks', 0) for v in fns.values()),
                                 example=next((v['example'] for v in fns.values() if v['mismatches']), None),
                                 compile_err_tail=(r.get('compile_err') or '')[-600:] or None))
        built = [r for r in rows if r['compiled'] and r['linked']]
        res['phases'][name] = dict(n=len(rows), compiled=sum(bool(r['compiled']) for r in rows), built=len(built),
                                   correct=sum(bool(r['correct']) for r in rows), kunit_pass=sum(bool(r['kunit_pass']) for r in built),
                                   wrong_built=sum(not r['correct'] for r in built),
                                   wrong_but_kunit_pass=sum(bool(r['kunit_pass']) and not r['correct'] for r in built), rows=rows)
    for m in MODS:
        s = sel['modules'][m]
        mu = s.get('mutants') or {}
        res['modules'][m] = dict(conditions=s['conditions'], selected=s['selected'], n_translations=s['n_translations'],
                                 n_correct=s['n_correct'], mutants={k: mu.get(k) for k in ('base_kind', 'clean_bases', 'generated', 'stillborn',
                                                                                            'alive', 'changed', 'changed_killed_kunit',
                                                                                            'changed_killed_main', 'killed_kunit',
                                                                                            'kunit_caught_main_missed',
                                                                                            'share_changed_killed_kunit',
                                                                                            'share_changed_killed_main',
                                                                                            'share_kunit_caught_main_missed',
                                                                                            'kunit_refs', 'exported', 'timeouts')})
    res['pilot_spend'] = sel['pilot']
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for name in ('pilot', 'pilot2'):
        p = res['phases'][name]
        print(name, {k: v for k, v in p.items() if k != 'rows'})
        for r in p['rows']:
            if not r['correct']:
                print('  неверен:', r['module'], r['key'], '| собран', r['compiled'], '| KUnit', r['kunit_pass'], '| расхождений',
                      r['main_mismatches'], '/', r['bnd_mismatches'], '| функции', r['fns_with_mismatch'], r['bnd_fns_with_mismatch'],
                      '| упавших порций', r['crashed_chunks'])
                if r['example']:
                    print('    пример:', r['example'][:240])
                if r['compile_err_tail']:
                    print('    сборка:', r['compile_err_tail'][-400:].replace('\n', ' | '))
    for m in MODS:
        x = res['modules'][m]
        mu = x['mutants']
        print(m, '| в тест', x['selected'], '|', {k: v for k, v in x['conditions'].items()}, '| мутанты: меняют', mu['changed'], 'KUnit', mu['changed_killed_kunit'],
              'сравнение', mu['changed_killed_main'], 'KUnit-только', mu['kunit_caught_main_missed'], 'из', mu['killed_kunit'])
    print('траты', res['pilot_spend'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
