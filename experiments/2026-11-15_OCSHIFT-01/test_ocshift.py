#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: проверки раскладки сред, загрузки и счёта (ожидания записаны до запуска). python3 test_ocshift.py"""
import json
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['OCSHIFT_IMPORT_ONLY'] = '1'
sys.path.insert(0, HERE)
import ocshift_extract as X  # noqa: E402
import analyze_ocshift as S  # noqa: E402
import analyze_ocshift_test as A  # noqa: E402
import dry_ocshift as D  # noqa: E402

Q, T = S.Q, S.T
bad = []


def check(name, ok):
    print(('✓ ' if ok else '✗ ') + name, flush=True)
    if not ok:
        bad.append(name)


# 1. Раскладка сред
t, p = X.environments('test'), X.environments('pilot')
ref = json.load(open(S.OCREP_PILOT, encoding='utf-8'))
check('блок сверки — первые 96 задач пилота OCREP-01 и его подсказка',
      t[0]['kind'] == 'check' and t[0]['prompt_head'] == ref['prompt_head'] and t[0]['problems'] == ref['problems'][:96])
check('тест: 10 сред по 2200 задач (X = 4…8, p = 0, 1); пилот: 5 сред по 300 (p = 9)',
      [(e['X'], e['p'], len(e['problems'])) for e in t[1:]] == [(x, q, 2200) for x in (4, 5, 6, 7, 8) for q in (0, 1)]
      and [(e['X'], e['p'], len(e['problems'])) for e in p[1:]] == [(x, 9, 300) for x in (4, 5, 6, 7, 8)])
ok_disj, ok_ex, ok_rng, ok_lbl = True, True, True, True
for x in X.RANGES:
    es = [e for e in t + p if e.get('X') == x]
    sets = [set((q['a'], q['b']) for q in e['problems']) for e in es]
    ok_disj &= all(not (a & b) for i, a in enumerate(sets) for b in sets[i + 1:])
    exs = set(tuple(int(z) for z in ln.split('=')[0].split('+')) for e in es for ln in e['prompt_head'].strip().split('\n'))
    ok_ex &= len(exs) == 12 and all(not (s_ & exs) for s_ in sets)
    ok_rng &= all(100 * x <= q['a'] <= 100 * x + 99 and 10 <= q['b'] <= 99 and q['sum'] == q['a'] + q['b'] for e in es for q in e['problems'])
    ok_lbl &= all((q['range'] == 'ID') == (q['sum'] < 100 * (x + 1)) for e in es for q in e['problems'])
check('среды одного диапазона не пересекаются по задачам', ok_disj)
check('12 разных примеров трёх подсказок диапазона в задачи не попали', ok_ex)
check('задачи в своём диапазоне, сумма верна, метка ID — сумма меньше границы', ok_rng and ok_lbl)
check('в подсказке два примера с суммой ниже границы и два — не ниже',
      all(sum(int(ln.split('=')[1]) < e['bound'] for ln in e['prompt_head'].strip().split('\n')) == 2 for e in t[1:] + p[1:]))
check('план двух видеокарт покрывает все девять голов по одному разу, большие модели — на разных картах',
      sorted(X.WORKERS[0] + X.WORKERS[1]) == list(range(9)) and 7 in X.WORKERS[0] and 8 in X.WORKERS[1])

