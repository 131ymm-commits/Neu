#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-02: сборка и прогон обвязки (PLAN-PILOT.md; устройство — harness/README.md).
  python3 harness/run.py check OUT.json [--n N]                 — оригиналы: KUnit; оригинал против себя на всех потоках правды
                                                                  (вердикт и независимый поиск); то же под UBSan
  python3 harness/run.py eval OUT.json PHASE [--n N] [--modules ...] [--heads ...]
                                                                — переводы translations/PHASE/<голова>/<модуль>_r<k>.rs:
                                                                  rustc, KUnit, сравнение с оригиналом
  python3 harness/run.py one OUT.json MODULE FILE.rs [--n N] [--seed S] [--boundary] [--no-kunit]
                                                                — один файл Rust: вердикт, и свой прогон (--seed/--boundary) для разбора
Семантика C — как у ядра (флаги Makefile v7.4-rc3). Rust — с проверками переполнения (CONFIG_RUST_OVERFLOW_CHECKS), panic=abort.
Символы оригинала для сравнения переименовываются objcopy: каждый определённый глобальный символ s → orig_s.
Вердикт «верен» (verdict_runs): собрался и слинковался, KUnit пройден, 0 расхождений в основном сравнении (n обычных проверок на
функцию) и 0 на крайних значениях (n проверок, зерно 777) — DEVIATIONS п. 10. Пределы времени — от времени оригинала на том же раннере."""
import glob
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(X)
WORK = os.path.join(X, 'work')
KFLAGS = ['-std=gnu11', '-O2', '-funsigned-char', '-fno-common', '-fno-strict-aliasing', '-fno-delete-null-pointer-checks',
          '-fno-strict-overflow', '-U_FORTIFY_SOURCE']   # gcc Ubuntu сам ставит _FORTIFY_SOURCE=3; в ядре CONFIG_FORTIFY_SOURCE не задан
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
    """Запуск в своей группе процессов: при пределе времени убивается вся группа (исполнители делают fork) — ERRORS № 219.
    Вывод декодируется с заменой: пример расхождения может нести сырой байт ≥ 0x80 (ERRORS № 194, № 219)."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out.decode('utf-8', 'replace'), err.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
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
            # все потоки, которыми судят и решают «меняет поведение» (разбор, Н16): вердикт — n обычных и n крайних (зерно 777);
            # независимый поиск — 10n обычных (зерно 20261119) и n крайних (зерно 1119); под UBSan — те же потоки
            r[f'self_{tag}'] = run_json([db, str(n)])[0] if okd else dict(build_error=ed)
            r[f'self_{tag}_boundary'] = run_json([db, str(n), '--boundary', '--seed', str(VERDICT_BND_SEED)])[0] if okd else None
            r[f'self_{tag}_ind'] = run_json([db, str(10 * n), '--seed', '20261119'])[0] if okd else None
            r[f'self_{tag}_ibnd'] = run_json([db, str(n), '--boundary', '--seed', '1119'])[0] if okd else None
            ku = r[f'kunit_{tag}'] or {}
            ok = (ku.get('failed') == 0 and ku.get('empty') == 0 and ku.get('total', 0) > 0
                  and all(mism(r[f'self_{tag}{x}']) == 0 for x in ('', '_boundary', '_ind', '_ibnd')))
            r[f'ok_{tag}'] = ok
            ok_all &= ok
            print(m, tag, '| KUnit: случаев', ku.get('total'), 'провалено', ku.get('failed'), 'пропущено', ku.get('skipped'),
                  'пустых', ku.get('empty'), '| против себя: расхождений', mism(r[f'self_{tag}']), '/ крайние', mism(r[f'self_{tag}_boundary']),
                  '/ независимый', mism(r[f'self_{tag}_ind']), '/ его крайние', mism(r[f'self_{tag}_ibnd']), '|', 'верно' if ok else 'НЕВЕРНО',
                  flush=True)
    res['ok'] = ok_all
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('обвязка:', 'верна' if ok_all else 'НЕВЕРНА')
    return 0 if ok_all else 1


def build_rust(path, out):
    rc, _, err = sh(RUSTC + ['-o', out, path], 900)
    return rc == 0, err[-2000:]


VERDICT_BND_SEED = 777                       # крайние значения входят в вердикт «верен» (DEVIATIONS п. 10)
FLOOR = dict(kunit=30, main=60, bnd=60)      # нижние границы пределов времени, с
TIME_MULT = 10                               # предел — не меньше TIME_MULT времён оригинала на том же раннере


def timed(cmd, timeout):
    """(json или None, истёк ли предел, секунды, хвост stderr)."""
    t0 = time.time()
    rc, out, err = sh(cmd, timeout)
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        d = None
    return d, rc == -999, time.time() - t0, (err or '')[-1500:]


def kunit_ok(kd):
    return bool(kd) and kd.get('failed') == 0 and kd.get('empty') == 0 and kd.get('total', 0) > 0


def verdict_runs(k_bin, d_bin, n, lim):
    """Прогоны вердикта «верен» — одни и те же в оценке переводов и у мутантов: KUnit (если k_bin), основное сравнение
    (n обычных проверок на функцию, зерно драйвера по умолчанию) и крайние значения (n проверок, зерно VERDICT_BND_SEED)."""
    r = {}
    if k_bin:
        kd, to, sec, ke = timed([k_bin], lim['kunit'])
        r.update(kunit=kd, kunit_timeout=to, kunit_s=round(sec, 2), kunit_pass=kunit_ok(kd))
        if kd is None:
            r['kunit_err'] = ke
    dm, to, sec, de = timed([d_bin, str(n)], lim['main'])
    r.update(diff=dm, main_timeout=to, main_s=round(sec, 2), main_mismatches=mism(dm))
    if dm is None:
        r['diff_err'] = de
    dbd, to, sec, be = timed([d_bin, str(n), '--boundary', '--seed', str(VERDICT_BND_SEED)], lim['bnd'])
    r.update(diff_boundary=dbd, bnd_timeout=to, bnd_s=round(sec, 2), bnd_mismatches=mism(dbd))
    if dbd is None:
        r['diff_boundary_err'] = be
    r['comparison_clean'] = dm is not None and dbd is not None and r['main_mismatches'] == 0 and r['bnd_mismatches'] == 0
    return r


