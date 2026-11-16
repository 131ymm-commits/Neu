#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01: тесты извлечения. Без torch — сверка сред и функции разбора; с --real — ещё сухой прогон на крошечной модели
(GitHub Actions: прогоны только на сторонних площадках).
  python3 test_ocdiv.py [--real]"""
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import tempfile

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