# 2. Загрузка нового вида, правда вторым способом, сверка цепочки
with tempfile.TemporaryDirectory() as tmp:
    d0 = D.build('one', 123)
    json.dump(d0, open(os.path.join(tmp, 'answers.json'), 'w'))
    d, envs = S.load_new(tmp)
    e = envs['X4_p0']
    ans, corr, rid, logp = Q.arrays(dict(problems=e['problems']), e['heads'])
    check('загрузка: 11 сред, 9 голов, массивы среды нужного размера',
          len(envs) == 11 and len(e['heads']) == 9 and corr.shape == (9, 2200) and logp.shape == (9, 2200) and len(ans[0]) == 2200)
    ch = S.check_block(envs)
    check('сверка цепочки на неизменённом блоке проходит: ответы равны, расхождение logp 0', ch['answers_equal'] and ch['max_abs_dlogp'] == 0.0 and ch['n_heads'] == 9)
    d1 = D.build('badcheck', 123)
    json.dump(d1, open(os.path.join(tmp, 'answers.json'), 'w'))
    check('сверка цепочки ловит один изменённый ответ', not S.check_block(S.load_new(tmp)[1])['answers_equal'])
    d0['heads'][2]['cols']['X5_p1']['correct'][7] ^= 1
    json.dump(d0, open(os.path.join(tmp, 'answers.json'), 'w'))
    try:
        S.load_new(tmp)
        check('загрузка ловит правду, не совпавшую с «ответ == a + b»', False)
    except AssertionError:
        check('загрузка ловит правду, не совпавшую с «ответ == a + b»', True)

# 3. Счёт по среде против зарегистрированного кода
st, info = S.prepare(e, 7)
idi, ood = info['idi'], info['ood']
pt = S.core(st, idi, ood)
ref_r = Q.crowd(st['ag'], st['corr'], st['logp'], st['fam'], st['keep'], idi, ood)
check('ИОИ, T и C восьми оценщиков совпадают с analyze_ocrep.crowd',
      all(abs(pt[f'ioi {x}'] - ref_r[x]['ioi']) < 1e-12 and abs(pt[f'T {x}'] - ref_r[x]['T']) < 1e-12 and abs(pt[f'C {x}'] - ref_r[x]['C']) < 1e-12 for x in S.EVALS))
check('MIN8 — наименьшее из восьми', pt['ioi MIN8'] == min(pt[f'ioi {x}'] for x in S.EVALS) and pt['brier MIN8'] == min(pt[f'brier {x}'] for x in S.EVALS))
cs = st['corr'][st['keep']]
hb = int(np.argmax(cs[:, idi].mean(1)))
claim = T.calibrate(st['logp'][st['keep']], cs, idi, ood)[hb]
check('ONE-BEST: голова с лучшей точностью на ID (в заглушке — седьмая), T — её точность OOD, C — её средняя заявка',
      hb == 6 and abs(pt['T ONE-BEST'] - cs[hb, ood].mean()) < 1e-12 and abs(pt['C ONE-BEST'] - claim.mean()) < 1e-12
      and abs(pt['ioi ONE-BEST'] - ((1 - cs[hb, ood].mean()) + max(0.0, claim.mean() - cs[hb, ood].mean()))) < 1e-12)
tt, cc = np.array([1.0, 0.0, 0.5]), np.array([0.9, 0.2, 0.6])
m = S.meas(tt, cc)
check('meas: T, C, ИОИ и Брайер (при ничьей «поровну» — средний по равным головам)',
      abs(m['T'] - 0.5) < 1e-12 and abs(m['C'] - 17 / 30) < 1e-12 and abs(m['ioi'] - (0.5 + 17 / 30 - 0.5)) < 1e-12
      and abs(m['brier'] - np.mean([0.01, 0.04, 0.5 * 0.16 + 0.5 * 0.36])) < 1e-12)
g = np.random.default_rng(5)
fit = g.choice(idi, len(idi))
fo = st['fold_of'][fit]
check('части кросс-подгонки: 5 частей по исходным задачам ID, копии задачи — в одной части, у OOD части нет',
      sorted(set(st['fold_of'][idi])) == [0, 1, 2, 3, 4] and (st['fold_of'][ood] == -1).all()
      and all(not (set(fit[fo != k]) & set(fit[fo == k])) for k in range(5)))
