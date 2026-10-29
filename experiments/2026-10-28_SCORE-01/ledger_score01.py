#!/usr/bin/env python3
"""SCORE-01: записи в реестр (tools/ledger.py) и веса опор (journal/support_bits.json) по отчёту — после проверки отчёта.
Статусы — по чтениям и статусу analysis_score01.json (PREREG §4); веса — по §6: класс «наш_рег», ложный уровень и P — меньшая мощность
сводного из pilot_power.json, min(P; 0,999); «не показано» — опоры нет (0 бит, соглашение §6); основная выборка и повтор — одна
группа опор. Разведка и пост-хок — гипотезы. Тексты утверждений — здесь; числа — из analysis_score01.json и report_facts_score01.json.
Запуск из папки опыта: python3 ledger_score01.py [--dry]"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
DRY = '--dry' in sys.argv
REP = 'experiments/2026-10-28_SCORE-01/REPORT-SCORE-01.md'
GROUP = 'SCORE-01 (78626cd)'
f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
COND = ('склад WH SELECT-01, 8 кандидатов, промпт на русском, effort medium, чистый контекст голов; правило объявлено в промпте, '
        'но не исполняется; проверены две строки правила — LOG (сумма ln вероятности верного ответа) и WIN (очко за верную сторону от 0,5)')


def main():
    A = json.load(open(os.path.join(HERE, 'analysis_score01.json'), encoding='utf-8'))
    P = json.load(open(os.path.join(HERE, 'pilot_power.json'), encoding='utf-8'))['comps']
    F = json.load(open(os.path.join(HERE, 'report_facts_score01.json'), encoding='utf-8'))['posthoc']
    V = lambda pid, st: A['verdicts'][f'{pid}|{st}']
    ci = lambda v, k='ci90': f"{f(v['mean'])} [{f(v[k][0])}; {f(v[k][1])}]"
    st = A['status']
    assert st['SA_opus']['status'] == st['SA_haiku']['status'] == st['SB_opus']['status'] == st['SB_haiku']['status'] == 'установлено'
    assert st['SD_opus']['status'] == st['SL_haiku']['status'] == 'подтверждено (повторено; причина не проверялась)'
    assert st['SC_opus']['main_reading'] == 'подтверждено' and st['SC_opus']['rep_reading'] != 'подтверждено'
    sd = F['P6']['self_dec']
    NEW = [
        ('SA_opus', 'разницы нет',
         f"SCORE-01 SA (Opus 5.5; {COND}): строки LOG и WIN не различают самообман оценщика (уверенность минус точность) больше чем на 0,1, "
         f"точность — больше чем на 0,1, Брайер — больше чем на 0,05; самообман WIN − LOG {ci(V('O1', 'main_opus'))} и {ci(V('O1', 'rep_opus'))} "
         '(90 %; основная выборка WH 8001–8100 и повтор WH 8101–8200). Установлено по §4 PREREG (обе выборки). Исключена разница порядка самого '
         'самообмана, а не любая; части почти одно измерение (самообман и точность зеркальны)'),
        ('SA_haiku', 'разницы нет',
         f"SCORE-01 SA (Haiku 5.5, два вызова на клетку; {COND}): строки LOG и WIN не различают самообман оценщика больше чем на 0,1, "
         f"точность — больше чем на 0,1, Брайер — больше чем на 0,05; самообман WIN − LOG {ci(V('H1', 'main_haiku'))} и {ci(V('H1', 'rep_haiku'))} (90 %). "
         'Установлено по §4 PREREG (обе выборки). Чувствительность низкая: два вызова одного промпта у Haiku расходятся почти как случайные'),
        ('SB_opus', 'подтверждено',
         f"SCORE-01 SB (Opus 5.5; {COND}): самообман оценщика есть в каждой руке — LOG, WIN и без строки о правиле (NONE): "
         f"{f(V('O4', 'main_opus')['mean'])}, {f(V('O5', 'main_opus')['mean'])}, {f(V('O6', 'main_opus')['mean'])} в основной выборке, "
         f"{f(V('O4', 'rep_opus')['mean'])}, {f(V('O5', 'rep_opus')['mean'])}, {f(V('O6', 'rep_opus')['mean'])} в повторе. "
         'Установлено по §4 PREREG (обе выборки); о наличии самообмана, не о механизме'),
        ('SB_haiku', 'подтверждено',
         f"SCORE-01 SB (Haiku 5.5; {COND}): самообман оценщика есть в каждой руке — LOG, WIN и NONE: "
         f"{f(V('H4', 'main_haiku')['mean'])}, {f(V('H5', 'main_haiku')['mean'])}, {f(V('H6', 'main_haiku')['mean'])} в основной выборке, "
         f"{f(V('H4', 'rep_haiku')['mean'])}, {f(V('H5', 'rep_haiku')['mean'])}, {f(V('H6', 'rep_haiku')['mean'])} в повторе. "
         'Установлено по §4 PREREG (обе выборки); о наличии самообмана, не о механизме'),
        ('SD_opus', 'подтверждено',
         f"SCORE-01 SD (Opus 5.5; {COND}): объявление правила (среднее LOG и WIN) удлиняет рассуждение оценщика против промпта без правила: "
         f"выходные токены +{V('O8', 'main_opus')['mean']:.0f} [{V('O8', 'main_opus')['ci95'][0]:.0f}; {V('O8', 'main_opus')['ci95'][1]:.0f}] "
         f"и +{V('O8', 'rep_opus')['mean']:.0f} [{V('O8', 'rep_opus')['ci95'][0]:.0f}; {V('O8', 'rep_opus')['ci95'][1]:.0f}] (95 %). "
         'Подтверждено и повторено; причина не проверялась: неспецифичный эффект слов не разведён (нет нейтральной строки)'),
        ('SL_haiku', 'подтверждено',
         f"SCORE-01 SL (Haiku 5.5; {COND}): строка WIN удлиняет рассуждение оценщика против строки LOG: выходные токены "
         f"+{V('H9', 'main_haiku')['mean']:.0f} [{V('H9', 'main_haiku')['ci95'][0]:.0f}; {V('H9', 'main_haiku')['ci95'][1]:.0f}] и "
         f"+{V('H9', 'rep_haiku')['mean']:.0f} [{V('H9', 'rep_haiku')['ci95'][0]:.0f}; {V('H9', 'rep_haiku')['ci95'][1]:.0f}] (95 %; в "
         f"{f(F['P4']['main_haiku']['ratio'], 2)} и {f(F['P4']['rep_haiku']['ratio'], 2)} раза). Подтверждено и повторено; причина не проверялась"),
        ('SC_opus', 'гипотеза',
         f"SCORE-01 SC (Opus 5.5; {COND}): объявление правила повышает точность оценщика против промпта без правила — "
         f"{ci(V('O7', 'main_opus'), 'ci95')} в основной выборке (подтверждено), {ci(V('O7', 'rep_opus'), 'ci95')} в повторе (не показано); "
         'неспецифичный эффект слов не разведён'),
    ]
    EXPL = [
        ('разведка', 'SCORE-01 (разведка, направления по пилоту 3): у Opus строка WIN снижает уверенность против LOG (OE1), без строки о правиле '
                     'самообман выше (OE2), с правилом выше AUC (OE3) — подтверждены только в основной выборке; у Haiku точность WIN − LOG > 0 (HE3) — '
                     'только в повторе'),
        ('не показано', 'SCORE-01 (не показано в обеих выборках; отрицательный результат): объявление правила удлиняет рассуждение Haiku (SD_haiku), '
                        'строка WIN укорачивает рассуждение Opus (SL_opus; в пилоте 3 было −874 токена), разведка H7, HE1, HE2 — интервалы '
                        'накрывают 0 в основной выборке и в повторе'),
        ('пост-хок П3', f"SCORE-01 (пост-хок, не в зачёт): уверенность голов-оценщиков почти не отличает их верные суждения о кандидате от неверных — "
                        f"AUC второго рода от {f(min(v['auc2'] for v in F['P3']['rows'].values()))} до {f(max(v['auc2'] for v in F['P3']['rows'].values()))} "
                        f"по 12 клеткам (этап × рука), 95 % интервал выше 0,5 в {F['P3']['ci_above_half']} из 12; согласуется с литературой "
                        '(Xiong и др., ICLR 2024). Симметричная монотонная перекалибровка уровень самообмана снимает, различение — нет'),
    ]

    def ledger(*args):
        cmd = [sys.executable, os.path.join(ROOT, 'tools', 'ledger.py'), *args]
        if DRY:
            print('СУХО:', ' | '.join(a if len(a) < 120 else a[:117] + '…' for a in args))
            return 'C-XXX'
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        print(out)
        return out.split()[0]

    sb_path = os.path.join(ROOT, 'journal', 'support_bits.json')
    sb = json.load(open(sb_path, encoding='utf-8'))
    for key, status, text in NEW:
        cid = ledger('add', text, '--status', status, '--support', f'{REP} ({key}; PREREG 78626cd)')
        p = P[key]
        rd = [A['readings'][f"{key}|{s}_{key.split('_')[1]}"] for s in ('main', 'rep')]
        sup = [dict(**{'class': 'наш_рег'}, group=GROUP, false_level=p['alpha'], power=min(p['power_low'], 0.999), held=True,
                    note=f'сводный {key}, {s}: {r}; PREREG-SCORE-01 §6')
               for s, r in zip(('основная выборка', 'повтор'), rd) if r == 'подтверждено']
        sb[cid] = dict(base='гипотеза_neu', text=text[:200] + '…', supports=sup)
    for key, text in EXPL:
        cid = ledger('add', text, '--status', 'гипотеза', '--support', f'{REP} ({key})')
        sup = [] if key == 'не показано' else [dict(**{'class': 'наш_разведка'}, group=GROUP,
                                                    note=f'{key}: правило или мера — после пилота или после результатов')]
        if key == 'пост-хок П3':
            sup.append(dict(**{'class': 'журнал'}, reading='сниппет', group='Xiong и др., ICLR 2024 (arXiv 2306.13063)',
                            note='словесная уверенность самоуверенна, AUROC предсказания ошибки чуть выше 0,5; docs/PRIORITY.md, SCORE-01'))
        sb[cid] = dict(base='гипотеза_neu', text=text[:200] + '…', supports=sup)
    if not DRY:
        json.dump(sb, open(sb_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('support_bits.json обновлён')


if __name__ == '__main__':
    main()
