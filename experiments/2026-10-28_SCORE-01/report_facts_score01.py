#!/usr/bin/env python3
"""SCORE-01: описательные факты прогона и пост-хок анализ для отчёта. Записан после результатов (29.10, после analysis_score01.json);
вердиктов не меняет. Список пост-хок мер задан здесь до их первого расчёта, считается один раз и идёт в отчёт целиком, без отбора.

Факты (не анализ гипотез):
  Ф1 хроника этапов по run/<этап>/run_log.jsonl: старт, паузы --stop-after и продолжения, конец (время Берлина); активное и полное время;
  Ф2 цена: сумма cost_usd итоговых записей (поле CLI в пересчёте на API) по этапам и всего — против оценки PREREG §7 (66 $ и 12 $);
  Ф3 ожидания сброса лимита, повторы, повторы API и оборванные ходы — по итоговым записям журналов.
Пост-хок, не в зачёт (PREREG §4 их не предсказывал):
  П1 WIN − LOG по самообману и точности: 95 % t-интервал и p перестановки (из analysis_score01.json, части O1, O2, H1, H2);
  П2 размах средних рук внутри этапа: уверенность против точности;
  П3 «оценка у оценки» — AUC второго рода: насколько уверенность max(p, 1 − p) отличает верные суждения о кандидате (p на верной
     стороне от 0,5) от неверных; суждения p = 0,5 не входят; по всем суждениям руки этапа; 95 % бутстреп по задачам (2000 повторений,
     зерно crc32 имени); и корреляция Пирсона уверенности и точности по задачам (значение руки в задаче — среднее годных вызовов);
  П4 длина рассуждения в разах: Haiku — WIN / LOG; Opus — (LOG + WIN)/2 / NONE (средние выходные токены руки);
  П5 направления, выбранные по пилотам (SC, SD, SL; разведка): в каких выборках подтвердились;
  П6 самообман и ИОИ по 12 клеткам (этап × рука): наименьшее, наибольшее, рука с наибольшим в каждом этапе.
  python3 report_facts_score01.py   → report_facts_score01.json, run/report_facts.log, run/posthoc_score01.md"""
import datetime as dt
import glob
import json
import math
import os
import random
import sys
import zlib
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = ('main_opus', 'rep_opus', 'main_haiku', 'rep_haiku')
ARMS = ('LOG', 'WIN', 'NONE')
BER = ZoneInfo('Europe/Berlin')
f = lambda x, d=3: (f'{x:.{d}f}').replace('.', ',').replace('-', '−')
hm = lambda s: dt.datetime.fromisoformat(s).astimezone(BER).strftime('%H:%M:%S')
N_BOOT = 2000


def timeline(st):
    ev = [json.loads(l) for l in open(os.path.join(HERE, 'run', st, 'run_log.jsonl'), encoding='utf-8')]
    seg, cur, out = [], None, dict(starts=[], pauses=[], done=None)
    for e in ev:
        t = dt.datetime.fromisoformat(e['at'])
        if e['event'] == 'старт':
            cur = t; out['starts'].append(e['at'])
        elif e['event'] in ('пауза', 'готово'):
            seg.append((t - cur).total_seconds()); cur = None
            out['pauses' if e['event'] == 'пауза' else 'done'] = (out['pauses'] + [e['at']]) if e['event'] == 'пауза' else e['at']
    t0, t1 = dt.datetime.fromisoformat(out['starts'][0]), dt.datetime.fromisoformat(out['done'])
    out['active_h'] = sum(seg) / 3600
    out['wall_h'] = (t1 - t0).total_seconds() / 3600
    out['n_calls_logged'] = sum(1 for e in ev if e['event'] == 'вызов')
    return out


def journal_flags(st):
    c = dict(final=0, waits=0, retries=0, api_retry_before=0, api_retry_after=0, broken=0, attempts_gt1=0)
    for p in glob.glob(os.path.join(HERE, 'run', st, 'WH_*.jsonl')):
        for l in open(p, encoding='utf-8'):
            r = json.loads(l)
            if not r.get('final'):
                continue
            c['final'] += 1
            c['waits'] += r.get('waits', 0)
            c['retries'] += r.get('retries', 0)
            c['attempts_gt1'] += r.get('attempt', 1) > 1
            fl = r.get('flags') or {}
            c['api_retry_before'] += fl.get('api_retry_до_начала', 0)
            c['api_retry_after'] += fl.get('api_retry_после_начала', 0)
            c['broken'] += bool(fl.get('оборванный_ход'))
    return c