tt_, cc_, tb_, cb_ = [], [], [], []
for k in range(5):
    tr, te = idi[st['fold_of'][idi] != k], idi[st['fold_of'][idi] == k]
    ck_ = T.calibrate(st['logp'][st['keep']], cs, tr, te)
    t_, c_, _ = S.select(ck_, cs[:, te].astype(float))
    tt_.append(t_); cc_.append(c_)
    hk_ = int(np.argmax(cs[:, tr].mean(1)))
    tb_.append(cs[hk_, te].astype(float)); cb_.append(ck_[hk_])
check('wc CONF = T − C на ID с кросс-подгонкой (пересчёт вторым способом)', abs(pt['wc CONF'] - (np.concatenate(tt_).mean() - np.concatenate(cc_).mean())) < 1e-12)
check('wc ONE-BEST — то же для головы, лучшей на обучающих частях', abs(pt['wc ONE-BEST'] - (np.concatenate(tb_).mean() - np.concatenate(cb_).mean())) < 1e-12)
e2 = dict(meta=e['meta'], problems=e['problems'], heads=[dict(h, rows=[dict(r) for r in h['rows']]) for h in e['heads']])
for j_, (r_, p_) in enumerate(zip(e2['heads'][0]['rows'], e2['problems'])):       # голова 0: вне диапазона все ответы неверны
    if p_['range'] == 'OOD':
        r_['answer'], r_['correct'] = p_['sum'] + 1, False
n_ok = 0
for r_, p_ in zip(e2['heads'][1]['rows'], e2['problems']):                         # голова 1: на ID только 10 верных
    if p_['range'] == 'ID':
        good = n_ok < 10
        n_ok += 1
        r_['answer'], r_['correct'] = (p_['sum'], True) if good else (p_['sum'] + 1, False)
st2, info2 = S.prepare(e2, 7)
m2 = info2['method']
check('проверка метода — только по ID: голова без верных ответов вне диапазона проходит; голова с 10 верными на ID — нет',
      m2[info2['names'][0]]['ok'] and m2[info2['names'][0]]['ood_correct'] == 0 and not m2[info2['names'][1]]['ok'] and info2['keep'][0] == 0 and 1 not in info2['keep'])
ex = S.extras(st, info)
check('R2 вторым способом: среднее по задачам ID равно wc CONF точки; ошибка — ст. отклонение / √n',
      abs(ex['wc_conf_normal']['mean'] - pt['wc CONF']) < 1e-12 and ex['wc_conf_normal']['n'] == len(idi) and 0 < ex['wc_conf_normal']['se'] < 0.05)
pt2 = S.core(st, idi, ood)
check('core детерминирован', all(pt[k] == pt2[k] for k in pt))

# 4. Неоднородность и вердикты
gg = np.random.default_rng(11)
same = [gg.normal(0.05, 0.02, 4000) for _ in range(10)]
h0 = A.heterogeneity([0.05 + 0.02 * z for z in (-0.5, 0.3, 0.1, -0.2, 0.4, -0.3, 0.0, 0.2, -0.1, 0.1)], same)
diff = A.heterogeneity([0.12, 0.10, -0.05, 0.11, -0.06, 0.12, -0.04, 0.10, 0.11, -0.05], same)
check('неоднородность: равные разности — p велико; разные (0,02 шума, разброс 0,08) — оба p меньше 0,0025',
      h0['p_chi2'] > 0.05 and h0['p_boot'] > 0.05 and diff['p_chi2'] < 0.0025 and diff['p_boot'] < 0.0025 and h0['df'] == 9)
w = 1 / np.array(h0['sd_env']) ** 2
pts_ = np.array([0.05 + 0.02 * z for z in (-0.5, 0.3, 0.1, -0.2, 0.4, -0.3, 0.0, 0.2, -0.1, 0.1)])
check('Q — по формуле Кохрена', abs(h0['Q'] - (w * (pts_ - (w * pts_).sum() / w.sum()) ** 2).sum()) < 1e-9)
check('val: разность по словарю; у R2 вычитаемого нет', A.val({'a': 3.0, 'b': 1.0}, ('a', 'b')) == 2.0 and A.val({'a': 3.0}, ('a', None)) == 3.0)
check('правила: R1 — ONE-BEST против MIN8, R2 — wc CONF, R3 — CONF против LR-AGREE',
      A.RULES == {'R1': ('ioi ONE-BEST', 'ioi MIN8'), 'R2': ('wc CONF', None), 'R3': ('ioi CONF', 'ioi LR-AGREE')})
