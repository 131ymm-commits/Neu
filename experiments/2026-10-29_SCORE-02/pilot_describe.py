#!/usr/bin/env python3
"""SCORE-02: описание пилота (PILOT_PLAN.md). Выгрузка журналов, меры (score02.py metrics), проверка контекста (ctx_check.py SCORE-01
с линией пилота 3 SCORE-01: промпт тот же), меры трёх источников уверенности, распределение уровней согласия, контрасты с бутстрепом по
задачам и мощность для теста (100 задач основной выборки и 59 повтора).
Мощность: в точке — Φ(направление·μ / SE_n − 1,96), SE_n = SD бутстрепа пилота × √(20 / n); с неопределённостью пилота — среднее той же
величины по бутстрепу задач пилота (μ_b вместо μ). Нормальное приближение; вердикты теста — по бутстреп-интервалу, не по нему.
  python3 pilot_describe.py   → pilot_describe.json, печать (журнал — run/pilot_describe.log)"""
import json
import math
import os
import subprocess
import sys
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SC1 = os.path.join(ROOT, 'experiments', '2026-10-28_SCORE-01')
sys.path.insert(0, HERE)
import score02_lib as L  # noqa: E402

f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
Z = NormalDist().inv_cdf(0.975)
PHI = NormalDist().cdf
CONTRASTS = [  # (мера, A, B, направление: +1 — ждём A − B > 0, −1 — < 0); главное — первое. Направления — доопытные (c137a7d)
    ('auc2', 'agree', 'single', +1), ('auc2', 'mean', 'single', +1), ('auc2', 'agree', 'mean', +1),
    ('acc', 'agree', 'single', +1), ('acc', 'mean', 'single', +1),
    ('self_dec', 'mean', 'single', -1), ('self_dec', 'agree', 'single', -1), ('brier', 'mean', 'single', -1),
]
# После проверки по трём линзам (LENSES-1, L3-1): контроль равной грубости — согласие против одного вызова, огрублённого до уровней
# согласия этапа (score02_lib.coarse_map); направление — по пилоту (X1o).
CONTRASTS_POST = [('auc2', 'agree', 'single_c', -1)]
B = 4000
cbin = lambda c: min(int(round((c - 0.5) * 10, 9)), 4)   # корзина от 0,5 с шагом 0,1; без round 0,6 и 0,7 уходят ниже (LENSES-1, L2-2)


