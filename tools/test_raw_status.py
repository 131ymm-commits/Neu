#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест замка ERRORS № 180 (совет 67): сводка сырого вывода (tools/raw_status.py) печатает только белый список полей.
Падает (код 1), если в сводку попала точность, ответы, logp, число задач или ответов, ответы без числа или любое поле сверх списка.
Запуск — в задании анализа каждого следующего опыта с выводом answers_*.json:  python3 tools/test_raw_status.py"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import raw_status as R  # noqa: E402

FAIL = []


def check(name, ok, info=''):
    print(('✓ ' if ok else '✗ ') + name + (f' — {info}' if info and not ok else ''))
    if not ok:
        FAIL.append(name)


# вывод задания с «метками»: числа, которых в сводке быть не должно
SENT = dict(acc=0.987654321, n=24681357, none=13579, logp=-7.123456789, ans=97531)
d = dict(source='test', model='org/fake-model', revision='abc123', commit='abc123def', n=SENT['n'], pick='first',
         envs=[dict(name='X4_p2', X=4, p=2, n=SENT['n'], idx=[0, 1], keys=[[400, 10], [401, 11]], prompt_sha256='f' * 64)],
         cols={'X4_p2': dict(answer=[SENT['ans'], 412], correct=[1, 0], logp=[SENT['logp'], -0.5], n_tok=[3, 3],
                             text_none={str(k): 'нет числа' for k in range(3)})},
         accuracy=SENT['acc'], acc_id=SENT['acc'], n_none=SENT['none'], n_correct=SENT['none'],
         versions=dict(python='3.13.18', torch='2.11.0+cpu', transformers='5.20.2', numpy='2.5.3', extra_acc=SENT['acc']),
         seconds=123.4, load_seconds=5.6, seconds_env={'X4_p2': 118.0}, load_errors=[], cpu_model='x', pip_freeze=['a==1'])
tmp = tempfile.mkdtemp(prefix='raw_status_')
os.makedirs(os.path.join(tmp, 'job_ok'))
json.dump(d, open(os.path.join(tmp, 'job_ok', 'answers_fake-model.json'), 'w', encoding='utf-8'), ensure_ascii=False)
e = dict(d, error='OSError: не загрузилась')
os.makedirs(os.path.join(tmp, 'job_err'))
json.dump(e, open(os.path.join(tmp, 'job_err', 'answers_fake-model.json'), 'w', encoding='utf-8'), ensure_ascii=False)
os.makedirs(os.path.join(tmp, 'job_empty'))

f = R.filtered(d)
check('filtered: только ключи белого списка', set(f) <= set(R.ALLOWED), str(sorted(set(f) - set(R.ALLOWED))))
check('filtered: в versions только номера версий пакетов', set(f['versions']) <= set(R.VERSION_KEYS), str(f['versions']))
out = subprocess.run([sys.executable, os.path.join(HERE, 'raw_status.py'), os.path.join(tmp, 'job_ok'), os.path.join(tmp, 'job_err'),
                      os.path.join(tmp, 'job_empty')], capture_output=True, text=True).stdout
for k, v in SENT.items():
    for s in {repr(v), str(v), f'{v:.4f}' if isinstance(v, float) else str(v), str(v).replace('.', ',')}:
        check(f'сводка не содержит метку {k} ({s})', s not in out, out[:300])
for word in ('correct', 'answer', 'logp', 'text_none', 'accuracy', 'acc_id', 'n_none', 'n_correct', 'n', 'idx', 'keys', 'extra_acc',
             'pip_freeze', 'cpu_model', 'cols', 'envs'):
    check(f'сводка не содержит поле {word}', f'"{word}"' not in out)      # ключ json в кавычках: имя файла answers_*.json — не поле
check('сводка показывает модель, ревизию, версии и время', 'org/fake-model' in out and 'abc123def' in out and '2.11.0+cpu' in out and '123.4' in out)
check('сводка показывает поле error', 'OSError: не загрузилась' in out)
check('сводка показывает папку без вывода', 'НЕТ файлов вывода' in out)
print(f'провалов: {len(FAIL)}')
sys.exit(1 if FAIL else 0)