b8 = {f'e{k}': gg.normal(0.0, 0.01, 4000) for k in range(8)}
m0 = A.max_t({e: 0.02 for e in b8}, b8)                     # восемь разностей по +2 ст. отклонения: по отдельности «значимы» на 0,025, после отбора — нет
m1 = A.max_t(dict({e: 0.0 for e in b8}, e3=0.06), b8)       # одна разность +6 ст. отклонений
check('max-T: восемь разностей по +2σ не значимы после отбора; одна +6σ — значима, и названа она',
      not m0['significant'] and m0['crit'] > 2.8 and m1['significant'] and m1['best'] == 'e3' and m1['p'] < 0.0025)
check('предохранитель знака: вывод против знака точки отменяется; согласный — остаётся; «не решено» не трогается',
      A.sign_guard('опровергнуто', -0.02) == 'не решено (точка и ДИ расходятся)' and A.sign_guard('подтверждено', 0.01) == 'не решено (точка и ДИ расходятся)'
      and A.sign_guard('подтверждено', -0.01) == 'подтверждено' and A.sign_guard('опровергнуто', 0.01) == 'опровергнуто'
      and A.sign_guard('не решено (только BC)', 0.5) == 'не решено (только BC)')
check('max-T по половинам повторов: одна +6σ значима в обеих половинах; восемь по +2σ — ни в одной',
      len(m1['halves']) == 2 and all(h_['significant'] for h_ in m1['halves']) and not any(h_['significant'] for h_ in m0['halves']))

# 5. Три интервала, строгая ветвь, предохранители, разложение D1 (совет 60; ожидания записаны до запуска)
gz = np.random.default_rng(21)
b0 = gz.normal(-0.05, 0.01, 10000)                      # без смещения: точка в середине повторов
i0, z0_, u0, _t0 = A.intervals(b0, -0.05, A.LEVEL)
check('три интервала без смещения: z0 около 0, границы BC определены, все три дают «подтверждено», обратный ≈ процентильному',
      abs(z0_) < 0.05 and u0 == [False, False] and A.verdict3(i0) == 'подтверждено'
      and abs(i0['ci_basic'][1] - i0['ci_percentile'][1]) < 0.002 and A.strict('подтверждено', u0) == 'подтверждено')
b1 = gz.normal(-0.062, 0.01, 10000)                     # повторы на 1,2 ст. отклонения ниже точки −0,05: z0 ≈ +1,2
i1, z1_, u1, _t1 = A.intervals(b1, -0.05, A.LEVEL)
check('смещение z0 ≈ +1,2: верхняя граница BC за разрешением повторов — взят наибольший повтор; обратная ≈ точка + (z0 + 2,807)·SE; вывод — «подтверждено»',
      1.0 < z1_ < 1.4 and u1 == [False, True] and i1['ci'][1] == float(b1.max())
      and abs(i1['ci_basic'][1] - (-0.05 + (1.2 + 2.807) * 0.01)) < 0.004 and A.verdict3(i1) == 'подтверждено')
check('строгая ветвь: «подтверждено» на границе BC за разрешением → «не решено (BC не определён)»; «опровергнуто» с определённой нижней и «не решено» — без изменений',
      A.strict('подтверждено', u1) == 'не решено (BC не определён)' and A.strict('опровергнуто', u1) == 'опровергнуто'
      and A.strict('не решено', u1) == 'не решено')
