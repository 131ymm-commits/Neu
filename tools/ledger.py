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
# «29 539» — одно число (разделитель тысяч: пробел, NBSP, узкий NBSP); хэши вида 964508d, даты 24.09.2026 и номера C-003 не числа
NUM = re.compile(r'(?<![\w.,−-])[−-]?(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?(?!\w)(?![.,]\d)(?:\s?%)?')
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
    t = re.sub(r'[\s\u00a0\u202f]', '', raw.replace('−', '-')).replace(',', '.')
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


def audit_numbers(file, dirs):
    """Числа текста против файлов данных: {'найдено'|'неинформативно'|'не найдено': [(строка, число, плотность/столбец)]}."""
    text = open(file, encoding='utf-8').read()
    files = [p for d in dirs for p in (glob.glob(os.path.join(d, '**', '*'), recursive=True) if os.path.isdir(d) else [d])
             if os.path.isfile(p) and p.endswith(DATA_ONLY) and os.path.getsize(p) < 50_000_000]
    idx, srt = index_numbers(files)
    res = {'найдено': [], 'неинформативно': [], 'не найдено': []}
    for ln, line in enumerate(text.splitlines(), 1):
        for m in NUM.finditer(line):
            raw = m.group(0).strip(); digits = re.sub(r'\D', '', raw)
            if len(digits) < 3 or re.fullmatch(r'(1[5-9]|20)\d\d', digits):
                continue   # мелкие целые и годы (1500–2099) не проверяем
            k, dens = check_number(raw, idx, srt)
            res[k].append((ln, raw, dens if k != 'не найдено' else m.start()))
    return res, len(files)


def cmd_audit(a):
    dirs = a.data or [os.path.join(ROOT, d) for d in ('studies', 'sources', 'experiments', 'results') if os.path.isdir(os.path.join(ROOT, d))]
    res, nfiles = audit_numbers(a.file, dirs)
    print(f"файлов данных: {nfiles}; чисел: {sum(map(len, res.values()))}; найдено: {len(res['найдено'])}; "
          f"неинформативно (совпадение вероятно случайно): {len(res['неинформативно'])}; не найдено: {len(res['не найдено'])}")
    for ln, raw, _ in res['не найдено']:
        print(f'  НЕТ  {a.file}:{ln}  {raw}  — нет в файлах данных (по памяти, пересчёт или ручная арифметика — проверить)')
    for ln, raw, dens in res['неинформативно']:
        print(f'  ??   {a.file}:{ln}  {raw}  — совпадение есть, но плотность {dens:.0%}: сузьте --data до файлов этого исследования')
    return len(res['не найдено'])


# ---------- проверка предрегистраций ----------
def _is_run(d, p):
    """Файл — результат прогона, по которому будет вердикт? Пилоты и сухие прогоны до регистрации допустимы."""
    rp = os.path.relpath(p, d).replace(os.sep, '/'); b = os.path.basename(p)
    if rp.startswith(('pilot', 'dry', 'test/')): return False
    return rp.startswith('run/') or b.startswith(('REPORT', 'results', 'raw_', 'out_', 'res')) or '_out' in b or b.startswith('analysis')


