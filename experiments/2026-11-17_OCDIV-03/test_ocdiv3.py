#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-03: проверки кода на заглушках (без torch). Сырой вывод теста не читается.
  python3 test_ocdiv3.py"""
import json
import os
import sys
import tempfile
from math import comb

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, X_DIR)
import ocdiv3 as T  # noqa: E402
W, D2, V = T.W, T.D2, T.V
NC = T.NC
FAIL = []


def check(name, ok, info=''):
    print(('✓ ' if ok else '✗ ') + name + (f' — {info}' if info and not ok else ''))
    if not ok:
        FAIL.append(name)


# 1. Среды теста: «тысячи», фаза test2; не пересекаются с пилотами 1 и 2; примеры подсказки не в задачах
te = D2.envs_ocdiv2('test2', ('thousands',))
p1e, p2e = D2.envs_ocdiv2('pilot', ('thousands',)), D2.envs_ocdiv2('pilot2', ('thousands',))
check('среды теста: пять сред «тысяч» по 2200 задач, p = 3, подсказка из четырёх примеров ID, 6 новых токенов',
      [e['name'] for e in te] == list(T.NONDEG_ENVS) and all(len(e['problems']) == 2200 and e['p'] == 3 and e['max_new'] == 6 for e in te)
      and all(len(e['prompt_head'].strip().split('\n')) == 4 and all(int(ln.split('=')[1]) < e['bound'] for ln in e['prompt_head'].strip().split('\n')) for e in te))
ok = True
for a, b, c in zip(p1e, p2e, te):
    ka, kb, kc = ({(q['a'], q['b']) for q in x['problems']} for x in (a, b, c))
    exc = set(D2.shots_id((100 * c['X'], 100 * c['X'] + 99), c['bound'], D2.OE.SHOTS_BASE + 1000 * c['X'] + 3)[1])
    ok &= not (kc & ka) and not (kc & kb) and not (kc & exc)
check('среды теста: задачи не пересекаются с пилотами 1 и 2, примеры подсказки — не задачи', ok)
n_ood = [sum(q['range'] != 'ID' for q in e['problems']) for e in te]
check('среды теста: вне диапазона 1100–1300 задач на среду (по строению)', all(1100 < n < 1300 for n in n_ood), str(n_ood))

# 2. Признаки и страты — только по входу
check('признаки: 1987+45 → c1 = 1, n9 = 0, u = 3, v = 2; 1999+10 → c1 = 0, n9 = 2, u = 0, v = 9',
      list(np.nonzero(T.feats(1987, 45))[0]) == [0, 2 + 3, 12 + 2] and T.feats(1999, 10)[1] == 2 and T.feats(1999, 10)[0] == 0
      and T.feats(1999, 10)[2 + 0] == 1 and T.feats(1999, 10)[12 + 9] == 1)
d = np.array([0.5, 0.1, 0.1, 0.9, 0.3, 0.3, 0.7, 0.2])
lab = T.strata_of(d, 4)
check('страты: равные группы по возрастанию d̂, ничьи — по номеру задачи', list(lab) == [2, 0, 0, 3, 1, 2, 3, 1], str(list(lab)))
check('страты: S = 8 на 1201 задаче — группы 150–151', sorted(np.bincount(T.strata_of(np.random.default_rng(3).random(1201), 8))) == [150] * 7 + [151])
src = open(os.path.join(X_DIR, 'ocdiv3.py'), encoding='utf-8').read()
body = src[src.index('def env_t4'):src.index('def seeds_of')]
check('страты Nd считаются до чтения ответов в нуле: из feats(a, b) задач и моделей пилота',
      "X = np.array([feats(probs[j]['a'], probs[j]['b']) for j in ood])" in body and 'd = dhat(models, crowd, X)' in body
      and body.index('sm = {') < body.index('t4_block_ocdiv2('))

# 3. Нули на мирах с известным устройством (k = 7; неверные ответы голов различны, если не сказано иное)
g = np.random.default_rng(11)
n, k = 4000, 7
hard = np.arange(n) % 2 == 1                                       # половина задач с ошибкой 0,8, половина — 0,2
perr = np.where(hard, 0.8, 0.2)
wrong = g.random((n, k)) < perr[:, None]
Dw = np.where(wrong, (np.arange(k) + 1)[None, :] * 7, 0).astype(np.int64)     # неверный ответ у каждой головы свой
G = lambda p: k * p ** (k - 1) - (k - 1) * p ** k                   # noqa: E731   формула Т4 (docs/2026-11-17_T4_formula.md)
t4_exp = (G(0.2) + G(0.8)) / 2 - G(0.5)
F, F0, t4 = W.f_stats(Dw, g, 30)
_, _, t4s = W.f_stats(Dw, g, 30, hard.astype(np.int64))
check('мир «только трудность»: Т4 ≈ E[G(p)] − G(E[p]) = 0,2260; нуль со стратами по трудности снимает его',
      abs(t4 - t4_exp) < 0.03 and abs(t4s) < 0.02 and abs(t4_exp - 0.2260) < 1e-4, f'{t4:.4f} {t4s:.4f} {t4_exp:.4f}')
# мир «трудность + один неверный ответ на всех» (потеря одного переноса): ложное большинство — не меньше 4 неверных из 7.
# Тогда G(p) = P(Bin(7, p) ≥ 4) симметрична около 0,5, и смесь 0,2 / 0,8 члена Йенсена не даёт; берём смесь 0,1 / 0,5.
wrong2 = g.random((n, k)) < np.where(hard, 0.5, 0.1)[:, None]
Dc = np.where(wrong2, -100, 0).astype(np.int64)
Gm = lambda p: sum(comb(k, j) * p ** j * (1 - p) ** (k - j) for j in range(4, k + 1))   # noqa: E731
jens = (Gm(0.1) + Gm(0.5)) / 2 - Gm(0.3)
sm = {'Nd2': hard.astype(np.int64), 'Nd4': hard.astype(np.int64), 'Nd8': hard.astype(np.int64), 'Nd16': hard.astype(np.int64),
      'переносы': hard.astype(np.int64), 'клетки c1×u': hard.astype(np.int64)}
pt, _ = T.descr_stream(Dc, sm, 1, 2, 3, 20, 3)
check(f'мир «трудность + один неверный ответ»: трудность по входу ≈ член Йенсена {jens:.3f}, совпадение ответов при N3 ≈ 0 (ответ и так один)',
      abs(pt['совпадение ответов']) < 0.01 and abs(pt['трудность по входу'] - jens) < 0.03,
      str({x: round(pt[x], 3) for x in ('трудность по входу', 'совместность ошибок', 'совпадение ответов')}))
check('разложение: три части в сумме дают Т4 N0', abs(pt['трудность по входу'] + pt['совместность ошибок'] + pt['совпадение ответов'] - pt['T4 N0']) < 1e-12)
ali = np.where(wrong, (np.arange(n) % 5 + 1)[:, None] * 1000, 0).astype(np.int64)   # одинаковый неверный ответ на задаче, разный между задачами
pt2, _ = T.descr_stream(ali, sm, 3, 4, 3, 20, 3)
check('мир «неверный ответ привязан к задаче»: совпадение ответов > 0,05', pt2['совпадение ответов'] > 0.05, f"{pt2['совпадение ответов']:.4f}")
Dp = T.permute_wrong(Dw, g, hard.astype(np.int64))
check('N3: где голова верна или без числа — на месте; набор неверных ответов головы внутри страты тот же',
      np.array_equal(Dp == 0, Dw == 0) and all(sorted(Dp[hard == s, c]) == sorted(Dw[hard == s, c]) for s in (0, 1) for c in range(k)))
flat = np.where(g.random((n, k)) < 0.5, (np.arange(k) + 1)[None, :] * 7, 0).astype(np.int64)
check('мир «без трудности и независимо»: Т4 и Т4 со стратами около 0', abs(W.f_stats(flat, g, 30)[2]) < 0.01
      and abs(W.f_stats(flat, g, 30, hard.astype(np.int64))[2]) < 0.01)

# 4. Т4 из формул — та же формула (distill.false_major_indep)
X1 = np.zeros((4, 22))
fm = T.t4_formula({'a': np.zeros(23)}, ['a'] * 7, X1)
check('Т4 из формул: при одинаковой трудности — 0', abs(fm['T4_pred']) < 1e-12)
Pm = np.array([[0.2, 0.8]] * 7)
F_ = np.mean([T.DS.false_major_indep(Pm[:, j]) for j in range(2)])
check('Т4 из формул: две задачи 0,2 и 0,8 — 0,2260, как в docs/2026-11-17_T4_formula.md', abs(F_ - T.DS.false_major_indep(Pm.mean(1)) - 0.2260) < 1e-4)

# 5. Правила: предохранитель по интервалу, пометка «общий», мощность
B = 4000
names = [f'e{i}' for i in range(5)]


def mk(points, sd):
    gg = np.random.default_rng(7)
    return {nm: points[i] + gg.normal(0, sd, B) for i, nm in enumerate(names)}, {nm: sd for nm in names}


pts = dict(zip(names, [0.20, 0.0, 0.0, 0.0, 0.0]))
bts, sds = mk(list(pts.values()), 0.005)
e1 = T.rule_entry(pts, bts, sds, names, set(names))
check('предохранитель: эффект в одной среде — «подтверждено» по среднему, но не держится без неё', e1['verdict'] == 'подтверждено'
      and e1['verdict_rule'] == T.UG and not e1['leave_one_env_out']['holds'], str((e1['verdict'], e1['verdict_rule'])))
pts2 = dict(zip(names, [0.05, 0.06, 0.04, 0.05, 0.002]))
bts2, sds2 = mk(list(pts2.values()), 0.005)
e2 = T.rule_entry(pts2, bts2, sds2, names, set(names))
check('правило: эффект в четырёх средах — «подтверждено», пометка «общий» (интервал > 0 в 4 средах)', e2['verdict_rule'] == 'подтверждено'
      and e2['mark'] == 'общий' and e2['n_env_positive'] == 4, str((e2['verdict_rule'], e2['mark'], e2['n_env_positive'])))
pts3 = dict(zip(names, [0.03, 0.025, 0.02, 0.02, 0.02]))
bts3, sds3 = mk(list(pts3.values()), 0.009)
e3 = T.rule_entry(pts3, bts3, sds3, names, set(names))
check('пометка: среднее надёжно, но интервал среды при 0,0025/5 > 0 только в одной — «сосредоточенный»',
      e3['verdict_rule'] == 'подтверждено' and e3['mark'] == 'сосредоточенный', str((e3['verdict_rule'], e3['mark'], e3['n_env_positive'])))
p0 = T.power3(0.0, 0.0, 0.01, n=200_000)
pbig = T.power3(0.1, 0.01, 0.01, n=20_000)
check('мощность: при нуле «подтверждено» не чаще уровня; при явном эффекте — почти 1 и «общий» тоже', p0['confirm'] <= 0.0025 and pbig['confirm'] > 0.99
      and pbig['general'] > 0.99, str((p0, pbig)))
check('мощность: предохранитель только снижает её', p0['confirm'] <= p0['confirm_no_guard'] and T.power3(0.02, 0.03, 0.01, n=20_000)['confirm']
      <= T.power3(0.02, 0.03, 0.01, n=20_000)['confirm_no_guard'])
check('z′ «общего»: уровень 0,0025 / 5 → 3,29', abs(T.Z_ENV - 3.2905) < 1e-3)

# 6. Пары производителей: 105 структур, точное p
st_all = T.structures(list(T.CROWD))
check('пары: 105 способов выбрать две непересекающиеся пары из семи голов; наблюдённая структура среди них', len(st_all) == 105
      and T.OBSERVED_PAIRS in st_all and comb(7, 2) * comb(5, 2) // 2 == 105)
crowd = list(T.CROWD)
r = np.full((7, 7), 0.01)
i0, i1, j0, j1 = crowd.index('Qwen2.5-0.5B-Instruct'), crowd.index('Qwen2.5-1.5B-Instruct'), crowd.index('SmolLM2-1.7B-Instruct'), crowd.index('SmolLM2-360M-Instruct')
r[i0, i1] = r[i1, i0] = r[j0, j1] = r[j1, j0] = 0.2
pt_ = T.pairs_test([(crowd, r)])
check('пары: заложенный избыток у пар одного производителя → контраст > 0 и p = 1/105', pt_['observed'] > 0.15 and abs(pt_['p_exact'] - 1 / 105) < 1e-12, str(pt_))
check('ДЕТЕРМИНИЗМ-НА-3: три разных задания из 35, выбор воспроизводим', len(set(T.rep_jobs())) == 3 and T.rep_jobs() == T.rep_jobs()
      and all(j[0] in T.CROWD and j[1] in T.NONDEG_ENVS for j in T.rep_jobs()))

# 7. Сквозной прогон на заглушках: пилот 2 и тест «тысяч», 7 голов; трудность растёт с переносом из единиц
tmp = tempfile.mkdtemp(prefix='ocdiv3_stub_')


def fake_cols(e, head_k, rng):
    c = dict(answer=[], correct=[], logp=[], n_tok=[], text_none={})
    for j, q in enumerate(e['problems']):
        if q['range'] == 'ID':
            pc = 0.9
        else:
            pc = 0.35 if (q['a'] % 10 + q['b'] % 10 >= 10) else 0.75
        r_ = rng.random()
        ans = q['sum'] if r_ < pc else q['sum'] + int(rng.choice([-1000, -100, 10 + head_k]))
        if rng.random() < 0.003:
            ans = None
        c['answer'].append(ans)
        c['correct'].append(int(ans == q['sum']))
        c['logp'].append(None if ans is None else float(-rng.random()))
        c['n_tok'].append(0 if ans is None else len(str(ans)) + 1)
        if ans is None:
            c['text_none'][str(j)] = 'x'
    return c


def write_job(jd, nm, envs, rng, k, phase):
    os.makedirs(jd, exist_ok=True)
    repo, commit = V.CROWD[nm].split('@')
    res = dict(experiment='OCDIV-02', phase=phase, model=repo, repo=repo, revision=commit, commit=commit,
               envs=[dict(name=e['name'], family=e['family'], X=e['X'], p=e['p'], max_new=e['max_new'], n=len(e['problems']), idx=e['idx'],
                          keys=[[q['a'], q['b']] for q in e['problems']], prompt_sha256=D2.DX.prompt_sha(e['prompt_head'])) for e in envs],
               seconds_env={e['name']: 0.3 * len(e['problems']) for e in envs}, versions=dict(torch='2.11.0+cpu', transformers='5.20.2'),
               cpu_model='заглушка', cols={e['name']: fake_cols(e, k, rng) for e in envs})
    json.dump(res, open(os.path.join(jd, f'answers_{nm}.json'), 'w', encoding='utf-8'), ensure_ascii=False)


rng = np.random.default_rng(21)
pdirs, tdirs = [], []
for k_, nm in enumerate(V.CROWD):
    jd = os.path.join(tmp, f'p_{k_}')
    write_job(jd, nm, D2.envs_ocdiv2('pilot2', ('thousands',)), rng, k_, 'pilot2')
    pdirs.append(jd)
    jt = os.path.join(tmp, f't_{k_}')
    write_job(jt, nm, te, rng, k_, 'test2')
    tdirs.append(jt)
mp = W.merge(os.path.join(tmp, 'mp'), 'pilot2', 'thousands', pdirs)
mt = W.merge(os.path.join(tmp, 'mt'), 'test2', 'thousands', tdirs)
check('сборка: пилот 2 и тест — семь голов, пять сред', len(mp['heads']) == 7 and len(mt['heads']) == 7 and not mp['head_errors'] and not mt['head_errors'])

# совпадение до бита блока N0 с ocdiv2.env_analysis (та же среда, те же зёрна, B = 6)
_, penvs = T.S.load_new(os.path.join(tmp, 'mp'))
env = penvs['T_X29_p1']
o = W.off_of(env['meta'])
nidt = W.test_id_count('thousands', 29, 'test2')
ref = W.env_analysis(env, W.SEED_CV2 + o, W.SEED_BOOT_PILOT + o, W.SEED_NULL + o, W.SEED_NULL_BOOT + o, nidt, set(), 6, 1, K_point=20, K_boot=3)
st, info = W.prepare_id(env, W.SEED_CV2 + o, nidt)
Dm = W.dmat([info['ans'][q] for q in info['keep']], [p['sum'] for p in env['problems']], list(info['ood']))
scr = np.array([W.carries(env['problems'][j]['a'], env['problems'][j]['b']) for j in info['ood']])
mine, _, _, hom = T.t4_block_ocdiv2(Dm, scr, W.SEED_NULL + o, W.SEED_NULL_BOOT + o, 6, 20, 3)
check('блок N0 совпадает с ocdiv2.env_analysis до бита (Т4, страты по переносам, гомоплазия)',
      all(mine[x] == ref['T4'][x] for x in ('F', 'F0', 'point', 'sd', 'F0_strata', 'point_strata', 'sd_strata'))
      and hom['H'] == ref['homoplasy']['H'] and hom['H0'] == ref['homoplasy']['H0'], str({x: (mine[x], ref['T4'][x]) for x in ('point', 'sd')}))

# совет 70, Н6: замки линзы 1 — состав толпы зависит только от предельных величин каждой головы на ID
import copy  # noqa: E402


def move_rows(env, in_id, seed):
    """Перестановка строк каждой головы между задачами ID (или вне диапазона): смещение d и «верен ли» переходят вместе со строкой."""
    e = copy.deepcopy(env)
    g_ = np.random.default_rng(seed)
    idx = [j for j, q in enumerate(e['problems']) if (q['range'] == 'ID') == in_id]
    for h in e['heads']:
        old = [dict(h['rows'][j]) for j in idx]
        for j_new, r_ in zip(idx, [old[i] for i in g_.permutation(len(idx))]):
            src_sum = None
            r2 = dict(r_)
            if r_['answer'] is not None:
                d_ = r_['answer'] - r_['_sum'] if '_sum' in r_ else None
                r2['answer'] = e['problems'][j_new]['sum'] + d_
            h['rows'][j_new] = r2
    return e


def with_sums(env):
    e = copy.deepcopy(env)
    for h in e['heads']:
        for j, r_ in enumerate(h['rows']):
            r_['_sum'] = e['problems'][j]['sum']
    return e


def strip_sums(env):
    for h in env['heads']:
        for r_ in h['rows']:
            r_.pop('_sum', None)
    return env


def flip_ood(env):
    """Правда вне диапазона перевёрнута: верный ответ → неверное число, неверное число → верный; «без числа» на месте."""
    e = copy.deepcopy(env)
    for h in e['heads']:
        for j, q in enumerate(e['problems']):
            if q['range'] == 'ID' or h['rows'][j]['answer'] is None:
                continue
            ok_ = h['rows'][j]['answer'] == q['sum']
            h['rows'][j] = dict(h['rows'][j], answer=(q['sum'] + 7 if ok_ else q['sum']), correct=(not ok_))
    return e


def t4id_of(env, seed_cv):
    st_, inf_ = W.prepare_id(env, seed_cv, nidt)
    Di = W.dmat([inf_['ans'][q] for q in inf_['keep']], [p['sum'] for p in env['problems']], list(inf_['idi']))
    return inf_['keep'], st_['fold_of'], T.t4_stream(Di, None, 5, 6, 30, 50, 3)[0]


base_keep, base_fold, base_id = t4id_of(env, W.SEED_CV2 + o)
ew = with_sums(env)
ka, _, _ = t4id_of(strip_sums(move_rows(ew, True, 31)), W.SEED_CV2 + o)
kb, _, _ = t4id_of(strip_sums(move_rows(ew, False, 32)), W.SEED_CV2 + o)
kc, fc, idc = t4id_of(flip_ood(env), W.SEED_CV2 + o)
check('Н6а: перестановка строк головы между задачами ID — состав толпы тот же', ka == base_keep, str((ka, base_keep)))
check('Н6б: то же между задачами вне диапазона — состав толпы тот же', kb == base_keep, str((kb, base_keep)))
check('Н6в: правда вне диапазона перевёрнута — толпа, части кросс-подгонки и Т4-ID те же', kc == base_keep and np.array_equal(fc, base_fold)
      and idc['point'] == base_id['point'] and idc['sd'] == base_id['sd'], str((kc, base_keep, idc['point'], base_id['point'])))
en = copy.deepcopy(env)
hk = en['heads'][2]
for j in [j for j, q in enumerate(en['problems']) if q['range'] == 'ID'][:30]:
    hk['rows'][j] = dict(hk['rows'][j], answer=None, correct=False, logp=None)
kn, _, _ = t4id_of(en, W.SEED_CV2 + o)
check('Н6г: замена ответов на «без числа» по ID может менять толпу — законно (доля «без числа» по ID — предельная величина головы)',
      2 not in kn and 2 in base_keep, str((kn, base_keep)))
jobs_dir = os.path.join(X_DIR, 'jobs')
n_t = len([f for f in os.listdir(jobs_dir) if f.startswith('ocdiv3_test_')])
n_r = len([f for f in os.listdir(jobs_dir) if f.startswith('ocdiv3_rep_')])
sumt = open(os.path.join(jobs_dir, 'ocdiv3_sum_test.sh'), encoding='utf-8').read()
merge_line = [ln for ln in sumt.splitlines() if 'merge "$OUT/merged"' in ln][0]
check('Н6д: шаблонов теста 35 и повторов 3; сборка теста берёт только gha_out/ocdiv3_test_*', n_t == 35 and n_r == 3
      and 'gha_out/ocdiv3_test_*' in merge_line and 'rep' not in merge_line, str((n_t, n_r, merge_line)))
jr = os.path.join(tmp, 'rep_dup')
write_job(jr, list(V.CROWD)[1], [te[1]], rng, 1, 'test2')
try:
    W.merge(os.path.join(tmp, 'm_dup'), 'test2', 'thousands', tdirs + [jr])
    check('Н6д: повтор под основным ключом в сборке → СТОП', False)
except SystemExit as ex:
    check('Н6д: повтор под основным ключом в сборке → СТОП', str(ex).startswith('СТОП') and 'дважды' in str(ex), str(ex)[:120])

# совет 70, Н1: проверка чтения П2
gr = np.random.default_rng(41)
nn = 1200
lab_i = np.repeat(np.arange(8), nn // 8)
dd = lab_i / 10 + gr.random(nn) * 0.01
Dr = np.where(gr.random((nn, 7)) < (0.1 + 0.1 * lab_i)[:, None], (np.arange(7) + 1)[None, :] * 0 - 100, 0).astype(np.int64)
rc = T.read_check_env(Dr, lab_i, dd, 3, 500)
check('Н1: страты различают трудность — шаг 0 и шаг 1 пройдены', rc['step0'] and rc['step1'] and rc['diff'] > 0.3, str(rc))
lab_r = gr.permutation(lab_i)
rr = T.read_check_env(Dr, lab_r, dd, 3, 500)
check('Н1: страты случайны — шаг 1 не пройден', not rr['step1'], str({k: rr[k] for k in ('diff', 'ci')}))
r0 = T.read_check_env(Dr, T.strata_of(np.full(nn, 0.5), 8), np.full(nn, 0.5), 3, 100)
check('Н1, шаг 0: все d̂ равны — 8 пустых страт из 8, шаг 0 не пройден', r0['n_empty'] == 8 and not r0['step0'] and not r0['step1'])
mk_ = lambda flags: {f'e{i}': dict(step0=True, step1=f, n_empty=0, diff=0.1, ci=[0.0, 0.2]) for i, f in enumerate(flags)}   # noqa: E731
check('Н1: «сверх трудности» — шаг 1 хотя бы в 4 годных средах; 3 из 5 и n_годных < 4 — неинформативно',
      T.read_verdict(mk_([1, 1, 1, 1, 0]), 5)['informative'] and not T.read_verdict(mk_([1, 1, 1, 0, 0]), 5)['informative']
      and not T.read_verdict(mk_([1, 1, 1]), 3)['informative'])

pres = T.pilot(os.path.join(tmp, 'pilot.json'), os.path.join(tmp, 'mp'), B=20, workers=1, ref=None)
check('пилот: пять сред, Т4, Т4ᵈ, Т4-ID и мощность посчитаны', len(pres['envs']) == 5 and all(np.isfinite(pres['envs'][x]['T4d']['point']) for x in pres['envs'])
      and all(pres['power'][x] for x in pres['power']), str(list(pres['power'])))
w_c1 = np.mean([w[1] for w in pres['models']['weights'].values()])
check('пилот: модели голов видят заложенную трудность (вес c1 > 0 у всех голов)', all(w[1] > 0 for w in pres['models']['weights'].values()), f'{w_c1:.3f}')
e29 = pres['envs']['T_X29_p1']
check('пилот: в заглушке трудность — только перенос из единиц, страты d̂ снимают Т4 (|Т4ᵈ| < |Т4|)', abs(e29['T4d']['point']) < abs(e29['T4']['point']) + 0.01,
      f"{e29['T4']['point']:.4f} {e29['T4d']['point']:.4f}")
check('пилот: Т4 из формул по задачам теста — для всех пяти сред теста', set(pres['formula_test']) == set(T.NONDEG_ENVS))
check('пилот: решение «П3 — правило или описательно» записано', isinstance(pres['p3_rule'], bool))
check('пилот (совет 70): правило Н1 по пяти средам с кросс-подгонкой и мощность при τ из верхней границы посчитаны',
      pres['read_pilot']['n_valid'] == 5 and isinstance(pres['read_pilot']['informative'], bool)
      and all('power_tau_hi' in pres['power'][x] for x in pres['power']), str(pres['read_pilot']))
REG = T.P3_RULE
check('константа PREREG задана по пилоту: П3 — правило (мощность Т4-ID ≥ 0,2)', REG is True, str(REG))
T.P3_RULE = None
try:
    T.test(os.path.join(tmp, 'never.json'), os.path.join(tmp, 'mt'), os.path.join(tmp, 'mp'), os.path.join(tmp, 'pilot.json'), B=5, B_descr=3)
    check('тест: без константы PREREG P3_RULE анализ не идёт', False)
except AssertionError:
    check('тест: без константы PREREG P3_RULE анализ не идёт', True)
T.P3_RULE = REG
tr = T.test(os.path.join(tmp, 'test.json'), os.path.join(tmp, 'mt'), os.path.join(tmp, 'mp'), os.path.join(tmp, 'pilot.json'), B=30, B_descr=5)
check('тест: опыт определён, три правила с вердиктами и пометками', tr['method']['ok'] and set(tr['verdicts']) == {'П1', 'П2', 'П3'}, str(tr.get('verdict')))
check('тест: описательные нули, разложение, пары и Т4 из формул посчитаны', 'descr_descr T4 Nd16' in tr and 'descr_descr совпадение ответов' in tr
      and tr['pairs'] and set(tr['formula']) == set(tr['method']['valid']))
check('тест: повторы бутстрепа и r не пишутся в json', not any(x in e for e in json.load(open(os.path.join(tmp, 'test.json')))['envs'].values() for x in ('_boot', '_r')))
check('тест (совет 70): чтение П2 по правилу Н1, Т4 − Т4-ID, различение страт и версии — в выводе', 'reading' in tr['П2']
      and tr['П2']['reading']['reading'] in (T.READ_INFORMATIVE, T.READ_NONINF) and 'descr_T4 − T4-ID' in tr
      and all('separation' in tr['envs'][n] for n in tr['method']['valid']) and set(tr['versions']) == {'python', 'numpy', 'scipy'})
check('тест (совет 70): чтение П2 не меняет вердикт П2', tr['П2']['verdict'] == tr['П2']['verdict_rule'])
pj = json.load(open(os.path.join(tmp, 'pilot.json'), encoding='utf-8'))
nm0 = sorted(pj['models']['weights'])[0]
pj['models']['weights'][nm0][1] += 0.5
json.dump(pj, open(os.path.join(tmp, 'pilot_bad.json'), 'w', encoding='utf-8'))
try:
    T.test(os.path.join(tmp, 'never2.json'), os.path.join(tmp, 'mt'), os.path.join(tmp, 'mp'), os.path.join(tmp, 'pilot_bad.json'), B=5, B_descr=3)
    check('тест: чужие веса моделей → СТОП', False)
except SystemExit as ex:
    check('тест: чужие веса моделей → СТОП', str(ex).startswith('СТОП'))
T.P3_RULE = False
trd = T.test(os.path.join(tmp, 'test_d.json'), os.path.join(tmp, 'mt'), os.path.join(tmp, 'mp'), os.path.join(tmp, 'pilot.json'), B=10, B_descr=3)
check('тест: при P3_RULE = False П3 — описательно, без пометки', trd['П3']['verdict'].startswith('описательно') and trd['marks']['П3'] is None)
T.P3_RULE = REG
print(f'провалов: {len(FAIL)}')
sys.exit(1 if FAIL else 0)
