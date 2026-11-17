#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-02: проверки кода на заглушках (без torch) и, с --real, сухой прогон извлечения на крошечной модели (GitHub Actions).
  python3 test_ocdiv2.py [--real]"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, X_DIR)
import ocdiv2 as W  # noqa: E402
import ocdiv2_extract as D2  # noqa: E402
V = W.V
FAIL = []


def check(name, ok, info=''):
    print(('✓ ' if ok else '✗ ') + name + (f' — {info}' if info and not ok else ''))
    if not ok:
        FAIL.append(name)


# 1. Среды: пилот и тест не пересекаются, примеры подсказок не в задачах, строение и детерминизм
pe, te = D2.envs_ocdiv2('pilot'), D2.envs_ocdiv2('test')
check('среды: по 10 у пилота и теста, по 400 и 2200 задач', len(pe) == len(te) == 10 and all(len(e['problems']) == 400 for e in pe)
      and all(len(e['problems']) == 2200 for e in te))
ok_dis, ok_ex = True, True
for a, b in zip(pe, te):
    ka, kb = {(q['a'], q['b']) for q in a['problems']}, {(q['a'], q['b']) for q in b['problems']}
    ar = (100 * a['X'], 100 * a['X'] + 99)
    ex = set(D2.OE.shots(ar, a['bound'], D2.OE.SHOTS_BASE + 1000 * a['X'])[1]) | set(D2.OE.shots(ar, a['bound'], D2.OE.SHOTS_BASE + 1000 * a['X'] + 2)[1])
    ok_dis &= not (ka & kb)
    ok_ex &= not ((ka | kb) & ex)
check('среды: задачи пилота и теста не пересекаются', ok_dis)
check('среды: примеры обеих подсказок не входят в задачи', ok_ex)
check('среды: построение детерминировано', [q['a'] for q in D2.envs_ocdiv2('test')[7]['problems']] == [q['a'] for q in te[7]['problems']])
check('среды: правда и диапазон — по коду', all(q['sum'] == q['a'] + q['b'] and (q['range'] == 'ID') == (q['sum'] < e['bound']) for e in pe + te for q in e['problems']))
check('среды: у «длины» 10 новых токенов, у «тысяч» 6', all(e['max_new'] == (10 if e['family'] == 'length' else 6) for e in pe + te))
check('среды: подсказка — два примера ID и два OOD', all(sorted(int(ln.split('=')[1]) >= e['bound'] for ln in e['prompt_head'].strip().split('\n')) == [False, False, True, True]
                                                          for e in pe + te))
check('среды: доля ID в тесте 0,44–0,47', all(0.44 < sum(q['range'] == 'ID' for q in e['problems']) / 2200 < 0.47 for e in te))

# 2. Вид ошибки, переносы, голоса и нуль
check('вид ошибки: −1000, 10, 1100, −110 — перенос; 7, 1001, 20 — прочее', [W.kind_of(d) for d in (-1000, 10, 1100, -110, 7, 1001, 20)]
      == ['перенос'] * 4 + ['прочее'] * 3)
check('переносы: 1987+45 → 3, 1950+50 → 2, 1901+95 → 0, 9999987+45 → 7', [W.carries(1987, 45), W.carries(1950, 50), W.carries(1901, 95), W.carries(9999987, 45)] == [3, 2, 0, 7])
NC = W.NONE_CODE
Dm = np.array([[0, 0, 5, 5, 5, NC + 5, 0], [5, 5, 0, 7, 9, NC + 5, NC + 6], [0, 0, 0, 0, 3, 3, 3], [NC, NC + 1, NC + 2, NC + 3, NC + 4, NC + 5, NC + 6],
               [4, 0, NC + 2, NC + 3, NC + 4, NC + 5, NC + 6]], np.int64)


def fm_slow(row):
    num = [x for x in row if x < NC]
    c = sum(x == 0 for x in num)
    w = max([num.count(x) for x in num if x != 0] or [0])
    return w >= 1 and w >= c


