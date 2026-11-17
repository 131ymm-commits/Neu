#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-01, пост-хок: чувствительность оценщика (тесты KUnit модуля и сравнение с оригиналом) к мутантам переводов.
Мутантов делает этот скрипт механически, не головы: одна правка на мутанта — сравнение (< ↔ <=, > ↔ >=, == ↔ !=), сложение
и вычитание (+ ↔ -, += ↔ -=, wrapping_add ↔ wrapping_sub), логика (&& ↔ ||), сдвиг (<< ↔ >>), целая константа (N → N+1).
Комментарии, строки и символьные литералы не трогаются; унарный минус не трогается. Места правки — случайная выборка
(зерно фиксировано) до --per-file на файл. Не собравшийся мутант («мертворождённый») в доли не входит.
Убит KUnit — провален хоть один случай, упал или завис исполнитель (дольше 20 с; оригинал — меньше секунды). Убит сравнением — хоть одно расхождение, падение или
зависание (дольше 60 с). Зависания считаются отдельно (kunit_timeouts, diff_timeouts). Сравнение — с тем же числом входов, что основная оценка (100 000 на функцию).
  python3 harness/mutants.py OUT.json TRANS_DIR [--per-file 25] [--n 100000] [--workers N] [--seed 17]"""
import concurrent.futures as cf
import glob
import hashlib
import json
import os
import random
import re
import signal
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run as R  # noqa: E402   (переходит в папку опыта; MODULES, CF, LIBS, orig_object)

TOK = re.compile(r'<<=|>>=|<<|>>|<=|>=|==|!=|&&|\|\||->|=>|\+=|-=|[<>+\-]|\bwrapping_(?:add|sub)\b|'
                 r'\b(?:0x[0-9a-fA-F_]+|\d[\d_]*)(?:[ui](?:8|16|32|64|128|size))?\b')
SWAP = {'<': '<=', '<=': '<', '>': '>=', '>=': '>', '==': '!=', '!=': '==', '&&': '||', '||': '&&', '<<': '>>', '>>': '<<',
        '+=': '-=', '-=': '+=', '+': '-', '-': '+', 'wrapping_add': 'wrapping_sub', 'wrapping_sub': 'wrapping_add'}
KIND = {'<': 'сравнение', '<=': 'сравнение', '>': 'сравнение', '>=': 'сравнение', '==': 'сравнение', '!=': 'сравнение',
        '&&': 'логика', '||': 'логика', '<<': 'сдвиг', '>>': 'сдвиг', '+=': 'плюс-минус', '-=': 'плюс-минус', '+': 'плюс-минус',
        '-': 'плюс-минус', 'wrapping_add': 'плюс-минус', 'wrapping_sub': 'плюс-минус'}


def mask(src):
    """Комментарии, строки и символьные литералы → пробелы; позиции сохраняются."""
    out = list(src)
    for m in re.finditer(r'//[^\n]*|/\*.*?\*/|b?"(?:\\.|[^"\\])*"|b?\'(?:\\.|[^\\\'])\'', src, flags=re.S):
        for k in range(m.start(), m.end()):
            if out[k] != '\n':
                out[k] = ' '
    return ''.join(out)


def sites(src):
    ms = mask(src)
    res = []
    for m in TOK.finditer(ms):
        t = m.group(0)
        if t in ('->', '=>', '<<=', '>>='):
            continue
        if t in ('+', '-'):
            prev = ms[:m.start()].rstrip()[-1:]
            if not prev or prev in '([{,;=:!<>&|+-*/%^':
                continue
        if t in SWAP:
            res.append((m.start(), m.end(), t, SWAP[t], KIND[t]))
            continue
        num = re.match(r'(0x[0-9a-fA-F_]+|\d[\d_]*)(.*)', t)
        hexa = num.group(1).startswith('0x')
        v = int(num.group(1).replace('_', ''), 16 if hexa else 10)
        res.append((m.start(), m.end(), t, (hex(v + 1) if hexa else str(v + 1)) + num.group(2), 'константа'))
    return res


def run_group(cmd, timeout):
    """Запуск в своей группе процессов: при зависании убивается вся группа (исполнители делают fork)."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err, False
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return -9, '', 'TIMEOUT', True


