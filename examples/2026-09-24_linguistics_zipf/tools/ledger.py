#!/usr/bin/env python3
"""ledger.py — инструменты протокола «Реестр утверждений».

  add "<текст>" [--status гипотеза] [--support ...]   новое утверждение (C-###)
  set <ID> <статус> --why "<почему>" [--support ...]  смена статуса (новая запись, старые не стираются)
  render                                              пересобрать CLAIMS.md из claims.jsonl
  audit <файл.md> [--data DIR ...]                    найти в тексте числа, которых нет ни в одном файле данных
  verify-plans                                        PLAN закоммичен раньше результатов и потом не менялся?
  brief                                               короткая сводка состояния (для начала сессии)
  export-chat [transcript.jsonl]                      выгрузить чат сессии в journal/ (с вычисткой секретов)
  check                                               всё сразу, ненулевой код при нарушениях (для CI и хуков)
"""
import json, os, re, sys, glob, subprocess, datetime, argparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LEDGER = os.path.join(ROOT, 'claims.jsonl')
STATUSES = ['гипотеза', 'план', 'подтверждено', 'опровергнуто', 'разницы нет', 'по памяти', 'чужое']
DATA_EXT = ('.json', '.csv', '.tsv', '.log', '.txt', '.md')


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


def git(*a):
    r = subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True)
    return r.stdout.strip()


# ---------- реестр ----------
def load():
    if not os.path.exists(LEDGER):
        return []
    return [json.loads(l) for l in open(LEDGER, encoding='utf-8') if l.strip()]


def state(events):
    claims = {}
    for e in events:
        c = claims.setdefault(e['id'], dict(id=e['id'], text='', status='', support='', updated='', history=[]))
        if e['op'] == 'add':
            c.update(text=e['text'], status=e['status'], support=e.get('support', ''), updated=e['ts'])
        else:
            c['history'].append(e)
            c.update(status=e['status'], updated=e['ts'])
            if e.get('support'):
                c['support'] = e['support']
    return claims


def append(e):
    with open(LEDGER, 'a', encoding='utf-8') as f:
        f.write(json.dumps(e, ensure_ascii=False) + '\n')


