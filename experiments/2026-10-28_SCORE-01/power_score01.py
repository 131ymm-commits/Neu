#!/usr/bin/env python3
"""SCORE-01: мощность и ложный уровень предсказаний PREREG по микропилоту 3 (чистый контекст; evals/pilot3_<модель>.json).
Предсказания — analyze_score01.PRED (одна копия). Пилот 3: 20 задач, руки LOG, WIN, NONE, по два вызова на клетку (повторы 0 и 1),
в одном прогоне, вызовы задачи вперемешку.
Цель — в том виде, в каком её даст тест:
  Opus (один вызов на клетку): значение задачи — по одному повтору k ∈ {0, 1} для всех рук цели (два варианта на задачу);
  Haiku (два вызова): значение задачи — по среднему двух повторов каждой руки (один вариант).
Мощность:
  «в точке» — нормальное приближение с t-квантилем при истинном эффекте, равном среднему пилота, и SD пилота; при слабом эффекте
  или среднем около допуска бутстреп выше точки (LENSES-1b, N3), так что «в точке» — не верхняя оценка;
  «с неопределённостью пилота» — двухуровневый бутстреп (как у проверяльщика, lenses/scripts/assurance.py): пилотные задачи
  пересэмплируются, затем тест из n задач по букве анализа; так же — совместно для сводных.
Встроенный A/A у Haiku (чтение §4; LENSES-1c П3). В том же бутстрепе, в мире исправной процедуры: A/A и разность A/A между руками
центрированы внутри каждого мира бутстрепа (E = 0: повторы — один промпт в случайном порядке). Считаются:
  dflag0 — флаг правила §4 (90 % интервал разности A/A между руками (WIN|1 − WIN|0) − (LOG|1 − LOG|0) хоть по одной мере не внутри
  ±2δ) — ложный флаг; sa_ok0 — SA_haiku подтверждён без флага; power_<мера> — флаг при артефакте одного повтора одной руки
  a = 2δ по этой мере (смещает SA на δ); strict0 и sa_strict0 — строгое правило по рукам (все интервалы A/A внутри δ; предлагал
  LENSES-1b) и SA_haiku вместе с ним, для записи. sd_ratio — SD A/A одной руки к SD WIN − LOG (среднее двух повторов) по пилоту.
  Сетка артефактов (LENSES-1d, Н3): артефакт одного повтора руки WIN размера a — самообман +a, точность −a, Брайер +a/2 (смещает SA
  на a/2) — и общий сдвиг повторов обеих рук того же вида при c = COMMON; доля флага у трёх правил: нового (разность A/A между
  руками вне ±2δ), «целиком вне» (интервал A/A руки целиком вне δ; черновик b739deb) и строгого (не все интервалы A/A рук внутри δ).
Ложный уровень — на границе: 0,025 у направленного (истинное среднее 0), 0,05 у эквивалентности (истинная разность ±δ).
Вес (правило 9962627 «по нижней», LENSES-1b N3): P = меньшая из мощностей «в точке» и «с неопределённостью пилота»;
  «подтверждено» — log₂(P / α), α не меньше 0,001; «опровергнуто» — log₂((1 − P)/(1 − α)), 1 − P не меньше 0,001; «не показано» — 0.
  python3 power_score01.py [--md] [--B 4000]   → pilot_power.json и таблица
Импорт ничего не пишет и не считает: md_table(json) печатает таблицы из готового pilot_power.json (сборщик PREREG)."""
import json
import math
import os
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_score01 import AA_D_FACTOR, AA_MARGIN, PRED, REPS, value, weights  # noqa: E402

N_TEST = 100
FLOOR = 0.001
ART_GRID = (0.05, 0.10, 0.13, 0.15, 0.20)                  # размеры артефакта одного повтора руки WIN (сдвиг SA = a/2)
COMMON = 0.15                                               # общий сдвиг повторов обеих рук (SA не смещает)
PILOT = 'pilot3'
f = lambda v, d=3: f'{v:.{d}f}'.replace('.', ',').replace('-', '−')


def _ok(r, m):
    return r is not None and r['valid'] and not (m == 'auc' and math.isnan(r['auc']))