def auc2(pairs):
    """AUC второго рода: P(уверенность верного суждения > уверенности неверного), ничьи — ½."""
    pos = sorted(c for c, ok in pairs if ok)
    neg = sorted(c for c, ok in pairs if not ok)
    if not pos or not neg:
        return float('nan')
    import bisect
    s = 0.0
    for c in pos:
        lo, hi = bisect.bisect_left(neg, c), bisect.bisect_right(neg, c)
        s += lo + 0.5 * (hi - lo)
    return s / (len(pos) * len(neg))


def judgments(rows, task, arm):
    out = []
    for k, r in rows.items():
        t, a, _ = k.split('|')
        if t != task or a != arm or not r['valid']:
            continue
        for p, y in zip(r['p'], r['labels']):
            if p == 0.5:
                continue
            out.append((max(p, 1 - p), (p > 0.5) == (y == 1)))
    return out


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sxy / (sx * sy) if sx > 0 and sy > 0 else float('nan')


def main():
    A = json.load(open(os.path.join(HERE, 'analysis_score01.json'), encoding='utf-8'))
    R = dict(facts={}, posthoc={})
    log, md = [], ['# SCORE-01 — пост-хок, не в зачёт (`report_facts_score01.py`; PREREG §4 этих мер не предсказывал; вердиктов не меняют)', '']
    # Ф1–Ф3
    cost_all, calls_all = dict(opus=0.0, haiku=0.0), 0
    for st in STAGES:
        E = json.load(open(os.path.join(HERE, 'evals', f'{st}.json'), encoding='utf-8'))
        cost = sum(r['cost'] for r in E['rows'].values() if r.get('cost') is not None)
        n = sum(1 for r in E['rows'].values())
        tl, jf = timeline(st), journal_flags(st)
        cost_all[st.split('_')[1]] += cost
        calls_all += n
        R['facts'][st] = dict(timeline=tl, flags=jf, cost=cost, calls=n, cost_per_call=cost / n)
        pz = ', '.join(f'пауза {hm(p)} → продолжение {hm(s)}' for p, s in zip(tl['pauses'], tl['starts'][1:]))
        log.append(f"{st}: старт {hm(tl['starts'][0])}, {pz + ', ' if pz else ''}конец {hm(tl['done'])} (Берлин); "
                   f"активно {f(tl['active_h'], 2)} ч, всего {f(tl['wall_h'], 2)} ч; вызовов {n} (в журнале запусков {tl['n_calls_logged']}); "
                   f"цена {f(cost, 2)} $ ({f(cost / n, 4)} $ на вызов); ожиданий сброса лимита {jf['waits']}, повторов {jf['retries']}, "
                   f"повторов API до начала {jf['api_retry_before']} и после начала {jf['api_retry_after']}, оборванных ходов {jf['broken']}, попыток > 1 — {jf['attempts_gt1']}")
    R['facts']['total'] = dict(calls=calls_all, cost_opus=cost_all['opus'], cost_haiku=cost_all['haiku'], cost=sum(cost_all.values()))
    log.append(f"всего: вызовов {calls_all}; цена Opus {f(cost_all['opus'], 2)} $, Haiku {f(cost_all['haiku'], 2)} $, вместе {f(sum(cost_all.values()), 2)} $ "
               '(оценка PREREG §7: около 66 $ и 12 $)')
    # П1
    md += ['## П1. WIN − LOG по самообману и точности (95 % t-интервал, p перестановки знаков — оценка Монте-Карло, 100 000)', '',
           '| Этап | Мера | Среднее | 95 % | p перестановки |', '|---|---|---|---|---|']
    p1 = {}
    for st in STAGES:
        mdl = st.split('_')[1]
        for pid, m in ((('O1', 'self_dec'), ('O2', 'acc')) if mdl == 'opus' else (('H1', 'self_dec'), ('H2', 'acc'))):
            v = A['verdicts'][f'{pid}|{st}']
            p1[f'{st}|{m}'] = dict(mean=v['mean'], ci95=v['ci95'], p=v['p_perm_two_sided'])
            md.append(f"| {st} | {m} | {f(v['mean'])} | [{f(v['ci95'][0])}; {f(v['ci95'][1])}] | {f(v['p_perm_two_sided'], 3)} |")
    neg = sum(1 for st in STAGES if p1[f'{st}|self_dec']['mean'] < 0)
    cov = sum(1 for st in STAGES if p1[f'{st}|self_dec']['ci95'][0] < 0 < p1[f'{st}|self_dec']['ci95'][1])
    md += ['', f'- Самообман WIN − LOG меньше нуля в {neg} этапах из 4; 95 % интервал накрывает 0 в {cov} из 4.', '']
    R['posthoc']['P1'] = dict(rows=p1, self_dec_negative=neg, ci95_covers0=cov)
    # П2, П6
    md += ['## П2. Размах средних рук внутри этапа', '', '| Этап | Уверенность: от — до (размах) | Точность: от — до (размах) |', '|---|---|---|']
    p2, cells = {}, []
    for st in STAGES:
        S = A['stages'][st]['summary']
        c, a = [S[x]['conf'] for x in ARMS], [S[x]['acc'] for x in ARMS]
        p2[st] = dict(conf=[min(c), max(c)], acc=[min(a), max(a)])
        md.append(f'| {st} | {f(min(c))} — {f(max(c))} ({f(max(c) - min(c))}) | {f(min(a))} — {f(max(a))} ({f(max(a) - min(a))}) |')
        for x in ARMS:
            cells.append((st, x, S[x]['self_dec'], S[x]['ioi']))
    wider = sum(1 for st in STAGES if p2[st]['acc'][1] - p2[st]['acc'][0] > p2[st]['conf'][1] - p2[st]['conf'][0])
    md += ['', f'- Размах точности больше размаха уверенности в {wider} этапах из 4.', '']
    R['posthoc']['P2'] = dict(rows=p2, acc_range_wider=wider)
    # П3
    md += ['## П3. «Оценка у оценки»: AUC второго рода и корреляция уверенности с точностью по задачам', '',
           '| Этап | Рука | Суждений (верных) | AUC второго рода [95 % бутстреп по задачам] | Корреляция по задачам |', '|---|---|---|---|---|']
    p3 = {}
    for st in STAGES:
        E = json.load(open(os.path.join(HERE, 'evals', f'{st}.json'), encoding='utf-8'))
        tasks = sorted({r['task'] for r in E['rows'].values()})
        for arm in ARMS:
            J = {t: judgments(E['rows'], t, arm) for t in tasks}
            allj = [j for t in tasks for j in J[t]]
            a0 = auc2(allj)
            rng = random.Random(zlib.crc32(f'P3|{st}|{arm}'.encode()))
            bs = []
            for _ in range(N_BOOT):
                smp = [j for t in (rng.choice(tasks) for _ in tasks) for j in J[t]]
                v = auc2(smp)
                if not math.isnan(v):
                    bs.append(v)
            bs.sort()
            lo, hi = bs[int(0.025 * len(bs))], bs[int(0.975 * len(bs)) - 1]
            xc, xa = [], []
            for t in tasks:
                rr = [r for k, r in E['rows'].items() if r['task'] == t and r['arm'] == arm and r['valid']]
                if rr:
                    xc.append(sum(r['conf'] for r in rr) / len(rr)); xa.append(sum(r['acc'] for r in rr) / len(rr))
            rho = pearson(xc, xa)
            p3[f'{st}|{arm}'] = dict(n=len(allj), n_correct=sum(ok for _, ok in allj), auc2=a0, ci95=[lo, hi], r_tasks=rho, n_tasks=len(xc))
            md.append(f'| {st} | {arm} | {len(allj)} ({sum(ok for _, ok in allj)}) | {f(a0)} [{f(lo)}; {f(hi)}] | {f(rho)} |')
    above = sum(1 for v in p3.values() if v['ci95'][0] > 0.5)
    md += ['', f'- 95 % интервал AUC второго рода выше 0,5 в {above} клетках из 12.', '']
    R['posthoc']['P3'] = dict(rows=p3, ci_above_half=above)
    # П4
    md += ['## П4. Длина рассуждения в разах (средние выходные токены руки)', '', '| Этап | Отношение | Величина |', '|---|---|---|']
    p4 = {}
    for st in STAGES:
        S = A['stages'][st]['summary']
        if st.endswith('haiku'):
            p4[st] = dict(kind='WIN/LOG', ratio=S['WIN']['out'] / S['LOG']['out'])
        else:
            p4[st] = dict(kind='(LOG+WIN)/2 / NONE', ratio=(S['LOG']['out'] + S['WIN']['out']) / 2 / S['NONE']['out'])
        md.append(f"| {st} | {p4[st]['kind']} | {f(p4[st]['ratio'], 2)} |")
    md.append('')
    R['posthoc']['P4'] = p4
    # П5
    picked = ['SC_opus', 'SD_opus', 'SL_opus', 'SD_haiku', 'SL_haiku']
    expl = ['OE1', 'OE2', 'OE3', 'H7', 'HE1', 'HE2', 'HE3']
    md += ['## П5. Направления, выбранные по пилотам (PREREG §3, §6): где подтвердились', '', '| Что | Основная | Повтор |', '|---|---|---|']
    p5 = {}
    for c in picked:
        s = A['status'][c]
        p5[c] = [s['main_reading'], s['rep_reading']]
        md.append(f'| {c} | {s["main_reading"]} | {s["rep_reading"]} |')
    for e in expl:
        mdl = 'opus' if e.startswith('O') else 'haiku'
        p5[e] = [A['verdicts'][f'{e}|main_{mdl}']['outcome'], A['verdicts'][f'{e}|rep_{mdl}']['outcome']]
        md.append(f'| {e} | {p5[e][0]} | {p5[e][1]} |')
    both_c = sum(1 for c in picked if p5[c] == ['подтверждено', 'подтверждено'])
    both_e = sum(1 for e in expl if p5[e] == ['подтверждено', 'подтверждено'])
    one_e = sum(1 for e in expl if p5[e].count('подтверждено') == 1)
    md += ['', f'- В обеих выборках подтвердились {both_c} сводных из {len(picked)}; частей разведки — {both_e} из {len(expl)} (ровно в одной выборке — {one_e}).', '']
    R['posthoc']['P5'] = dict(rows=p5, composites_both=both_c, explore_both=both_e, explore_one=one_e)
    # П5б и П7 — добавлены 29.10 после независимой проверки отчёта (lenses/REPORT_CHECK.md, находки 3 и 13 г); тоже пост-хок, не в зачёт
    sys.path.insert(0, HERE)
    from analyze_score01 import PRED
    PW = json.load(open(os.path.join(HERE, 'pilot_power.json'), encoding='utf-8'))['preds']
    EX = {q['id']: q['expect'] for q in PRED}
    comp_part = dict(SC_opus='O7', SD_opus='O8', SL_opus='O9', SD_haiku='H8', SL_haiku='H9')
    parts = list(comp_part.values()) + expl
    sign_ok = {}
    for pid in parts:
        mdl = 'opus' if pid.startswith('O') else 'haiku'
        q = next(x for x in PRED if x['id'] == pid)
        want = -1 if q['kind'] == 'lt0' else 1
        sign_ok[pid] = [A['verdicts'][f'{pid}|{s}_{mdl}']['mean'] * want > 0 for s in ('main', 'rep')]
    n_both = sum(1 for v in sign_ok.values() if all(v))
    conf_main = dict(c=sum(1 for c in picked if p5[c][0] == 'подтверждено'), e=sum(1 for e in expl if p5[e][0] == 'подтверждено'))
    conf_rep = dict(c=sum(1 for c in picked if p5[c][1] == 'подтверждено'), e=sum(1 for e in expl if p5[e][1] == 'подтверждено'))
    sums = dict(expect_c=sum(EX[comp_part[c]] for c in picked), expect_e=sum(EX[e] for e in expl),
                power_c=sum(PW[comp_part[c]]['power_low'] for c in picked), power_e=sum(PW[e]['power_low'] for e in expl))
    shrink = {pid: [PW[pid]['pilot_mean'] / A['verdicts'][f'{pid}|{s}_haiku']['mean'] for s in ('main', 'rep')] for pid in ('H8', 'H9', 'HE3')}
    md += ['## П5б. Знаки и число подтверждений против ожиданий §5 и мощности §6 (добавлено после проверки отчёта)', '',
           f'- Знак теста совпал с направлением, выбранным по пилотам, в обеих выборках у {n_both} частей из {len(parts)}'
           f" (не совпал у: {', '.join(p for p, v in sign_ok.items() if not all(v))}).",
           f"- Подтверждено в основной выборке: сводных {conf_main['c']} из {len(picked)}, частей разведки {conf_main['e']} из {len(expl)}; "
           f"в повторе — {conf_rep['c']} и {conf_rep['e']}.",
           f"- Сумма моих ожиданий §5: {f(sums['expect_c'], 2)} (сводные) и {f(sums['expect_e'], 2)} (разведка); сумма нижних мощностей §6: "
           f"{f(sums['power_c'], 2)} и {f(sums['power_e'], 2)}.",
           '- Пилот 3 к тесту, во сколько раз пилотное среднее больше тестового (основная выборка; повтор): '
           + '; '.join(f'{pid} {f(v[0], 1)} и {f(v[1], 1)}' for pid, v in shrink.items()) + '.', '']
    R['posthoc']['P5b'] = dict(sign_both=n_both, n_parts=len(parts), sign_ok=sign_ok, confirmed_main=conf_main, confirmed_rep=conf_rep, sums=sums, shrink=shrink)
    md += ['## П7. Два вызова одного промпта у Haiku в тесте (добавлено после проверки отчёта)', '',
           '| Этап | Рука | Корреляция p двух вызовов | Доля суждений на одной стороне от 0,5 (среди пар, где оба p ≠ 0,5) |', '|---|---|---|---|']
    p7 = {}
    for st in ('main_haiku', 'rep_haiku'):
        E = json.load(open(os.path.join(HERE, 'evals', f'{st}.json'), encoding='utf-8'))
        for arm in ARMS:
            xs, ys, same, tot = [], [], 0, 0
            for t in sorted({r['task'] for r in E['rows'].values()}):
                a, b = E['rows'].get(f'{t}|{arm}|0'), E['rows'].get(f'{t}|{arm}|1')
                if a and b and a['valid'] and b['valid']:
                    for x, y in zip(a['p'], b['p']):
                        xs.append(x); ys.append(y)
                        if x != 0.5 and y != 0.5:
                            tot += 1; same += (x > 0.5) == (y > 0.5)
            p7[f'{st}|{arm}'] = dict(r=pearson(xs, ys), same_side=same / tot, n=tot)
            md.append(f'| {st} | {arm} | {f(pearson(xs, ys))} | {f(same / tot)} |')
    md.append('')
    R['posthoc']['P7'] = p7
    # П6
    sd = sorted(cells, key=lambda x: x[2])
    io = sorted(cells, key=lambda x: x[3])
    top_sd = {st: max((c for c in cells if c[0] == st), key=lambda x: x[2])[1] for st in STAGES}
    top_io = {st: max((c for c in cells if c[0] == st), key=lambda x: x[3])[1] for st in STAGES}
    md += ['## П6. Самообман и ИОИ по 12 клеткам', '',
           f'- Самообман: от {f(sd[0][2])} ({sd[0][0]}, {sd[0][1]}) до {f(sd[-1][2])} ({sd[-1][0]}, {sd[-1][1]}); '
           f"наибольший в этапе — {', '.join(f'{st} {top_sd[st]}' for st in STAGES)}.",
           f'- ИОИ: от {f(io[0][3])} ({io[0][0]}, {io[0][1]}) до {f(io[-1][3])} ({io[-1][0]}, {io[-1][1]}); '
           f"наибольший в этапе — {', '.join(f'{st} {top_io[st]}' for st in STAGES)}.", '']
    R['posthoc']['P6'] = dict(self_dec=[sd[0], sd[-1]], ioi=[io[0], io[-1]], top_self_dec=top_sd, top_ioi=top_io)
    json.dump(R, open(os.path.join(HERE, 'report_facts_score01.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, 'run', 'report_facts.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    open(os.path.join(HERE, 'run', 'posthoc_score01.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    print('\n'.join(log)); print(); print('\n'.join(md))


if __name__ == '__main__':
    main()
