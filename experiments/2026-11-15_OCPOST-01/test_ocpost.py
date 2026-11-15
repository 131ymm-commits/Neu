#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCPOST-01: проверки раскладки сред, быстрой изотоники, статистик (второй способ), правил (ожидания записаны до запуска).
  python3 test_ocpost.py [--real]
--real — ещё сверка с зарегистрированным анализом OCSHIFT-01 на его десяти средах теста (настоящие данные — только на
сторонней площадке: задание GitHub Actions ocpost_pilot)."""
import inspect
import json
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
os.environ['OCPOST_IMPORT_ONLY'] = '1'
os.environ['OCSHIFT_IMPORT_ONLY'] = '1'
sys.path.insert(0, HERE)
import ocpost_extract as X  # noqa: E402
import ocpost as P  # noqa: E402
import ocshift_extract as XS  # noqa: E402
import dry_ocpost as D  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402

S, T, O = P.S, P.T, P.O
bad = []


def check(name, ok):
    print(('✓ ' if ok else '✗ ') + name, flush=True)
    if not ok:
        bad.append(name)


# 1. Раскладка свежих сред
t = X.environments('test')
old = XS.environments('test') + XS.environments('pilot')[1:]
ref = json.load(open(S.OCREP_PILOT, encoding='utf-8'))
check('блок сверки — тот же, что в OCSHIFT-01 (первые 96 задач пилота OCREP-01 и его подсказка)',
      t[0] == old[0] and t[0]['prompt_head'] == ref['prompt_head'] and t[0]['problems'] == ref['problems'][:96])
check('пять свежих сред по 2200 задач: X = 4…8, p = 2, вид test', [(e['X'], e['p'], e['kind'], len(e['problems'])) for e in t[1:]] == [(x, 2, 'test', 2200) for x in X.RANGES])
ok_disj, ok_ex, ok_rng, ok_lbl, ok_id = True, True, True, True, True
for x in X.RANGES:
    new = [e for e in t if e.get('X') == x][0]
    ns = set((q['a'], q['b']) for q in new['problems'])
    olds = [e for e in old if e.get('X') == x]
    ok_disj &= len(olds) == 3 and all(not (ns & set((q['a'], q['b']) for q in e['problems'])) for e in olds)
    exs = set(tuple(int(z) for z in ln.split('=')[0].split('+')) for e in olds + [new] for ln in e['prompt_head'].strip().split('\n'))
    ok_ex &= len(exs) == 16 and not (ns & exs)
    ok_rng &= all(100 * x <= q['a'] <= 100 * x + 99 and 10 <= q['b'] <= 99 and q['sum'] == q['a'] + q['b'] for q in new['problems'])
    ok_lbl &= all((q['range'] == 'ID') == (q['sum'] < 100 * (x + 1)) for q in new['problems'])
    used = set(e for p in (0, 1, 9) for e in XS.shots((100 * x, 100 * x + 99), 100 * (x + 1), XS.SHOTS_BASE + 1000 * x + p)[1])
    pairs = [(a, b) for a in range(100 * x, 100 * x + 100) for b in range(10, 100) if (a, b) not in used]
    ok_id &= all(pairs[q['id']] == (q['a'], q['b']) for q in new['problems'])
    perm = np.random.default_rng(XS.SPLIT_BASE + x).permutation(len(pairs))
    ok_id &= min(int(np.nonzero(perm == q['id'])[0][0]) for q in new['problems']) >= 2 * 2200 + 300
check('свежие задачи не пересекаются с задачами OCSHIFT-01 того же диапазона (тест p = 0, 1 и пилот p = 9)', ok_disj)
check('16 разных примеров четырёх подсказок диапазона в свежие задачи не попали', ok_ex)
check('задачи в своём диапазоне, сумма верна, метка ID — сумма меньше границы', ok_rng and ok_lbl)
check('номер задачи — место в том же списке пар, что в OCSHIFT-01; места перестановки — после 4700 занятых', ok_id)
check('в подсказке p = 2 два примера с суммой ниже границы и два — не ниже',
      all(sum(int(ln.split('=')[1]) < e['bound'] for ln in e['prompt_head'].strip().split('\n')) == 2 for e in t[1:]))
same_src = all(inspect.getsource(getattr(X, f)) == inspect.getsource(getattr(XS, f))
               for f in ('shots', 'problems', 'check_block', 'answer_logp', 'load', 'run', 'worker', 'gpu_count'))
same_const = all(getattr(X, c) == getattr(XS, c) for c in ('HEADS', 'WORKERS', 'RANGES', 'B_RANGE', 'SHOTS_BASE', 'SPLIT_BASE', 'N_ENV', 'N_PILOT', 'P_TEST', 'P_PILOT', 'CHECK_N'))
check('извлечение: функции счёта, головы, план карт и константы — те же, что в ocshift_extract.py', same_src and same_const)
src_x, src_s = open(os.path.join(HERE, 'ocpost_extract.py'), encoding='utf-8').read(), open(XS.__file__, encoding='utf-8').read()
main_x, main_s = src_x[src_x.index('def main():'):], src_s[src_s.index('def main():'):]
check('main() отличается от OCSHIFT-01 только строкой design (p_new, n_old)',
      main_x.replace(', p_new=P_NEW, n_old=N_OLD', '').replace("OCPOST_IMPORT_ONLY", "OCSHIFT_IMPORT_ONLY") == main_s)
check('MODE = test; переменная импорта без запуска — OCPOST_IMPORT_ONLY', X.MODE == 'test' and "os.environ.get('OCPOST_IMPORT_ONLY')" in src_x)

# 2. Быстрая изотоника равна sklearn до бита
g = np.random.default_rng(1)


def sk(x, y, q):
    return IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(np.asarray(x, float), np.asarray(y, float)).predict(np.asarray(q, float))


cases = []
for n in (1, 2, 3, 5, 40, 800):
    for kind in ('cont', 'ties', 'consty', 'constx', 'eps'):
        x = g.normal(size=n)
        if kind == 'ties':
            x = np.round(x * 3) / 3
        if kind == 'constx':
            x = np.full(n, 0.7)
        if kind == 'eps':
            x = np.repeat(g.normal(size=n // 2 + 1), 2)[:n] + g.choice([0.0, 1e-16, 3e-16], n)
        y = (g.random(n) < 0.4).astype(float) if kind != 'consty' else np.ones(n)
        q = np.concatenate([g.normal(size=50) * 2, x[:5], [x.min() - 1, x.max() + 1]])
        cases.append((x, y, q))
diffs = [float(np.max(np.abs(P.iso_predict(x, y, q) - sk(x, y, q)))) for x, y, q in cases]
check(f'iso_predict = sklearn IsotonicRegression до бита на {len(cases)} наборах (связки, постоянные x и y, n = 1, разница x 1e-16)', max(diffs) == 0.0)
M, C = g.normal(size=(9, 600)), g.random((9, 600)) < 0.35
fit, cols = g.choice(600, 600), g.choice(600, 300)
P.FAST = True
a = P.calibrate(M, C, fit, cols)
P.FAST = False
b = P.calibrate(M, C, fit, cols)
P.FAST = True
check('calibrate (быстрый путь) = analyze_ocgeo_test.calibrate до бита (выборка с повторами)', np.array_equal(a, b))

# 3. Статистики: быстрый путь = зарегистрированный путь; вложенная кросс-подгонка и FIXED — вторым способом
par = O.world_params(0, P.META_T_PILOT)
st, idi, ood = O.draw(par, np.random.default_rng([P.META_T_PILOT, 9, 0]))
fx = st['keep'].index(P.FIXED_WORLD)
fit_b, cols_b = g.choice(idi, len(idi)), g.choice(ood, len(ood))
P.FAST = True
r1 = P.post_stats(st, fit_b, cols_b, fx)
P.FAST = False
r2 = P.post_stats(st, fit_b, cols_b, fx)
P.FAST = True
check('post_stats: быстрый путь = путь sklearn до бита (мир, повтор бутстрепа)', all((r1[k] == r2[k]) or (np.isnan(r1[k]) and np.isnan(r2[k])) for k in r1))


def naive(st, fit, cols, fx):
    """Второй способ: прямые циклы через analyze_ocgeo_test.calibrate и analyze_ocshift.iso_fit, без общих калибровок пар."""
    keep = st['keep']
    cs, L = st['corr'][keep], st['logp'][keep]
    fo = st['fold_of'][fit]
    yc = cs[:, cols].astype(float)
    cal = T.calibrate(L, cs, fit, cols)
    t, c, _ = S.select(cal, yc)
    pairs_t, pairs_c = [], []
    wT, wC, fT, fC = [], [], [], []
    for k in range(5):
        it, ic = [], []
        for j in range(5):
            if j == k:
                continue
            cj = T.calibrate(L, cs, fit[(fo != k) & (fo != j)], fit[fo == j])
            tj, cjj, _ = S.select(cj, cs[:, fit[fo == j]].astype(float))
            it.append(tj)
            ic.append(cjj)
        ck = T.calibrate(L, cs, fit[fo != k], fit[fo == k])
        tk, ckk, _ = S.select(ck, cs[:, fit[fo == k]].astype(float))
        pairs_t.append(tk)
        pairs_c.append(ckk)
        wT.append(tk)
        wC.append(S.iso_fit(np.concatenate(ic), np.concatenate(it)).predict(ckk))
        fT.append(cs[fx, fit[fo == k]].astype(float))
        fC.append(ck[fx])
    post = S.meas(t, S.iso_fit(np.concatenate(pairs_c), np.concatenate(pairs_t)).predict(c))
    return dict(wc_post=float(np.mean(np.concatenate(wT)) - np.mean(np.concatenate(wC))),
                wc_fixed=float(np.mean(np.concatenate(fT)) - np.mean(np.concatenate(fC))),
                wc_conf=float(np.mean(np.concatenate(pairs_t)) - np.mean(np.concatenate(pairs_c))), ioi_post=post['ioi'], brier_post=post['brier'],
                ioi_fixed=S.meas(yc[fx], cal[fx])['ioi'])


nv = naive(st, fit_b, cols_b, fx)
check('wc POST (вложенная кросс-подгонка) = второй способ (прямые циклы, 20 внутренних калибровок)', abs(r1['wc POST'] - nv['wc_post']) < 1e-12)
check('wc FIXED, wc CONF, ИОИ и Брайер POST-CV, ИОИ FIXED = второй способ', max(abs(r1['wc FIXED'] - nv['wc_fixed']), abs(r1['wc CONF'] - nv['wc_conf']),
                                                                          abs(r1['ioi POST-CV'] - nv['ioi_post']), abs(r1['brier POST-CV'] - nv['brier_post']),
                                                                          abs(r1['ioi FIXED'] - nv['ioi_fixed'])) < 1e-12)
check('ign + dec = ioi у CONF, POST-CV, ONE-BEST, FIXED; T у POST-CV = T у CONF (выбор не меняется)',
      all(abs(r1[f'ign {e}'] + r1[f'dec {e}'] - r1[f'ioi {e}']) < 1e-12 for e in ('CONF', 'POST-CV', 'ONE-BEST', 'FIXED')) and r1['T POST-CV'] == r1['T CONF'])
tt_, cc_, _ = S.select(T.calibrate(st['logp'][st['keep']], st['corr'][st['keep']], fit_b, cols_b), st['corr'][st['keep']][:, cols_b].astype(float))
sh = S.meas(tt_, np.clip(cc_ + nv['wc_conf'], 0.0, 1.0))
check('SHIFT («тупое сжатие», совет 64): выбранная заявка CONF + wc CONF, обрезка в [0, 1] — вторым способом', abs(r1['ioi SHIFT'] - sh['ioi']) < 1e-12 and abs(r1['brier SHIFT'] - sh['brier']) < 1e-12)
r3 = P.post_stats(st, fit_b, cols_b, None)
check('без головы FIXED: ключи FIXED — nan, остальные ключи те же', set(r3) == set(r1) and np.isnan(r3['wc FIXED']) and np.isnan(r3['ioi FIXED'])
      and r3['wc POST'] == r1['wc POST'])
fo = st['fold_of'][fit_b]
check('части кросс-подгонки закреплены за исходными задачами: копии задачи — в одной части', all(len(set(fo[fit_b == i])) <= 1 for i in np.unique(fit_b)))

# 4. Правила и интервал
check('M4: точка ± z·ст. откл., z = Φ⁻¹(0,9975) = 2,807', abs(P.Z - 2.807) < 1e-3 and P.m4(1.0, np.array([0.0, 2.0]))[0] == [1.0 - P.Z * np.std([0, 2], ddof=1), 1.0 + P.Z * np.std([0, 2], ddof=1)])
check('знаковое правило: верх < 0 — подтверждено; низ > 0 — опровергнуто; иначе не решено',
      [P.verdict('sign', iv) for iv in ([-0.2, -0.01], [0.01, 0.3], [-0.1, 0.1], [-0.1, 0.0])] == ['подтверждено', 'опровергнуто', 'не решено', 'не решено'])
check('правило эквивалентности: интервал в [−0,02; 0,02] — подтверждено; целиком вне — опровергнуто; иначе не решено',
      [P.verdict('equiv', iv) for iv in ([-0.02, 0.02], [-0.019, 0.005], [0.021, 0.05], [-0.06, -0.03], [-0.01, 0.03], [-0.03, 0.03])]
      == ['подтверждено', 'подтверждено', 'опровергнуто', 'опровергнуто', 'не решено', 'не решено'])
pc, pr = P.power_one('sign', -0.08, 0.0, 0.002, 5)
pe, _ = P.power_one('equiv', 0.0, 0.0, 0.001, 5)
pw, _ = P.power_one('equiv', 0.0, 0.0, 0.05, 5)
check('мощность: сильный эффект — около 1; эквивалентность при малом разбросе — около 1, при большом — 0', pc > 0.999 and pr < 1e-6 and pe > 0.999 and pw == 0.0)

# 5. Правило Т на заготовленных частях
with tempfile.TemporaryDirectory() as tmp:
    def part(name, misses_low, n=3000, first=0):
        ws = []
        for k in range(2):
            pts, sds, bms = [], [], []
            for i in range(n // 2):
                row_p, row_s = [], []
                for s_ in P.TAIL_KEYS:
                    miss = i < misses_low.get(s_, 0) // 2
                    row_p.append(1.0 if miss else 0.0)        # правда 0; промах снизу: нижняя граница выше правды
                    row_s.append(0.1)
                pts.append(row_p)
                sds.append(row_s)
                bms.append(row_p)
            ws.append(dict(k=first + k, truth={s_: 0.0 for s_ in P.TAIL_KEYS}, sd_true={s_: 0.1 for s_ in P.TAIL_KEYS}, point=pts, boot_sd=sds, boot_mean=bms))
        f = os.path.join(tmp, name)
        json.dump(dict(meta=1, worlds=ws), open(f, 'w'))
        return f
    v_ok = P.tail(os.path.join(tmp, 'a.json'), [part('p1.json', {'P1': 8})])['verdict']
    v_bad = P.tail(os.path.join(tmp, 'b.json'), [part('p2.json', {'P2': 80})])['verdict']
    v_mid = P.tail(os.path.join(tmp, 'c.json'), [part('p3.json', {'P3': 30})])['verdict']
    two = P.tail(os.path.join(tmp, 'd.json'), [part('p4.json', {}, n=1000, first=0), part('p5.json', {}, n=1000, first=2)])
    fnan = part('p6.json', {}, n=3000)                                   # совет 64, п. 1: NaN — промах на обе стороны, знаменатель полный
    dn = json.load(open(fnan))
    dn['worlds'][0]['truth']['P0'] = float('nan')                         # правда мира — не число: все 1500 опытов мира — промахи
    dn['worlds'][1]['point'][0][P.TAIL_KEYS.index('P3')] = float('nan')   # один опыт с точкой не числом
    json.dump(dn, open(fnan, 'w'))
    tn = P.tail(os.path.join(tmp, 'e.json'), [fnan])
check('Т: 8 промахов из 3000 — подтверждено; 80 — опровергнуто; 30 — не решено; части складываются по мирам',
      (v_ok, v_bad, v_mid) == ('подтверждено', 'опровергнуто', 'не решено') and two['n_worlds'] == 4 and two['stats']['P0']['n'] == 2000)
check('Т: NaN — промах на обе стороны, знаменатель полный (мир с правдой NaN — 1500 промахов; опыт с точкой NaN — 1), вердикт — опровергнуто',
      tn['stats']['P0']['n'] == 3000 and tn['stats']['P0']['miss_low'] == 1500 and tn['stats']['P0']['miss_high'] == 1500
      and tn['stats']['P3']['n'] == 3000 and tn['stats']['P3']['miss_low'] == 1 and tn['stats']['P3']['miss_high'] == 1 and tn['stats']['P3']['n_nan'] == 1
      and tn['verdict'] == 'опровергнуто')

# 6. Сухой прогон: заглушка строится и читается, правда сходится, сверка цепочки проходит
with tempfile.TemporaryDirectory() as tmp:
    json.dump(D.build('select', 1), open(os.path.join(tmp, 'answers.json'), 'w'))
    d, envs = S.load_new(tmp)
    chk = S.check_block(envs)
    check('заглушка: правда сходится при загрузке, сверка цепочки проходит, сред теста — 5',
          chk['answers_equal'] and chk['max_abs_dlogp'] == 0 and sum(v['meta'].get('kind') == 'test' for v in envs.values()) == 5)
    json.dump(D.build('badcheck', 1), open(os.path.join(tmp, 'answers.json'), 'w'))
    d, envs = S.load_new(tmp)
    check('заглушка badcheck: сверка цепочки не проходит', not S.check_block(envs)['answers_equal'])

# 7. Сверка с зарегистрированным анализом OCSHIFT-01 (только --real: настоящие данные, сторонняя площадка)
if '--real' in sys.argv:
    rr = json.load(open(os.path.join(ROOT, 'gha_out', 'ocshift_test', 'analysis.json'), encoding='utf-8'))
    d, envs = S.load_new(os.path.join(ROOT, 'experiments', '2026-11-15_OCSHIFT-01', 'run', 'out'))
    mx, n_env = 0.0, 0
    for name, e in envs.items():
        if e['meta'].get('kind') != 'test':
            continue
        meta = e['meta']
        st_, info = S.prepare(e, P.SEED_CV + 10 * meta['X'] + meta['p'])
        pt = P.post_stats(st_, info['idi'], info['ood'], P.fixed_index(info))
        rp = rr['envs'][name]['point']
        ex = rr['envs'][name]['extras']['evaluators']['CONF']['post_cv']
        dd = [abs(pt[k] - rp[v]) for k, v in P.REPRO.items()] + [abs(pt['ioi POST-CV'] - ex['ioi']), abs(pt['brier POST-CV'] - ex['brier'])]
        mx = max(mx, max(dd))
        n_env += 1
    check(f'на {n_env} средах теста OCSHIFT-01: ИОИ CONF, ONE-BEST, POST-IN, wc CONF, wc ONE-BEST, Брайер, T, C и POST-CV '
          f'совпадают с зарегистрированным анализом (наибольшая разность {mx:.1e})', n_env == 10 and mx < 1e-12)

print(f'провалов: {len(bad)}' + (f' — {bad}' if bad else ''))
sys.exit(1 if bad else 0)