check('ложное большинство: векторный счёт равен прямому', list(W.false_major(Dm)) == [fm_slow(list(r)) for r in Dm], str(list(W.false_major(Dm))))
g = np.random.default_rng(1)
Dp = W.permute_cols(Dm, g)
check('нуль: перестановка сохраняет набор ответов каждой головы', all(sorted(Dp[:, k]) == sorted(Dm[:, k]) for k in range(7)))
strat = np.array([0, 0, 1, 1, 1])
Dq = W.permute_cols(Dm, g, strat)
check('нуль со стратами: перестановка не выходит из страты', all(sorted(Dq[strat == s, k]) == sorted(Dm[strat == s, k]) for s in (0, 1) for k in range(7)))
n, nh = 3000, 7
ind = np.where(g.random((n, nh)) < 0.6, 0, g.choice([-10, -100, 1000, 37], size=(n, nh)))
F, F0, dF = W.f_stats(ind, g, 50)
check('нуль: при независимых ошибках F − F₀ около нуля', abs(dF) < 0.01, f'{dF:.4f}')
hard = g.random(n) < 0.4
cor = np.where(hard[:, None], -1000, 0) * np.ones((1, nh), np.int64)
cor[g.random((n, nh)) < 0.1] = 0
_, _, dFc = W.f_stats(cor, g, 50)
from math import comb  # noqa: E402
q_ = 0.4 * 0.9                                                     # доля неверных в столбце; ложное большинство — не меньше 4 неверных из 7
exp_ = 0.4 * sum(comb(7, k) * 0.9 ** k * 0.1 ** (7 - k) for k in range(4, 8)) - sum(comb(7, k) * q_ ** k * (1 - q_) ** (7 - k) for k in range(4, 8))
check('нуль: при общих трудных задачах и одном неверном ответе F − F₀ — как по биномиальной формуле (около 0,18)', abs(dFc - exp_) < 0.02,
      f'{dFc:.4f} против {exp_:.4f}')
u = W.uncond(Dm, list('abcdefg'), [(0, 1), (2, 3)])
check('безусловное совпадение: доля задач, где обе ошиблись одним ответом', abs(u[0]['u'] - 1 / 5) < 1e-12 and abs(u[1]['u'] - 1 / 5) < 1e-12,
      str([r['u'] for r in u]))

# 3. Вердикты и мощность
check('вердикты: sign, pos, over, unit', [W.verdict2('sign', (-0.3, -0.1)), W.verdict2('pos', (0.01, 0.2)), W.verdict2('over', (0.03, 0.08)),
                                          W.verdict2('over', (-0.01, 0.015)), W.verdict2('unit', (0.2, 0.8)), W.verdict2('unit', (1.0, 1.4)),
                                          W.verdict2('unit', (-0.1, 0.5))]
      == ['подтверждено', 'подтверждено', 'подтверждено', 'опровергнуто', 'подтверждено', 'опровергнуто', 'не решено'])
check('мощность: явные эффекты дают почти 1', W.power_mc('sign', -0.05, 0.0, 0.005, n=20000)[0] > 0.99 and W.power_mc('over', 0.1, 0.01, 0.01, n=20000)[0] > 0.99
      and W.power_mc('unit', 0.5, 0.05, 0.05, n=20000)[0] > 0.99 and W.power_mc('pos', 0.1, 0.0, 0.01, n=20000)[0] > 0.99)
check('мощность: при нуле «подтверждено» не чаще уровня', W.power_mc('sign', 0.0, 0.0, 0.01, n=200000)[0] < 0.005)

# 4. Сборка и разбор пилота на заглушках: семь голов с заданной точностью; у «длины» разрыв больше
tmp = tempfile.mkdtemp(prefix='ocdiv2_stub_')
ACC = {'thousands': dict(id=0.9, ood=0.86), 'length': dict(id=0.9, ood=0.55)}


def fake_cols(e, head_k, acc, rng):
    c = dict(answer=[], correct=[], logp=[], n_tok=[], text_none={})
    for j, q in enumerate(e['problems']):
        a_ = acc['id'] if q['range'] == 'ID' else acc['ood']
        r = rng.random()
        if r > 0.995:
            ans = None
        elif r < a_:
            ans = q['sum']
        else:
            ans = q['sum'] + int(rng.choice([-1000, -10, 100, 7 + head_k]))
        c['answer'].append(ans)
        c['correct'].append(int(ans == q['sum']))
        c['logp'].append(None if ans is None else float(-rng.random() * (0.5 if ans == q['sum'] else 2.0)))
        c['n_tok'].append(0 if ans is None else 4)
        if ans is None:
            c['text_none'][str(j)] = 'x'
    return c