def cmd_verify_plans(_=None):
    bad = 0
    for plan in sorted(glob.glob(os.path.join(ROOT, 'studies', '*', 'PLAN*.md')) + glob.glob(os.path.join(ROOT, 'experiments', '*', 'PREREG*.md'))):
        if '_TEMPLATE' in plan:
            continue
        d = os.path.dirname(plan); rel = os.path.relpath(plan, ROOT)
        first = git('log', '--diff-filter=A', '--format=%H %ct', '--', rel).splitlines()
        if not first:
            # Черновик до регистрации допустим, пока в папке нет результатов прогона (пилоты и сухие прогоны не в счёт).
            drafts_runs = [p for p in glob.glob(os.path.join(d, '**', '*'), recursive=True) if os.path.isfile(p) and p != plan and _is_run(d, p)]
            if drafts_runs: print(f'  ✗ {rel}: не закоммичен, а прогон уже есть: {os.path.relpath(drafts_runs[0], ROOT)}'); bad += 1
            else: print(f'  ⚠ {rel}: черновик, не закоммичен (прогона ещё нет)')
            continue
        h, t = first[-1].split(); t = int(t)
        # Правило (PROTOCOL.md §3.3, 27.09.2026): PREREG закоммичен раньше первого прогона, по которому будет вердикт, и не менялся после него.
        # Код, сухой прогон и пилоты до регистрации допустимы. Прогон = файлы в run/ или результаты/отчёт/сырые выводы в папке опыта.
        others = [p for p in glob.glob(os.path.join(d, '**', '*'), recursive=True) if os.path.isfile(p) and p != plan]
        def is_run(p): return _is_run(d, p)
        run_times = []
        for p in others:
            if not is_run(p): continue
            r = git('log', '--diff-filter=A', '--format=%ct', '--', os.path.relpath(p, ROOT)).splitlines()
            if r: run_times.append((int(r[-1]), os.path.relpath(p, ROOT)))
        t_run = min(run_times)[0] if run_times else None
        late = [p for tt, p in run_times if tt < t] if t_run is not None else []
        changed = [c for c in git('log', '--format=%h %ct', f'{h}..HEAD', '--', rel).splitlines() if t_run is not None and int(c.split()[1]) > t_run]
        ok = not changed and not late
        bad += not ok
        print(f"  {'✓' if ok else '✗'} {rel}: закоммичен {h[:7]}" + ('' if run_times else ' (прогона ещё нет)')
              + (f'; изменён после первого прогона: {", ".join(c.split()[0] for c in changed)}' if changed else '')
              + (f'; прогон раньше плана: {", ".join(late[:3])}' if late else ''))
    return bad


# ---------- проверки протокола кодом (критерий 2, DECISIONS 27.09.2026; корпус — tools/protocol_tests.py) ----------
def _exp_id(d):
    b = os.path.basename(d); return b.split('_', 1)[1] if '_' in b and b[:4].isdigit() else b


def _exp_dirs():
    return [d for d in sorted(glob.glob(os.path.join(ROOT, 'experiments', '2*'))) if os.path.isdir(d)]


def _rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, '/')


_ADD = {}


def _added(p, with_hash=False):
    """Время первого коммита файла (unix) или None, если файл не закоммичен. Один git log на всю историю (кэш)."""
    if not _ADD:
        h = t = None
        for l in git('log', '--diff-filter=A', '--no-renames', '--format=%x00%h %ct', '--name-only').splitlines():
            if l.startswith('\x00'): h, t = l[1:].split(); t = int(t)
            elif l.strip(): _ADD[l.strip()] = (t, h)   # лог от новых к старым: последняя запись = первое добавление
        _ADD[None] = (None, None)
    r = _ADD.get(_rel(p), (None, None))
    return r if with_hash else r[0]


def _files(d):
    return [p for p in glob.glob(os.path.join(d, '**', '*'), recursive=True) if os.path.isfile(p) and '__pycache__' not in p]


def _aux(p, d):
    """Пилоты, сухие прогоны и тесты — не прогон (CLAUDE.md, ворота 1; PROTOCOL.md §3.3)."""
    return os.path.relpath(p, d).replace(os.sep, '/').startswith(('pilot', 'dry', 'test'))


def _is_run(p, d):
    """Прогон, по которому будет вердикт: run/, результаты, сырые выводы, отчёт (как в verify-plans)."""
    if _aux(p, d): return False
    rp = os.path.relpath(p, d).replace(os.sep, '/'); b = os.path.basename(p)
    return rp.startswith('run/') or b.startswith(('REPORT', 'results', 'raw_', 'out_', 'res')) or '_out' in b or b.startswith('analysis')


def _t_run(d):
    ts = [_added(p) for p in _files(d) if _is_run(p, d)]
    ts = [t for t in ts if t]
    return min(ts) if ts else None


def _read(p):
    return open(p, encoding='utf-8', errors='replace').read()


def _is_commit(h):
    return subprocess.run(['git', '-C', ROOT, 'cat-file', '-e', f'{h}^{{commit}}'], capture_output=True).returncode == 0