def variants(model):
    """По задаче пилота — матрица вариантов значений всех предсказаний модели (строка — вариант «вызова теста»)."""
    R = json.load(open(os.path.join(HERE, 'evals', f'{PILOT}_{model}.json')))['rows']
    T = sorted({r['task'] for r in R.values()})
    ps = [p for p in PRED if p['model'] == model]
    per_task = []
    layouts = [('0',), ('1',)] if len(REPS[model]) == 1 else [('0', '1')]
    for t in T:
        rows = []
        for reps in layouts:
            row = []
            for p in ps:
                m, w = p['measure'], weights(p['target'])
                vals = {}
                for a in w:
                    v = [value(R[f'{t}|{a}|{k}'], m) for k in reps if _ok(R.get(f'{t}|{a}|{k}'), m)]
                    if v:
                        vals[a] = sum(v) / len(v)
                row.append(sum(wa * vals[a] for a, wa in w.items()) if len(vals) == len(w) else np.nan)
            rows.append(row)
        per_task.append(np.array(rows, dtype=float))
    return ps, per_task


def aa_values(model):
    """По задаче пилота — повтор 1 − повтор 0 у рук LOG и WIN по мерам AA_MARGIN (только при двух вызовах на клетку)."""
    R = json.load(open(os.path.join(HERE, 'evals', f'{PILOT}_{model}.json')))['rows']
    T = sorted({r['task'] for r in R.values()})
    keys = [(a, m) for a in ('LOG', 'WIN') for m in AA_MARGIN]
    X = []
    for t in T:
        row = []
        for a, m in keys:
            r0, r1 = R.get(f'{t}|{a}|0'), R.get(f'{t}|{a}|1')
            row.append(value(r1, m) - value(r0, m) if _ok(r0, m) and _ok(r1, m) else np.nan)
        X.append(row)
    return keys, np.array(X, dtype=float)


def _ci_pos(x, q, margin):
    """(интервал внутри ±margin, интервал целиком вне ±margin) для t-интервала уровня 2q − 1."""
    x = x[~np.isnan(x)]
    n = len(x); h = stats.t.ppf(q, n - 1) * x.std(ddof=1) / math.sqrt(n); m = x.mean()
    return (m - h > -margin) and (m + h < margin), (m - h >= margin) or (m + h <= -margin)


def verdict(x, p):
    x = x[~np.isnan(x)]
    n = len(x); m = x.mean(); s = x.std(ddof=1)
    if p['kind'] == 'equiv':
        h = stats.t.ppf(0.95, n - 1) * s / math.sqrt(n)
        return (m - h > -p['margin']) and (m + h < p['margin'])
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return (m + h < 0) if p['kind'] == 'lt0' else (m - h > 0)


def point_power(p, mu, s, n=N_TEST):
    se = s / math.sqrt(n)
    if p['kind'] == 'equiv':
        t = stats.t.ppf(0.95, n - 1); d = p['margin']
        return max(0.0, stats.norm.cdf((d - mu) / se - t) + stats.norm.cdf((d + mu) / se - t) - 1), 0.05
    t = stats.t.ppf(0.975, n - 1)
    z = (-mu if p['kind'] == 'lt0' else mu) / se
    return stats.norm.cdf(z - t), 0.025


