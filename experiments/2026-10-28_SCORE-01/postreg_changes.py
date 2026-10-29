#!/usr/bin/env python3
"""SCORE-01: что добавлено и изменено после регистрации (78626cd) — командой, по коммитам (ERRORS № 119, № 125: список по памяти
дважды выходил неполным). Журналы прогонов (run/<этап>/WH_*.jsonl) сводятся в одну строку на коммит. Записан после проверки отчёта.
  python3 postreg_changes.py   → печать (журнал — run/postreg_changes.log)"""
import collections
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
REG = '78626cd'
EXP = 'experiments/2026-10-28_SCORE-01/'


def main():
    out = subprocess.run(['git', 'log', '--reverse', '--format=@@%h %ad', '--date=format:%d.%m %H:%M', '--name-status', f'{REG}..HEAD'],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    commits, cur = [], None
    for line in out.splitlines():
        if line.startswith('@@'):
            cur = [line[2:], []]
            commits.append(cur)
        elif line.strip():
            st, *paths = line.split('\t')
            cur[1].append((st[0], paths[-1]))
    lines = [f'Изменения после регистрации {REG} (git log --name-status {REG}..HEAD), по коммитам; журналы прогонов свёрнуты:']
    for head, files in commits:
        mine = [(s, p) for s, p in files if p.startswith(EXP) or not p.startswith('experiments/')]
        if not mine:
            continue
        journ = collections.Counter()
        rest = []
        for s, p in mine:
            m = re.match(re.escape(EXP) + r'run/([a-z_]+)/(WH_\d+\.jsonl|run_log\.jsonl|init_\w+\.json|run_config\.json)$', p)
            if m:
                journ[m.group(1)] += 1
            else:
                rest.append(f'{s} {p[len(EXP):] if p.startswith(EXP) else p}')
        parts = rest + [f'журнал run/{k}/ — файлов {v}' for k, v in sorted(journ.items())]
        lines.append(f'- {head}: ' + '; '.join(parts))
    print('\n'.join(lines))
    open(os.path.join(HERE, 'run', 'postreg_changes.log'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