def _ancestor(a, b):
    return subprocess.run(['git', '-C', ROOT, 'merge-base', '--is-ancestor', a, b], capture_output=True).returncode == 0


HASH = re.compile(r'(?<![\w/])[0-9a-f]{7,40}(?![\w/])')


def chk_report_hash(d):
    """PROTOCOL.md §3.5 / SKILL «После эксперимента» 1: REPORT ссылается на хеш коммита предрегистрации;
    §3.3: хеш — доказательство, значит он должен быть в истории (git cat-file -e), в текущей ветке (merge-base
    --is-ancestor) и содержать сам PREREG. Отчёт без хеша вовсе — предупреждение (не считается)."""
    bad = 0; eid = _exp_id(d); pres = glob.glob(os.path.join(d, 'PREREG*.md'))
    for rep in sorted(glob.glob(os.path.join(d, 'REPORT*.md'))):
        txt = _read(rep); cands = []
        for m in HASH.finditer(txt):
            h = m.group(0); before = txt[max(0, m.start() - 25):m.start()].lower()
            if re.search(r'[a-f]', h) or re.search(r'коммит|хеш|hash|commit|prereg|предрегистрац', before):
                cands.append(h)
        if not cands:
            print(f'  ⚠ {eid}: {os.path.basename(rep)} не ссылается на хеш предрегистрации'); continue
        ok = False; why = []
        for h in dict.fromkeys(cands):
            if not _is_commit(h): why.append(f'{h}: нет в истории'); continue
            if not _ancestor(h, 'HEAD'): why.append(f'{h}: не в текущей ветке'); continue
            if pres and not any(subprocess.run(['git', '-C', ROOT, 'cat-file', '-e', f'{h}:{_rel(p)}'], capture_output=True).returncode == 0 for p in pres):
                why.append(f'{h}: в этом коммите нет PREREG'); continue
            ok = True; break
        if not ok:
            print(f'  ✗ {eid}: хеш предрегистрации в {os.path.basename(rep)} не подтверждён историей ({"; ".join(why)})'); bad += 1
    return bad


APPROX = re.compile(r'(около|примерно|порядка|почти|≈|~|>|<|≥|≤)\s*$')
ITEM = re.compile(r'(№|§|п\.|пп\.|пункт\w*|урок\w*|строк\w*|заседани\w*|сесси\w*|ревизи\w*|редакци\w*|верси\w*|правил\w*|ошибк\w*|ERRORS|шаг\w*|глав\w*|раздел\w*|табл\w*|рис\w*)\s*$', re.I)


def _norm_num(raw):
    return re.sub(r'[\s  ]', '', raw.replace('−', '-')).replace(',', '.')


EXP_REF = re.compile(r'\b[A-Z]{2,}-\d{2,}\b')
PRODUCT = re.compile(r'^[^()]{0,60}\(([^()]*[×*][^()]*)\)')


def _prereg_nums(d):
    out = set()
    for p in glob.glob(os.path.join(d, 'PREREG*.md')):
        out |= {_norm_num(m.group(0).strip()) for m in NUM.finditer(_read(p))}
    return out


