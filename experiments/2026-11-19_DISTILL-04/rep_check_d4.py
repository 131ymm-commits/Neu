#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: повтор извлечения на другом раннере — детерминизм (описательно, PREREG §2, §12). Для каждого задания
distill04_rep_<голова>_<среда> — доля совпавших значений в каждом столбце cols[среда] против distill04_test_<голова>_<среда>.
Сырые ответы читает только задание анализа после регистрации (замок № 180: до анализа — tools/raw_status.py).
  python3 rep_check_d4.py ВЫХОД.json [КОРЕНЬ gha_out]"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def cols_of(job_dir):
    """{среда: {столбец: список}} из answers_*.json папки; файлы с error или без cols пропускаются (их видно в raw_status)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(job_dir, 'answers_*.json'))):
        h = json.load(open(f, encoding='utf-8'))
        if 'error' in h or 'cols' not in h:
            continue
        for env, c in h['cols'].items():
            out[env] = c
    return out


def compare(rep, test):
    """По каждому столбцу, который есть в обоих: число позиций и доля совпавших значений; длины разные — доля None."""
    res = {}
    for k in sorted(set(rep) & set(test)):
        a, b = rep[k], test[k]
        if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b):
            res[k] = dict(n=None, equal_share=None)
            continue
        res[k] = dict(n=len(a), equal_share=(sum(x == y for x, y in zip(a, b)) / len(a)) if a else None)
    return res


def main(a):
    dst = a[0]
    root = a[1] if len(a) > 1 else os.path.join(ROOT, 'gha_out')
    out = {}
    for rd in sorted(glob.glob(os.path.join(root, 'distill04_rep_*'))):
        name = os.path.basename(rd)
        td = os.path.join(root, name.replace('distill04_rep_', 'distill04_test_', 1))
        rc, tc = cols_of(rd), cols_of(td)
        envs = sorted(set(rc) & set(tc))
        out[name] = dict(test_job=os.path.basename(td), envs=envs, columns={e: compare(rc[e], tc[e]) for e in envs},
                         missing=sorted(set(rc) ^ set(tc)))
        print(name, '|', {e: {k: v['equal_share'] for k, v in out[name]['columns'][e].items()} for e in envs}, flush=True)
    json.dump(dict(jobs=out, n_jobs=len(out)), open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
