#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: сухой прогон всей цепочки на заглушках (до регистрации).

Задания строятся platon_jobs.build на зёрнах сухого прогона (80001+), журнал пишется в формате run_sealed2
(итоговые записи: role «основной», final, answer, usage), затем platon_analyze считает всё как в тесте.
Заглушки голов:
  oracle — канонический закон в T (своими формами), НЕТ в Z;          ждём: TC(T) = 1, FC = 0, третий исход.
  prior  — знакомый закон при именах S в любых данных, при N — НЕТ;     ждём: FC(ZS) = 1, FC(ZN) = 0, P1 и P2 отвергнуты.
  none   — всегда НЕТ;                                                   ждём: K = 0, «не определено».
  junk   — разные неверные выражения;                                    ждём: K = 0.
  split  — две головы закон, две НЕТ;                                    ждём: K = 0 (клика 2).
  lossy  — prior, но голова h4 потеряна, h3 неразборна;                  ждём: K = 0 (две годные из четырёх).
  regimes — оба режима на одних таблицах: свободный — oracle, F — prior при S и junk при N;
            ждём: свободный — третий исход; F — гипотеза подтверждена; P4 отвергнута; Холм на 6 проверках;
            в Z режима F уверенность 0,02 → правило C: «порог уверенности снимает ложное согласие».
Запуск: python3 dry_platon.py  → dry/<заглушка>/..., dry/dry_summary.json; код 1 при несовпадении ожиданий.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import platon_jobs as J
import platon_world as W

HERE = Path(__file__).resolve().parent
DRY = HERE / 'dry'
SEEDS = [{'seed': 80001 + i, 'law': W.LAW_ORDER[i % len(W.LAW_ORDER)]} for i in range(20)]   # n = 20: при 0 ложных согласий верхняя граница 0,139 < 0,15

# функциональные переписывания канонического выражения (для разнообразия форм у голов)
REWRITE = [lambda e: e, lambda e: f'1/({e})', lambda e: f'log({e})', lambda e: f'2*({e})']
JUNK = ['{a}*{b}', '{a}+{b}', '{a}/{b}**2', '{a}-{b}', 'sqrt({a})*{b}', '{a}**2+{b}']


def answer(strategy, tb, inst, k):
    names = tb['names']; data = tb['data']
    canon = W.inv_in_names(inst, names)
    idents = tb['idents']
    if strategy == 'oracle':
        return REWRITE[k % 4](canon) if data == 'T' else 'НЕТ'
    if strategy in ('prior', 'lossy'):
        if strategy == 'lossy' and k == 2:
            return 'v**2/2 + g*h'                  # неизвестное имя → неразборно
        return REWRITE[k % 4](canon) if names == 'S' else 'НЕТ'
    if strategy == 'none':
        return 'НЕТ'
    if strategy == 'junk':
        return JUNK[k % len(JUNK)].format(a=idents[0], b=idents[1])
    if strategy == 'split':
        return canon if k < 2 else 'НЕТ'
    if strategy == 'regimes':                       # свободный режим — оракул; режим F — априор при S, мусор при N
        if tb.get('regime', 'free') == 'free':
            return answer('oracle', tb, inst, k)
        return REWRITE[k % 4](canon) if names == 'S' else JUNK[k % len(JUNK)].format(a=idents[0], b=idents[1])
    raise KeyError(strategy)


def fake_journal(strategy, jobs, tables, jdir):
    jdir.mkdir(parents=True, exist_ok=True)
    tbs = {t['table']: t for t in tables}
    insts = {}
    by_task = {}
    for j in jobs:
        tid = j['id'].rsplit('|', 1)[0]
        k = int(j['id'].rsplit('|h', 1)[1]) - 1
        tb = tbs[tid]
        key = (tb['seed'], tb['law'])
        if key not in insts:
            insts[key] = W.make_instance(*key)
        conf = 0.02 if (strategy == 'regimes' and tb.get('regime') == 'forced' and tb['data'] == 'Z') else 0.8
        rec = {'task': j['task'], 'job': j['id'], 'arm': j['arm'], 'attempt': 1, 'role': 'основной',
               'outcome': 'годный', 'final': 'годный',
               'answer': {'invariant': answer(strategy, tb, insts[key], k), 'confidence': conf},
               'usage': {'inp': 1000, 'out': 100, 'cost_usd': 0.001}, 'thinking_tokens': 50}
        if strategy == 'lossy' and k == 3:
            rec.update(outcome='сбой ответа', final='потерян', answer=None, reason='заглушка: потерян')
        by_task.setdefault(j['task'], []).append(rec)
    for t, recs in by_task.items():
        (jdir / f'{t}.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')


