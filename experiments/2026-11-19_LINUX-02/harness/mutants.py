#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-02: оценка оценщиков мутантами до PREREG (PLAN-PILOT.md, «Мутанты до PREREG», правило отбора п. 3; уточнения —
DEVIATIONS.md, запись 19.11 до оценки пилота; числа — harness/README.md).

Мутантов делает этот скрипт механически, не головы: одна правка на мутанта. Виды правки — как в LINUX-01 (harness/mutants.py там же):
сравнение (< ↔ <=, > ↔ >=, == ↔ !=), плюс-минус (+ ↔ -, += ↔ -=, wrapping_add ↔ wrapping_sub), логика (&& ↔ ||), сдвиг (<< ↔ >>),
константа N → N+1. Новое по плану — «разрыв C и Rust», ширина целого в приведении: as u8 ↔ as u16, as u32 ↔ as u64, as i32 ↔ as u32
(у «as u32» два кандидата: u64 и i32). Комментарии, строки и символьные литералы не трогаются; унарный минус не трогается.
Места — случайная выборка до --per-file на основу (зерно 17, как в LINUX-01). Не собравшийся мутант («мертворождённый») не считается.

Основа мутантов (уточнение плана, решено до оценки пилота):
  * чистый перевод пилота — собрался, прошёл KUnit, 0 расхождений в основном сравнении и 0 в независимом поиске. Неверный перевод
    основой не берётся: его мутанты «меняли бы поведение» и «убивались сравнением» по построению;
  * если у модуля нет ни одного чистого перевода — основа оригинал на C (те же виды правки; приведения — в виде C: (u8) ↔ (u16),
    (u32) ↔ (u64), (u32) ↔ (s32), (int) ↔ (unsigned int)); у min_heap правки и в include/linux/min_heap.h — его встроенные функции
    собираются в lib/min_heap.c (мутант заголовка подставляется только при сборке реализации).

Три прогона каждого мутанта:
  * KUnit — убит, если KUnit не «прошёл» по правилу оценки (run.py: провалов 0, пустых 0, случаев > 0), упал или завис;
  * основное сравнение — как в оценке (то же зерно, --n на функцию, без крайних) — убит при расхождении, падении, зависании;
  * независимый поиск — другое зерно, в 10 раз больше входов и крайние значения (--boundary, своё зерно). Расхождение, падение или
    зависание — мутант «меняет поведение».
