#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-02: сборка и прогон обвязки (PLAN-PILOT.md; устройство — harness/README.md).
  python3 harness/run.py check OUT.json [--n N]                 — оригиналы: KUnit; оригинал против себя (обычные входы и крайние);
                                                                  то же со сборкой под UBSan (неопределённое поведение оригинала)
  python3 harness/run.py eval OUT.json PHASE [--n N] [--modules ...] [--heads ...]
                                                                — переводы translations/PHASE/<голова>/<модуль>_r<k>.rs:
                                                                  rustc, KUnit, сравнение с оригиналом
  python3 harness/run.py one OUT.json MODULE FILE.rs [--n N] [--seed S] [--boundary] [--no-kunit]
                                                                — один файл Rust (для мутантов и независимого поиска)
Семантика C — как у ядра (флаги Makefile v7.4-rc3). Rust — с проверками переполнения (CONFIG_RUST_OVERFLOW_CHECKS), panic=abort.
Символы оригинала для сравнения переименовываются objcopy: каждый определённый глобальный символ s → orig_s."""
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
KFLAGS = ['-std=gnu11', '-O2', '-funsigned-char', '-fno-common', '-fno-strict-aliasing', '-fno-delete-null-pointer-checks',
          '-fno-strict-overflow']
CF = KFLAGS + ['-Werror=implicit-function-declaration', '-Werror=int-conversion', '-Iharness/include', '-Iharness', '-Isrc/include',
               '-Isrc/lib/842', '-Isrc/lib/crypto/tests', '-include', 'harness/kernel_shim.h']
UBSAN = ['-fsanitize=undefined', '-fno-sanitize=alignment', '-fno-sanitize-recover=all']   # без alignment: README, «UBSan»
LIBS = ['-lpthread', '-ldl', '-lm', '-lrt']
RUSTC = ['rustc', '--edition', '2021', '--crate-type', 'staticlib', '-C', 'opt-level=2', '-C', 'overflow-checks=on', '-C', 'panic=abort']
MODULES = {
    'errseq': dict(src='lib/errseq.c', test='lib/tests/errseq_kunit.c', diff='harness/diff_errseq.c', extra=[]),
    '842_decompress': dict(src='lib/842/842_decompress.c', test='lib/tests/842_decompress_kunit.c', diff='harness/diff_842.c',
                           extra=['src/lib/842/842_compress.c']),
    'md5': dict(src='lib/crypto/md5.c', test='lib/crypto/tests/md5_kunit.c', diff='harness/diff_md5.c', extra=[]),
    'random32': dict(src='lib/random32.c', test='lib/tests/random32_kunit.c', diff='harness/diff_random32.c', extra=[]),
    'min_heap': dict(src='lib/min_heap.c', test='lib/tests/min_heap_kunit.c', diff='harness/diff_min_heap.c', extra=[]),
    'string_helpers': dict(src='lib/string_helpers.c', test='lib/tests/string_helpers_kunit.c', diff='harness/diff_string_helpers.c',
                           extra=[]),
}


def sh(cmd, timeout=1800):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -999, '', 'TIMEOUT'


def must(cmd, what):
    rc, out, err = sh(cmd)
    if rc != 0:
        raise SystemExit(f'СТОП: {what}: {err[-1500:]}')
    return out


def lines(path):
    return sum(1 for l in open(path, encoding='utf-8', errors='ignore') if l.strip())


def obj(src, out, extra=()):
    must(['gcc'] + CF + list(extra) + ['-c', src, '-o', out], f'сборка {src}')
    return out


def helpers(tag, extra=()):
    """Общие объекты: функции ядра, lib/cmdline.c (с собственным skip_spaces), исполнитель KUnit."""
    d = os.path.join(WORK, f'common_{tag}')
    os.makedirs(d, exist_ok=True)
    return dict(kh=obj('harness/kernel_helpers.c', os.path.join(d, 'kh.o'), extra),
                cmdline=obj('src/lib/cmdline.c', os.path.join(d, 'cmdline.o'), list(extra) + ['-Dskip_spaces=harness_skip_spaces']),
                runner=obj('harness/kunit_runner.c', os.path.join(d, 'runner.o'), extra))


def orig_objects(m, tag, extra=()):
    """Оригинал: как есть (для KUnit и самопроверки) и с переименованными глобальными символами (для сравнения)."""
    d = os.path.join(WORK, f'{m}_{tag}')
    os.makedirs(d, exist_ok=True)
    plain = obj(f"src/{MODULES[m]['src']}", os.path.join(d, 'orig_plain.o'), extra)
    out = must(['nm', '-g', '--defined-only', plain], 'nm')
    syms = [l.split()[-1] for l in out.splitlines() if l.split() and l.split()[-2] in ('T', 'D', 'B', 'R', 'W', 'V')]
    renamed = os.path.join(d, 'orig_renamed.o')
    must(['objcopy'] + [a for s in syms for a in ('--redefine-sym', f'{s}=orig_{s}')] + [plain, renamed], 'objcopy')
    extras = [obj(e, os.path.join(d, os.path.basename(e) + '.o'), extra) for e in MODULES[m]['extra']]
    test = obj(f"src/{MODULES[m]['test']}", os.path.join(d, 'test.o'), extra)
    drv = obj(MODULES[m]['diff'], os.path.join(d, 'diff.o'), extra)
    return dict(plain=plain, renamed=renamed, syms=syms, extras=extras, test=test, drv=drv, dir=d)


def run_json(cmd, timeout=3600):
    rc, out, err = sh(cmd, timeout)
    try:
        return json.loads(out), rc, err[-2000:]
    except json.JSONDecodeError:
        return None, rc, (err or out)[-2000:]


def kunit_bin(o, impl, h, out, extra=()):
    rc, _, err = sh(['gcc'] + list(extra) + ['-o', out, o['test'], impl, h['runner'], h['kh'], h['cmdline']] + LIBS)
    return rc == 0, err[-1500:]


def diff_bin(o, impl, h, out, extra=()):
    rc, _, err = sh(['gcc'] + list(extra) + ['-o', out, o['drv'], o['renamed'], impl] + o['extras'] + [h['kh'], h['cmdline']] + LIBS)
    return rc == 0, err[-1500:]


def mism(diff):
    return sum(v['mismatches'] for v in diff['fns'].values()) if diff else None


def check(dst, n, mods):
    res = dict(mode='check', n=n, kflags=KFLAGS, ubsan=UBSAN, gcc=sh(['gcc', '--version'])[1].splitlines()[0], modules={})
    ok_all = True
    for tag, extra in (('plain', ()), ('ubsan', UBSAN)):
        h = helpers(tag, extra)
        for m in mods:
            o = orig_objects(m, tag, extra)
            r = res['modules'].setdefault(m, dict(c_lines=lines(f"src/{MODULES[m]['src']}"), exported=o['syms']))
            kb, db = os.path.join(o['dir'], 'kunit'), os.path.join(o['dir'], 'diff_self')
            okk, ek = kunit_bin(o, o['plain'], h, kb, extra)
            r[f'kunit_{tag}'] = run_json([kb])[0] if okk else dict(build_error=ek)
            okd, ed = diff_bin(o, o['plain'], h, db, extra)
            nn = n if tag == 'plain' else max(1, n // 10)
            r[f'self_{tag}'] = run_json([db, str(nn)])[0] if okd else dict(build_error=ed)
            r[f'self_{tag}_boundary'] = run_json([db, str(nn), '--boundary', '--seed', '777'])[0] if okd else None
            ku = r[f'kunit_{tag}'] or {}
            ok = (ku.get('failed') == 0 and ku.get('empty') == 0 and ku.get('total', 0) > 0
                  and mism(r[f'self_{tag}']) == 0 and mism(r[f'self_{tag}_boundary']) == 0)
            r[f'ok_{tag}'] = ok
            ok_all &= ok
            print(m, tag, '| KUnit: случаев', ku.get('total'), 'провалено', ku.get('failed'), 'пропущено', ku.get('skipped'),
                  'пустых', ku.get('empty'), '| против себя: расхождений', mism(r[f'self_{tag}']), '/ крайние', mism(r[f'self_{tag}_boundary']),
                  '|', 'верно' if ok else 'НЕВЕРНО', flush=True)
    res['ok'] = ok_all
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('обвязка:', 'верна' if ok_all else 'НЕВЕРНА')
    return 0 if ok_all else 1


def build_rust(path, out):
    rc, _, err = sh(RUSTC + ['-o', out, path])
    return rc == 0, err[-2000:]


def eval_one(m, path, h, o, n, seed=None, boundary=False, kunit=True, tag='x'):
    src = open(path, encoding='utf-8').read()
    r = dict(file=os.path.relpath(path, X), rs_lines=lines(path), unsafe=len(re.findall(r'\bunsafe\b', src)),
             sha256=hashlib.sha256(src.encode()).hexdigest())
    d = os.path.join(WORK, 'trans', tag)
    os.makedirs(d, exist_ok=True)
    lib = os.path.join(d, 'lib.a')
    r['compiled'], err = build_rust(path, lib)
    if not r['compiled']:
        r['compile_err'] = err
        r['correct'] = False
        return r
    if kunit:
        kb = os.path.join(d, 'kunit')
        okk, ek = kunit_bin(o, lib, h, kb)
        r['kunit_linked'] = okk
        if okk:
            r['kunit'], _, ke = run_json([kb])
            if r['kunit'] is None:
                r['kunit_err'] = ke
        else:
            r['kunit_link_err'] = ek
    db = os.path.join(d, 'diff')
    okd, ed = diff_bin(o, lib, h, db)
    r['diff_linked'] = okd
    if okd:
        cmd = [db, str(n)] + (['--seed', str(seed)] if seed is not None else []) + (['--boundary'] if boundary else [])
        r['diff'], _, de = run_json(cmd)
        if r['diff'] is None:
            r['diff_err'] = de
    else:
        r['diff_link_err'] = ed
    ku, df = r.get('kunit') or {}, r.get('diff')
    r['kunit_pass'] = bool(kunit and r.get('kunit_linked') and ku and ku.get('failed') == 0 and ku.get('empty') == 0 and ku.get('total', 0) > 0)
    r['mismatches'] = mism(df)
    r['correct'] = bool(r['compiled'] and (not kunit or r['kunit_pass']) and df is not None and r['mismatches'] == 0)
    return r


def evaluate(dst, phase, n, mods, heads):
    h = helpers('plain')
    res = dict(mode='eval', phase=phase, n=n, rustc=sh(['rustc', '--version'])[1].strip(), kflags=KFLAGS, modules={})
    for m in mods:
        o = orig_objects(m, 'plain')
        res['modules'][m] = dict(c_lines=lines(f"src/{MODULES[m]['src']}"), translations={})
        for path in sorted(glob.glob(os.path.join(X, 'translations', phase, '*', f'{m}_r*.rs'))):
            head = os.path.basename(os.path.dirname(path))
            if heads and head not in heads:
                continue
            key = f"{head}/{os.path.basename(path)[:-3]}"
            r = eval_one(m, path, h, o, n, tag=key.replace('/', '_'))
            res['modules'][m]['translations'][key] = r
            ku = r.get('kunit') or {}
            print(m, key, '| собран', r['compiled'], '| KUnit провалено', ku.get('failed'), 'из', ku.get('total'), '| расхождений',
                  r.get('mismatches'), '| верен', r['correct'], flush=True)
            json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


def main(a):
    os.makedirs(WORK, exist_ok=True)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d   # noqa: E731
    n = int(opt('--n', '20000'))
    if a[0] == 'check':
        return check(a[1], n, opt('--modules', ','.join(MODULES)).split(','))
    if a[0] == 'eval':
        mods = opt('--modules', ','.join(MODULES)).split(',')
        heads = opt('--heads', '').split(',') if opt('--heads') else []
        return evaluate(a[1], a[2], n, mods, heads)
    if a[0] == 'one':
        m, path = a[2], a[3]
        h = helpers('plain')
        o = orig_objects(m, 'plain')
        seed = int(opt('--seed')) if opt('--seed') else None
        r = eval_one(m, path, h, o, n, seed=seed, boundary='--boundary' in a, kunit='--no-kunit' not in a,
                     tag='one_' + hashlib.sha256(path.encode()).hexdigest()[:12])
        json.dump(r, open(a[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(json.dumps({k: r.get(k) for k in ('compiled', 'kunit_pass', 'mismatches', 'correct')}, ensure_ascii=False))
        return 0
    raise SystemExit('режим: check | eval | one')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