b2 = gz.normal(-0.045, 0.01, 10000)                     # повторы на 2,5 ст. отклонения ниже точки −0,02
check('расхождение интервалов: процентильный и BC дают «подтверждено», обратный — нет → «не решено (только BC и процентильный)»',
      A.verdict3(A.intervals(b2, -0.02, A.LEVEL)[0]) == 'не решено (только BC и процентильный)')
check('выводы разных знаков → «не решено (ДИ противоречат)»',
      A.verdict3(dict(ci=[-0.3, -0.1], ci_percentile=[-0.3, -0.1], ci_basic=[0.1, 0.3])) == 'не решено (ДИ противоречат)')
e1_ = A.ci3_entry(b1, -0.05, A.LEVEL)
check('запись правила: метка границы BC, доли за границами, сдвиг «медиана − точка» ≈ −0,012, по другую сторону нуля повторов нет',
      e1_['bc_undetermined'] == [False, True] and 'верхняя' in e1_['bc_note'] and e1_['bc_tail'][1] < A.MIN_TAIL
      and abs(e1_['boot_shift'] + 0.012) < 0.001 and e1_['n_above_0'] == 0)
by = {'a0': -0.20, 'a1': -0.22, 'b0': 0.01, 'b1': 0.02, 'c0': 0.01, 'c1': 0.0, 'd0': 0.02, 'd1': 0.01, 'e0': 0.01, 'e1': 0.02}
grp = {k_: k_[0] for k_ in by}
v_, info_ = A.range_guard('подтверждено', by, grp)
check('без одного диапазона: среднее сделал один диапазон → «не решено (без одного диапазона)»; сред того же знака 2 из 10',
      v_ == 'не решено (без одного диапазона)' and not info_['holds'] and info_['n_same_sign'] == 2 and info_['n'] == 10
      and info_['mean_without']['a'] > 0 and len(info_['mean_without']) == 5)
by2 = {k_: -0.05 - 0.01 * i_ for i_, k_ in enumerate(by)}
v2_, info2_ = A.range_guard('подтверждено', by2, grp)
check('без одного диапазона: все среды одного знака — вывод остаётся; «не решено» предохранитель не трогает',
      v2_ == 'подтверждено' and info2_['holds'] and info2_['n_same_sign'] == 10 and A.range_guard('не решено', by, grp)[0] == 'не решено')
check('разложение ИОИ: незнание + самообман = ИОИ — у ONE-BEST и у лучшего из восьми',
      abs(pt['ign ONE-BEST'] + pt['dec ONE-BEST'] - pt['ioi ONE-BEST']) < 1e-12 and abs(pt['ign MIN8'] + pt['dec MIN8'] - pt['ioi MIN8']) < 1e-12
      and pt['dec ONE-BEST'] >= 0 and pt['dec MIN8'] >= 0)
neg_ = dict(ci=[-0.3, -0.1], ci_percentile=[-0.3, -0.1], ci_basic=[-0.3, -0.1])
zer_ = dict(ci=[-0.1, 0.1], ci_percentile=[-0.1, 0.1], ci_basic=[-0.1, 0.1])
pos_ = dict(ci=[0.1, 0.3], ci_percentile=[0.1, 0.3], ci_basic=[0.1, 0.3])
check('правило чтения R1: знак дала точность — «одна голова точнее; о честности оценки вывода нет»; знак дал самообман — «оценка одной головы честнее…»',
      A.reading_r1(neg_, zer_)['if_confirmed'] == 'одна голова точнее; о честности оценки вывода нет'
      and A.reading_r1(zer_, neg_)['if_confirmed'].startswith('оценка одной головы честнее')
      and A.reading_r1(zer_, zer_)['if_confirmed'] == A.READ_NONE and A.reading_r1(pos_, pos_)['if_refuted'] == 'толпа точнее, и её оценка честнее'
      and A.reading_r1(neg_, pos_)['if_confirmed'] == 'одна голова точнее, но её оценка обманывается сильнее')
print('провалов:', bad)
sys.exit(1 if bad else 0)
