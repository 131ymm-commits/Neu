#!/usr/bin/env python3
"""SCORE-01: что голова получила на входе первого запроса — сумма input + cache_creation + cache_read из первого message_start
потока (LENSES-1, L1-1: при рабочей папке внутри репозитория CLI добавлял снимок git, и вход одного промпта рос по ходу прогона).
Одинаковые промпты в чистом контексте дают одинаковый вход (с точностью до нескольких токенов).
  python3 ctx_check.py <папка потоков> [<папка потоков> …]   → по вызову: id, время, вход первого запроса"""
import glob
import gzip
import json
import os
import sys


def first_input(path):
    with gzip.open(path, 'rt', encoding='utf-8') as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            e = o.get('event') or {}
            if o.get('type') == 'stream_event' and e.get('type') == 'message_start':
                u = e['message'].get('usage') or {}
                return u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
    return None


rows = []
for d in sys.argv[1:]:
    for p in sorted(glob.glob(os.path.join(d, '*', '*.jsonl.gz'))):
        name = os.path.basename(p).split('-')[0]
        rows.append((os.path.getmtime(p), d, name, first_input(p)))
rows.sort()
by = {}
for t, d, name, inp in rows:
    key = name.rsplit('_', 1)[0]                     # задача_рука без номера повтора — один промпт
    by.setdefault((d, key), []).append(inp)
    print(f'{os.path.basename(d.rstrip("/"))}\t{name}\t{inp}')
print('одинаковые промпты (задача и рука): разброс входа')
for (d, key), v in sorted(by.items()):
    if len(v) > 1:
        print(f'  {os.path.basename(d.rstrip("/"))} {key}: {v} → размах {max(v) - min(v)}')