def chk_report_numbers(d):
    """CLAUDE.md «Мои правила/Выводы»: каждое число в отчёте берётся из json и сверяется ledger.py audit;
    PROTOCOL.md §5.1: любое число — с путём к файлу результатов. Проверяем числа REPORT против файлов данных
    папки опыта тем же audit. Не ловим: годы, номера пунктов/уроков, ID (audit), хеши коммитов, числа из PREREG
    (пороги и параметры), числа с пометкой приближения («около», «≈»), числа с показанной арифметикой
    «N (a × b × c)», а число в строке, где назван другой опыт, ищем и в его папке/PREREG."""
    bad = 0; eid = _exp_id(d)
    pre_nums = _prereg_nums(d); other = {}
    for rep in sorted(glob.glob(os.path.join(d, 'REPORT*.md'))):
        res, _ = audit_numbers(rep, [d]); lines = _read(rep).splitlines()
        miss = []
        for ln, raw, col in res['не найдено']:
            line = lines[ln - 1]; before = line[:col]; after = line[col + len(raw):]
            n = _norm_num(raw); v = n.rstrip('%').strip()
            if n in pre_nums or v in pre_nums: continue
            if APPROX.search(before) or ITEM.search(before): continue
            if re.fullmatch(r'\d{7,40}', n) and _is_commit(n): continue
            m = PRODUCT.match(after)
            if m:
                prod = 1
                for f in re.findall(r'\d+', m.group(1)): prod *= int(f)
                if str(prod) == v: continue   # арифметика показана и сходится
            found = False
            for ref in set(EXP_REF.findall(line)) - {eid}:
                for od in glob.glob(os.path.join(ROOT, 'experiments', f'*_{ref}')):
                    if od not in other:
                        r2, _ = audit_numbers(rep, [od]); other[od] = ({(l, w) for l, w, _ in r2['не найдено']}, _prereg_nums(od))
                    if (ln, raw) not in other[od][0] or v in other[od][1]: found = True
            if found: continue
            miss.append(f'{raw} (строка {ln})')
        if miss:
            print(f'  ✗ {eid}: числа в {os.path.basename(rep)} не найдены в файлах данных папки: ' + ', '.join(miss[:6])); bad += 1
    return bad


THRESH_RE = re.compile(r'[≥≤<>]|порог|не менее|не более|хотя бы|минимум|максимум')
FAIL_RE = re.compile(r'провал|не подтвержд|опровергн|отверг|не засчит|✗|неудач', re.I)


def chk_prereg_thresholds(d):
    """PROTOCOL.md §3.3 / SKILL «Перед любым экспериментом» 1: PREREG содержит предсказания с порогами и
    критерий провала. Без порога предсказание непроверяемо (CLAUDE.md, ворота 2, линза 3) — нарушение;
    без слов критерия провала — предупреждение (формулировки разнятся, не считается)."""
    bad = 0; eid = _exp_id(d)
    for pre in sorted(glob.glob(os.path.join(d, 'PREREG*.md'))):
        if '_TEMPLATE' in pre: continue
        txt = _read(pre)
        if not THRESH_RE.search(txt):
            print(f'  ✗ {eid}: {os.path.basename(pre)} без предсказаний с порогами (нет ≥/≤/</>/«порог»)'); bad += 1
        elif not FAIL_RE.search(txt):
            print(f'  ⚠ {eid}: {os.path.basename(pre)} без явного критерия провала')
    return bad


CODE_EXT = ('.py', '.js', '.mjs', '.sh')


def chk_code_after_run(d):
    """PROTOCOL.md §3.3: после регистрации PREREG не правится, отклонения — в DEVIATIONS.md; §3.4: код в той же папке.
    Код прогона (кроме pilot/dry/test), изменённый после первого прогона зарегистрированного опыта, — отклонение,
    которое должно быть записано в DEVIATIONS.md. Код, добавленный после прогона (упаковщики, анализ), —
    предупреждение. Пост-хок скрипты (в имени posthoc) — §3.6, отдельно."""
    eid = _exp_id(d); t_run = _t_run(d)
    if t_run is None or not glob.glob(os.path.join(d, 'PREREG*.md')) or glob.glob(os.path.join(d, 'DEVIATIONS*.md')): return 0
    changed = []; added = []
    for p in _files(d):
        if not p.endswith(CODE_EXT) or _aux(p, d) or re.search(r'post[-_]?hoc', os.path.basename(p), re.I): continue
        ta = _added(p)
        if ta is None: continue
        if ta > t_run:
            added.append(_rel(p)); continue
        later = [c for c in git('log', '--format=%h %ct', '--', _rel(p)).splitlines() if int(c.split()[1]) > t_run]
        if later: changed.append(f'{_rel(p)} ({", ".join(c.split()[0] for c in later[:3])})')
    if changed:
        print(f'  ✗ {eid}: код изменён после первого прогона, а DEVIATIONS.md нет: ' + '; '.join(changed[:4])); return 1
    if added:
        print(f'  ⚠ {eid}: код добавлен после первого прогона без DEVIATIONS.md: ' + ', '.join(os.path.relpath(p, os.path.dirname(d)) for p in added[:3]))
    return 0