def write_job(jd, nm, fam, envs, rng, rev=None, k=0, mutate=None, phase='pilot'):
    os.makedirs(jd, exist_ok=True)
    repo, commit = V.CROWD[nm].split('@')
    res = dict(experiment='OCDIV-02', phase=phase, model=repo, repo=repo, revision=rev or commit, commit=rev or commit,
               envs=[dict(name=e['name'], family=e['family'], X=e['X'], p=e['p'], max_new=e['max_new'], n=len(e['problems']), idx=e['idx'],
                          keys=[[q['a'], q['b']] for q in e['problems']], prompt_sha256=D2.DX.prompt_sha(e['prompt_head'])) for e in envs],
               seconds_env={e['name']: 0.3 * len(e['problems']) for e in envs}, versions=dict(torch='2.11.0+cpu', transformers='5.20.2'),
               cpu_model='заглушка', cols={e['name']: fake_cols(e, k, ACC[fam], rng) for e in envs})
    if mutate:
        mutate(res)
    json.dump(res, open(os.path.join(jd, f"answers_{nm}.json"), 'w', encoding='utf-8'), ensure_ascii=False)


rng = np.random.default_rng(5)
dirs = {f: [] for f in D2.FAMILIES}
for f in D2.FAMILIES:
    envs = D2.envs_ocdiv2('pilot', (f,))
    for k, nm in enumerate(V.CROWD):
        jd = os.path.join(tmp, f'job_{f}_{k}')
        write_job(jd, nm, f, envs, rng, k=k)
        dirs[f].append(jd)
m = {f: W.merge(os.path.join(tmp, f'm_{f}'), 'pilot', f, dirs[f]) for f in D2.FAMILIES}
check('сборка: семь голов, пять сред, без ошибок', all(len(m[f]['heads']) == 7 and not m[f]['head_errors'] and len(m[f]['envs']) == 5 for f in m))


def stops(mut, fam='thousands'):
    envs = D2.envs_ocdiv2('pilot', (fam,))
    jd = tempfile.mkdtemp(prefix='ocdiv2_bad_')
    write_job(jd, 'Qwen2.5-0.5B-Instruct', fam, envs, rng, mutate=mut)
    try:
        W.merge(os.path.join(jd, 'm'), 'pilot', fam, [jd])
    except SystemExit as e:
        return str(e).startswith('СТОП')
    return False


def m_idx(r):
    r['envs'][0]['idx'] = r['envs'][0]['idx'][1:] + r['envs'][0]['idx'][:1]


def m_keys(r):
    r['envs'][1]['keys'][3] = [1, 2]


def m_sha(r):
    r['envs'][2]['prompt_sha256'] = '0' * 64


def m_len(r):
    r['cols'][r['envs'][0]['name']]['answer'].pop()


check('сборка: чужие номера задач → СТОП', stops(m_idx))
check('сборка: чужой ключ задачи → СТОП', stops(m_keys))
check('сборка: чужая подсказка → СТОП', stops(m_sha))
check('сборка: длина столбца не та → СТОП', stops(m_len))
jd = tempfile.mkdtemp(prefix='ocdiv2_rev_')
write_job(jd, 'Qwen2.5-0.5B-Instruct', 'thousands', D2.envs_ocdiv2('pilot', ('thousands',)), rng, rev='другая')
mr = W.merge(os.path.join(jd, 'm'), 'pilot', 'thousands', [jd])
check('сборка: чужая ревизия — голова в head_errors, не в толпе', not mr['heads'] and mr['head_errors'])
pres = W.pilot(os.path.join(tmp, 'pilot.json'), {f: os.path.join(tmp, f'm_{f}') for f in D2.FAMILIES}, B=20, workers=1)
fs = pres['families']
check('пилот: «длина» годна, «тысячи» — нет (разрыв 0,05 < 0,10); выбрана «длина»', fs['length']['qualifies'] and not fs['thousands']['qualifies']
      and pres['chosen'] == 'length', str({f: (round(fs[f]['drop_mean'], 3), fs[f]['qualifies']) for f in fs}))
el = pres['envs']['L_X99_p0']
check('пилот: все среды годны, Т1–Т4 и описательные числа посчитаны', all(pres['envs'][n]['valid'] for n in pres['envs'])
      and all(k in el['point'] for k in ('T1', 'T2', 'T3', 'D3', 'wc CONF')) and np.isfinite(el['T4']['point']) and np.isfinite(el['T4']['sd']))
check('пилот: Т3 — по головам с разрывом ≥ 0,10 (у заглушки «длины» — все семь)', len(el['t3_heads']) == 7, str(el['t3_heads']))
check('пилот: мощность посчитана для Т1–Т4', all(fs['length']['power'].get(k) for k in ('T1', 'T2', 'T3', 'T4')))
check('пилот: точность головы — по коротким именам, проверка метода — тоже', set(el['acc']) == set(V.CROWD) and set(el['method']) == set(V.CROWD))