def assurance(model, rng, B, n=N_TEST):
    ps, per_task = variants(model)
    K = len(per_task)
    comps = sorted({p['comp'] for p in ps if p['comp']})
    hits = np.zeros(len(ps)); chits = {c: 0 for c in comps}
    aa = len(REPS[model]) > 1
    if aa:
        aa_keys, AA = aa_values(model)
        ms = list(AA_MARGIN)
        D = np.stack([AA[:, aa_keys.index(('WIN', m))] - AA[:, aa_keys.index(('LOG', m))] for m in ms], 1)
        tol = [AA_D_FACTOR * AA_MARGIN[m] for m in ms]
        cnt = dict(dflag0=0, sa_ok0=0, strict0=0, sa_strict0=0, **{f'power_{m}': 0 for m in ms})
        for rule in ('new', 'gross', 'strict'):
            cnt.update({f'art_{rule}_{x}': 0 for x in ART_GRID}); cnt[f'common_{rule}'] = 0
        vec = lambda x: np.array([x if m == 'self_dec' else (-x if m == 'acc' else x / 2) for m in ms])
        win_cols = [aa_keys.index(('WIN', m)) for m in ms]
        marg = [AA_MARGIN[m] for _, m in aa_keys]
        gross_of = lambda Y: any(_ci_pos(Y[:, k], 0.95, marg[k])[1] for k in range(Y.shape[1]))
        sa_j = [j for j, p in enumerate(ps) if p['comp'] == f'SA_{model}']
        inside = lambda Y, tl: all(_ci_pos(Y[:, k], 0.95, tl[k])[0] for k in range(Y.shape[1]))
    for _ in range(B):
        base = rng.integers(0, K, K)                              # пилот пересэмплирован: истина неизвестна
        idx = base[rng.integers(0, K, n)]
        X = np.array([per_task[i][rng.integers(0, len(per_task[i]))] for i in idx])
        okv = [verdict(X[:, j], p) for j, p in enumerate(ps)]
        hits += okv
        for c in comps:
            chits[c] += all(okv[j] for j, p in enumerate(ps) if p['comp'] == c)
        if aa:                                                    # мир исправной процедуры: E[A/A] = 0 внутри мира
            A0 = AA[idx] - np.nanmean(AA[base], 0)
            D0 = D[idx] - np.nanmean(D[base], 0)
            sa_ok = all(okv[j] for j in sa_j)
            fl = not inside(D0, tol)
            cnt['dflag0'] += fl; cnt['sa_ok0'] += sa_ok and not fl
            st_ = inside(A0, [AA_MARGIN[m] for _, m in aa_keys])
            cnt['strict0'] += st_; cnt['sa_strict0'] += sa_ok and st_
            for k, m in enumerate(ms):                            # артефакт одного повтора одной руки: a = 2δ по мере m
                Da = D0.copy(); Da[:, k] += tol[k]
                cnt[f'power_{m}'] += not inside(Da, tol)
            for x in ART_GRID:                                    # сетка артефактов руки WIN (LENSES-1d, Н3)
                Aa = A0.copy(); Aa[:, win_cols] += vec(x)
                cnt[f'art_new_{x}'] += not inside(D0 + vec(x), tol)
                cnt[f'art_gross_{x}'] += gross_of(Aa)
                cnt[f'art_strict_{x}'] += not inside(Aa, marg)
            Ac = A0 + np.tile(vec(COMMON), 2)                     # общий сдвиг повторов: D не меняется
            cnt['common_new'] += fl
            cnt['common_gross'] += gross_of(Ac)
            cnt['common_strict'] += not inside(Ac, marg)
    extra = None
    if aa:
        extra = {k: v / B for k, v in cnt.items()}
        ja = {m: next(j for j, p in enumerate(ps) if p['comp'] == f'SA_{model}' and p['measure'] == m) for m in ms}
        sa_vals = {m: np.concatenate([v[:, ja[m]] for v in per_task]) for m in ms}
        extra['sd_ratio'] = {f'{a}|{m}': float(np.nanstd(AA[:, aa_keys.index((a, m))], ddof=1) / np.nanstd(sa_vals[m], ddof=1))
                             for a in ('LOG', 'WIN') for m in ms}
    return {p['id']: hits[j] / B for j, p in enumerate(ps)}, {c: v / B for c, v in chits.items()}, ps, per_task, extra


def bits(P, alpha):
    """(вес при «подтверждено», вес при «опровергнуто») по правилу «по нижней»; «не показано» — 0."""
    return math.log2(max(P, 1e-12) / max(alpha, FLOOR)), math.log2(max(1 - P, FLOOR) / (1 - alpha))


def compute(B):
    rng = np.random.default_rng(20261029)
    out = dict(pilot=PILOT, B=B, n_test=N_TEST, preds={}, comps={}, aa={})
    for model in ('opus', 'haiku'):
        if not any(p['model'] == model for p in PRED):
            continue
        a_un, c_un, ps, per_task, extra = assurance(model, rng, B)
        if extra:
            out['aa'][model] = extra
        for j, p in enumerate(ps):
            x = np.concatenate([v[:, j] for v in per_task]); x = x[~np.isnan(x)]
            mu, s = float(x.mean()), float(x.std(ddof=1))
            pw, a = point_power(p, mu, s)
            pw15, _ = point_power(p, mu, 1.5 * s)
            low = min(pw, a_un[p['id']]); b_ok, b_bad = bits(low, a)
            out['preds'][p['id']] = dict(model=model, measure=p['measure'], target=p['target'], kind=p['kind'], margin=p.get('margin'),
                                         pilot_mean=mu, pilot_sd=s, pilot_n=len(x), power_point=pw, power_point_sd15=pw15,
                                         power_assurance=a_un[p['id']], power_low=low, alpha=a, bits=b_ok, bits_refuted=b_bad)
        for c, v in c_un.items():
            parts = [p['id'] for p in ps if p['comp'] == c]
            a_ = max(out['preds'][i]['alpha'] for i in parts)
            prod = math.prod(out['preds'][i]['power_point'] for i in parts)
            low = min(prod, v); b_ok, b_bad = bits(low, a_)
            out['comps'][c] = dict(parts=parts, alpha=a_, power_point_product=prod, power_assurance_joint=v, power_low=low,
                                   bits=b_ok, bits_refuted=b_bad)
    return out


