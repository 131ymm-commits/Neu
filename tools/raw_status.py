#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сводка сырого вывода заданий ДО анализа — только поля из белого списка (замок для ERRORS № 180, совет 67, 16.11.2026).
  python3 tools/raw_status.py DIR [DIR ...]     DIR — папка gha_out/<задание> (или файл answers_*.json)
По каждой папке печатается: есть ли файлы вывода, и по каждому файлу — модель, ревизия, поле error, сбои загрузки, версии, время.
Папка без answers_*.json (вывод другого вида): по каждому файлу — размер, читается ли json, его поля из того же белого списка,
метки сбоя задания в log.txt (ERRORS № 193: до этого такая папка давала «НЕТ файлов вывода», и я смотрел хвост log.txt).
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


MARKERS = {'marker_job_failed': 'завершилось с ошибкой', 'marker_partial': 'вывод частичный'}   # строки neu-par.yml


def generic_lines(p):
    """Папка без answers_*.json (вывод другого вида, например LINUX-01): только имя файла, размер, читается ли json, его поля из
    белого списка и метки сбоя задания в log.txt. Содержимое файлов не печатается (ERRORS № 193)."""
    fs = sorted(f for f in glob.glob(os.path.join(p, '**', '*'), recursive=True) if os.path.isfile(f))
    if not fs:
        return [f'{p}: НЕТ файлов вывода']
    out = []
    for f in fs:
        rec = dict(bytes=os.path.getsize(f))
        if f.endswith('.json'):
            try:
                d = json.load(open(f, encoding='utf-8'))
                rec['json'] = 'читается'
                if isinstance(d, dict):
                    rec['fields'] = filtered(d)
            except (OSError, ValueError) as e:
                rec['json'] = f'не читается ({type(e).__name__})'
        if os.path.basename(f) == 'log.txt':
            t = open(f, encoding='utf-8', errors='ignore').read()
            rec.update({k: s in t for k, s in MARKERS.items()})
        out.append(f'{os.path.relpath(f)} (другой вид вывода): ' + json.dumps(rec, ensure_ascii=False, sort_keys=True))
    return out


def status_lines(paths):
    lines = []
    for p in paths:
        fs = files_of(p)
        if not fs:
            lines.extend(generic_lines(p) if os.path.isdir(p) else [f'{p}: НЕТ файлов вывода'])
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
          f"без вывода: {sum(1 for x in lines if 'НЕТ файлов' in x)}; другого вида: {sum(1 for x in lines if '(другой вид вывода)' in x)}; "
          f"с меткой сбоя задания: {sum(1 for x in lines if '\"marker_job_failed\": true' in x or '\"marker_partial\": true' in x)}")


if __name__ == '__main__':
    main()