def main():
    sys.path.insert(0, SC1)
    import ctx_check as C
    from analyze_score02 import describe
    log, out = [], {}
    for m in ('opus', 'haiku'):
        st = f'pilot_{m}'
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'run_sealed2.py'), 'export', '--journal', os.path.join(HERE, 'run', st),
                        '--out', os.path.join(HERE, 'run', f'{st}_out.jsonl')], check=True, cwd=ROOT, capture_output=True)
        r = subprocess.run([sys.executable, os.path.join(HERE, 'score02.py'), 'metrics', st, 'pilot', os.path.join(HERE, 'run', f'{st}_out.jsonl'), '5'],
                           check=True, capture_output=True, text=True)
        open(os.path.join(HERE, 'run', f'{st}_metrics.log'), 'w', encoding='utf-8').write(r.stdout)
        E = json.load(open(os.path.join(HERE, 'evals', f'{st}.json'), encoding='utf-8'))
        ctx = C.stage(os.path.join(HERE, 'run', st), os.path.join(HERE, 'run', 'pilot_jobs.jsonl'))
        J = L.load(st)
        cand = L.load_cand(st)
        tasks = sorted(J)
        M = L.measures(J, tasks)
        D = describe(J, cand, tasks, E)
        lev = {}
        for t in tasks:
            for c, _ in J[t]['agree']:
                lev[round(c, 2)] = lev.get(round(c, 2), 0) + 1
        una = {}   # единогласные суждения agree по числу вызовов с p ≠ 0,5: {n: [единогласных, всего суждений]}
        for t in tasks:
            for r, n in cand[t]:
                if n and 2 * r != n:
                    u = una.setdefault(n, [0, 0]); u[1] += 1; u[0] += int(r in (0, n))
        bs = L.bootstrap(J, tasks, [c[:3] for c in CONTRASTS + CONTRASTS_POST], B=B, name=st)
        res = {}
        log.append(f'== {st}: вызовов {E["calls"]["n"]}, годных {E["calls"]["valid"]}; выход в среднем {E["calls"]["out"]:.0f} токенов; цена {f(E["calls"]["cost"], 2)} $')
        log.append(f'   контекст: флаг {ctx["flag"]} ({"; ".join(ctx["why"]) or "нет"}); против линии пилота 3 SCORE-01 среднее {f(ctx.get("abs_mean", float("nan")), 1)}, '
                   f'наибольший |остаток| {f(ctx.get("abs_max", float("nan")), 1)}; внутри задачи наибольший |остаток| {f(ctx.get("max_abs_resid") or 0, 1)}')
        for s in L.SOURCES:
            v = M[s]
            log.append(f'   {s:6s}: суждений {v["n"]}, AUC второго рода {f(v["auc2"])}, точность {f(v["acc"])}, уверенность {f(v["conf"])}, '
                       f'самообман {f(v["self_dec"])}, Брайер {f(v["brier"])}, ИОИ {f(v["ioi"])} = незнание {f(v["ign"])} + самообман⁺ {f(v["dec_pos"])}')
        log.append(f'   один вызов, огрублённый до уровней согласия (контроль X1oc): AUC второго рода {f(M["single_c"]["auc2"])}; уровни '
                   + ', '.join(f'{f(x["level"], 3)} — доля agree {f(x["agree_share"])}, доля single после огрубления {f(x["single_c_share"])}' for x in D['levels']))
        tot = sum(lev.values())
        log.append('   уровни согласия (доля вызовов на стороне большинства): ' + ', '.join(f'{f(k, 2)} — {v} ({f(v / tot, 2)})' for k, v in sorted(lev.items())))
        log.append('   единогласные суждения agree по числу вызовов с p ≠ 0,5: ' + ', '.join(f'{n} — {u[0]} из {u[1]}' for n, u in sorted(una.items(), reverse=True))
                   + f'; всего {sum(u[0] for u in una.values())} из {sum(u[1] for u in una.values())}')
        dx, ex = D['decomp_x2'], D['excl']
        log.append(f'   разложение X2: T = {f(dx["T"])} (X2 < 0 при T > {f(dx["T_break"])}), приближение {f(dx["approx"])}, факт {f(dx["x2"])}; '
                   f'исключено: p = 0,5 — {ex["half_calls"]} из {ex["call_judgments"]} вызовов-суждений, ничьих сторон — {ex["side_ties"]} из {ex["cand_with_side"]} кандидатов')
        acc_lev, acc_bin = {}, {}
        for t in tasks:
            for c, o in J[t]['agree']:
                a_ = acc_lev.setdefault(round(c, 2), [0, 0]); a_[0] += 1; a_[1] += o
            for c, o in J[t]['single']:
                b_ = acc_bin.setdefault(cbin(c), [0, 0]); b_[0] += 1; b_[1] += o
        log.append('   точность по уровню согласия: ' + ', '.join(f'{f(k, 2)} — {f(v[1] / v[0])} ({v[0]})' for k, v in sorted(acc_lev.items())))
        log.append('   один вызов, точность по уверенности (корзины от 0,5 с шагом 0,1): '
                   + ', '.join(f'{f(0.5 + k / 10, 1)} — {f(v[1] / v[0])} ({v[0]})' for k, v in sorted(acc_bin.items())))
        for (meas, a, b, d) in CONTRASTS + CONTRASTS_POST:
            mu = L.contrast(M, (meas, a, b))
            xs = bs[(meas, a, b)]
            sd = (sum((x - sum(xs) / len(xs)) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
            lo, hi = L.pct(xs, 0.025), L.pct(xs, 0.975)
            pw = {}
            for n in (100, 59):
                se = sd * math.sqrt(len(tasks) / n)
                pw[n] = dict(point=PHI(d * mu / se - Z) if se > 0 else float('nan'),
                             unc=sum(PHI(d * x / se - Z) for x in xs) / len(xs) if se > 0 else float('nan'))
            res[f'{meas}|{a}-{b}'] = dict(mean=mu, ci95=[lo, hi], sd_boot=sd, direction=d, power=pw)
            log.append(f'   {meas} {a} − {b}: {f(mu)} [{f(lo)}; {f(hi)}] (SD бутстрепа {f(sd)}); мощность, ждём {"> 0" if d > 0 else "< 0"}: '
                       f'100 задач — {f(pw[100]["point"], 2)} в точке, {f(pw[100]["unc"], 2)} с неопределённостью; 59 задач — {f(pw[59]["point"], 2)} и {f(pw[59]["unc"], 2)}')
        out[st] = dict(calls=E['calls'], ctx={k: ctx[k] for k in ('flag', 'why', 'abs_mean', 'abs_max', 'max_abs_resid') if k in ctx}, measures=M,
                       agree_levels=lev, acc_by_agree={str(k): v for k, v in acc_lev.items()}, acc_by_conf_bin={str(k): v for k, v in acc_bin.items()},
                       unanimous={str(k): v for k, v in una.items()}, describe=D, contrasts=res)
    json.dump(out, open(os.path.join(HERE, 'pilot_describe.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, 'run', 'pilot_describe.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
