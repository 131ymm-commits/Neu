#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: промпты и задания голов для tools/run_sealed2.py.

  python3 platon_jobs.py build --seeds SEEDS.json --heads 4 --out DIR [--cells TS,TN,ZS,ZN]
      SEEDS.json: [{"seed": 1001, "law": "fall"}, ...]. --variant b (по умолчанию): у каждой головы свои строки;
      a — одна таблица на все головы (пилот 90002–90011). Пишет DIR/jobs.jsonl (задача = экземпляр I<зерно>,
      id = I<зерно>|<ячейка>|h<k>, рука = ячейка), DIR/tables.json (метаданные таблиц: закон, ячейка, имена, sha256 промпта;
      правды в промптах нет) и DIR/prompts.sha256.
  python3 platon_jobs.py show --seed 1001 --law fall --cell ZS   — печатает промпт.
Ячейка = данные (T | Z) + имена (S | N). В варианте a четыре головы ячейки получают один промпт, в варианте b — свои
строки той же системы (тот же закон, те же постоянные, тот же порядок столбцов и те же имена).
"""
import argparse
import hashlib
import json
from pathlib import Path

import platon_world as W

SCHEMA = {
    'type': 'object',
    'properties': {
        'invariant': {'type': 'string'},
        'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
    },
    'required': ['invariant', 'confidence'],
    'additionalProperties': False,
}

INTRO = ('Ниже — таблица измерений одной системы. Каждая строка — отдельное измерение. '
         'Значения округлены до трёх значащих цифр.')

TASK = """Найди величину, которая сохраняется: выражение от столбцов, значение которого одинаково во всех строках с точностью до округления. Если в этих данных такой величины нет, ответь НЕТ.

Как записать выражение:
- синтаксис Python: + - * / ** и скобки, числа, имена столбцов, функции sqrt, log, exp;
- никаких других имён и постоянных: если нужна постоянная, впиши её числом;
- без знака «=»;
- выражение зависит хотя бы от двух столбцов.

Поля ответа:
- invariant — выражение или НЕТ;
- confidence — вероятность от 0 до 1, что выражение действительно сохраняется во всех строках таблицы."""

# Режим F («опубликуй»): без права ответить НЕТ — голова обязана назвать выражение, которое сохраняется лучше всего.
TASK_F = """Найди выражение от столбцов, которое сохраняется лучше всего: его значение должно быть как можно ближе к одинаковому во всех строках. Ответ НЕТ не принимается: назови лучшее выражение, которое сможешь найти.

Как записать выражение:
- синтаксис Python: + - * / ** и скобки, числа, имена столбцов, функции sqrt, log, exp;
- никаких других имён и постоянных: если нужна постоянная, впиши её числом;
- без знака «=»;
- выражение зависит хотя бы от двух столбцов.

Поля ответа:
- invariant — выражение;
- confidence — вероятность от 0 до 1, что выражение действительно сохраняется во всех строках таблицы."""

CELLS = ['TS', 'TN', 'ZS', 'ZN']
REGIMES = {'free': TASK, 'forced': TASK_F}


def prompt_for(inst, cell, head=0, regime='free'):
    data, names = cell[0], cell[1]
    idents, desc, rows, _ = W.table_view(inst, data, names, head)
    if names == 'S':
        cols = '\n'.join(f'- {c} — {d}' for c, d in zip(idents, desc))
    else:
        cols = '\n'.join(f'- {c}' for c in idents)
    head = '| ' + ' | '.join(idents) + ' |'
    sep = '|' + '|'.join('---' for _ in idents) + '|'
    body = '\n'.join('| ' + ' | '.join(W.fmt3(r[c]) for c in idents) + ' |' for r in rows)
    return f'{INTRO}\n\nСтолбцы:\n{cols}\n\n{head}\n{sep}\n{body}\n\n{REGIMES[regime]}'


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def build(seeds, heads, out, cells=CELLS, variant='b', regimes=('free',)):
    """variant 'a' — одна таблица на все головы (пилот 90002–90011); 'b' — у каждой головы свои строки.
    regimes: 'free' — с правом ответить НЕТ (id таблицы I<зерно>|<ячейка>); 'forced' — режим F (id I<зерно>F|<ячейка>).
    Таблицы режимов на одном экземпляре одни и те же: меняется только текст задачи."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    jobs, tables, shas = [], [], []
    for ent in seeds:
        inst = W.make_instance(ent['seed'], ent['law'], heads=None if variant == 'a' else heads)
        for regime in regimes:
          for cell in cells:
            tid = f"I{ent['seed']}{'F' if regime == 'forced' else ''}|{cell}"
            idents, _, _, _ = W.table_view(inst, cell[0], cell[1])
            prs = [prompt_for(inst, cell, k, regime) for k in range(heads)]
            tables.append({'table': tid, 'task': f"I{ent['seed']}", 'seed': ent['seed'], 'law': ent['law'],
                           'cell': cell, 'data': cell[0], 'names': cell[1], 'idents': idents, 'variant': variant,
                           'regime': regime, 'heads': heads, 'prompt_sha256': [sha(pr) for pr in prs],
                           'z_tries': inst['z_tries']})
            for k, pr in enumerate(prs, 1):
                shas.append(f'{sha(pr)}  {tid}|h{k}')
                arm = cell + ('F' if regime == 'forced' else '')
                jobs.append({'task': f"I{ent['seed']}", 'id': f'{tid}|h{k}', 'arm': arm, 'prompt': pr, 'schema': SCHEMA})
    (out / 'jobs.jsonl').write_text(''.join(json.dumps(j, ensure_ascii=False) + '\n' for j in jobs), encoding='utf-8')
    (out / 'tables.json').write_text(json.dumps(tables, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'prompts.sha256').write_text('\n'.join(shas) + '\n', encoding='utf-8')
    return jobs, tables


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--seeds', required=True)
    b.add_argument('--heads', type=int, default=4)
    b.add_argument('--out', required=True)
    b.add_argument('--cells', default=','.join(CELLS))
    b.add_argument('--variant', choices=['a', 'b'], default='b')
    b.add_argument('--regimes', default='free', help='free,forced')
    s = sub.add_parser('show')
    s.add_argument('--seed', type=int, required=True)
    s.add_argument('--law', required=True)
    s.add_argument('--cell', required=True)
    s.add_argument('--head', type=int, default=0)
    s.add_argument('--variant', choices=['a', 'b'], default='b')
    s.add_argument('--regime', choices=['free', 'forced'], default='free')
    a = ap.parse_args()
    if a.cmd == 'build':
        seeds = json.loads(Path(a.seeds).read_text(encoding='utf-8'))
        jobs, tables = build(seeds, a.heads, a.out, a.cells.split(','), a.variant, tuple(a.regimes.split(',')))
        print(f'заданий {len(jobs)}, таблиц {len(tables)} → {a.out}')
    else:
        print(prompt_for(W.make_instance(a.seed, a.law, heads=None if a.variant == 'a' else 4), a.cell, a.head, a.regime))


if __name__ == '__main__':
    main()