def md_table(out):
    """Таблицы §6 из готового pilot_power.json (ничего не пересчитывает)."""
    L = ['| | Модель | Мера | Что сравнивается | Предсказание | Пилот 3: среднее (SD; значений) | Мощность в точке | В точке при SD × 1,5 | '
         'С неопределённостью пилота | Ложный уровень | Вес, бит: подтверждено / опровергнуто |',
         '|---|---|---|---|---|---|---|---|---|---|---|']
    for pid, q in out['preds'].items():
        tg = q['target']
        what = (f'{tg[1]} − {tg[2]}' if tg[0] == 'pair' else f'рука {tg[1]}' if tg[0] == 'arm' else
                ' '.join(f"{'+' if w > 0 else '−'} {f(abs(w), 1) + '·' if abs(w) != 1 else ''}{a_}" for a_, w in tg[1].items()).lstrip('+ '))
        kind = {'lt0': '< 0', 'gt0': '> 0', 'equiv': f'\\|·\\| < {f(q.get("margin") or 0, 2)}'}[q['kind']]
        d = 0 if q['measure'] == 'out' else 3
        L.append(f"| {pid} | {q['model']} | {q['measure']} | {what} | {kind} | {f(q['pilot_mean'], d)} ({f(q['pilot_sd'], d)}; {q['pilot_n']}) | "
                 f"{f(q['power_point'])} | {f(q['power_point_sd15'])} | {f(q['power_assurance'])} | {f(q['alpha'])} | "
                 f"{f(q['bits'], 1)} / {f(q['bits_refuted'], 1)} |")
    L += ['', '| Сводный | Части | Ложный уровень | Мощность в точке (произведение) | С неопределённостью пилота (совместно) | Вес, бит: подтверждено / опровергнуто |',
          '|---|---|---|---|---|---|']
    for c, v in out['comps'].items():
        L.append(f"| {c} | {', '.join(v['parts'])} | {f(v['alpha'])} | {f(v['power_point_product'])} | {f(v['power_assurance_joint'])} | "
                 f"{f(v['bits'], 1)} / {f(v['bits_refuted'], 1)} |")
    for m, v in out.get('aa', {}).items():
        r = v['sd_ratio']
        L += ['', f"- **Встроенный A/A ({m})** — бутстреп пилота 3 в мире исправной процедуры (A/A центрированы, E = 0):",
              f"  - флаг правила §4 (разность A/A между руками вне ±2δ) — ложный в доле {f(v['dflag0'])}; SA_{m} подтверждён без флага — "
              f"{f(v['sa_ok0'])} (без условия A/A — {f(out['comps'][f'SA_{m}']['power_assurance_joint'])});",
              f"  - артефакт одного повтора одной руки, смещающий SA на δ, флаг ловит в доле: самообман {f(v['power_self_dec'])}, точность "
              f"{f(v['power_acc'])}, Брайер {f(v['power_brier'])};",
              f"  - строгое правило по рукам (все интервалы A/A внутри δ) выполнено в {f(v['strict0'])}, SA_{m} вместе с ним — {f(v['sa_strict0'])};",
              f"  - SD A/A одной руки к SD разности WIN − LOG (среднее двух повторов) по пилоту 3 — от {f(min(r.values()), 2)} до {f(max(r.values()), 2)};",
              f"  - доля флага по правилам при артефакте одного повтора руки WIN (самообман +a, точность −a, Брайер +a/2; SA смещается на a/2) и при общем сдвиге повторов обеих рук (c = {f(COMMON, 2)}; SA не смещается):",
              '',
              '| Правило | ' + ' | '.join(f'a = {f(x, 2)}' for x in ART_GRID) + f' | общий сдвиг c = {f(COMMON, 2)} |',
              '|---|' + '---|' * (len(ART_GRID) + 1),
              *[f"| {nmr} | " + ' | '.join(f(v[f'art_{rk}_{x}']) for x in ART_GRID) + f" | {f(v[f'common_{rk}'])} |"
                for rk, nmr in (('new', 'разность A/A между руками вне ±2δ (§4)'), ('gross', 'A/A руки целиком вне δ (черновик b739deb)'),
                                ('strict', 'не все A/A рук внутри δ (LENSES-1b)'))]]
    return '\n'.join(L)


def main():
    B = int(sys.argv[sys.argv.index('--B') + 1]) if '--B' in sys.argv else 4000
    out = compute(B)
    json.dump(out, open(os.path.join(HERE, 'pilot_power.json'), 'w'), ensure_ascii=False, indent=1)
    print(md_table(out) if '--md' in sys.argv else json.dumps(out['comps'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
