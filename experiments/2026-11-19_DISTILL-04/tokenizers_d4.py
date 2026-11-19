#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: как токенизатор каждой из семи голов (ocdiv.CROWD, те же ревизии) режет числа — описательно, до любой ковариаты
«токенизатор» (совет 77: вводить только после этого задания; ТОКЕНИЗАТОР-ПРОЧИХ в описи). Только токенизаторы, без весов моделей.
Ответы моделей и их выводы ничем не исполняются; печатаются куски токенов.
  python3 tokenizers_d4.py ВЫХОД.json"""
import json
import os
import sys

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, os.path.join(ROOT, 'experiments', '2026-11-16_OCDIV-01'))
import ocdiv  # noqa: E402

SAMPLES = ['7', '86', '957', '2043', '1957', '12043', '20043', '195786', ' 2043', '=2043', '1957 + 86 = 2043', '1957+86=2043']


def main(a):
    from transformers import AutoTokenizer
    import transformers
    out = dict(transformers=transformers.__version__, samples=SAMPLES, heads={})
    for name, spec in ocdiv.CROWD.items():
        repo, rev = spec.split('@')
        tok = AutoTokenizer.from_pretrained(repo, revision=rev)
        rows = {}
        for s in SAMPLES:
            ids = tok.encode(s, add_special_tokens=False)
            rows[s] = [tok.decode([i]) for i in ids]
        digits = rows['2043']
        out['heads'][name] = dict(repo=repo, revision=rev, pieces=rows,
                                  digits_per_token_2043=[len(p.strip()) for p in digits], one_digit_tokens=all(len(p.strip()) == 1 for p in digits))
        print(name, '| 2043 →', digits, '| 1957 + 86 = 2043 →', rows['1957 + 86 = 2043'], flush=True)
    json.dump(out, open(a[0], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