CKPT_EXT = ('.pkl', '.pt', '.pth', '.ckpt', '.safetensors')


def chk_checkpoints_in_git():
    """CLAUDE.md п. 5 / PROTOCOL.md §6.3: чекпойнты моделей в git не класть."""
    big = [f for f in git('ls-files').splitlines() if f.lower().endswith(CKPT_EXT)]
    if big:
        print(f'  ✗ чекпойнты в git (CLAUDE.md п. 5): ' + ', '.join(big[:5])); return 1
    return 0


TRUTH_RE = re.compile(r'truth|secret|answers_full', re.I)


def chk_truth_near_heads(d):
    """CLAUDE.md «Постановки с головами Claude»: правду не класть туда, где её могут прочитать головы; правда
    вне репозитория (tools/audit_heads.py: пути к правде /root/*_secret). Папка с промптами голов — та, где лежат
    сценарии workflow (*_step.js, *runner*.js). Файл правды рядом с ними — нарушение; проверяльщик правды
    (verify_*/check_*) — не правда, а код второго способа."""
    eid = _exp_id(d)
    heads = [p for p in _files(d) if not _aux(p, d) and re.search(r'(_step\.js|runner[^/]*\.js)$', p)]
    if not heads: return 0
    truth = [p for p in _files(d) if not _aux(p, d) and TRUTH_RE.search(os.path.basename(p))
             and not re.match(r'(verify|check|audit)', os.path.basename(p), re.I)]
    if truth:
        print(f'  ✗ {eid}: файл правды рядом с промптами голов: ' + ', '.join(_rel(p) for p in truth[:4])); return 1
    return 0


def chk_errors_deleted():
    """CLAUDE.md п. 2 / PROTOCOL.md §4.2: записи journal/ERRORS.md не удаляются и не переписываются,
    исправление дописывается. Смотрим git log -p (и незакоммиченный diff): удалённая строка «N. …» без
    новой строки «N. …», начинающейся тем же текстом, — нарушение."""
    rel = 'journal/ERRORS.md'
    if not os.path.exists(os.path.join(ROOT, rel)): return 0
    out = git('log', '-p', '--format=commit %h', '--', rel) + '\ncommit (рабочая копия)\n' + git('diff', 'HEAD', '--', rel)
    bad = []
    for chunk in re.split(r'^commit ', out, flags=re.M)[1:]:
        h = chunk.split('\n', 1)[0].strip()
        gone = [l[1:] for l in chunk.splitlines() if re.match(r'^-\d+\.\s', l)]
        new = [l[1:] for l in chunk.splitlines() if re.match(r'^\+\d+\.\s', l)]
        for g in gone:
            n = g.split('.', 1)[0]; core = g.strip()[:60]
            if not any(a.split('.', 1)[0] == n and a.strip().startswith(core) for a in new):
                bad.append(f'{h}: «{g.strip()[:50]}»')
    if bad:
        print(f'  ✗ journal/ERRORS.md: удалены или переписаны записи: ' + '; '.join(bad[:3])); return 1
    return 0


def chk_results_after_report(d):
    """PROTOCOL.md §3.5–3.6: вердикт — по букве предрегистрации; всё после отчёта — пост-хок, отдельно, и порождает
    следующую предрегистрацию. Новые результаты или второй REPORT после первого без нового PREREG — нарушение.
    Пост-хок допустим, если файл (или файл из того же коммита) назван posthoc либо описан в .md папки
    (REPORT/POSTHOC/DEVIATIONS)."""
    eid = _exp_id(d); reps = [(_added(p), p) for p in glob.glob(os.path.join(d, 'REPORT*.md'))]
    reps = [(t, p) for t, p in reps if t]
    if not reps: return 0
    t_rep = min(reps)[0]
    if any((_added(p) or 0) > t_rep for p in glob.glob(os.path.join(d, 'PREREG*.md'))): return 0
    md = ' '.join(_read(p) for p in glob.glob(os.path.join(d, '*.md')))
    def documented(p):
        return bool(re.search(r'post[-_]?hoc', p, re.I)) or os.path.splitext(os.path.basename(p))[0] in md
    late = []; by_commit = {}
    for p in _files(d):
        ta = _added(p)
        if ta is None or ta <= t_rep: continue
        h = _added(p, with_hash=True)[1]
        by_commit.setdefault(h, []).append(p)
    for h, ps in by_commit.items():
        ok = any(documented(p) for p in ps)
        for p in ps:
            if not _is_run(p, d): continue
            if os.path.basename(p).startswith('REPORT'): late.append(_rel(p) + ' (второй отчёт)')
            elif not ok: late.append(_rel(p))
    if late:
        print(f'  ✗ {eid}: после отчёта новые результаты без новой предрегистрации: ' + ', '.join(late[:4])); return 1
    return 0


