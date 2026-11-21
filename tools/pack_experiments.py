#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Архив документов опытов Neu за период — для автора (слово автора 18.11.2026: «дай мне файлы по всем эксперементам за последние 4 дня»).
  python3 tools/pack_experiments.py С ПО АРХИВ.zip      С, ПО — даты ГГГГ-ММ-ДД (по имени папки опыта experiments/<дата>_<ID>)
В архиве:
- README.md — оглавление: по каждому опыту заголовок и первый раздел отчёта или записки (выдержка из файла, числа не переписываются);
- папки опытов целиком, без __pycache__;
- results/<папка> — выводы анализа на GitHub Actions (папки gha_out без сырых ответов голов answers_*.json; задания извлечения не берутся);
- councils/ — стенограммы советов за эти даты; literature/ — записки литературы за эти даты.
Секретов в этих файлах нет (репозиторий открытый); архив кладётся туда, куда указано, и в репозиторий не коммитится."""
import glob
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = {'OCSHIFT-01': 'ocshift', 'OCINT-01': 'ocint', 'OCREP-01': 'ocrep', 'OCPOST-01': 'ocpost', 'OCDIV-01': 'ocdiv_', 'OCDIV-02': 'ocdiv2_',
          'OCDIV-03': 'ocdiv3_', 'OCDIV-04': 'ocdiv4_', 'DISTILL-01': 'distill', 'LINUX-01': 'linux'}


def first_section(path, max_lines=30):
    lines = open(path, encoding='utf-8').read().splitlines()
    title = next((x for x in lines if x.startswith('# ')), os.path.basename(path))
    out, started = [], False
    for x in lines[1:]:
        if x.startswith('## '):
            if started:
                break
            started = True
        if started:
            out.append(x)
        if len(out) >= max_lines:
            out.append('…')
            break
    return title, out


def main(a):
    d0, d1, dst = a[0], a[1], a[2]
    exps = sorted(p for p in glob.glob(os.path.join(ROOT, 'experiments', '20*_*'))
                  if d0 <= os.path.basename(p)[:10] <= d1 and os.path.isdir(p))
    readme = [f'# Опыты Neu с {d0} по {d1} — архив документов', '',
              'Для каждого опыта — заголовок и первый раздел отчёта (или записки) дословно; полные тексты — в папках опытов. '
              'Выводы анализа — в results/, стенограммы советов — в councils/, литература — в literature/.', '']
    zf = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
    n = 0
    for p in exps:
        name = os.path.basename(p)
        eid = name[11:]
        rep = sorted(glob.glob(os.path.join(p, 'REPORT-*.md'))) or sorted(glob.glob(os.path.join(p, 'NOTE-*.md')))
        readme += [f'## {name}', '']
        if rep:
            title, sec = first_section(rep[0])
            readme += [f'Документ: `{name}/{os.path.basename(rep[0])}` — {title.lstrip("# ")}', ''] + sec + ['']
        else:
            hyp = sorted(glob.glob(os.path.join(p, 'HYPOTHESIS*.md'))) + sorted(glob.glob(os.path.join(p, 'PREREG-*.md')))
            readme += ['Отчёта ещё нет — опыт идёт. Документы: ' + ', '.join(f'`{name}/{os.path.basename(h)}`' for h in hyp), '']
        for f in sorted(glob.glob(os.path.join(p, '**', '*'), recursive=True)):
            if os.path.isfile(f) and '__pycache__' not in f:
                zf.write(f, os.path.join(name, os.path.relpath(f, p))); n += 1
        pre = PREFIX.get(eid)
        if pre:
            for g in sorted(glob.glob(os.path.join(ROOT, 'gha_out', pre + '*'))):
                files = [f for f in glob.glob(os.path.join(g, '**', '*'), recursive=True) if os.path.isfile(f)]
                if any(os.path.basename(f).startswith('answers_') for f in files):
                    continue                                   # задание извлечения: сырые ответы голов не берутся
                for f in files:
                    zf.write(f, os.path.join('results', os.path.basename(g), os.path.relpath(f, g))); n += 1
    for sub, pat in (('councils', 'docs/council/{d}*'), ('literature', 'docs/prior_art/{d}*')):
        for f in sorted(glob.glob(os.path.join(ROOT, pat.format(d='20*')))):
            if d0 <= os.path.basename(f)[:10] <= d1 and os.path.isfile(f):
                zf.write(f, os.path.join(sub, os.path.basename(f))); n += 1
    zf.writestr('README.md', '\n'.join(readme) + '\n')
    zf.close()
    print(f'записано {dst}: файлов {n + 1}, опытов {len(exps)}, {os.path.getsize(dst) / 1e6:.1f} МБ')


if __name__ == '__main__':
    main(sys.argv[1:])