Пределы времени — от времени оригинала на том же раннере: не меньше 10 его времён и не меньше нижней границы (README).
Правило п. 3 (строгое, без разбора по одному): среди меняющих поведение основное сравнение убивает ≥ 0,95; «KUnit поймал, основное
сравнение пропустило» ≤ 2 % от всех живых мутантов, убитых KUnit. Нет меняющих поведение — правило не выполнено.
Условие п. 5 (добавлено до оценки пилота, DEVIATIONS.md): KUnit может провалить перевод — объект теста ссылается хотя бы на одну
экспортируемую функцию переводимого файла (nm) и среди меняющих поведение мутантов KUnit убивает хотя бы одного.
  python3 harness/mutants.py OUT.json MODULE [--phase pilot] [--per-file 25] [--seed 17] [--n 20000] [--workers N]
                                             [--bases PATH.rs,...] (только для сухого прогона на заглушках)"""
import concurrent.futures as cf
import glob
import hashlib
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run as R  # noqa: E402   (переходит в папку опыта: MODULES, CF, LIBS, helpers, orig_objects, kunit_bin, diff_bin, build_rust)

IND_SEED, BND_SEED = 20261119, 1119          # независимый поиск: свои зёрна (основное сравнение — зерно по умолчанию драйвера)
IND_MULT = 10                                 # во сколько раз больше входов в независимом поиске
FLOOR = dict(kunit=30, main=60, ind=120, bnd=60)   # нижние границы пределов времени, с
TIME_MULT = 10                                # предел — не меньше TIME_MULT времён оригинала
C_EXTRA_FILES = {'min_heap': ['include/linux/min_heap.h']}   # заголовки, чьи встроенные функции собираются в реализацию

TOK = re.compile(r'<<=|>>=|<<|>>|<=|>=|==|!=|&&|\|\||->|=>|\+\+|--|\+=|-=|[<>+\-]|\bwrapping_(?:add|sub)\b|'
                 r'\bas\s+(?:u8|u16|u32|u64|i32)\b|'
                 r'\((?:u8|u16|u32|u64|s32|int|unsigned int)\)|'
                 r'\b(?:0x[0-9a-fA-F_]+|\d[\d_]*)(?:[ui](?:8|16|32|64|128|size)|[uU]?[lL]{0,2}|[lL]{1,2}[uU]?)?\b')
SWAP = {'<': '<=', '<=': '<', '>': '>=', '>=': '>', '==': '!=', '!=': '==', '&&': '||', '||': '&&', '<<': '>>', '>>': '<<',
        '+=': '-=', '-=': '+=', '+': '-', '-': '+', 'wrapping_add': 'wrapping_sub', 'wrapping_sub': 'wrapping_add'}
KIND = {'<': 'сравнение', '<=': 'сравнение', '>': 'сравнение', '>=': 'сравнение', '==': 'сравнение', '!=': 'сравнение',
        '&&': 'логика', '||': 'логика', '<<': 'сдвиг', '>>': 'сдвиг', '+=': 'плюс-минус', '-=': 'плюс-минус', '+': 'плюс-минус',
        '-': 'плюс-минус', 'wrapping_add': 'плюс-минус', 'wrapping_sub': 'плюс-минус'}
CAST_RS = {'u8': ['u16'], 'u16': ['u8'], 'u32': ['u64', 'i32'], 'u64': ['u32'], 'i32': ['u32']}
CAST_C = {'u8': ['u16'], 'u16': ['u8'], 'u32': ['u64', 's32'], 'u64': ['u32'], 's32': ['u32'], 'int': ['unsigned int'],
          'unsigned int': ['int']}


def mask(src, lang):
    """Комментарии, строки, символьные литералы (и строки #include в C) → пробелы; позиции сохраняются."""
    out = list(src)
    pat = r'//[^\n]*|/\*.*?\*/|b?"(?:\\.|[^"\\])*"|b?\'(?:\\.|[^\\\'])\''
    if lang == 'c':
        pat = r'^[ \t]*#[ \t]*include[^\n]*|' + r"'(?:\\.|[^\\'])+'|" + pat
    for m in re.finditer(pat, src, flags=re.S | re.M):
        for k in range(m.start(), m.end()):
            if out[k] != '\n':
                out[k] = ' '
    return ''.join(out)


def bump_const(t, lang):
    """N → N+1 с сохранением основания и суффикса; в C ведущий 0 — восьмеричное."""
    m = re.match(r'(0x[0-9a-fA-F_]+|\d[\d_]*)(.*)', t)
    body, suf = m.group(1), m.group(2)
    if body.startswith('0x'):
        return hex(int(body.replace('_', ''), 16) + 1) + suf
    if lang == 'c' and len(body) > 1 and body.startswith('0'):
        return '0' + format(int(body, 8) + 1, 'o') + suf
    return str(int(body.replace('_', '')) + 1) + suf


def sites(src, lang):
    """Кандидаты правки: (начало, конец, было, стало, вид)."""
    ms = mask(src, lang)
    res = []
    for m in TOK.finditer(ms):
        t = m.group(0)
        if t in ('->', '=>', '<<=', '>>=', '++', '--'):
            continue
        if t in ('+', '-'):
            prev = ms[:m.start()].rstrip()[-1:]
            if not prev or prev in '([{,;=:!<>&|+-*/%^?':
                continue
        if t in SWAP:
            res.append((m.start(), m.end(), t, SWAP[t], KIND[t]))
            continue
        if t.startswith('as'):
            if lang != 'rust':
                continue
            ty = t.split()[-1]
            res += [(m.start(), m.end(), t, 'as ' + to, 'приведение') for to in CAST_RS[ty]]
            continue
        if t.startswith('('):
            if lang != 'c':
                continue
            ty = t[1:-1]
            res += [(m.start(), m.end(), t, f'({to})', 'приведение') for to in CAST_C[ty]]
            continue
        if lang == 'rust' and re.search(r'[lLU]$', t) and not re.search(r'size$', t):
            continue                                     # суффиксы C в Rust не бывают — это часть идентификатора или ошибка разбора
        res.append((m.start(), m.end(), t, bump_const(t, lang), 'константа'))
    return res


def run_group(cmd, timeout):
    """Запуск в своей группе процессов: при зависании убивается вся группа (исполнители делают fork).
    Вывод декодируется с заменой: пример расхождения может нести сырой байт (ERRORS № 194)."""
    t0 = time.time()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
                         start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err, False, time.time() - t0
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return -9, '', 'TIMEOUT', True, time.time() - t0


def jload(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def mism(df):
    return sum(v['mismatches'] for v in df['fns'].values()) if df else None


def kunit_ok(kd):
    return bool(kd) and kd.get('failed') == 0 and kd.get('empty') == 0 and kd.get('total', 0) > 0


def three_runs(k_bin, d_bin, n, lim):
    """KUnit, основное сравнение, независимый поиск (обычные входы и крайние) — с пределами времени lim."""
    rec = {}
    _, out, _, to, sec = run_group([k_bin], lim['kunit'])
    kd = jload(out)
    rec.update(kunit_timeout=to, kunit_s=round(sec, 2), kunit_total=(kd or {}).get('total'), kunit_failed=(kd or {}).get('failed'),
               kunit_empty=(kd or {}).get('empty'), killed_kunit=not kunit_ok(kd))
    _, out, _, to, sec = run_group([d_bin, str(n)], lim['main'])
    df = jload(out)
    rec.update(main_timeout=to, main_s=round(sec, 2), main_mismatches=mism(df), killed_main=df is None or mism(df) > 0)
    _, out, _, to1, sec1 = run_group([d_bin, str(n * IND_MULT), '--seed', str(IND_SEED)], lim['ind'])
    di = jload(out)
    _, out, _, to2, sec2 = run_group([d_bin, str(n), '--boundary', '--seed', str(BND_SEED)], lim['bnd'])
    db = jload(out)
    rec.update(ind_timeout=to1, ind_s=round(sec1, 2), ind_mismatches=mism(di), bnd_timeout=to2, bnd_s=round(sec2, 2),
               bnd_mismatches=mism(db), changed=di is None or mism(di) > 0 or db is None or mism(db) > 0)
    return rec


def build_impl(lang, src_text, rel, work, ctx):
    """Реализация модуля из текста: Rust → staticlib; C → объект (мутант заголовка — через свою папку include первой)."""
    os.makedirs(work, exist_ok=True)
    if lang == 'rust':
        rs, lib = os.path.join(work, 'impl.rs'), os.path.join(work, 'impl.a')
        open(rs, 'w', encoding='utf-8').write(src_text)
        rc, _, err, _, _ = run_group(R.RUSTC + ['-o', lib, rs], 600)
        return (lib if rc == 0 else None), err[-1500:]
    mod_src = f"src/{R.MODULES[ctx['module']]['src']}"
    inc = []
    if rel == R.MODULES[ctx['module']]['src']:
        cpath = os.path.join(work, os.path.basename(rel))
        open(cpath, 'w', encoding='utf-8').write(src_text)
        # #include "..." в исходнике ищется сначала рядом с файлом — добавляется папка оригинала
        inc = ['-iquote', os.path.dirname(mod_src)]
    else:
        hdir = os.path.join(work, 'inc')
        hpath = os.path.join(hdir, rel.split('include/', 1)[1])
        os.makedirs(os.path.dirname(hpath), exist_ok=True)
        open(hpath, 'w', encoding='utf-8').write(src_text)
        cpath, inc = mod_src, ['-I', hdir]
    obj = os.path.join(work, 'impl.o')
    rc, _, err, _, _ = run_group(['gcc'] + inc + R.CF + ['-c', cpath, '-o', obj], 600)
    return (obj if rc == 0 else None), err[-1500:]


def eval_impl(job):
    """Один мутант или одна основа: сборка, сборка исполнителей, три прогона. Сбой обвязки — в строку (error), прогон идёт дальше."""
    try:
        return eval_impl1(job)
    except Exception as ex:                      # noqa: BLE001
        return dict(base=job['base'], site=job.get('site'), error=repr(ex)[:300], compiled=None)


def eval_impl1(job):
    ctx = job['ctx']
    work = os.path.join(R.WORK, 'mut2', ctx['module'], job['tag'])
    shutil.rmtree(work, ignore_errors=True)
    rec = {k: job[k] for k in ('base', 'lang', 'file', 'site', 'line', 'frm', 'to', 'kind') if k in job}
    impl, err = build_impl(job['lang'], job['text'], job['file'], work, ctx)
    rec['compiled'] = impl is not None
    if impl is None:
        rec['compile_err_tail'] = err[-300:]
    else:
        k_bin, d_bin = os.path.join(work, 'kunit'), os.path.join(work, 'diff')
        ok1, e1 = R.kunit_bin(ctx['o'], impl, ctx['h'], k_bin)
        ok2, e2 = R.diff_bin(ctx['o'], impl, ctx['h'], d_bin)
        rec['linked'] = ok1 and ok2
        if not rec['linked']:
            rec['link_err_tail'] = (e1 or e2)[-300:]
        else:
            rec.update(three_runs(k_bin, d_bin, ctx['n'], ctx['lim']))
    if not job.get('keep'):
        shutil.rmtree(work, ignore_errors=True)
    return rec


def summary(rows):
    alive = [r for r in rows if r.get('compiled') and r.get('linked') and 'changed' in r]
    ch = [r for r in alive if r['changed']]
    kk = [r for r in alive if r['killed_kunit']]
    s = dict(generated=len(rows), harness_errors=sum('error' in r for r in rows), stillborn=sum(r.get('compiled') is False for r in rows),
             not_linked=sum(bool(r.get('compiled')) and not r.get('linked') for r in rows), alive=len(alive), changed=len(ch),
             changed_killed_kunit=sum(r['killed_kunit'] for r in ch), changed_killed_main=sum(r['killed_main'] for r in ch),
             killed_kunit=len(kk), kunit_caught_main_missed=sum(not r['killed_main'] for r in kk),
             kunit_caught_main_missed_changed=sum(not r['killed_main'] for r in kk if r['changed']),
             main_killed_not_changed=sum(r['killed_main'] and not r['changed'] for r in alive),
             survived_all=sum(not r['killed_kunit'] and not r['killed_main'] and not r['changed'] for r in alive),
             timeouts=dict(kunit=sum(bool(r.get('kunit_timeout')) for r in alive), main=sum(bool(r.get('main_timeout')) for r in alive),
                           ind=sum(bool(r.get('ind_timeout')) for r in alive), bnd=sum(bool(r.get('bnd_timeout')) for r in alive)))
    s['share_changed_killed_kunit'] = s['changed_killed_kunit'] / len(ch) if ch else None
    s['share_changed_killed_main'] = s['changed_killed_main'] / len(ch) if ch else None
    s['share_kunit_caught_main_missed'] = s['kunit_caught_main_missed'] / len(kk) if kk else None
    s['rule3_main'] = bool(ch) and s['share_changed_killed_main'] >= 0.95
    s['rule3_kunit_not_stronger'] = (not kk) or s['share_kunit_caught_main_missed'] <= 0.02
    s['rule3'] = s['rule3_main'] and s['rule3_kunit_not_stronger']
    s['rule5_mutant_part'] = s['changed_killed_kunit'] >= 1
    return s


def limits(orig_rec):
    return {k: max(FLOOR[k], TIME_MULT * orig_rec[f'{k}_s']) for k in FLOOR}


def main(a):
    dst, m = a[0], a[1]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d   # noqa: E731
    phase, per, seed = opt('--phase', 'pilot'), int(opt('--per-file', '25')), int(opt('--seed', '17'))
    n, workers = int(opt('--n', '20000')), int(opt('--workers', str(os.cpu_count() or 2)))
    assert m in R.MODULES, m
    h = R.helpers('plain')
    o = R.orig_objects(m, 'plain')
    ctx = dict(module=m, h=h, o=o, n=n, lim=dict(FLOOR))
    t0 = time.time()
    # 1. оригинал против себя: время для пределов и проверка, что все три прогона дают «чисто»
    k_bin, d_bin = os.path.join(o['dir'], 'kunit_mut'), os.path.join(o['dir'], 'diff_mut')
    assert R.kunit_bin(o, o['plain'], h, k_bin)[0] and R.diff_bin(o, o['plain'], h, d_bin)[0], 'оригинал не собрался'
    orig = three_runs(k_bin, d_bin, n, {k: 3600 for k in FLOOR})
    orig_ok = not (orig['killed_kunit'] or orig['killed_main'] or orig['changed'])
    lim = limits(orig)
    ctx['lim'] = lim
    nm_u = R.sh(['nm', '-u', o['test']])[1].split()
    kunit_refs = sorted(x for x in o['syms'] if x in nm_u)
    res = dict(module=m, phase=phase, n=n, exported=o['syms'], kunit_refs=kunit_refs, ind=dict(seed=IND_SEED, n=n * IND_MULT), bnd=dict(seed=BND_SEED, n=n), per_file=per, seed=seed,
               workers=workers, rustc=R.sh(['rustc', '--version'])[1].strip(), gcc=R.sh(['gcc', '--version'])[1].splitlines()[0],
               nproc=os.cpu_count(), orig=orig, orig_ok=orig_ok, limits_s=lim)
    if not orig_ok:
        res['stop'] = 'оригинал не чист в трёх прогонах — мутанты не считаются'
        json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(res['stop'], orig)
        return 1
    # 2. основы: переводы фазы (или заглушки сухого прогона)
    paths = opt('--bases').split(',') if opt('--bases') else sorted(glob.glob(os.path.join(R.X, 'translations', phase, '*', f'{m}_r*.rs')))
    base_jobs = []
    for p in paths:
        head = os.path.basename(os.path.dirname(p)) + '/' + os.path.basename(p)[:-3]
        base_jobs.append(dict(base=head, lang='rust', file=os.path.relpath(p, R.X), text=open(p, encoding='utf-8').read(),
                              tag='base_' + hashlib.sha256(head.encode()).hexdigest()[:10], ctx=ctx))
    with cf.ProcessPoolExecutor(workers) as ex:
        bases = list(ex.map(eval_impl, base_jobs))
    for b in bases:
        b['clean'] = bool(b.get('compiled') and b.get('linked') and not b.get('killed_kunit') and not b.get('killed_main')
                          and not b.get('changed'))
    res['bases'] = bases
    clean = [j for j, b in zip(base_jobs, bases) if b['clean']]
    if clean:
        res['base_kind'] = 'чистые переводы пилота'
        sources = [(j['base'], 'rust', j['file'].replace(os.sep, '/'), j['text']) for j in clean]
    else:
        res['base_kind'] = 'оригинал на C (чистого перевода нет)'
        files = [R.MODULES[m]['src']] + C_EXTRA_FILES.get(m, [])
        sources = [('orig_c/' + os.path.basename(f), 'c', f, open(os.path.join('src', f), encoding='utf-8').read()) for f in files]
    # 3. мутанты
    jobs = []
    for base, lang, rel, text in sources:
        st = sites(text, lang)
        rng = random.Random(int(hashlib.sha256(f'{seed}/{base}/{m}'.encode()).hexdigest()[:12], 16))
        pick = sorted(rng.sample(range(len(st)), min(per, len(st))))
        for k in pick:
            s, e, frm, to, kind = st[k]
            jobs.append(dict(base=base, lang=lang, file=rel if lang == 'c' else rel, site=k, line=text.count('\n', 0, s) + 1, frm=frm,
                             to=to, kind=kind, text=text[:s] + to + text[e:], tag=f"m_{hashlib.sha256(f'{base}/{k}'.encode()).hexdigest()[:10]}",
                             ctx=ctx))
        res.setdefault('sites', {})[base] = dict(candidates=len(st), picked=len(pick))
    with cf.ProcessPoolExecutor(workers) as ex:
        rows = list(ex.map(eval_impl, jobs))
    res['rows'] = rows
    res['total'] = summary(rows)
    res['by_base'] = {b: summary([r for r in rows if r['base'] == b]) for b in sorted({r['base'] for r in rows})}
    res['by_kind'] = {k: summary([r for r in rows if r.get('kind') == k]) for k in sorted({r.get('kind') for r in rows if r.get('kind')})}
    res['rule5'] = bool(kunit_refs) and res['total']['rule5_mutant_part']
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    t = res['total']
    print(m, '| основа:', res['base_kind'], '| чистых основ', len(clean), 'из', len(bases), '| мутантов', t['generated'], '| мертворождённых',
          t['stillborn'], '| живых', t['alive'], '| меняют поведение', t['changed'], '| из них убито KUnit', t['changed_killed_kunit'],
          '| сравнением', t['changed_killed_main'], '| KUnit поймал, сравнение пропустило', t['kunit_caught_main_missed'], 'из',
          t['killed_kunit'], '| правило 3:', t['rule3'], '| KUnit ссылается на', len(kunit_refs), 'из', len(o['syms']), '| условие 5:',
          res['rule5'], '|', res['seconds'], 'с', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