PRED_ID = re.compile(r'\bP[A-Z]?\d+\b')
YES_RE = re.compile(r'✓|подтвержд'); NO_RE = re.compile(r'✗|опровергн')


def chk_status_vs_support(cl):
    """CLAUDE.md «Работа с собой»: выводы меняются только через реестр, с опорой; PROTOCOL.md §3.5: вердикты по букве.
    Если опора — REPORT и в нём по букве для того же предсказания только противоположный вердикт — нарушение.
    Проверяется лишь однозначный случай: в тексте утверждения то же слово статуса и ID предсказания."""
    bad = 0
    for c in cl.values():
        st = c['status']
        if st not in ('подтверждено', 'опровергнуто'): continue
        sup = str(c.get('support') or '').split()[0] if c.get('support') else ''
        if not re.search(r'REPORT[^/]*\.md$', sup) or not os.path.exists(os.path.join(ROOT, sup)): continue
        text = c['text']
        if not re.search(st[:9], text, re.I) or re.search(r'не подтвержд|разницы нет|неверн', text, re.I): continue
        rep = _read(os.path.join(ROOT, sup)).splitlines()
        for pid in dict.fromkeys(PRED_ID.findall(text)):
            lines = [l for l in rep if re.search(rf'\b{pid}\b', l)]
            yes = any(YES_RE.search(l) for l in lines); no = any(NO_RE.search(l) for l in lines)
            if lines and yes != no and (no if st == 'подтверждено' else yes):
                print(f"  ✗ {c['id']}: статус «{st}», а в опоре {sup} для {pid} по букве — противоположный вердикт"); bad += 1; break
    return bad