def orig_limits(o, h, n, floor=None):
    """Оригинал против себя на этом раннере: время → пределы max(нижняя граница, TIME_MULT × время); заодно проверка, что чист."""
    floor = floor or FLOOR
    kb, db = os.path.join(o['dir'], 'kunit_lim'), os.path.join(o['dir'], 'diff_lim')
    assert kunit_bin(o, o['plain'], h, kb)[0] and diff_bin(o, o['plain'], h, db)[0], 'оригинал не собрался'
    r = verdict_runs(kb, db, n, {k: 3600 for k in FLOOR})
    ok = r['kunit_pass'] and r['comparison_clean']
    slim = {k: v for k, v in r.items() if k not in ('kunit', 'diff', 'diff_boundary')}
    return {k: max(floor[k], TIME_MULT * r[f'{k}_s']) for k in FLOOR}, slim, ok, (kb, db)


def eval_one(m, path, h, o, n, lim, kunit=True, tag='x'):
    src = open(path, encoding='utf-8').read()
    r = dict(file=os.path.relpath(path, X), rs_lines=lines(path), unsafe=len(re.findall(r'\bunsafe\b', src)),
             sha256=hashlib.sha256(src.encode()).hexdigest())
    d = os.path.join(WORK, 'trans', tag)
    os.makedirs(d, exist_ok=True)
    lib = os.path.join(d, 'lib.a')
    r['compiled'], err = build_rust(path, lib)
    r['linked'] = False
    if not r['compiled']:
        r['compile_err'] = err
        r['correct'] = False
        return r
    kb, db = os.path.join(d, 'kunit'), os.path.join(d, 'diff')
    okk, ek = kunit_bin(o, lib, h, kb) if kunit else (True, '')
    okd, ed = diff_bin(o, lib, h, db)
    r.update(kunit_linked=okk, diff_linked=okd, linked=okk and okd)
    if not okk:
        r['kunit_link_err'] = ek
    if not okd:
        r['diff_link_err'] = ed
    if not r['linked']:
        r['correct'] = False
        return r
    r.update(verdict_runs(kb if kunit else None, db, n, lim))
    r['mismatches'] = None if r['main_mismatches'] is None or r['bnd_mismatches'] is None else r['main_mismatches'] + r['bnd_mismatches']
    r['correct'] = bool((not kunit or r['kunit_pass']) and r['comparison_clean'])
    r['diff_bin'] = db
    return r


def evaluate(dst, phase, n, mods, heads):
    h = helpers('plain')
    res = dict(mode='eval', phase=phase, n=n, verdict_boundary_seed=VERDICT_BND_SEED, rustc=sh(['rustc', '--version'])[1].strip(),
               kflags=KFLAGS, modules={}, done=False)
    for m in mods:
        o = orig_objects(m, 'plain')
        lim, orig, ok, _ = orig_limits(o, h, n)
        paths = sorted(glob.glob(os.path.join(X, 'translations', phase, '*', f'{m}_r*.rs')))
        keys = [f"{os.path.basename(os.path.dirname(p))}/{os.path.basename(p)[:-3]}" for p in paths]
        res['modules'][m] = dict(c_lines=lines(f"src/{MODULES[m]['src']}"), limits_s=lim, orig=orig, orig_ok=ok, expected=keys,
                                 translations={})
        for path, key in zip(paths, keys):
            if heads and key.split('/')[0] not in heads:
                continue
            r = eval_one(m, path, h, o, n, lim, tag=key.replace('/', '_'))
            r.pop('diff_bin', None)
            res['modules'][m]['translations'][key] = r
            ku = r.get('kunit') or {}
            print(m, key, '| собран', r['compiled'], '| слинкован', r['linked'], '| KUnit провалено', ku.get('failed'), 'из', ku.get('total'),
                  '| расхождений', r.get('main_mismatches'), '/ крайние', r.get('bnd_mismatches'), '| верен', r['correct'], flush=True)
            json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        res['modules'][m]['complete'] = sorted(res['modules'][m]['translations']) == sorted(k for k in keys if not heads or k.split('/')[0] in heads)
    res['done'] = True
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
        lim, _, _, _ = orig_limits(o, h, n)
        r = eval_one(m, path, h, o, n, lim, kunit='--no-kunit' not in a, tag='one_' + hashlib.sha256(path.encode()).hexdigest()[:12])
        if (opt('--seed') or '--boundary' in a) and r.get('linked'):       # свой прогон для разбора, в вердикт не входит
            cmd = [r['diff_bin'], str(n)] + (['--seed', opt('--seed')] if opt('--seed') else []) + (['--boundary'] if '--boundary' in a else [])
            r['custom'], r['custom_timeout'], _, _ = timed(cmd, 3600)
            r['custom_mismatches'] = mism(r['custom'])
        r.pop('diff_bin', None)
        json.dump(r, open(a[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(json.dumps({k: r.get(k) for k in ('compiled', 'linked', 'kunit_pass', 'main_mismatches', 'bnd_mismatches', 'custom_mismatches',
                                                'correct')}, ensure_ascii=False))
        return 0
    raise SystemExit('режим: check | eval | one')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
