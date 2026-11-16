#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сводка сырого вывода заданий ДО анализа — только поля из белого списка (замок для ERRORS № 180, совет 67, 16.11.2026).
  python3 tools/raw_status.py DIR [DIR ...]     DIR — папка gha_out/<задание> (или файл answers_*.json)
По каждой папке печатается: есть ли файлы вывода, и по каждому файлу — модель, ревизия, поле error, сбои загрузки, версии, время.
Точность, ответы, logp, число задач и ответов, ответы без числа и всё остальное из вывода не читается в сводку и не печатается:
функция filtered() отдаёт только ключи из ALLOWED. Тест — tools/test_raw_status.py (он падает, если в сводку попало что-то сверх
белого списка). Свою сводку сырого вывода до анализа не писать: PREREG разрешает смотреть наличие файлов, error, ревизию, версии и время."""
import glob
import json
import os
import sys

ALLOWED = ('model', 'revision', 'commit', 'error', 'load_errors', 'versions', 'seconds', 'load_seconds', 'seconds_env')
VERSION_KEYS = ('python', 'torch', 'transformers', 'numpy')


def filtered(d):
    """Только белый список; у versions — только номера версий пакетов; у seconds_env — только время по средам."""
    out = {}
    for k in ALLOWED:
        if k not in d:
            continue
        v = d[k]
        if k == 'versions' and isinstance(v, dict):
            v = {kk: str(v[kk]) for kk in VERSION_KEYS if kk in v}
        elif k == 'seconds_env' and isinstance(v, dict):
            v = {str(kk): float(vv) for kk, vv in v.items() if isinstance(vv, (int, float))}
        elif k in ('seconds', 'load_seconds'):
            v = float(v) if isinstance(v, (int, float)) else None
        elif k == 'load_errors':
            v = [str(x)[:200] for x in v] if isinstance(v, list) else []
        else:
            v = None if v is None else str(v)[:300]
        out[k] = v
    return out


def files_of(p):
    if os.path.isfile(p):
        return [p]
    return sorted(glob.glob(os.path.join(p, 'answers_*.json')))


def status_lines(paths):
    lines = []
    for p in paths:
        fs = files_of(p)
        if not fs:
            lines.append(f'{p}: НЕТ файлов вывода')
            continue
        for f in fs:
            try:
                d = json.load(open(f, encoding='utf-8'))
            except (OSError, ValueError) as e:
                lines.append(f'{f}: не читается ({type(e).__name__})')
                continue
            s = filtered(d)
            lines.append(f"{os.path.relpath(f)}: " + json.dumps(s, ensure_ascii=False, sort_keys=True))
    return lines


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    lines = status_lines(sys.argv[1:])
    print('\n'.join(lines))
    print(f"файлов: {sum(1 for x in lines if ': {' in x)}; с полем error: {sum(1 for x in lines if '\"error\": \"' in x)}; "
          f"без вывода: {sum(1 for x in lines if 'НЕТ файлов' in x)}")


if __name__ == '__main__':
    main()