# 4б. Анализ теста на заглушках: семейство «длина», 7 голов × 5 сред по 2200 задач, B = 30
tdirs = []
tenvs = D2.envs_ocdiv2('test', ('length',))
for k, nm in enumerate(V.CROWD):
    jd = os.path.join(tmp, f'tjob_{k}')
    write_job(jd, nm, 'length', tenvs, rng, k=k, phase='test')
    tdirs.append(jd)
mt = W.merge(os.path.join(tmp, 'mt'), 'test', 'length', tdirs)
check('сборка теста: семь голов, пять сред', len(mt['heads']) == 7 and not mt['head_errors'] and len(mt['envs']) == 5)
try:
    W.test(os.path.join(tmp, 'never.json'), os.path.join(tmp, 'mt'), B=5)
    check('тест: без констант PREREG анализ не идёт', False)
except AssertionError:
    check('тест: без констант PREREG анализ не идёт', True)
W.FAMILY_TEST, W.T3_HEADS, W.T2_DESCRIPTIVE, W.T4_STRATA = 'length', list(V.CROWD), False, False
tr = W.test(os.path.join(tmp, 'test.json'), os.path.join(tmp, 'mt'), B=30, workers=1)
check('тест: опыт определён, вердикты Т1–Т4 есть', tr['method']['ok'] and set(tr['verdicts']) == {'T1', 'T2', 'T3', 'T4'}, str(tr.get('verdicts')))
check('тест: у заглушки «длины» Т1 и Т4 > 0, Т3 внутри (0; 1) по точке', tr['T1']['delta'] > 0 and tr['T4']['delta'] > -0.05 and 0 < tr['T3']['delta'] < 1,
      str({k: round(tr[k]['delta'], 3) for k in ('T1', 'T3', 'T4')}))
check('тест: описательные числа и безусловное совпадение посчитаны', 'descr_D3' in tr and tr['uncond_cross']['u'] is not None and tr['parts_mean'])
check('тест: повторы бутстрепа не пишутся в json', not any(k in e for e in json.load(open(os.path.join(tmp, 'test.json')))['envs'].values()
                                                            for k in ('_boot', '_boot_T4')))       # ключи, а не подстрока (есть поле n_boot_finite)
W.FAMILY_TEST = W.T3_HEADS = W.T2_DESCRIPTIVE = W.T4_STRATA = None

# 5. С --real (GitHub Actions): сухой прогон извлечения на крошечной модели и равенство с ocdiv_extract.run при 6 новых токенах
if '--real' in sys.argv:
    out = tempfile.mkdtemp(prefix='ocdiv2_dry_')
    tiny = 'hf-internal-testing/tiny-random-LlamaForCausalLM'
    r = subprocess.run([sys.executable, os.path.join(X_DIR, 'ocdiv2_extract.py'), '--phase', 'pilot', '--model', tiny, '--envs', 'T_X19_p0,L_X99999_p0',
                        '--limit', '8', '--out', out, '--bs', '4'], capture_output=True, text=True)
    print(r.stdout[-1500:], r.stderr[-1500:])
    f = os.path.join(out, 'answers_tiny-random-LlamaForCausalLM.json')
    d = json.load(open(f)) if os.path.exists(f) else {}
    check('сухой прогон: вывод есть, ошибки нет', bool(d) and 'error' not in d, d.get('error', ''))
    if 'cols' in d:
        check('сухой прогон: две среды по 8 ответов, ключи и подсказка записаны', sorted(d['cols']) == ['L_X99999_p0', 'T_X19_p0']
              and all(len(c['answer']) == 8 for c in d['cols'].values()) and all('keys' in e and 'prompt_sha256' in e for e in d['envs']))
        check('сухой прогон: в лог не пишутся точность и счёт ответов', 'точность' not in r.stdout and 'без числа' not in r.stdout)
        import importlib
        import torch  # noqa: F401
        e6 = [dict(e, problems=e['problems'][:8]) for e in D2.env_by_name('pilot', ['T_X19_p0'])]
        a1 = D2.run(tiny, 'main', e6, 4, lambda *x: None)
        DXm = importlib.import_module('ocdiv_extract')
        a2 = DXm.run(tiny, 'main', e6, 4, lambda *x: None)
        c1, c2 = a1['cols']['T_X19_p0'], a2['cols']['T_X19_p0']
        check('равенство с ocdiv_extract.run при 6 новых токенах: ответы и logp', c1['answer'] == c2['answer'] and c1['logp'] == c2['logp'])

print(f'провалов: {len(FAIL)}')
sys.exit(1 if FAIL else 0)
