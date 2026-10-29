#!/usr/bin/env python3
"""Хеши регистрации SCORE-01: файлы из prereg_hashes.json — по содержимому в коммите 78626cd (git show) и в рабочей копии.
Сводные хеши задач и пулов — свой расчёт (имя файла + sha256 содержимого, по сортировке имён)."""
import hashlib, json, os, subprocess, glob

ROOT = '/home/claude/neu'
EXP_REL = 'experiments/2026-10-28_SCORE-01'
EXP = f'{ROOT}/{EXP_REL}'
REG = '78626cd'


def git_blob(path_rel_root, rev=REG):
    return subprocess.run(['git', '-C', ROOT, 'show', f'{rev}:{path_rel_root}'], capture_output=True, check=True).stdout


def norm(p):
    return os.path.normpath(os.path.join(EXP_REL, p))


reg_now = json.load(open(f'{EXP}/prereg_hashes.json'))
reg_then = json.loads(git_blob(f'{EXP_REL}/prereg_hashes.json'))
print('prereg_hashes.json в 78626cd = рабочей копии:', reg_now == reg_then, len(reg_then))
bad_then, bad_now = [], []
for k, v in reg_then.items():
    if k.startswith('SELECT-01/'):
        continue
    h_then = hashlib.sha256(git_blob(norm(k))).hexdigest()
    h_now = hashlib.sha256(open(os.path.join(EXP, k), 'rb').read()).hexdigest()
    if h_then != v:
        bad_then.append(k)
    if h_now != v:
        bad_now.append(k)
for kind in ('tasks', 'pools'):
    key = [k for k in reg_then if k.startswith(f'SELECT-01/{kind}/')][0]
    for label, getter in (('78626cd', lambda rel: git_blob(rel)), ('рабочая', lambda rel: open(f'{ROOT}/{rel}', 'rb').read())):
        if label == '78626cd':
            ls = subprocess.run(['git', '-C', ROOT, 'ls-tree', '--name-only', REG, f'experiments/2026-10-07_SELECT-01/{kind}/'],
                                capture_output=True, text=True, check=True).stdout.split()
            fs = sorted(f for f in ls if os.path.basename(f).startswith('WH_8') and os.path.basename(f)[4] in '012')
        else:
            fs = sorted(os.path.relpath(p, ROOT) for p in glob.glob(f'{ROOT}/experiments/2026-10-07_SELECT-01/{kind}/WH_8[0-2]*.json'))
        h = hashlib.sha256()
        for rel in fs:
            h.update(os.path.basename(rel).encode()); h.update(hashlib.sha256(getter(rel)).hexdigest().encode())
        ok = h.hexdigest() == reg_then[key]
        print(f'{kind} ({label}): файлов {len(fs)}, сводный хеш совпал: {ok}')
print('не совпали с регистрацией в 78626cd:', bad_then)
print('не совпали в рабочей копии:', bad_now)
# изменился ли PREREG после регистрации
d = subprocess.run(['git', '-C', ROOT, 'diff', '--stat', REG, 'HEAD', '--', f'{EXP_REL}/PREREG-SCORE-01.md'], capture_output=True, text=True).stdout
print('PREREG-SCORE-01.md после регистрации:', d.strip() or 'не менялся')