def jload(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def eval_mut(job):
    head, m, idx, s, e, frm, to, kind, src, n = job
    mod, test, syms = R.MODULES[m]
    d = os.path.join(R.WORK, 'mut')
    tag = f'{head}_{m}_{idx}'
    rs, lib = os.path.join(d, tag + '.rs'), os.path.join(d, tag + '.a')
    k_bin, d_bin = os.path.join(d, 'k_' + tag), os.path.join(d, 'd_' + tag)
    open(rs, 'w', encoding='utf-8').write(src[:s] + to + src[e:])
    rec = dict(head=head, module=m, site=idx, line=src.count('\n', 0, s) + 1, frm=frm, to=to, kind=kind)
    rc, _, _, _ = run_group(['rustc', '--edition', '2021', '--crate-type', 'staticlib', '-C', 'opt-level=2', '-C', 'overflow-checks=on',
                             '-C', 'panic=abort', '-o', lib, rs], 300)
    rec['compiled'] = rc == 0
    if rc == 0:
        rc1, _, _, _ = run_group(['gcc'] + R.CF + ['-o', k_bin, f'src/{test}', 'harness/kunit_runner.c', 'harness/kernel_helpers.c', lib]
                                 + R.LIBS, 300)
        force = [f'-Wl,-u,{x}' for x in syms if x != 'efficient_ffs_key']
        rc2, _, _, _ = run_group(['gcc'] + R.CF + ['-o', d_bin, 'harness/diff_main.c', os.path.join(R.WORK, f'orig_{m}.o'),
                                                    'harness/kernel_helpers.c'] + force + [lib] + R.LIBS, 300)
        rec['linked'] = rc1 == 0 and rc2 == 0
        if rec['linked']:
            _, out, _, to1 = run_group([k_bin], 20)
            kd = jload(out)
            rec.update(kunit_timeout=to1, kunit_total=(kd or {}).get('total'), kunit_failed=(kd or {}).get('failed'))
            rec['killed_kunit'] = kd is None or kd.get('failed', 0) > 0
            _, out, _, to2 = run_group([d_bin, m, str(n)], 60)
            df = jload(out)
            rec.update(diff_timeout=to2, diff_mismatches=sum(v['mismatches'] for v in df.values()) if df else None,
                       diff_crashed_chunks=sum(v['crashed_chunks'] for v in df.values()) if df else None)
            rec['killed_diff'] = df is None or any(v['mismatches'] > 0 for v in df.values())
    for f in (rs, lib, k_bin, d_bin):
        if os.path.exists(f):
            os.remove(f)
    return rec


def summary(rows):
    alive = [r for r in rows if r['compiled'] and r.get('linked')]
    kk = sum(r['killed_kunit'] for r in alive)
    kd = sum(r['killed_diff'] for r in alive)
    return dict(generated=len(rows), stillborn=sum(not r['compiled'] for r in rows), not_linked=sum(r['compiled'] and not r.get('linked') for r in rows),
                alive=len(alive), killed_kunit=kk, killed_diff=kd, killed_either=sum(r['killed_kunit'] or r['killed_diff'] for r in alive),
                kunit_missed_diff_caught=sum((not r['killed_kunit']) and r['killed_diff'] for r in alive),
                diff_missed_kunit_caught=sum(r['killed_kunit'] and not r['killed_diff'] for r in alive),
                survived_both=sum(not r['killed_kunit'] and not r['killed_diff'] for r in alive),
                kunit_timeouts=sum(bool(r.get('kunit_timeout')) for r in alive), diff_timeouts=sum(bool(r.get('diff_timeout')) for r in alive),
                share_killed_kunit=kk / len(alive) if alive else None, share_killed_diff=kd / len(alive) if alive else None)


def main(a):
    dst, trans = a[0], a[1]
    per = int(a[a.index('--per-file') + 1]) if '--per-file' in a else 25
    n = int(a[a.index('--n') + 1]) if '--n' in a else 100000
    workers = int(a[a.index('--workers') + 1]) if '--workers' in a else (os.cpu_count() or 2)
    seed = int(a[a.index('--seed') + 1]) if '--seed' in a else 17
    os.makedirs(os.path.join(R.WORK, 'mut'), exist_ok=True)
    jobs = []
    for path in sorted(glob.glob(os.path.join(trans, '*', '*.rs'))):
        head, m = os.path.basename(os.path.dirname(path)), os.path.basename(path)[:-3]
        if m not in R.MODULES:
            continue
        R.orig_object(m)
        src = open(path, encoding='utf-8').read()
        st = sites(src)
        rng = random.Random(int(hashlib.sha256(f'{seed}/{head}/{m}'.encode()).hexdigest()[:12], 16))
        pick = sorted(rng.sample(range(len(st)), min(per, len(st))))
        jobs += [(head, m, k, *st[k], src, n) for k in pick]
    rows = []
    with cf.ProcessPoolExecutor(workers) as ex:
        for r in ex.map(eval_mut, jobs):
            rows.append(r)
    mods = sorted({r['module'] for r in rows}, key=list(R.MODULES).index)
    res = dict(n=n, per_file=per, seed=seed, workers=workers, rustc=R.sh(['rustc', '--version'])[1].strip(),
               total=summary(rows), by_module={m: summary([r for r in rows if r['module'] == m]) for m in mods},
               by_head={h: summary([r for r in rows if r['head'] == h]) for h in sorted({r['head'] for r in rows})},
               by_kind={k: summary([r for r in rows if r['kind'] == k]) for k in sorted({r['kind'] for r in rows})}, rows=rows)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    t = res['total']
    print('мутантов', t['generated'], '| мертворождённых', t['stillborn'], '| живых', t['alive'], '| убито KUnit', t['killed_kunit'],
          '| убито сравнением', t['killed_diff'], '| KUnit пропустил, сравнение поймало', t['kunit_missed_diff_caught'],
          '| выжили оба', t['survived_both'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