def _remote_heads():
    """Головы origin: по сети (git ls-remote, 15 с), иначе локальные origin/*."""
    try:
        r = subprocess.run(['git', '-C', ROOT, 'ls-remote', '--heads', 'origin'], capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return [l.split()[0] for l in r.stdout.splitlines() if l.strip()], True
    except subprocess.TimeoutExpired:
        pass
    return [l.strip() for l in git('branch', '-r', '--format=%(objectname)').splitlines() if l.strip()], False


def chk_prereg_pushed(d, heads, live):
    """CLAUDE.md п. 3 / PROTOCOL.md §3.3 / SKILL 2: PREREG коммитится и пушится до первого прогона. Время пуша не
    записано, проверяем достижимое: если origin есть и коммит PREREG в нём отсутствует — нарушение. Если голова
    origin неизвестна локально (не fetch-нута) или origin старее коммита — проверить нельзя, молчим."""
    bad = 0; eid = _exp_id(d)
    if not heads: return 0
    known = [h for h in heads if _is_commit(h)]
    for pre in sorted(glob.glob(os.path.join(d, 'PREREG*.md'))):
        if '_TEMPLATE' in pre: continue
        first = git('log', '--diff-filter=A', '--format=%H', '--', _rel(pre)).splitlines()
        if not first: continue
        h = first[-1]
        if any(_ancestor(h, k) for k in known): continue
        if not known or (not live and all(_ancestor(k, h) for k in known)): continue   # origin известен хуже, чем HEAD
        print(f'  ✗ {eid}: коммит предрегистрации {h[:7]} ({os.path.basename(pre)}) не запушен в origin'); bad += 1
    return bad


def chk_set_without_why(events):
    """CLAUDE.md «Работа с собой» / PROTOCOL.md §4.3: смена статуса — с опорой и причиной (set … --why)."""
    bad = [f"{e['id']}→{e['status']} ({e.get('ts', '')})" for e in events if e.get('op') == 'set' and not str(e.get('why') or '').strip()]
    if bad:
        print('  ✗ смена статуса без причины (why): ' + ', '.join(bad[:5])); return 1
    return 0


def protocol_checks(cl, events=None):
    bad = 0
    prio = ''
    for pp in (os.path.join(ROOT, 'docs', 'PRIORITY.md'), os.path.join(ROOT, 'archive', 'neu_archive_2026-09-16', 'docs', 'PRIORITY.md')):
        if os.path.exists(pp): prio += open(pp, encoding='utf-8').read()
    council = ' '.join(os.listdir(os.path.join(ROOT, 'docs', 'council'))) if os.path.isdir(os.path.join(ROOT, 'docs', 'council')) else ''
    claims_text = ' '.join(c['text'] + ' ' + str(c['support']) for c in cl.values())
    # V4: опора должна существовать (если это путь)
    for c in cl.values():
        sup = str(c.get('support') or '')
        if sup and re.match(r'^(experiments|docs|journal|archive|tools)/\S+\.(md|json|txt|py)$', sup.split()[0]) and not os.path.exists(os.path.join(ROOT, sup.split()[0])):
            print(f"  ✗ {c['id']}: опора не найдена: {sup}"); bad += 1
    heads, live = _remote_heads()
    for d in _exp_dirs():
        eid = _exp_id(d); pre = glob.glob(os.path.join(d, 'PREREG*.md')); rep = glob.glob(os.path.join(d, 'REPORT*.md'))
        has_run = bool(rep) or any(os.path.basename(x).startswith(('raw_', 'out_', 'res', 'results')) for x in glob.glob(os.path.join(d, 'run', '*')))
        if has_run and not pre:  # V6
            print(f'  ✗ {eid}: прогон или отчёт без предрегистрации'); bad += 1
        if pre:
            ptxt = ' '.join(open(x, encoding='utf-8').read() for x in pre)
            lit = glob.glob(os.path.join(d, 'LITERATURE*.md')) or re.search(r'кто раньше|занято|не найдено', ptxt)
            if eid not in prio and not lit:  # V5
                print(f'  ✗ {eid}: нет строки «кто раньше» (docs/PRIORITY.md или LITERATURE.md)'); bad += 1
            if re.search(r'совет|заседани', ptxt, re.I) and eid not in council:  # V8
                print(f'  ✗ {eid}: PREREG ссылается на совет, стенограммы в docs/council/ нет'); bad += 1
        if rep and eid not in claims_text:  # V7
            print(f'  ✗ {eid}: есть отчёт, но в реестре нет утверждения с этим ID'); bad += 1
        bad += chk_report_hash(d) + chk_report_numbers(d) + chk_prereg_thresholds(d) + chk_code_after_run(d)
        bad += chk_truth_near_heads(d) + chk_results_after_report(d) + chk_prereg_pushed(d, heads, live)
    bad += chk_checkpoints_in_git() + chk_errors_deleted() + chk_status_vs_support(cl) + chk_set_without_why(events or [])
    return bad


# ---------- сводка ----------
def cmd_brief(_=None):
    cl = state(load())
    by = {s: [c for c in cl.values() if c['status'] == s] for s in STATUSES}
    print('Состояние исследования (tools/ledger.py brief):')
    print('  утверждений: ' + ', '.join(f'{s} {len(v)}' for s, v in by.items() if v) if cl else '  реестр пуст')
    for c in by['по памяти'][:5]:
        print(f"  по памяти: {c['id']} {c['text'][:90]}")
    studies = sorted(glob.glob(os.path.join(ROOT, 'studies', '2*')) + glob.glob(os.path.join(ROOT, 'experiments', '2*')))
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
    bad += protocol_checks(cl, load())
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
