#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01: тесты извлечения. Без torch — сверка сред и функции разбора; с --real — ещё сухой прогон на крошечной модели
(GitHub Actions: прогоны только на сторонних площадках).
  python3 test_ocdiv.py [--real]"""
import importlib.util
import inspect
import itertools
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
sys.path.insert(0, X)
import ocdiv_extract as D  # noqa: E402

FAIL = []


def check(name, ok, info=''):
    print(('✓ ' if ok else '✗ ') + name + (f' — {info}' if info else ''), flush=True)
    if not ok:
        FAIL.append(name)


def load_ocshift_extract():
    os.environ['OCSHIFT_IMPORT_ONLY'] = '1'
    here = os.getcwd()
    os.chdir(tempfile.mkdtemp(prefix='ocshift_import_'))
    try:
        spec = importlib.util.spec_from_file_location('ocshift_extract', os.path.join(ROOT, 'experiments/2026-11-15_OCSHIFT-01/ocshift_extract.py'))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    finally:
        os.chdir(here)
    return m


# 1. Тест: пять сред OCPOST-01 из сырого вывода совпадают со средами, пересчитанными кодом ocpost_extract.environments
te = D.envs_of('test', 'all', 0)
code = {e['name']: e for e in D.OE.environments('test') if e.get('kind') != 'check'}
check('тест: пять сред X4_p2 … X8_p2', [e['name'] for e in te] == [f'X{x}_p2' for x in range(4, 9)], str([e['name'] for e in te]))
check('тест: по 2200 задач', all(len(e['problems']) == 2200 for e in te))
check('тест: подсказки совпадают с кодом OCPOST-01', all(e['prompt_head'] == code[e['name']]['prompt_head'] for e in te))
check('тест: задачи совпадают с кодом OCPOST-01', all([(p['a'], p['b']) for p in e['problems']] == [(p['a'], p['b']) for p in code[e['name']]['problems']] for e in te))

# 2. Пилот: десять сред OCSHIFT-01 (первые 300 задач) совпадают с кодом ocshift_extract.environments
SE = load_ocshift_extract()
pi = D.envs_of('pilot', 'all', 300)
scode = {e['name']: e for e in SE.environments('test') if e.get('kind') != 'check'}
check('пилот: десять сред OCSHIFT-01', len(pi) == 10 and all(e['p'] in (0, 1) for e in pi), str([e['name'] for e in pi]))
check('пилот: по 300 задач', all(len(e['problems']) == 300 for e in pi))
check('пилот: подсказки и задачи совпадают с кодом OCSHIFT-01',
      all(e['prompt_head'] == scode[e['name']]['prompt_head'] and [(p['a'], p['b']) for p in e['problems']] == [(p['a'], p['b']) for p in scode[e['name']]['problems'][:300]] for e in pi))
check('пилот и тест не пересекаются по задачам',
      not ({(p['a'], p['b']) for e in te for p in e['problems']} & {(p['a'], p['b']) for e in pi for p in e['problems']}))

# 3. Разбор ответа — одна и та же функция у Pythia (OCSHIFT-01, OCPOST-01) и у новых голов
check('answer_logp — тот же текст в ocshift_extract и ocpost_extract', inspect.getsource(SE.answer_logp) == inspect.getsource(D.OE.answer_logp))
check('answer_logp в OCDIV-01 — функция ocpost_extract', D.answer_logp is D.OE.answer_logp)


class FakeTok:
    def __init__(self, pieces):
        self.p = pieces

    def decode(self, ids, skip_special_tokens=True):
        return ''.join(self.p[i] for i in ids)


tok = FakeTok({0: '4', 1: '3', 2: '0', 3: '\n', 4: '1', 5: ' ', 6: 'x'})
lp = [[-0.1 * (k + 1)] * 7 for k in range(6)]
ans, text, lsum, n = D.answer_logp(tok, [0, 1, 2, 3, 4, 4], lp)
check('разбор: «430\\n11» → 430, logp по трём цифрам', ans == 430 and n == 3 and abs(lsum - (-0.1 - 0.2 - 0.3)) < 1e-12, f'{ans}, {n}, {lsum}')
ans, text, lsum, n = D.answer_logp(tok, [6, 0, 1], lp)
check('разбор: ответ без числа → None', ans is None and lsum is None and n == 0)
ans, text, lsum, n = D.answer_logp(tok, [5, 0, 2], lp)
check('разбор: ведущий пробел допускается', ans == 40 and n == 3, f'{ans}, {n}')

# 3а. Выборка задач пилота 2 (ERRORS № 175): случайная, с зерном среды, повторяемая, с естественной долей ID и OOD
src_p = json.load(open(D.SRC['pilot'], encoding='utf-8'))
penvs = [e for e in src_p['envs'] if e.get('kind') != 'check']
ix = {e['name']: D.pick_idx(e, 600, 'random') for e in penvs}
check('пилот 2: по 600 разных номеров, по возрастанию, в пределах среды',
      all(len(v) == 600 and v == sorted(set(v)) and 0 <= v[0] and v[-1] < 2200 for v in ix.values()))
check('пилот 2: выборка повторяется при втором вызове', all(D.pick_idx(e, 600, 'random') == ix[e['name']] for e in penvs))
check('пилот 2: у сред разные выборки', len({tuple(v) for v in ix.values()}) == len(ix))
fr = {e['name']: np.mean([e['problems'][i]['range'] == 'ID' for i in ix[e['name']]]) for e in penvs}
full = {e['name']: np.mean([p['range'] == 'ID' for p in e['problems']]) for e in penvs}
check('пилот 2: доля ID в выборке близка к доле во всей среде (±0,06)', all(abs(fr[k] - full[k]) <= 0.06 for k in fr),
      ', '.join(f'{k} {fr[k]:.2f}/{full[k]:.2f}' for k in fr))
check('пилот 1: first — первые N', D.pick_idx(penvs[0], 300, 'first') == list(range(300)) and D.pick_idx(penvs[0], 0, 'random') == list(range(2200)))
pe = D.envs_of('pilot', ['X4_p0'], 600, 'random')[0]
check('envs_of: задачи — по номерам выборки', [p['id'] for p in pe['problems']] == [penvs[0]['problems'][i]['id'] for i in ix['X4_p0']])

# 3б. Сборка, совпадение ошибок и поправка на точность (ocdiv.py) — на синтетике, без torch
import ocdiv as V  # noqa: E402

rng = np.random.default_rng(1)
s_ = [int(x) for x in rng.integers(400, 600, 500)]
heads_ = {f'h{k}': [None if rng.random() < 0.03 else (t if rng.random() < 0.6 else t + int(rng.choice([-10, 10, -100, 1, 2**70]))) for t in s_]
          for k in range(4)}


def q_ref(a, b, s):
    both = [(x is not None) and (y is not None) and x != t and y != t for x, y, t in zip(a, b, s)]
    m = sum(both)
    return (sum(x == y for x, y, bb in zip(a, b, both) if bb) / m if m else float('nan')), m


enc, sc = V.encode(heads_, s_)
lab = list(heads_)
prs = list(itertools.combinations(range(4), 2))
ps = V.pair_stats(enc, sc, lab, prs)
check('q: векторный счёт равен прямому (и с числами больше int64)',
      all(abs(r['q'] - q_ref(heads_[r['i']], heads_[r['j']], s_)[0]) < 1e-12 and r['m'] == q_ref(heads_[r['i']], heads_[r['j']], s_)[1] for r in ps))
idx_b = rng.choice(len(s_), len(s_))
psb = V.pair_stats(enc, sc, lab, prs, idx_b)
check('q на повторе бутстрепа равен прямому счёту на тех же задачах',
      all(abs(r['q'] - q_ref([heads_[r['i']][i] for i in idx_b], [heads_[r['j']][i] for i in idx_b], [s_[i] for i in idx_b])[0]) < 1e-12 for r in psb))
check('acc: нет числа — неверно', all(abs(r['acc_i'] - np.mean([x == t for x, t in zip(heads_[r['i']], s_)])) < 1e-12 for r in ps))
fake_new = [dict(q=0.1 + 0.5 * a + 0.07, m=5, acc_pair=a) for a in (0.3, 0.5, 0.7)]
fake_py = [dict(q=0.1 + 0.5 * a, m=5, acc_pair=a) for a in (0.2, 0.4, 0.6, 0.8)]
dlt, bet, alp = V.adj_of(fake_new, fake_py)
check('поправка на точность: МНК находит δ, β, α', abs(dlt - 0.07) < 1e-9 and abs(bet - 0.5) < 1e-9 and abs(alp - 0.1) < 1e-9, f'{dlt}, {bet}, {alp}')
n_id_s = sum(p['range'] == 'ID' for p in pe['problems'])
thr_s = int(np.ceil(20 * n_id_s / 1004.6))
id_pos = [k for k, p in enumerate(pe['problems']) if p['range'] == 'ID']


def fake_head(name, n_wrong_id):
    wrong = set(id_pos[:n_wrong_id])
    rows = [dict(answer=p['sum'] + (1 if k in wrong else 0), correct=k not in wrong, logp=-0.5 if k in wrong else -0.1, n_tok=3)
            for k, p in enumerate(pe['problems'])]
    return dict(model=name, revision='main', rows=rows)


fenv = dict(meta=dict(X=4, p=0), problems=pe['problems'],
            heads=[fake_head('на пороге', thr_s), fake_head('ниже порога', thr_s - 1)] + [fake_head(f'г{k}', 50 + k) for k in range(5)])
_, inf_ = V.prepare_scaled(fenv, 7, 1004.6)
check('проверка метода в масштабе теста: порог 20·n_ID/n_ID_теста вверх; на пороге годна, ниже — нет; общий порог восстановлен',
      inf_['min_each'] == thr_s and inf_['method']['на пороге']['ok'] and not inf_['method']['ниже порога']['ok'] and V.S.MIN_EACH == 20
      and inf_['valid'], f'n_ID {n_id_s}, порог {thr_s}')

# сборка: голова двумя файлами (p = 0 и p = 1), номера задач сверяются; подмена номеров — ошибка, а не тихое смещение
tmp = tempfile.mkdtemp(prefix='ocdiv_merge_')
for half in (0, 1):
    es = D.envs_of('pilot', [f'X{x}_p{half}' for x in range(4, 9)], 600, 'random')
    jd = os.path.join(tmp, f'job{half}')
    os.makedirs(jd)
    json.dump(dict(source='pilot', model='org/fake', repo='org/fake', commit='c0ffee', revision='main', n=600, pick='random',
                   envs=[dict(name=e['name'], n=600, idx=e['idx']) for e in es], seconds_env={e['name']: 60.0 for e in es},
                   cols={e['name']: dict(answer=[p['sum'] for p in e['problems']], correct=[1] * 600, logp=[-0.1] * 600, n_tok=[3] * 600, text_none={})
                         for e in es}), open(os.path.join(jd, 'answers_fake.json'), 'w'))
mg = V.merge(os.path.join(tmp, 'm'), 'pilot', 600, [os.path.join(tmp, 'job0'), os.path.join(tmp, 'job1')], pick='random')
check('сборка: два файла одной головы → одна голова на десяти средах, без ошибок',
      len(mg['heads']) == 1 and not mg['head_errors'] and len(mg['heads'][0]['cols']) == 10 and mg['heads'][0]['vendor'] == 'org')
bad = json.load(open(os.path.join(tmp, 'job1', 'answers_fake.json')))
bad['envs'][0]['idx'] = bad['envs'][0]['idx'][1:] + [bad['envs'][0]['idx'][0]]
json.dump(bad, open(os.path.join(tmp, 'job1', 'answers_fake.json'), 'w'))
mg2 = V.merge(os.path.join(tmp, 'm2'), 'pilot', 600, [os.path.join(tmp, 'job0'), os.path.join(tmp, 'job1')], pick='random')
check('сборка: чужие номера задач → ошибка, голова не входит', len(mg2['heads']) == 0 and any('номера задач' in x['error'] for x in mg2['head_errors']))
py5 = V.pythia_envs('pilot', 600, 'random')
check('Pythia: те же задачи выборки', [(p['a'], p['b']) for p in py5['X4_p0']['problems']] == [(p['a'], p['b']) for p in pe['problems']]
      and all(len(h['answer']) == 600 for h in py5['X4_p0']['heads']))
rc = V.range_counts('test')
check('строение теста: ~1000 задач ID и ~1200 OOD на среду', 950 < rc['ID'] < 1050 and abs(rc['all'] - 2200) < 1e-9, str(rc))

# 4. Сухой прогон на крошечной модели (только с --real; на GitHub Actions)
if '--real' in sys.argv:
    out = tempfile.mkdtemp(prefix='ocdiv_dry_')
    r = subprocess.run([sys.executable, os.path.join(X, 'ocdiv_extract.py'), '--source', 'pilot', '--model', 'hf-internal-testing/tiny-random-LlamaForCausalLM',
                        '--envs', 'X4_p0,X8_p1', '--n', '8', '--out', out, '--bs', '4'], capture_output=True, text=True)
    print(r.stdout[-1500:], r.stderr[-1500:])
    f = os.path.join(out, 'answers_tiny-random-LlamaForCausalLM.json')
    ok = os.path.exists(f)
    d = json.load(open(f)) if ok else {}
    check('сухой прогон: файл вывода есть, ошибки нет', ok and 'error' not in d, d.get('error', ''))
    if ok and 'cols' in d:
        check('сухой прогон: две среды по 8 ответов', sorted(d['cols']) == ['X4_p0', 'X8_p1'] and all(len(c['answer']) == 8 for c in d['cols'].values()))
        check('сухой прогон: ревизия и версии записаны', bool(d.get('commit')) and 'torch' in d.get('versions', {}), str(d.get('commit')))
    bad = subprocess.run([sys.executable, os.path.join(X, 'ocdiv_extract.py'), '--source', 'pilot', '--model', 'no-such-org/no-such-model-ocdiv',
                          '--envs', 'X4_p0', '--n', '4', '--out', out], capture_output=True, text=True)
    fb = os.path.join(out, 'answers_no-such-model-ocdiv.json')
    check('сухой прогон: несуществующая модель — ошибка записана, задание не падает', bad.returncode == 0 and os.path.exists(fb) and 'error' in json.load(open(fb)))

print(f'провалов: {len(FAIL)}')
sys.exit(1 if FAIL else 0)