EXPECT = {
    'oracle': lambda s, t: (s['TS']['TC'] == s['TS']['n_tables'] and s['TN']['TC'] == s['TN']['n_tables']
                            and s['ZS']['FC'] == 0 and s['ZN']['FC'] == 0 and t['third_outcome_rare_false_consensus']),
    'prior': lambda s, t: (s['ZS']['FC'] == s['ZS']['n_tables'] and s['ZN']['FC'] == 0 and s['TS']['TC'] == s['TS']['n_tables']
                           and t['P1']['rejected_holm'] and t['P2']['rejected_holm']
                           and s['ZS']['rep_canonical_among_K'] == s['ZS']['K']),
    'none': lambda s, t: all(s[c]['K'] == 0 for c in s) and not t['valid'] and all(s[c]['none_consensus'] == s[c]['n_tables'] for c in s),
    'junk': lambda s, t: all(s[c]['K'] == 0 for c in s),
    'split': lambda s, t: all(s[c]['K'] == 0 for c in s),
    'lossy': lambda s, t: all(s[c]['K'] == 0 for c in s) and s['ZS']['head_kinds'].get('LOST') == s['ZS']['n_tables']
                          and s['ZS']['head_kinds'].get('PARSE_ERR') == s['ZS']['n_tables'],
}
# оба режима: ждём — свободный: третий исход; F: гипотеза подтверждена; P4 отвергнута
EXPECT_REG = lambda d: (d['tests']['third_outcome_rare_false_consensus']
                        and d['tests_forced']['P1']['rejected_holm'] and d['tests_forced']['P2']['rejected_holm']
                        and d['regime_cmp']['rejected_holm'] and d['summary']['ZSF']['FC'] == d['summary']['ZSF']['n_tables']
                        and d['summary']['ZNF']['FC'] == 0 and d['holm_family']['m'] == 6
                        and d['summary']['ZSF']['FC_conf'] == 0
                        and d['conf_rule_forced']['verdict'] == 'порог уверенности снимает ложное согласие')


def main():
    if DRY.exists():
        shutil.rmtree(DRY)
    DRY.mkdir()
    (DRY / 'seeds_dry.json').write_text(json.dumps(SEEDS, ensure_ascii=False, indent=1), encoding='utf-8')
    jobs, tables = J.build(SEEDS, 4, DRY / 'jobs')
    res, bad = {}, []
    for strat in EXPECT:
        jdir = DRY / strat / 'journal'
        fake_journal(strat, jobs, tables, jdir)
        outp = DRY / strat / 'dry_out.json'
        r = subprocess.run([sys.executable, str(HERE / 'platon_analyze.py'), '--tables', str(DRY / 'jobs' / 'tables.json'),
                            '--journal', str(jdir), '--out', str(outp)], capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            bad.append(strat)
            continue
        d = json.loads(outp.read_text(encoding='utf-8'))
        s, t = d['summary'], d['tests']
        ok = bool(EXPECT[strat](s, t))
        res[strat] = {'ok': ok, 'verdict': t['verdict'],
                      'cells': {c: {k: s[c][k] for k in ('K', 'FC', 'TC', 'none_consensus', 'head_kinds')} for c in s},
                      'P1_p': t['P1']['p_one_sided'], 'P2_p': t['P2']['p_one_sided']}
        print(f'{strat}: {"✓" if ok else "✗"}  {t["verdict"]}')
        for c in s:
            print(f"    {c}: K {s[c]['K']} FC {s[c]['FC']} TC {s[c]['TC']} НЕТ {s[c]['none_consensus']} {s[c]['head_kinds']}")
        if not ok:
            bad.append(strat)
    # оба режима на одних таблицах
    jobs2, tables2 = J.build(SEEDS, 4, DRY / 'jobs2', regimes=('free', 'forced'))
    jdir = DRY / 'regimes' / 'journal'
    fake_journal('regimes', jobs2, tables2, jdir)
    outp = DRY / 'regimes' / 'dry_out.json'
    r = subprocess.run([sys.executable, str(HERE / 'platon_analyze.py'), '--tables', str(DRY / 'jobs2' / 'tables.json'),
                        '--journal', str(jdir), '--out', str(outp)], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr); bad.append('regimes')
    else:
        d = json.loads(outp.read_text(encoding='utf-8'))
        ok = bool(EXPECT_REG(d))
        res['regimes'] = {'ok': ok, 'verdict_free': d['tests']['verdict'], 'verdict_forced': d['tests_forced']['verdict'],
                          'P4': d['regime_cmp']['verdict'], 'holm': d['holm_family']['rejected']}
        print(f"regimes: {'✓' if ok else '✗'}  свободный: {d['tests']['verdict']} | F: {d['tests_forced']['verdict']} | P4: {d['regime_cmp']['verdict']}")
        if not ok:
            bad.append('regimes')
    (DRY / 'dry_summary.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print('несовпадений:', bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
