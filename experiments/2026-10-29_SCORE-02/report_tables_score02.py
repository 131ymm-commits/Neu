#!/usr/bin/env python3
"""SCORE-02: таблицы отчёта из analysis_score02.json и evals/<этап>.json — командой, не перепечаткой (CLAUDE.md: числа из json).
Записан до результатов теста; проверялся на анализе сухого прогона (dry/analysis_<ветка>.json). Импорт ничего не пишет.
  python3 report_tables_score02.py [--analysis analysis_score02.json] [--evals evals] [--out run/report_tables.md]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
def f(x, d=3):
    if x is None or x != x:
        return '—'
    s = f'{x:.{d}f}'.replace('.', ',')
    return s[1:] if s.startswith('-') and set(s[1:]) <= set('0,') else s.replace('-', '−')   # −0,000 → 0,000
NAME = dict(single='один вызов', mean='среднее p', agree='согласие', single_c='один вызов, огрублённый')
MNAME = dict(auc2='AUC второго рода', acc='точность', conf='уверенность', self_dec='самообман', brier='Брайер')
KIND = dict(family='семья', check='проверка', explore='разведка')
STAGES = ('main_opus', 'rep_opus', 'main_haiku', 'rep_haiku')


def arg(a, k, d):
    return a[a.index(k) + 1] if k in a else d


def tables(R, evals_dir):
    out = []
    st_all = [s for s in STAGES if s in R['measures']]
    out.append('### Вызовы, покрытие, контекст\n')
    out.append('| Этап | Заданий | Годных | Нет записи | Негодных | Цена, $ | Выход в среднем, ток. | Контекст: флаг | Против линии: среднее / наибольший остаток | Внутри задачи: наибольший остаток |')
    out.append('|---|---|---|---|---|---|---|---|---|---|')
    for st in st_all:
        c, x = R['coverage'][st], R['ctx'][st]
        E = json.load(open(os.path.join(evals_dir, f'{st}.json'), encoding='utf-8'))['calls']
        out.append(f"| {st} | {c['jobs']} | {c['valid']} | {c['missing']} | {c['invalid']} | {f(E['cost'], 2)} | {f(E['out'], 0)} | "
                   f"{'да' if x.get('flag') else 'нет'} | {f(x.get('abs_mean'), 1)} / {f(x.get('abs_max'), 1)} | {f(x.get('max_abs_resid'), 1)} |")
    out.append('\n### Меры источников (все суждения этапа вместе)\n')
    out.append('| Этап | Источник | Суждений | AUC второго рода | Точность | Уверенность | Самообман | Брайер | ИОИ = незнание + самообман⁺ |')
    out.append('|---|---|---|---|---|---|---|---|---|')
    for st in st_all:
        for s in ('single', 'mean', 'agree'):
            m = R['measures'][st][s]
            out.append(f"| {st} | {NAME[s]} | {m['n']} | {f(m['auc2'])} | {f(m['acc'])} | {f(m['conf'])} | {f(m['self_dec'])} | {f(m['brier'])} | "
                       f"{f(m['ioi'])} = {f(m['ign'])} + {f(m['dec_pos'])} |")
        m = R['measures'][st]['single_c']
        out.append(f"| {st} | {NAME['single_c']} | {m['n']} | {f(m['auc2'])} | — | — | — | — | — |")
    out.append('\n### Вердикты частей (95 % интервал бутстрепа задач, B = 10 000)\n')
    out.append('| Часть | Вид | Этап | Мера | Контраст | Предсказание | Среднее [95 %] | Задач | Исход | Чтение |')
    out.append('|---|---|---|---|---|---|---|---|---|---|')
    for q in R['pred']:
        for st in st_all:
            v = R['verdicts'].get(f"{q['id']}|{st}")
            if v is None:
                continue
            ci = f"{f(v['mean'])} [{f(v['ci95'][0])}; {f(v['ci95'][1])}]" if 'mean' in v else '—'
            out.append(f"| {q['id']} | {KIND[q['kind']]} | {st} | {MNAME[q['measure']]} | {q['a']} − {q['b']} | {'> 0' if q['dir'] > 0 else '< 0'} | {ci} | "
                       f"{v['n_tasks']} | {v['outcome']} | {v.get('reading', v['outcome'])}{('; ' + v['caveat']) if v.get('caveat') else ''} |")
    out.append('\n### Сводные: чтения и статусы\n')
    out.append('| Сводный | Части | Основная | Повтор | Статус |')
    out.append('|---|---|---|---|---|')
    for c, s in R['status'].items():
        out.append(f"| {c} | {', '.join(R['comp'][c])} | {s['main']} | {s['rep']} | {s['status']} |")
    out.append('\n### Описательно: разложение самообмана согласия, исключения, огрубление\n')
    out.append('| Этап | T = ср. (1 − s)·1(s > ½) | Порог T | X2 приближённо | X2 факт | Единогласных суждений согласия | p = 0,5 (вызовов-суждений) | Ничьих сторон (кандидатов) |')
    out.append('|---|---|---|---|---|---|---|---|')
    for st in st_all:
        d, e = R['describe'][st]['decomp_x2'], R['describe'][st]['excl']
        out.append(f"| {st} | {f(d['T'])} | {f(d['T_break'])} | {f(d['approx'])} | {f(d['x2'])} | {f(d['unanimous'])} | {e['half_calls']} из {e['call_judgments']} | "
                   f"{e['side_ties']} из {e['cand_with_side']} |")
    out.append('\n| Этап | Непустых уровней: agree / single_c |')
    out.append('|---|---|')
    for st in st_all:
        ne = R['describe'][st].get('nonempty', {})
        out.append(f"| {st} | {ne.get('agree', '—')} / {ne.get('single_c', '—')} |")
    out.append('\n| Этап | Уровень согласия | Доля суждений согласия | Доля суждений одного вызова после огрубления |')
    out.append('|---|---|---|---|')
    for st in st_all:
        for x in R['describe'][st]['levels']:
            out.append(f"| {st} | {f(x['level'])} | {f(x['agree_share'])} | {f(x['single_c_share'])} |")
    return '\n'.join(out) + '\n'


def main():
    a = sys.argv[1:]
    R = json.load(open(os.path.join(HERE, arg(a, '--analysis', 'analysis_score02.json')), encoding='utf-8'))
    t = tables(R, os.path.join(HERE, arg(a, '--evals', 'evals')))
    out = os.path.join(HERE, arg(a, '--out', os.path.join('run', 'report_tables.md')))
    open(out, 'w', encoding='utf-8').write(t)
    print(t)


if __name__ == '__main__':
    main()
