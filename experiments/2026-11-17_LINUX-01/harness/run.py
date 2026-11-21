#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-01: сборка и прогон обвязки (PLAN.md).
  python3 harness/run.py check OUT.json [--n N]           — оригиналы: тесты KUnit в обвязке и оригинал против самого себя
  python3 harness/run.py eval OUT.json TRANS_DIR [--n N]  — переводы TRANS_DIR/<голова>/<модуль>.rs: rustc, KUnit, сравнение
Запускать из папки опыта. Rust собирается с проверками переполнения (как CONFIG_RUST_OVERFLOW_CHECKS) и panic=abort."""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(X)
WORK = os.path.join(X, 'work')
CF = ['-std=gnu11', '-O1', '-w', '-Iharness/include', '-include', 'harness/kernel_shim.h']
LIBS = ['-lpthread', '-ldl', '-lm', '-lrt']
MODULES = {
    'int_pow': ('lib/math/int_pow.c', 'lib/math/tests/int_pow_kunit.c', ['int_pow']),
    'int_sqrt': ('lib/math/int_sqrt.c', 'lib/math/tests/int_sqrt_kunit.c', ['int_sqrt']),
    'gcd': ('lib/math/gcd.c', 'lib/math/tests/gcd_kunit.c', ['gcd', 'efficient_ffs_key']),
    'rational': ('lib/math/rational.c', 'lib/math/tests/rational_kunit.c', ['rational_best_approximation']),
    'int_log': ('lib/math/int_log.c', 'lib/math/tests/int_log_kunit.c', ['intlog2', 'intlog10']),
    'cmdline': ('lib/cmdline.c', 'lib/tests/cmdline_kunit.c', ['get_option', 'get_options', 'memparse', 'parse_option_str', 'next_arg']),
}


def sh(cmd, timeout=900):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -999, '', 'TIMEOUT'


def lines(path):
    return sum(1 for l in open(path, encoding='utf-8', errors='ignore') if l.strip())


def orig_object(m):
    mod, _, syms = MODULES[m]
    out = os.path.join(WORK, f'orig_{m}.o')
    rc, _, err = sh(['gcc'] + CF + [f'-D{s}=orig_{s}' for s in syms] + ['-c', f'src/{mod}', '-o', out])
    if rc != 0:
        raise SystemExit(f'СТОП: оригинал {m} не собрался: {err[:500]}')
    return out


def run_json(cmd, timeout=900):
    rc, out, err = sh(cmd, timeout)
    try:
        return json.loads(out), rc, err[-2000:]
    except json.JSONDecodeError:
        return None, rc, (err or out)[-2000:]


def check(dst, n):
    res = dict(mode='check', n=n, modules={})
    for m, (mod, test, _) in MODULES.items():
        k_bin, d_bin = os.path.join(WORK, f'k_{m}'), os.path.join(WORK, f'd_{m}')
        rc1, _, e1 = sh(['gcc'] + CF + ['-o', k_bin, f'src/{mod}', f'src/{test}', 'harness/kunit_runner.c', 'harness/kernel_helpers.c'])
        kunit, _, ke = run_json([k_bin]) if rc1 == 0 else (None, rc1, e1)
        rc2, _, e2 = sh(['gcc'] + CF + ['-o', d_bin, 'harness/diff_main.c', orig_object(m), f'src/{mod}', 'harness/kernel_helpers.c'])
        diff, _, de = run_json([d_bin, m, str(n)]) if rc2 == 0 else (None, rc2, e2)
        res['modules'][m] = dict(c_lines=lines(f'src/{mod}'), kunit=kunit, kunit_err=None if kunit else ke, self_diff=diff, diff_err=None if diff else de)
        print(m, '| KUnit:', (kunit or {}).get('total'), 'случаев, провалено', (kunit or {}).get('failed'),
              '| самопроверка: расхождений', sum(v['mismatches'] for v in (diff or {}).values()) if diff else 'ошибка')
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ok = all(v['kunit'] and v['kunit']['failed'] == 0 and v['self_diff'] and all(x['mismatches'] == 0 for x in v['self_diff'].values())
             for v in res['modules'].values())
    print('обвязка:', 'верна' if ok else 'НЕВЕРНА')
    return 0 if ok else 1


def evaluate(dst, trans_dir, n):
    res = dict(mode='eval', n=n, trans_dir=trans_dir, rustc=sh(['rustc', '--version'])[1].strip(), modules={})
    for m, (mod, test, syms) in MODULES.items():
        orig = orig_object(m)
        res['modules'][m] = dict(c_lines=lines(f'src/{mod}'), heads={})
        for path in sorted(glob.glob(os.path.join(trans_dir, '*', f'{m}.rs'))):
            head = os.path.basename(os.path.dirname(path))
            lib = os.path.join(WORK, f'{head}_{m}.a')
            r = dict(rs_lines=lines(path), unsafe=len(re.findall(r'\bunsafe\b', open(path, encoding='utf-8').read())),
                     sha256=hashlib.sha256(open(path, 'rb').read()).hexdigest())
            rc, _, err = sh(['rustc', '--edition', '2021', '--crate-type', 'staticlib', '-C', 'opt-level=2', '-C', 'overflow-checks=on',
                             '-C', 'panic=abort', '-o', lib, path])
            r['compiled'] = rc == 0
            if rc != 0:
                r['compile_err'] = err[-1500:]
                r['correct'] = False
                res['modules'][m]['heads'][head] = r
                print(m, head, '| не собрался')
                continue
            k_bin, d_bin = os.path.join(WORK, f'k_{head}_{m}'), os.path.join(WORK, f'd_{head}_{m}')
            rc1, _, e1 = sh(['gcc'] + CF + ['-o', k_bin, f'src/{test}', 'harness/kunit_runner.c', 'harness/kernel_helpers.c', lib] + LIBS)
            r['linked'] = rc1 == 0
            if rc1 != 0:
                r['link_err'] = e1[-1500:]
            else:
                r['kunit'], _, ke = run_json([k_bin])
                if r['kunit'] is None:
                    r['kunit_err'] = ke
            force = [f'-Wl,-u,{s_}' for s_ in syms if s_ != 'efficient_ffs_key']   # слабые ссылки не вытягивают функции из .a
            rc2, _, e2 = sh(['gcc'] + CF + ['-o', d_bin, 'harness/diff_main.c', orig, 'harness/kernel_helpers.c'] + force + [lib] + LIBS)
            if rc2 == 0:
                r['diff'], _, de = run_json([d_bin, m, str(n)])
                if r['diff'] is None:
                    r['diff_err'] = de
            else:
                r['diff_link_err'] = e2[-1500:]
            kd = r.get('kunit') or {}
            df = r.get('diff') or {}
            r['correct'] = bool(r['compiled'] and r['linked'] and kd and kd.get('failed') == 0 and df
                                and all(v['mismatches'] == 0 for v in df.values()))
            res['modules'][m]['heads'][head] = r
            print(m, head, '| KUnit провалено', kd.get('failed'), 'из', kd.get('total'), '| расхождений',
                  sum(v['mismatches'] for v in df.values()) if df else 'нет', '| верен', r['correct'])
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


def main(a):
    os.makedirs(WORK, exist_ok=True)
    n = int(a[a.index('--n') + 1]) if '--n' in a else 100000
    if a[0] == 'check':
        return check(a[1], n)
    if a[0] == 'eval':
        return evaluate(a[1], a[2], n)
    raise SystemExit('режим: check | eval')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
