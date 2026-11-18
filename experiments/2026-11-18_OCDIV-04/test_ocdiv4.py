#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: проверки кода на заглушках (без настоящих ответов голов). Ожидания — из построения миров, а не из головы (ERRORS № 181).
  python3 test_ocdiv4.py        печатает ✓/✗ по каждой проверке и «провалов: N»"""
import os
import sys

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, X_DIR)
import ocdiv4 as C  # noqa: E402

W, NC = C.W, C.NC
fails = []


def check(name, ok, info=''):
    print(('✓ ' if ok else '✗ ') + name + ('' if ok else f'  [{info}]'), flush=True)
    if not ok:
        fails.append(name)


# 1. Узор переносов: внутри области κ принимает ровно два значения, их различает c1 (обе семьи, все среды гипотезы)
ok = True
for X in (19, 29, 39, 49, 59, 69, 79, 89, 9, 99, 999):
    lo, bound = 100 * X, 100 * (X + 1)
    for ood in (True, False):
        pats = {}
        for a in range(lo, lo + 100):
            for b in range(10, 100):
                if (a + b >= bound) == ood:
                    pats.setdefault(C.c1_of(a, b), set()).add(C.kappa(a, b))
        ok &= set(pats) == {0, 1} and all(len(v) == 1 for v in pats.values()) and pats[0] != pats[1]
check('узор переносов: внутри области — два значения, различает только c1 (11 сред, обе области)', ok)
check('κ: 1987 + 45 → переносы (1, 1, 1, 0); 1903 + 12 → (0, 0, 0, 0)', C.kappa(1987, 45) == (1, 1, 1, 0) and C.kappa(1903, 12) == (0, 0, 0, 0))

# 2. Виды смещений (по слагаемым и коду)
kinds = {1932 - 2032: '−10^2', 1032 - 2032: '−10^3', 2022 - 2032: '−10^1', 2932 - 2032: '+9·10^2', 2035 - 2032: 'малое (|d| < 10)',
         0: 'верно', NC + 3: 'без числа', 2132 - 2032: '+10^2', 777: 'прочее'}
check('виды смещений: потеря переноса в разряде k, лишняя девятка, малое, прочее', all(C.offset_kind(d) == k for d, k in kinds.items()),
      str({d: C.offset_kind(d) for d in kinds}))


# 3. Миры на заглушках: n задач, h голов; смещения головы — из её словаря
def world(n, h, seed, p_err, shared=0.0, item_dep_p=False):
    """p_err — доля ошибок головы; item_dep_p — вероятность ошибки зависит от задачи (трудность, общая для голов);
    shared — доля ошибок, в которых голова берёт общее для задачи смещение (заложенное совпадение)."""
    g = np.random.default_rng(seed)
    st = (g.random(n) < 0.5).astype(np.int64)                       # страта c1
    diff = g.uniform(0.05, 0.95, n) if item_dep_p else np.full(n, p_err)
    common = g.choice([-10, -100, -1000, 900], n)                     # общее для задачи смещение
    D = np.zeros((n, h), np.int64)
    for k in range(h):
        vocab = np.array([-10, -100, -1000, 900, 1, -1, 7 + k, 11 * (k + 1)])
        for j in range(n):
            if g.random() < diff[j]:
                D[j, k] = common[j] if g.random() < shared else int(g.choice(vocab))
            if g.random() < 0.01:
                D[j, k] = NC + k
    return D, st


D, st = world(600, 7, 1, 0.5)
g = np.random.default_rng(5)
Dp = C.permute_wrong(D, g, st)
same_pattern = np.array_equal(D == 0, Dp == 0) and np.array_equal(D >= NC, Dp >= NC)
multiset = all(sorted(D[(st == s) & C.wrong_num(D)[:, k], k]) == sorted(Dp[(st == s) & C.wrong_num(Dp)[:, k], k]) for k in range(7) for s in (0, 1))
check('N3c: верные ответы и «без числа» на месте; набор неверных смещений головы внутри страты тот же', same_pattern and multiset)
check('N3c: множества совместных ошибок пар не меняются (K сравним между областями)', [c for c, _ in C.pair_counts(D)] == [c for c, _ in C.pair_counts(Dp)])

# мир «независимо, смещения не зависят от задачи»: Δ3c и K около нуля
D0, st0 = world(1500, 7, 2, 0.6)
F, F0, d0 = C.d3c_point(D0, st0, np.random.default_rng(3), 200)
kr, k0, kk0 = C.k_point(D0, st0, np.random.default_rng(4), 200)
check('мир «смещения не зависят от задачи»: Δ3c и K около нуля', abs(d0) < 0.02 and abs(kk0) < 0.02, f'Δ3c {d0:.4f}, K {kk0:.4f}')

# мир «только трудность»: Т4(N0) заметно ≠ 0, а Δ3c около нуля — N3c сохраняет картину «кто где ошибся»
Dd, std = world(1500, 7, 6, 0.5, item_dep_p=True)
_, _, t4 = W.f_stats(Dd, np.random.default_rng(7), 200)
_, _, dd = C.d3c_point(Dd, std, np.random.default_rng(8), 200)
check('мир «только трудность»: |Т4(N0)| > 0,03, а |Δ3c| < 0,02', abs(t4) > 0.03 and abs(dd) < 0.02, f'Т4 {t4:.4f}, Δ3c {dd:.4f}')

# мир «заложенное совпадение»: K и Δ3c > 0
Ds, sts = world(1500, 7, 9, 0.6, shared=0.4)
_, _, ds = C.d3c_point(Ds, sts, np.random.default_rng(10), 200)
_, _, ks = C.k_point(Ds, sts, np.random.default_rng(11), 200)
check('мир «общее для задачи смещение у 40 % ошибок»: K > 0,1 и Δ3c > 0,03', ks > 0.1 and ds > 0.03, f'K {ks:.4f}, Δ3c {ds:.4f}')

# 4. Потоки и повторы
a1, b1 = C.d3c_stream(Ds[:300], sts[:300], 1, 2, 20, 30, 3)
a2, b2 = C.d3c_stream(Ds[:300], sts[:300], 1, 2, 20, 30, 3)
check('Δ3c: точка и повторы воспроизводимы по зёрнам; ст. откл. конечно', a1 == a2 and np.array_equal(b1, b2) and np.isfinite(a1['sd']))
k1, kb1 = C.k_stream(Ds[:300], sts[:300], 3, 4, 20, 30, 3)
check('K: точка и повторы воспроизводимы, ст. откл. конечно', np.isfinite(k1['sd']) and np.array_equal(kb1, C.k_stream(Ds[:300], sts[:300], 3, 4, 20, 30, 3)[1]))

# 5. t по средам
te = C.t_envs({'a': 1.0, 'b': 2.0, 'c': 3.0})
check('t по средам: среднее 2, ст. откл. 1, n = 3 → t = 2·√3; квантиль t(0,9975; 2) > 14',
      abs(te['t'] - 2 * np.sqrt(3)) < 1e-12 and te['df'] == 2 and 14 < te['crit'] < 14.2, str(te))

# 6. Сухой прогон пост-хока (шаг 3) на заглушках: 7 голов × 5 сред теста OCDIV-03; вне диапазона у части ошибок — общее для задачи
#    смещение «потеря переноса в сотни» (−100) при c1 = 1 и «в тысячи» (−1000) при c1 = 0; на ID смещения головы не зависят от задачи
import json  # noqa: E402
import tempfile  # noqa: E402
import posthoc_offsets3 as PH  # noqa: E402

D2 = W.D2


def fake_cols(e, k, rng):
    c = dict(answer=[], correct=[], logp=[], n_tok=[], text_none={})
    for j, q in enumerate(e['problems']):
        pc = 0.9 if q['range'] == 'ID' else 0.4
        if rng.random() < pc:
            ans = q['sum']
        elif q['range'] != 'ID' and rng.random() < 0.5:
            ans = q['sum'] + (-100 if C.c1_of(q['a'], q['b']) else -1000) * (1 if (q['a'] + q['b']) % 3 else 10)
        else:
            ans = q['sum'] + int(rng.choice([-10, 9 + k, 21 * (k + 1), -7]))
        c['answer'].append(ans)
        c['correct'].append(int(ans == q['sum']))
        c['logp'].append(float(-rng.random()))
        c['n_tok'].append(len(str(ans)) + 1)
    return c


tmp = tempfile.mkdtemp(prefix='ocdiv4_stub_')
te = D2.envs_ocdiv2('test2', ('thousands',))
rng = np.random.default_rng(31)
dirs = []
for k, nm in enumerate(C.V.CROWD):
    jd = os.path.join(tmp, f't_{k}')
    os.makedirs(jd)
    repo, commit = C.V.CROWD[nm].split('@')
    res = dict(experiment='OCDIV-02', phase='test2', model=repo, repo=repo, revision=commit, commit=commit,
               envs=[dict(name=e['name'], family=e['family'], X=e['X'], p=e['p'], max_new=e['max_new'], n=len(e['problems']), idx=e['idx'],
                          keys=[[q['a'], q['b']] for q in e['problems']], prompt_sha256=D2.DX.prompt_sha(e['prompt_head'])) for e in te],
               seconds_env={e['name']: 1.0 for e in te}, versions=dict(torch='2.11.0+cpu', transformers='5.20.2'), cpu_model='заглушка',
               cols={e['name']: fake_cols(e, k, rng) for e in te})
    json.dump(res, open(os.path.join(jd, f'answers_{nm}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    dirs.append(jd)
W.merge(os.path.join(tmp, 'm'), 'test2', 'thousands', dirs)
r = PH.run(os.path.join(tmp, 'm'), os.path.join(tmp, 'posthoc.json'), B=3, workers=1)
sm = r['summary']
check('сухой прогон пост-хока: пять сред годны, сводка по всем мерам посчитана',
      sum(e['valid'] for e in r['envs'].values()) == 5 and all(k in sm for k in ('d3c_ood', 'd3c_id', 'k_ood', 'k_id', 'd3u_ood', 't4_ood', 'k_ood_minus_id')))
check('сухой прогон: заложенное совпадение вне диапазона находится (K вне диапазона > 0,1), на ID K около нуля',
      sm['k_ood']['delta'] > 0.1 and abs(sm['k_id']['delta']) < 0.05, f"K ood {sm['k_ood']['delta']:.4f}, K id {sm['k_id']['delta']:.4f}")
kd = r['envs']['T_X19_p3']['same_pairs_ood']['kinds']
check('сухой прогон: совпавшие смещения вне диапазона — в основном вида −10^2 и −10^3', kd.get('−10^2', 0) + kd.get('−10^3', 0) > 0.5, str(kd))
saved = json.load(open(os.path.join(tmp, 'posthoc.json'), encoding='utf-8'))
check('пост-хок: повторы бутстрепа в json не пишутся (ключа _boot нет ни в одной среде)', all('_boot' not in e for e in saved['envs'].values()))

# 7. Сухой прогон всей цепочки OCDIV-04 на заглушках: задания pilot3 и test3 (7 голов × 11 сред), сборка merge4, разбор пилота,
#    константы PREREG, анализ теста. Вне диапазона у «тысяч» — общее для задачи смещение у доли ошибок (заложенное совпадение).
X4 = C.X4


def fake4(e, k, rng, shared):
    c = dict(answer=[], correct=[], logp=[], n_tok=[], text_none={})
    for j, q in enumerate(e['problems']):
        pc = 0.88 if q['range'] == 'ID' else 0.45
        if rng.random() < pc:
            ans = q['sum']
        elif q['range'] != 'ID' and rng.random() < shared:
            ans = q['sum'] - 10 ** (1 + (q['a'] * 7 + q['b']) % 3)
        else:
            ans = q['sum'] + int(rng.choice([-10, 9 + k, 21 * (k + 1), -7, 13]))
        c['answer'].append(ans)
        c['correct'].append(int(ans == q['sum']))
        c['logp'].append(float(-rng.random()))
        c['n_tok'].append(len(str(ans)) + 1)
    return c


def jobs4(phase, tag, shared, seed):
    rng_ = np.random.default_rng(seed)
    out = {}
    for fam in C.FAMS:
        envs_ = X4.envs_ocdiv4(phase, (fam,))
        ds = []
        for k, nm in enumerate(C.V.CROWD):
            jd = os.path.join(tmp, f'{tag}_{fam}_{k}')
            os.makedirs(jd)
            repo, commit = C.V.CROWD[nm].split('@')
            res = dict(experiment='OCDIV-04', phase=phase, model=repo, repo=repo, revision=commit, commit=commit,
                       envs=[dict(name=e['name'], family=e['family'], X=e['X'], p=e['p'], max_new=e['max_new'], n=len(e['problems']),
                                  idx=e['idx'], keys=[[q['a'], q['b']] for q in e['problems']], prompt_sha256=D2.DX.prompt_sha(e['prompt_head']))
                             for e in envs_],
                       seconds_env={e['name']: 1.0 for e in envs_}, versions=dict(torch='2.11.0+cpu', transformers='5.20.2'), cpu_model='заглушка',
                       cols={e['name']: fake4(e, k, rng_, shared[fam]) for e in envs_})
            json.dump(res, open(os.path.join(jd, f'answers_{nm}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
            ds.append(jd)
        C.merge4(os.path.join(tmp, f'm_{tag}_{fam}'), phase, fam, ds)
        out[fam] = os.path.join(tmp, f'm_{tag}_{fam}')
    return out


C.K_POINT, C.K_PAIRS = 40, 10                                    # только для скорости сухого прогона
mp4 = jobs4('pilot3', 'p', {'thousands': 0.35, 'length': 0.35}, 41)
mt4 = jobs4('test3', 't', {'thousands': 0.35, 'length': 0.35}, 42)
check('merge4: обе фазы, оба семейства собраны тем же кодом OCDIV-02 (7 голов)',
      all(len(json.load(open(os.path.join(d, 'answers.json')))['heads']) == 7 for d in list(mp4.values()) + list(mt4.values())))
pr4 = C.pilot4(os.path.join(tmp, 'pilot4.json'), mp4, B=4, workers=1)
check('разбор пилота: мощность трёх правил, кривая вброса растёт с δ, годность N3c и ожидания посчитаны',
      all(pr4['power'][r] is not None for r in C.RULES) and pr4['spike']['mean_curve'][-1] > pr4['spike']['mean_curve'][1] > 0
      and isinstance(pr4['n3c_fit'], bool) and set(pr4['expect']) == set(C.RULES), json.dumps(pr4['spike'], default=float)[:300])
check('вброс: δ для прироста +0,02 найден, приросты сред около +0,02, мощность при заложенном приросте посчитана',
      pr4['spike']['targets']['0.02']['delta'] is not None and abs(np.mean(list(pr4['spike']['targets']['0.02']['increments'].values())) - 0.02) < 0.005
      and pr4['spike']['targets']['0.02']['power_at_target'] is not None, json.dumps(pr4['spike']['targets'], default=float)[:400])
try:
    C.test4(os.path.join(tmp, 'test4_x.json'), mt4, os.path.join(tmp, 'pilot4.json'), B=3)
    no_const = False
except AssertionError:
    no_const = True
check('анализ теста без констант PREREG не идёт', no_const)
C.RULES_ACTIVE, C.NONDEG, C.N3C_FIT = pr4['rules_active'], pr4['nondeg'], pr4['n3c_fit']
tr4 = C.test4(os.path.join(tmp, 'test4.json'), mt4, os.path.join(tmp, 'pilot4.json'), B=4)
check('анализ теста: вердикты трёх правил, знак по средам, описательное и пары посчитаны',
      set(tr4['verdicts']) == set(C.RULES) and all('signs' in tr4['rules'][r] for r in C.RULES) and tr4['pairs'] is not None
      and 'thousands d3c_id' in tr4['descr'], json.dumps(tr4['verdicts'], ensure_ascii=False))
check('мир с заложенным совпадением: Р1-Т — среднее Δ3c вне диапазона > 0, все восемь сред > 0 по точке',
      tr4['rules']['Р1-Т']['delta'] > 0 and all(v > 0 for v in tr4['rules']['Р1-Т']['by_env'].values()), json.dumps(tr4['rules']['Р1-Т']['by_env']))
C.RULES_ACTIVE = C.NONDEG = C.N3C_FIT = None

# 10. Каркас отчёта собирается на выводе анализа заглушки (до данных теста)
import report_ocdiv4 as RP  # noqa: E402
xs = dict(expectations=[dict(id='E1', text='Р1-Т подтверждено', p=0.5, key='Р1-Т:подтверждено'), dict(id='E2', text='опыт определён', p=0.95, key='method')])
md = RP.render(json.load(open(os.path.join(tmp, 'test4.json'))), json.load(open(os.path.join(tmp, 'pilot4.json'))), xs)
check('каркас отчёта: собирается на заглушке, в нём три правила, обе таблицы сред, ожидания и вес опоры',
      all(x in md for x in ('Р1-Т —', 'Р1-Л —', 'Р2-Т —', 'По средам: «тысячи»', 'По средам: «длина»', '| E1 |', '## Вес опоры')), md[:300])

# 8. Извлечение на заглушке (без моделей в сессии): ocdiv4_extract.main с подменённым ocdiv2_extract.run; вывод собирается merge4
import subprocess  # noqa: E402
import make_jobs4 as MJ  # noqa: E402

orig_run = X4.X2.run


def fake_run(repo, rev, envs, bs, log):
    rr = np.random.default_rng(7)
    return dict(repo=repo, revision=rev, commit=rev, load_seconds=0.0, load_errors=[], seconds=0.0, seconds_env={e['name']: 0.0 for e in envs},
                cols={e['name']: fake4(e, 0, rr, 0.3) for e in envs}, versions=dict(torch='2.11.0+cpu', transformers='5.20.2'), cpu_model='заглушка')


X4.X2.run = fake_run
ex_dir = os.path.join(tmp, 'ex')
argv0 = sys.argv
try:
    nm0 = 'Qwen2.5-0.5B-Instruct'
    repo0, rev0 = C.V.CROWD[nm0].split('@')
    for e in X4.envs_ocdiv4('pilot3', ('length',)):
        sys.argv = ['ocdiv4_extract.py', '--phase', 'pilot3', '--model', repo0, '--revision', rev0, '--envs', e['name'], '--out',
                    os.path.join(ex_dir, e['name'])]
        X4.main()
finally:
    X4.X2.run, sys.argv = orig_run, argv0
outs = [json.load(open(os.path.join(ex_dir, e['name'], f'answers_{nm0}.json'))) for e in X4.envs_ocdiv4('pilot3', ('length',))]
check('извлечение на заглушке: фаза pilot3, по одной среде в файле, ключи и номера задач записаны',
      all(o['phase'] == 'pilot3' and o['experiment'] == 'OCDIV-04' and len(o['envs']) == 1 and len(o['envs'][0]['keys']) == 600 for o in outs))
mm = C.merge4(os.path.join(tmp, 'm_ex'), 'pilot3', 'length', [os.path.join(ex_dir, e['name']) for e in X4.envs_ocdiv4('pilot3', ('length',))])
check('сборка вывода извлечения: голова со всеми тремя средами «длины» собрана, без ошибок', len(mm['heads']) == 1 and not mm['head_errors'])

# 9. Файлы заданий: 77 заданий пилота с верной фазой; без --dir генератор останавливается; повторы детерминизма воспроизводимы
jd4 = os.path.join(tmp, 'jobs_pilot')
r_ = subprocess.run([sys.executable, os.path.join(X_DIR, 'make_jobs4.py'), 'pilot', '--dir', jd4], capture_output=True, text=True)
files = sorted(os.listdir(jd4))
check('make_jobs4 pilot: 77 файлов ocdiv4_pilot_*, у каждого --phase pilot3 и ревизия из ocdiv.CROWD',
      len(files) == 77 and all(f.startswith('ocdiv4_pilot_') for f in files)
      and all('--phase pilot3' in open(os.path.join(jd4, f)).read() for f in files)
      and all(any(C.V.CROWD[nm].split('@')[1] in open(os.path.join(jd4, f)).read() for nm in C.V.CROWD) for f in files), r_.stderr[-300:])
r2 = subprocess.run([sys.executable, os.path.join(X_DIR, 'make_jobs4.py'), 'pilot'], capture_output=True, text=True)
check('make_jobs4 без --dir останавливается (ERRORS № 198)', r2.returncode != 0)
check('ДЕТЕРМИНИЗМ-НА-3 (тест): три разных задания из 77, выбор воспроизводим', len(set(MJ.rep_jobs())) == 3 and MJ.rep_jobs() == MJ.rep_jobs())

print(f'провалов: {len(fails)}')
sys.exit(len(fails) > 0)