def render():
    cl = state(load())
    L = ['# Реестр утверждений', '',
         '_Файл собирается командой `python3 tools/ledger.py render` из `claims.jsonl` (только дописывается). Не править руками._', '',
         'Статусы: ' + ' · '.join(STATUSES) + ' (см. PROTOCOL.md).', '',
         '| ID | Утверждение | Статус | Опора | Обновлено |', '|---|---|---|---|---|']
    for c in cl.values():
        L.append(f"| {c['id']} | {c['text']} | {c['status']} | {c['support'] or '—'} | {c['updated']} |")
    L += ['', '## История изменений статусов', '', '| Дата | ID | Стало | Почему | Опора |', '|---|---|---|---|---|']
    for c in cl.values():
        for h in c['history']:
            L.append(f"| {h['ts']} | {c['id']} | {h['status']} | {h.get('why', '')} | {h.get('support', '')} |")
    open(os.path.join(ROOT, 'CLAIMS.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')


def cmd_add(a):
    ev = load(); n = 1 + sum(1 for e in ev if e['op'] == 'add')
    assert a.status in STATUSES, f'статус должен быть одним из {STATUSES}'
    cid = f'C-{n:03d}'
    append(dict(op='add', id=cid, text=a.text, status=a.status, support=a.support or '', ts=now()))
    render(); print(cid)


def cmd_set(a):
    assert a.status in STATUSES, f'статус должен быть одним из {STATUSES}'
    assert a.id in state(load()), f'нет утверждения {a.id}'
    if a.status in ('подтверждено', 'опровергнуто', 'разницы нет') and not a.support:
        sys.exit('для этого статуса нужна опора: --support "studies/.../REPORT.md" или файл:строка')
    append(dict(op='set', id=a.id, status=a.status, why=a.why, support=a.support or '', ts=now()))
    render(); print(a.id, '→', a.status)


# ---------- аудит текста ----------
NUM = re.compile(r'(?<![\w.,])[−-]?\d+(?:[.,]\d+)?(?:\s?%)?')
DATA_ONLY = ('.json', '.jsonl', '.csv', '.tsv', '.log', '.txt', '.out')
CNUM = re.compile(rb'-?\d+\.?\d*(?:[eE][-+]?\d+)?')


def index_numbers(files):
    """Все числа из файлов данных, округлённые до 0…6 знаков (сравнение по значению, а не по подстроке)."""
    idx = {d: set() for d in range(7)}
    for p in files:
        for m in CNUM.finditer(open(p, 'rb').read()):
            try:
                x = abs(float(m.group(0)))
            except ValueError:
                continue
            if x > 1e12 or x != x:
                continue
            for d in range(7):
                idx[d].add(f'{x:.{d}f}')
    srt = {d: sorted(float(k) for k in idx[d]) for d in range(7)}
    return idx, srt


def density(v, d, srt):
    """Доля занятых значений с той же точностью в той же декаде: вероятность случайного совпадения."""
    import bisect, math
    lo = 10 ** math.floor(math.log10(v)) if v > 0 else 0.0
    hi = lo * 10 if v > 0 else 10 ** (-d)
    step = 10 ** (-d)
    total = max(1, round((hi - lo) / step))
    n = bisect.bisect_left(srt[d], hi) - bisect.bisect_left(srt[d], lo)
    return n / total


def check_number(raw, idx, srt):
    t = raw.replace('−', '-').replace(' ', '').replace(',', '.')
    pct = t.endswith('%'); t = t.rstrip('%').lstrip('-')
    d = min(6, len(t.split('.')[1]) if '.' in t else 0)
    v = float(t)
    cands = [(v, d)] + ([(v / 100, d + 2)] if pct and d + 2 <= 6 else [])
    hit = [(x, dd) for x, dd in cands if f'{x:.{dd}f}' in idx[dd]]
    if not hit:
        return 'не найдено', 0.0
    dens = min(density(x, dd, srt) for x, dd in hit)
    return ('неинформативно' if dens > THRESH else 'найдено'), dens


THRESH = 0.05   # если в той же декаде с той же точностью занято > 5 % значений, совпадение ничего не доказывает


def cmd_audit(a):
    text = open(a.file, encoding='utf-8').read()
    dirs = a.data or [os.path.join(ROOT, d) for d in ('studies', 'sources', 'experiments', 'results') if os.path.isdir(os.path.join(ROOT, d))]
    files = [p for d in dirs for p in (glob.glob(os.path.join(d, '**', '*'), recursive=True) if os.path.isdir(d) else [d])
             if os.path.isfile(p) and p.endswith(DATA_ONLY) and os.path.getsize(p) < 50_000_000]
    idx, srt = index_numbers(files)
    res = {'найдено': [], 'неинформативно': [], 'не найдено': []}
    for ln, line in enumerate(text.splitlines(), 1):
        for m in NUM.finditer(line):
            raw = m.group(0).strip(); digits = re.sub(r'\D', '', raw)
            if len(digits) < 3 or re.fullmatch(r'(19|20)\d\d', digits):
                continue   # мелкие целые и годы не проверяем
            k, dens = check_number(raw, idx, srt)
            res[k].append((ln, raw, dens))
    print(f"файлов данных: {len(files)}; чисел: {sum(map(len, res.values()))}; найдено: {len(res['найдено'])}; "
          f"неинформативно (совпадение вероятно случайно): {len(res['неинформативно'])}; не найдено: {len(res['не найдено'])}")
    for ln, raw, _ in res['не найдено']:
        print(f'  НЕТ  {a.file}:{ln}  {raw}  — нет в файлах данных (по памяти, пересчёт или ручная арифметика — проверить)')
    for ln, raw, dens in res['неинформативно']:
        print(f'  ??   {a.file}:{ln}  {raw}  — совпадение есть, но плотность {dens:.0%}: сузьте --data до файлов этого исследования')
    return len(res['не найдено'])


# ---------- проверка предрегистраций ----------
def cmd_verify_plans(_=None):
    bad = 0
    for plan in sorted(glob.glob(os.path.join(ROOT, 'studies', '*', 'PLAN*.md')) + glob.glob(os.path.join(ROOT, 'experiments', '*', 'PREREG*.md'))):
        if '_TEMPLATE' in plan:
            continue
        d = os.path.dirname(plan); rel = os.path.relpath(plan, ROOT)
        first = git('log', '--diff-filter=A', '--format=%H %ct', '--', rel).splitlines()
        if not first:
            print(f'  ⚠ {rel}: не закоммичен'); bad += 1; continue
        h, t = first[-1].split(); t = int(t)
        changed = git('log', '--format=%h', f'{h}..HEAD', '--', rel).splitlines()
        others = [p for p in glob.glob(os.path.join(d, '**', '*'), recursive=True) if os.path.isfile(p) and p != plan]
        earlier = []
        for p in others:
            r = git('log', '--diff-filter=A', '--format=%ct', '--', os.path.relpath(p, ROOT)).splitlines()
            if r and int(r[-1]) < t:
                earlier.append(os.path.relpath(p, ROOT))
        ok = not changed and not earlier
        bad += not ok
        print(f"  {'✓' if ok else '✗'} {rel}: закоммичен {h[:7]}"
              + (f'; изменён после: {", ".join(changed)}' if changed else '')
              + (f'; файлы появились раньше плана: {", ".join(earlier[:3])}' if earlier else ''))
    return bad


# ---------- сводка ----------
def cmd_brief(_=None):
    cl = state(load())
    by = {s: [c for c in cl.values() if c['status'] == s] for s in STATUSES}
    print('Состояние исследования (tools/ledger.py brief):')
    print('  утверждений: ' + ', '.join(f'{s} {len(v)}' for s, v in by.items() if v) if cl else '  реестр пуст')
    for c in by['по памяти'][:5]:
        print(f"  по памяти: {c['id']} {c['text'][:90]}")
    studies = sorted(glob.glob(os.path.join(ROOT, 'studies', '2*')))
    open_st = [os.path.basename(s) for s in studies if not glob.glob(os.path.join(s, 'REPORT*.md'))]
    if open_st:
        print('  исследования без отчёта: ' + ', '.join(open_st))
    err = os.path.join(ROOT, 'journal', 'ERRORS.md')
    if os.path.exists(err):
        tail = [l for l in open(err, encoding='utf-8').read().splitlines() if re.match(r'^\d+\.', l.strip()) and '<' not in l][-3:]
        for l in tail:
            print('  недавняя ошибка ИИ: ' + l.strip()[:110])
    miss = os.path.join(ROOT, 'sources', 'SOURCES.md')
    if os.path.exists(miss):
        s = open(miss, encoding='utf-8').read().split('## Чего не хватает')[-1]
        items = [l.strip('- ').strip() for l in s.splitlines() if l.strip().startswith('-') and l.strip('- ').strip()]
        if items:
            print(f'  не хватает источников: {len(items)} (sources/SOURCES.md)')


# ---------- выгрузка чата ----------
SECRET = [re.compile(p) for p in (r'sk-[A-Za-z0-9_-]{16,}', r'gh[pousr]_[A-Za-z0-9]{20,}', r'AKIA[0-9A-Z]{16}',
                                  r'(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+')]


def redact(t):
    for p in SECRET:
        t = p.sub('[вычищено]', t)
    return t


def cmd_export_chat(a):
    tp = a.transcript
    if not tp and not sys.stdin.isatty():
        try:
            tp = json.loads(sys.stdin.read() or '{}').get('transcript_path')   # вход хука Claude Code
        except Exception:
            tp = None
    if not tp:
        c = sorted(glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl')), key=os.path.getmtime)
        tp = c[-1] if c else None
    if not tp or not os.path.exists(tp):
        print('транскрипт не найден'); return
    sid = os.path.basename(tp).split('.')[0][:8]
    day = datetime.date.today().isoformat()
    out = os.path.join(ROOT, 'journal', f'CHAT_{day}_{sid}.md')
    tmp = out + '.tmp'
    subprocess.run([sys.executable, os.path.join(ROOT, 'journal', 'export_chat.py'), tp, tmp], check=True, capture_output=True)
    open(out, 'w', encoding='utf-8').write(redact(open(tmp, encoding='utf-8').read())); os.remove(tmp)
    print('чат сохранён:', os.path.relpath(out, ROOT))


def cmd_check(_=None):
    render()
    bad = cmd_verify_plans()
    cl = state(load())
    orphan = [c['id'] for c in cl.values() if c['status'] in ('подтверждено', 'опровергнуто', 'разницы нет') and not c['support']]
    for o in orphan:
        print(f'  ✗ {o}: статус без опоры')
    bad += len(orphan)
    print('проверка:', 'всё в порядке' if not bad else f'нарушений: {bad}')
    sys.exit(1 if bad else 0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest='cmd', required=True)
    x = s.add_parser('add'); x.add_argument('text'); x.add_argument('--status', default='гипотеза'); x.add_argument('--support')
    x = s.add_parser('set'); x.add_argument('id'); x.add_argument('status'); x.add_argument('--why', required=True); x.add_argument('--support')
    s.add_parser('render')
    x = s.add_parser('audit'); x.add_argument('file'); x.add_argument('--data', nargs='*')
    s.add_parser('verify-plans'); s.add_parser('brief'); s.add_parser('check')
    x = s.add_parser('export-chat'); x.add_argument('transcript', nargs='?')
    a = p.parse_args()
    {'add': cmd_add, 'set': cmd_set, 'render': lambda a: render(), 'audit': lambda a: sys.exit(1 if cmd_audit(a) else 0),
     'verify-plans': lambda a: sys.exit(1 if cmd_verify_plans() else 0), 'brief': cmd_brief,
     'export-chat': cmd_export_chat, 'check': cmd_check}[a.cmd](a)


if __name__ == '__main__':
    main()
