#!/usr/bin/env python3
"""Оркестратор автотестов Magnetics (design/FINAL_SPEC.md §11) на headless-сервере Factorio 2.0.77.

Что делает (параллельно, подпроцессами):
  * для каждой конфигурации base / bq / be / sa:
      - `--create` только с модом (S1: загрузка без ошибок);
      - `--dump-data` с модом и без него (полный data.raw движка: S2, S3, S7, S10, S12, S13, S4-dump);
      - прогон ячеек стенда (magnetics-tests, модули cells/_all.lua + static) через tools/run.py;
  * один раз: `--dump-prototype-locale` в en/ru/de (S11, как игра видит имена), разбор locale-файлов (S11),
    поиск SA-имён вне охраны `mods["space-age"]` в Lua мода (S8-grep).
Ожидания Python-части берутся из design/FINAL_SPEC.md (таблицы §2.1, §2.3, §3, §4, §5.1, §7, §9 разбираются
прямо из текста спецификации — независимый путь к правде, не через spec.py) и из прочтённых в игре чисел,
которые ячейка cells/static.lua выгружает в magnetics-static-export.json.

Выход: tools/test_results.json (все записи) и tools/test_results.md (по конфигурациям: сколько прошло/не прошло
по каждому тесту, провалы с got/expected).

Запуск:  python3 tools/tests.py [--configs base,sa] [--jobs 4] [--ticks N] [--cells static,smoke] [--keep]
                                [--skip-cells] [--skip-dumps] [--work DIR]
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run            # noqa: E402  (BIN, FACTORIO, MOD_SRC, TESTS_SRC, mod_version, run)
import check_props    # noqa: E402

CONFIGS = ('base', 'bq', 'be', 'sa')
DLC = {'base': (), 'bq': ('quality',), 'be': ('elevated-rails',), 'sa': ('elevated-rails', 'quality', 'space-age')}
QUALITY_CFGS = ('bq', 'sa')
SPEC_MD = os.path.join(ROOT, 'design', 'FINAL_SPEC.md')
PROTO_API = '/opt/factorio-api/prototype-api.json'
LOCALES = ('en', 'ru', 'de')
P = 'magnetics-'
ERR_RE = re.compile(r'\bError\b|non-recoverable|stack traceback|Failed to load')
WARN_RE = re.compile(r'\bWarning\b')


# ------------------------------------------------------------------------------------------------ результаты
class Results:
    def __init__(self):
        self.records = []

    def add(self, cfg, test, name, ok, got=None, exp=None, note=None, source='python'):
        self.records.append(dict(config=cfg, test=test, name=name, pass_=bool(ok), got=_short(got), expected=_short(exp),
                                 note=note, source=source))
        return ok

    def eq(self, cfg, test, name, got, exp, tol=None, note=None):
        if tol is not None and isinstance(got, (int, float)) and isinstance(exp, (int, float)) and not isinstance(got, bool):
            ok = abs(got - exp) <= tol
        else:
            ok = got == exp
        return self.add(cfg, test, name, ok, got, exp, note)


def _short(v, limit=4000):
    if v is None or isinstance(v, (bool, int, float)):
        return v
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
    return s if len(s) <= limit else s[:limit] + '…'


# ------------------------------------------------------------------------------------------------ запуск сервера
def prepare_mods(work, cfg, with_mod, locale=None):
    """Папка модов и config.ini: только базовая игра + DLC конфигурации (+ magnetics). Тестовый мод не ставится."""
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    mods = os.path.join(work, 'mods')
    os.makedirs(mods)
    lst = [{'name': 'base', 'enabled': True}] + [{'name': n, 'enabled': n in DLC[cfg]} for n in ('elevated-rails', 'quality', 'space-age')]
    if with_mod:
        shutil.copytree(run.MOD_SRC, os.path.join(mods, f'magnetics_{run.mod_version(run.MOD_SRC)}'))
        lst.append({'name': 'magnetics', 'enabled': True})
    json.dump({'mods': lst}, open(os.path.join(mods, 'mod-list.json'), 'w'))
    wd = os.path.join(work, 'wd')
    cfg_ini = f'[path]\nread-data={run.FACTORIO}/data\nwrite-data={wd}\n'
    if locale:
        cfg_ini += f'[general]\nlocale={locale}\n'
    open(os.path.join(work, 'config.ini'), 'w').write(cfg_ini)
    return mods, wd


def factorio(work, cfg, with_mod, args, locale=None, timeout=1200):
    mods, wd = prepare_mods(work, cfg, with_mod, locale)
    t = time.time()
    try:
        r = subprocess.run([run.BIN, '-c', os.path.join(work, 'config.ini'), '--mod-directory', mods] + args,
                           capture_output=True, text=True, timeout=timeout)
        rc, out = r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        rc, out = 'timeout', str(e)
    logp = os.path.join(wd, 'factorio-current.log')
    log = open(logp, encoding='utf-8', errors='replace').read() if os.path.exists(logp) else ''
    return dict(rc=rc, out=out, log=log, wd=wd, work=work, seconds=round(time.time() - t, 1))


def job_create(base_work, cfg):
    w = os.path.join(base_work, cfg, 'create')
    save = os.path.join(w, 'save.zip')
    r = factorio(w, cfg, True, ['--create', save])
    r['save_exists'] = os.path.exists(save)
    return r


def job_dump(base_work, cfg, with_mod):
    w = os.path.join(base_work, cfg, 'dump_with' if with_mod else 'dump_without')
    r = factorio(w, cfg, with_mod, ['--dump-data'])
    p = os.path.join(r['wd'], 'script-output', 'data-raw-dump.json')
    r['dump'] = p if os.path.exists(p) else None
    return r


def job_locale(base_work, lang):
    w = os.path.join(base_work, 'locale', lang)
    r = factorio(w, 'base', True, ['--dump-prototype-locale'], locale=lang)
    r['dir'] = os.path.join(r['wd'], 'script-output')
    return r


def bump_tests_version(mods):
    """Поднять версию тестового мода в папке mods (между --create и --benchmark): у модов вызывается
    on_configuration_changed — так проверяется перестройка списка катушек (R9, PILOT-19)."""
    for d in os.listdir(mods):
        if d.startswith('magnetics-tests_'):
            info = os.path.join(mods, d, 'info.json')
            j = json.load(open(info, encoding='utf-8'))
            a, b, c = (int(x) for x in j['version'].split('.'))
            j['version'] = f'{a}.{b}.{c + 1}'
            json.dump(j, open(info, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            os.rename(os.path.join(mods, d), os.path.join(mods, 'magnetics-tests_' + j['version']))
            return j['version']


def job_cells(base_work, cfg, max_ticks, modules, wall=3600, sub='cells', bump=False):
    """Прогон ячеек стенда: --create, затем --benchmark с потолком max_ticks; как только стенд записал
    magnetics-done.txt (после magnetics-results.json), сервер останавливается — число тиков знать заранее не нужно.
    sub — своя рабочая папка (отдельные прогоны: катушка в изоляции, повтор, смена версии); bump — поднять версию
    тестового мода после --create."""
    w = os.path.join(base_work, cfg, sub)
    t = time.time()
    mods, wd = run.prepare(cfg, w, True, (), modules)
    base = [run.BIN, '-c', os.path.join(w, 'config.ini'), '--mod-directory', mods]
    save = os.path.join(w, 'test.zip')
    logp = os.path.join(wd, 'factorio-current.log')
    r1 = subprocess.run(base + ['--create', save, '--map-gen-seed', '20260930'], capture_output=True, text=True, timeout=900)
    log1 = open(logp, encoding='utf-8', errors='replace').read() if os.path.exists(logp) else ''
    res = dict(cfg=cfg, work=w, create_ok=r1.returncode == 0 and os.path.exists(save), bench_ok=None, finished=False)
    if bump and res['create_ok']:
        res['bumped_to'] = bump_tests_version(mods)
    log2 = ''
    if res['create_ok']:
        done = os.path.join(wd, 'script-output', 'magnetics-done.txt')
        with open(os.path.join(w, 'bench-stdout.txt'), 'w') as so:
            p = subprocess.Popen(base + ['--benchmark', save, '--benchmark-ticks', str(max_ticks)], stdout=so, stderr=subprocess.STDOUT)
            t0 = time.time()
            while p.poll() is None:
                if os.path.exists(done):
                    time.sleep(0.5)
                    p.terminate()
                    try:
                        p.wait(15)
                    except subprocess.TimeoutExpired:
                        p.kill()
                    break
                if time.time() - t0 > wall:
                    p.kill()
                    res['timeout'] = True
                    break
                time.sleep(0.1)
            p.wait()
        res['finished'] = os.path.exists(done)
        res['done'] = open(done).read() if res['finished'] else None
        res['bench_ok'] = res['finished']
        log2 = open(logp, encoding='utf-8', errors='replace').read() if os.path.exists(logp) else ''
    out = {}
    so = os.path.join(wd, 'script-output')
    if os.path.isdir(so):
        for f in os.listdir(so):
            fp = os.path.join(so, f)
            if os.path.isfile(fp):
                txt = open(fp, encoding='utf-8', errors='replace').read()
                try:
                    out[f] = json.loads(txt)
                except Exception:  # noqa: BLE001
                    out[f] = txt
    res['output'] = out
    res['errors'] = [l for l in (log1 + log2).splitlines() if ERR_RE.search(l)]
    res['warnings'] = [l for l in (log1 + log2).splitlines() if WARN_RE.search(l)]
    res['seconds'] = round(time.time() - t, 1)
    return res


# ------------------------------------------------------------------------------------------------ модули ячеек
def cell_modules(extra=('static',)):
    txt = open(os.path.join(run.TESTS_SRC, 'cells', '_all.lua'), encoding='utf-8').read()
    txt = re.sub(r'--[^\n]*', '', txt)
    mods = re.findall(r'"([^"]+)"', txt)
    for x in extra:
        if x not in mods:
            mods.append(x)
    return mods


def test_id(rec):
    """Номер теста для записи ячейки: группа, если это номер (S4, G3, T-W, PILOT-…); иначе номер в начале имени
    (R11 …, PILOT-24 …, G3:setup); иначе группа (имя модуля)."""
    g, n = str(rec.get('group') or ''), str(rec.get('name') or '')
    if re.fullmatch(r'[A-Z]{1,2}\d+[a-z]?|[A-Z]-[A-Z]|PILOT-[\w-]+', g):
        return g
    m = re.match(r'(PILOT-\d+|[A-Z]{1,2}\d+[a-z]?)(?=[\s:]|$)', n)
    if m:
        return m.group(1)
    return g or '?'


# ------------------------------------------------------------------------------------------------ FINAL_SPEC.md
def md_section(text, title_re):
    """Текст раздела от заголовка, совпавшего с title_re, до следующего заголовка того же или более высокого уровня."""
    lines = text.splitlines()
    for i, l in enumerate(lines):
        m = re.match(r'(#+)\s+(.*)', l)
        if m and re.search(title_re, m.group(2)):
            lvl = len(m.group(1))
            out = []
            for l2 in lines[i + 1:]:
                m2 = re.match(r'(#+)\s', l2)
                if m2 and len(m2.group(1)) <= lvl:
                    break
                out.append(l2)
            return '\n'.join(out)
    raise KeyError(title_re)


def md_tables(section):
    tables, cur = [], None
    for l in section.splitlines():
        if l.startswith('|'):
            cells = [c.strip() for c in l.strip().strip('|').split('|')]
            if all(re.fullmatch(r':?-{3,}:?', c) for c in cells if c):
                continue
            if cur is None:
                cur = []
                tables.append(cur)
            cur.append(cells)
        else:
            cur = None
    return tables


def clean(s):
    return re.sub(r'\*\*|`', '', s).strip()


def first_num(s):
    m = re.search(r'-?\d+(?:\.\d+)?', s)
    return float(m.group(0)) if m else None


class Doc:
    """Числа FINAL_SPEC, разобранные из markdown (без spec.py)."""
    PACKS = {'A': 'automation-science-pack', 'L': 'logistic-science-pack', 'M': 'military-science-pack',
             'C': 'chemical-science-pack', 'P': 'production-science-pack', 'U': 'utility-science-pack',
             'S': 'space-science-pack', 'Met': 'metallurgic-science-pack', 'EM': 'electromagnetic-science-pack'}
    MAG_CATS = ('sintering', 'induction', 'winding', 'cryogenics', 'resonance', 'separation')

    def __init__(self, path=SPEC_MD):
        self.text = open(path, encoding='utf-8').read()
        self._recipes = self._parse_recipes()
        self.techs = self._parse_techs()
        self.stacks = self._parse_stacks()
        self.tints = self._parse_tints()
        self.locale = self._parse_locale()

    # имя из таблицы: ванильное, если есть в ванили; иначе magnetics-<имя>; TOP- — по конфигурации
    @staticmethod
    def resolve(name, vanilla_names, sa):
        name = name.strip()
        if name.startswith('TOP-'):
            return ('turbo-' if sa else 'express-') + name[4:]
        if name.startswith(P) or name in vanilla_names:
            return name
        return P + name

    @staticmethod
    def amounts(cell):
        cell = re.sub(r'\([^)]*\)', '', clean(cell))          # пояснения в скобках
        if cell.startswith('—') or not cell.strip():
            return []
        out = []
        for part in re.split(r'[,;]', cell):
            part = part.strip()
            if not part:
                continue
            m = re.match(r'([A-Za-z0-9-]+)\s+(\d+(?:\.\d+)?)(.*)', part)
            if not m:
                raise ValueError(f'не разобрано: {part!r}')
            prob = re.search(r'probability\s*=\s*([\d.]+)', m.group(3))
            out.append((m.group(1), float(m.group(2)), float(prob.group(1)) if prob else 1.0))
        return out

    def _parse_recipes(self):
        sec3 = md_section(self.text, r'^3\. Recipes')
        out = {}
        # §3.1
        t31 = md_tables(md_section(sec3, r'^3\.1 '))[0]
        for row in t31[1:]:
            name = re.search(r'magnetics-[\w-]+', row[0]).group(0)
            cat = clean(row[1])
            out[name] = dict(category=(P + cat) if cat in self.MAG_CATS else cat, ing=self.amounts(row[2]),
                             res=self.amounts(row[3].replace('with', ' with')), energy=first_num(row[4]),
                             prod=clean(row[5]).startswith('yes'), ar=clean(row[6]).startswith('true'),
                             allow_quality='allow_quality = false' not in row[7])
        # §3.2 боеприпасы: crafting, Prod no
        t32 = md_tables(md_section(sec3, r'^3\.2 '))[0]
        for row in t32[1:]:
            name = clean(row[0])
            res = self.amounts(row[2])
            out[name] = dict(category='crafting', ing=self.amounts(row[1]), res=res, energy=first_num(row[3]), prod=False,
                             ar=clean(row[4]).startswith('true'), allow_quality=True)
        # §3.3 постройки: crafting, если не указано; Prod no; AR true; результат 1 (или → 2)
        t33 = md_tables(md_section(sec3, r'^3\.3 '))[0]
        for row in t33[1:]:
            c0 = row[0]
            name = re.search(r'magnetics-[\w-]+', c0).group(0)
            catm = re.search(r'`(crafting-with-fluid)`', c0)
            cnt = re.search(r'→\s*\*\*(\d+)\*\*', c0)
            out[name] = dict(category=catm.group(1) if catm else 'crafting', ing=self.amounts(row[1]),
                             res=[(name, float(cnt.group(1)) if cnt else 1.0, 1.0)], energy=first_num(row[2]), prod=False,
                             ar=True, allow_quality=True)
        return out

    def recipes(self, vanilla_names, fluids, sa):
        """Рецепты с разрешёнными именами для конфигурации: {name: {..., ing: ['item:name*amt'], res: [...]}}."""
        out = {}
        for n, d in self._recipes.items():
            def fmt(lst, prod):
                o = []
                for nm, amt, pr in lst:
                    full = self.resolve(nm, vanilla_names, sa)
                    typ = 'fluid' if full in fluids else 'item'
                    a = int(amt) if amt == int(amt) else amt
                    o.append(f'{typ}:{full}*{a}' + (f'@{pr:g}' if prod else ''))
                return sorted(o)
            out[n] = dict(d, ing=fmt(d['ing'], False), res=fmt(d['res'], True))
        return out

    def _parse_techs(self):
        sec = md_section(self.text, r'^5\.1 Tree')
        t = md_tables(sec)[0]
        tnum = {clean(r[0]): clean(r[1]) for r in t[1:]}
        out = {}
        for r in t[1:]:
            name = clean(r[1])

            def split_base_sa(cell):
                c = clean(cell)
                if 'base:' in c:
                    m = re.match(r'base:\s*(.*?)\.\s*SA:\s*(.*)', c)
                    return m.group(1).strip(), m.group(2).strip()
                return c, None
            pre_b, pre_s = split_base_sa(r[2])
            cnt_b, cnt_s = split_base_sa(r[3])
            pk_b, pk_s = split_base_sa(r[4])

            def pre(s):
                return [tnum[x.strip()] if re.fullmatch(r'T\d+', x.strip()) else x.strip() for x in s.split(',') if x.strip()]

            def ct(s):
                m = re.match(r'(\d+)\s*×\s*(\d+)\s*s', s)
                return int(m.group(1)), int(m.group(2))
            d = dict(pre=pre(pre_b), count=ct(cnt_b)[0], time=ct(cnt_b)[1], packs=[self.PACKS[x] for x in pk_b.split()],
                     unlocks=[P + x.strip() for x in clean(r[5]).split(',')])
            if pre_s:
                d['sa'] = dict(pre=d['pre'] + pre(pre_s.lstrip('+ ').strip()), count=ct(cnt_s)[0], time=ct(cnt_s)[1],
                               packs=[self.PACKS[x] for x in pk_s.split()])
            out[name] = d
        return out

    def _parse_stacks(self):
        sec = md_section(self.text, r'^2\. Items and fluids')
        out = {}
        for row in md_tables(md_section(sec, r'^2\.1 '))[0][1:]:
            out[clean(row[0])] = int(first_num(row[2]))
        for row in md_tables(md_section(sec, r'^2\.3 '))[0][1:]:
            out[clean(row[0])] = int(first_num(row[1]))
        return out

    def _parse_tints(self):
        """Оттенки построек из таблиц §4.2–§4.6 (последний столбец «tint»; «same» — как у ленты)."""
        sec = md_section(self.text, r'^4\. Entities')
        out = {}
        last = None
        for t in md_tables(sec):
            hdr = [clean(c).lower() for c in t[0]]
            idx = [i for i, h in enumerate(hdr) if h.startswith('tint')]
            if not idx:
                continue
            i = idx[0]
            for row in t[1:]:
                m = re.search(r'magnetics-[\w-]+', row[0])
                if not m:
                    continue
                cell = clean(row[i])
                nums = re.findall(r'\d\.\d+', cell)
                if len(nums) == 3:
                    last = [float(x) for x in nums]
                    out[m.group(0)] = last
                elif cell.startswith('same') and last:
                    out[m.group(0)] = last
        # ремонтная катушка: оттенок только в тексте §4.5 — `picture = accumulator_picture({r, g, b, 1})`
        m = re.search(r'magnetics-mend-coil.*?accumulator_picture\(\{([\d.]+),\s*([\d.]+),\s*([\d.]+)', sec, re.S)
        if m:
            out['magnetics-mend-coil'] = [float(x) for x in m.groups()]
        return out

    def _parse_locale(self):
        sec = md_section(self.text, r'^9\. Locale')
        out = {}      # (section, key) -> {lang: text}
        for sub, kind in ((r'^9\.1 ', None), (r'^9\.2 ', 'entity'), (r'^9\.3 ', None), (r'^9\.4 ', 'technology')):
            t = md_tables(md_section(sec, sub))[0]
            for row in t[1:]:
                key = clean(row[0])
                if kind:
                    k_kind, k_name = kind, key
                else:
                    k_kind, k_name = key.split(None, 1)
                vals = [clean(x) for x in row[1:]]
                out[(k_kind + '-name', k_name)] = dict(en=vals[0], ru=vals[1], de=vals[2])
                if len(vals) >= 5:
                    out[(k_kind + '-description', k_name)] = dict(en=vals[3], ru=vals[4])
        return out


# ------------------------------------------------------------------------------------------------ data.raw
class Api:
    def __init__(self, path=PROTO_API):
        p = json.load(open(path))
        self.by_name = {x['name']: x for x in p['prototypes']}
        self.typename = {x['typename']: x['name'] for x in p['prototypes'] if x.get('typename')}

    def is_kind(self, typename, base):
        n = self.typename.get(typename)
        while n:
            if n == base:
                return True
            n = self.by_name[n].get('parent')
        return False


def walk(v, path=()):
    """Все (путь, словарь) в дереве."""
    if isinstance(v, dict):
        yield path, v
        for k, x in v.items():
            yield from walk(x, path + (k,))
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from walk(x, path + (i,))


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)


def diff(a, b, path, out, limit=200):
    if len(out) >= limit:
        return
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        out.append((path, a, b))
        return
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                out.append((f'{path}.{k}', '<нет>', b[k]))
            elif k not in b:
                out.append((f'{path}.{k}', a[k], '<нет>'))
            else:
                diff(a[k], b[k], f'{path}.{k}', out, limit)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append((path, f'len {len(a)}', f'len {len(b)}'))
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f'{path}[{i}]', out, limit)
    elif a != b:
        out.append((path, a, b))


def color_tuple(c):
    if isinstance(c, dict):
        return (c.get('r', c.get('1', 0)), c.get('g', c.get('2', 0)), c.get('b', c.get('3', 0)), c.get('a', c.get('4', 1)))
    if isinstance(c, list):
        return tuple(list(c) + [1] * (4 - len(c)))[:4]
    return None


# ------------------------------------------------------------------------------------------------ S1
def t_s1(R, cfg, cr):
    R.add(cfg, 'S1', 'create exit code 0', cr['rc'] == 0, cr['rc'], 0)
    R.add(cfg, 'S1', 'save written', cr.get('save_exists'), cr.get('save_exists'), True)
    errs = [l for l in cr['log'].splitlines() if ERR_RE.search(l)]
    R.add(cfg, 'S1', 'log: 0 Error/non-recoverable/stack traceback lines', not errs, errs[:20], [])
    warns = [l for l in cr['log'].splitlines() if WARN_RE.search(l) and 'magnetics' in l.lower()]
    R.add(cfg, 'S1', 'log: 0 Warning lines naming magnetics', not warns, warns[:20], [])
    order = re.findall(r'Loading mod (\S+) \S+ \(data\.lua\)', cr['log'])
    if cfg == 'sa':
        ok = 'magnetics' in order and 'space-age' in order and order.index('magnetics') > order.index('space-age')
        R.add(cfg, 'PILOT-1', 'magnetics data.lua runs after space-age data.lua (log order)', ok, order, 'space-age before magnetics')


# ------------------------------------------------------------------------------------------------ S2
EXPECTED_COUNTS = {'entity(buildings)': 26, 'item': 37, 'fluid': 2, 'recipe(non-recycling)': 40, 'technology': 14,
                   'ammo-category': 3, 'fuel-category': 1, 'recipe-category': 6, 'item-subgroup': 1, 'projectile': 3,
                   'beam': 2, 'chain-active-trigger': 1, 'explosion': 1}


def t_s2(R, cfg, W, WO, api):
    new = [(t, n) for t, lst in W.items() if isinstance(lst, dict) for n in lst if not (t in WO and n in WO[t])]
    removed = [(t, n) for t, lst in WO.items() if isinstance(lst, dict) for n in lst if not (t in W and n in W[t])]
    R.add(cfg, 'S2', 'no vanilla prototype removed', not removed, removed[:30], [])
    bad = [f'{t}/{n}' for t, n in new if not n.startswith(P)]
    R.add(cfg, 'S2', 'every new name starts with magnetics-', not bad, bad[:30], [])
    rec = [(t, n) for t, n in new if n.endswith('-recycling')]
    if cfg in QUALITY_CFGS:
        badr = [f'{t}/{n}' for t, n in rec if not (t == 'recipe' and W[t][n].get('category') == 'recycling')]
        R.add(cfg, 'S2', 'generated *-recycling are recycling recipes', not badr, badr, [])
    else:
        R.add(cfg, 'S2', 'no *-recycling without quality', not rec, rec[:10], [])
    barrel = [f'{t}/{n}' for t, n in new if n.startswith('empty-magnetics-') or ('magnetics' in n and 'barrel' in n)]
    R.add(cfg, 'S2', 'no barrel names', not barrel, barrel, [])
    vanilla_names = {n for lst in WO.values() if isinstance(lst, dict) for n in lst}
    clash = sorted({n for _, n in new if n in vanilla_names})
    R.add(cfg, 'S2', 'no new name shared with a vanilla name (any type)', not clash, clash, [])
    counts, other = {}, []
    for t, n in new:
        if api.is_kind(t, 'EntityPrototype') and t not in ('projectile', 'beam', 'explosion'):
            k = 'entity(buildings)'
        elif api.is_kind(t, 'ItemPrototype'):
            k = 'item'
        elif t == 'recipe':
            k = 'recipe(recycling)' if n.endswith('-recycling') and W[t][n].get('category') == 'recycling' else 'recipe(non-recycling)'
        elif t in EXPECTED_COUNTS:
            k = t
        else:
            k = t
            other.append(f'{t}/{n}')
        counts[k] = counts.get(k, 0) + 1
    for k, v in EXPECTED_COUNTS.items():
        R.eq(cfg, 'S2', f'count {k}', counts.get(k, 0), v)
    R.add(cfg, 'S2', 'no prototype of an unexpected type', not other, other, [])
    R.add(cfg, 'S2', 'recycling recipes count (информация; набор проверяет S9)', True, counts.get('recipe(recycling)', 0), None)


# ------------------------------------------------------------------------------------------------ S3
def t_s3(R, cfg, dump_path):
    n, hard, soft = check_props.check_mod(dump_path, P)
    R.add(cfg, 'S3', f'check_props: 0 unknown keys ({n} prototypes, {soft} tolerated vanilla patterns)', not hard,
          [f'{p}: {m}' for p, m in hard[:40]], [])


# ------------------------------------------------------------------------------------------------ S7
PPD = [f'physical-projectile-damage-{i}' for i in range(1, 8)]
WSS = [f'weapon-shooting-speed-{i}' for i in range(1, 7)]
MCATS = ['magnetics-slug', 'magnetics-gauss', 'magnetics-rail']
MTURRETS = ['magnetics-coilgun-turret', 'magnetics-gauss-turret', 'magnetics-rail-cannon']


def t_s7(R, cfg, W, WO):
    sa = cfg == 'sa'
    top = 'turbo' if sa else 'express'
    links = {('wall', 'stone-wall'): 'magnetics-ferrite-wall', ('gate', 'gate'): 'magnetics-magnet-gate',
             ('mining-drill', 'electric-mining-drill'): 'magnetics-magnetic-drill',
             ('accumulator', 'accumulator'): 'magnetics-superconducting-accumulator',
             ('electric-pole', 'big-electric-pole'): 'magnetics-superconducting-pylon',
             ('transport-belt', f'{top}-transport-belt'): 'magnetics-maglev-transport-belt',
             ('underground-belt', f'{top}-underground-belt'): 'magnetics-maglev-underground-belt',
             ('splitter', f'{top}-splitter'): 'magnetics-maglev-splitter'}
    inserts = {('assembling-machine', 'electromagnetic-plant'): ['magnetics-winding'],
               ('assembling-machine', 'cryogenic-plant'): ['magnetics-cryogenics'],
               ('assembling-machine', 'foundry'): ['magnetics-sintering', 'magnetics-induction']} if sa else {}
    unexpected, seen_links, seen_ins = [], set(), set()
    for t, lst in WO.items():
        if not isinstance(lst, dict) or t not in W:
            continue
        for n, a in lst.items():
            b = W[t].get(n)
            if b is None:
                continue
            d = []
            diff(a, b, f'{t}/{n}', d)
            if not d:
                continue
            for path, x, y in d:
                key = (t, n)
                if key in links and path == f'{t}/{n}.next_upgrade' and y == links[key]:
                    seen_links.add(key)
                    continue
                if key in inserts and path.startswith(f'{t}/{n}.crafting_categories'):
                    want = a.get('crafting_categories', []) + inserts[key]
                    if b.get('crafting_categories') == want:
                        seen_ins.add(key)
                        continue
                if t == 'technology' and (n in PPD or n in WSS) and path.startswith(f'{t}/{n}.effects'):
                    ea, eb = a.get('effects', []), b.get('effects', [])
                    app = eb[len(ea):]
                    ok = eb[:len(ea)] == ea and app and all(e.get('ammo_category') in MCATS or e.get('turret_id') in MTURRETS for e in app)
                    if ok:
                        continue
                unexpected.append(f'{path}: {json.dumps(x, default=str)[:80]} -> {json.dumps(y, default=str)[:80]}')
    unexpected = sorted(set(unexpected))
    R.add(cfg, 'S7', 'vanilla untouched except §7.2 whitelist', not unexpected, unexpected[:40], [])
    missing = sorted(f'{t}/{n} -> {v}' for (t, n), v in links.items() if (t, n) not in seen_links)
    R.add(cfg, 'S7', 'every §7.2 next_upgrade link present', not missing, missing, [])
    if sa:
        mi = sorted(f'{t}/{n}' for (t, n) in inserts if (t, n) not in seen_ins)
        R.add(cfg, 'S7', 'SA category inserts present (appended)', not mi, mi, [])
    changed_techs = sorted(n for n in PPD + WSS if W['technology'][n].get('effects') != WO['technology'][n].get('effects'))
    R.eq(cfg, 'S7', 'PPD-1..7 and WSS-1..6 got appended effects', changed_techs, sorted(PPD + WSS))


# ------------------------------------------------------------------------------------------------ S10 (выгрузка)
def t_s10(R, cfg, W):
    for f in ('magnetics-ferrofluid', 'magnetics-liquid-nitrogen'):
        R.eq(cfg, 'S10', f'{f} auto_barrel = false (data.raw)', (W.get('fluid', {}).get(f) or {}).get('auto_barrel'), False)


# ------------------------------------------------------------------------------------------------ S12
S12_VANILLA = [('furnace', 'stone-furnace'), ('furnace', 'electric-furnace'), ('assembling-machine', 'assembling-machine-2'),
               ('assembling-machine', 'assembling-machine-3'), ('assembling-machine', 'chemical-plant'),
               ('assembling-machine', 'centrifuge'), ('mining-drill', 'electric-mining-drill'),
               ('transport-belt', 'express-transport-belt'), ('underground-belt', 'express-underground-belt'),
               ('splitter', 'express-splitter'), ('accumulator', 'accumulator'), ('electric-pole', 'big-electric-pole'),
               ('burner-generator', 'burner-generator'), ('solar-panel', 'solar-panel'), ('wall', 'stone-wall'),
               ('gate', 'gate'), ('electric-energy-interface', 'electric-energy-interface'), ('ammo-turret', 'gun-turret'),
               ('electric-turret', 'laser-turret')]
SPECIAL_LEAF = ('draw_as_shadow', 'draw_as_glow', 'draw_as_light', 'apply_runtime_tint')
# §4.1 шаг 7: в эти ключи окраска не заходит; рабочие визуализации с apply_recipe_tint/apply_tint не красятся
SKIP_KEYS = ('circuit_connector', 'circuit_connector_flipped', 'water_reflection', 'frozen_patch', 'belt_reader',
             'connector_frame_sprites', 'icons', 'icon')


def walk_ctx(v, path=(), skipped=None):
    """(путь, словарь, причина пропуска или None): причина — ближайший предок из SKIP_KEYS или с apply_recipe_tint/apply_tint."""
    if isinstance(v, dict):
        why = skipped
        if why is None and (v.get('apply_recipe_tint') or v.get('apply_tint')):
            why = 'apply_recipe_tint/apply_tint'
        yield path, v, why
        for k, x in v.items():
            yield from walk_ctx(x, path + (k,), why or (k if k in SKIP_KEYS else None))
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from walk_ctx(x, path + (i,), skipped)


def tint_leaves(proto):
    """(путь, tint) для всех таблиц с ключом tint."""
    return sorted((('/'.join(map(str, p))), json.dumps(d.get('tint'), sort_keys=True)) for p, d in walk(proto) if 'tint' in d)


def t_s12(R, cfg, W, WO, doc, spec_json):
    for t, n in S12_VANILLA:
        a, b = (WO.get(t) or {}).get(n), (W.get(t) or {}).get(n)
        if a is None or b is None:
            R.add(cfg, 'S12', f'{t}/{n} present', False, [a is not None, b is not None], [True, True])
            continue
        la, lb = tint_leaves(a), tint_leaves(b)
        R.add(cfg, 'S12', f'vanilla {n}: tint leaves identical with/without the mod', la == lb,
              [x for x in lb if x not in la][:10], [x for x in la if x not in lb][:10])
    ents = spec_json['entities']
    for name, e in sorted(ents.items()):
        proto = (W.get(e['type']) or {}).get(name)
        if proto is None:
            R.add(cfg, 'S12', f'{name} present', False, None, True)
            continue
        tint = doc.tints.get(name)
        R.add(cfg, 'S12', f'{name}: §4 tint = spec.py tint', tint is not None and all(abs(x - y) < 1e-9 for x, y in zip(tint, e['tint'])),
              tint, e['tint'])
        if tint is None:
            continue
        want = tuple(tint) + (1,)
        ours, bad, bad_skip = 0, [], []
        for path, d, why in walk_ctx(proto):
            if not any(k in d for k in ('filename', 'filenames', 'stripes')) or 'tint' not in d:
                continue
            c = color_tuple(d['tint'])
            if c is None or any(abs(x - y) > 1e-6 for x, y in zip(c, want)):
                continue
            if any(d.get(k) for k in SPECIAL_LEAF):
                bad.append('/'.join(map(str, path)))
            elif why:
                bad_skip.append('/'.join(map(str, path)) + f' ({why})')
            else:
                ours += 1
        R.add(cfg, 'S12', f'{name}: >= 1 leaf with its tint', ours >= 1, ours, '>= 1')
        R.add(cfg, 'S12', f'{name}: 0 tinted shadow/glow/light/runtime-tint leaves', not bad, bad[:10], [])
        R.add(cfg, 'S12', f'{name}: 0 tinted leaves in skipped subtrees (§4.1 step 7)', not bad_skip, bad_skip[:10], [])
        icons = [d for p, d in walk(proto.get('icons') or []) if 'tint' in d]
        R.add(cfg, 'S12', f'{name}: icons untinted', not icons, len(icons), 0)


# ------------------------------------------------------------------------------------------------ S13
def png_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            return im.size, None
    except ImportError:
        b = open(path, 'rb').read(24)
        if b[:8] != b'\x89PNG\r\n\x1a\n':
            return None, 'не PNG'
        return (int.from_bytes(b[16:20], 'big'), int.from_bytes(b[20:24], 'big')), None
    except Exception as e:  # noqa: BLE001
        return None, f'не декодируется: {e}'


def expected_size(rel):
    if rel.startswith('graphics/icons/'):
        return (64, 64)
    if rel.startswith('graphics/technology/'):
        return (256, 256)
    if rel == 'graphics/entity/rail-tracer.png':
        return (512, 440)
    return None


def t_s13(R, cfg, W):
    refs = sorted({s for t, lst in W.items() if isinstance(lst, dict) for p in lst.values() for s in strings(p)
                   if s.startswith('__magnetics__/')})
    R.add(cfg, 'S13', 'referenced __magnetics__ paths (информация)', True, len(refs), None)
    missing, bad = [], []
    for s in refs:
        rel = s[len('__magnetics__/'):]
        fp = os.path.join(run.MOD_SRC, rel)
        if not os.path.exists(fp):
            missing.append(rel)
            continue
        size, err = png_size(fp)
        want = expected_size(rel)
        if err:
            bad.append(f'{rel}: {err}')
        elif want and tuple(size) != want:
            bad.append(f'{rel}: {size[0]}x{size[1]} (надо {want[0]}x{want[1]})')
    R.add(cfg, 'S13', f'every referenced PNG exists ({len(refs)})', not missing, missing[:50] + ([f'… всего {len(missing)}'] if len(missing) > 50 else []), [])
    R.add(cfg, 'S13', 'every existing PNG decodes and has the right size', not bad, bad[:50], [])
    th = os.path.join(run.MOD_SRC, 'thumbnail.png')
    if os.path.exists(th):
        size, err = png_size(th)
        R.add(cfg, 'S13', 'thumbnail.png 144x144', not err and tuple(size) == (144, 144), err or size, (144, 144))
    else:
        R.add(cfg, 'S13', 'thumbnail.png 144x144', False, 'нет файла', (144, 144))


# ------------------------------------------------------------------------------------------------ S4-dump
def dig(d, *path):
    for k in path:
        if isinstance(d, dict):
            d = d.get(k)
        elif isinstance(d, list) and isinstance(k, int) and k < len(d):
            d = d[k]
        else:
            return None
    return d


def t_s4_dump(R, cfg, W, WO, doc, spec_json):
    """Поля, которых нет в API времени игры: ожидания набраны из FINAL_SPEC §2–§4 (номер раздела в имени)."""
    E = lambda t, n: (W.get(t) or {}).get(n) or {}  # noqa: E731
    chk = lambda name, got, exp, tol=None: R.eq(cfg, 'S4', 'dump ' + name, got, exp, tol)  # noqa: E731
    # §4.6 турели: скорость поворота, энергия выстрела
    for n, rot, eps in (('magnetics-coilgun-turret', 0.015, '40kJ'), ('magnetics-gauss-turret', 0.008, '250kJ'),
                        ('magnetics-rail-cannon', 0.005, '4MJ')):
        chk(f'§4.6 {n} rotation_speed', E('ammo-turret', n).get('rotation_speed'), rot)
        chk(f'§4.6 {n} energy_per_shot', E('ammo-turret', n).get('energy_per_shot'), eps)
    # §4.4 накопители: tertiary в данных
    for n in ('magnetics-coil-capacitor', 'magnetics-superconducting-accumulator'):
        chk(f'§4.4 {n} usage_priority (data)', dig(E('accumulator', n), 'energy_source', 'usage_priority'), 'tertiary')
    # §4.5 ремонтная катушка
    mc = E('electric-energy-interface', 'magnetics-mend-coil')
    chk('§4.5 mend-coil gui_mode', mc.get('gui_mode'), 'none')
    chk('§4.5 mend-coil allow_copy_paste', mc.get('allow_copy_paste'), False)
    chk('§4.5 mend-coil energy_production', mc.get('energy_production'), '0W')
    chk('§4.5 mend-coil energy_usage', mc.get('energy_usage'), '0W')
    chk('§4.5 mend-coil output_flow_limit', dig(mc, 'energy_source', 'output_flow_limit'), '0W')
    chk('§4.5 mend-coil hidden', mc.get('hidden', False) in (False, None), True)
    # §4.5 стены: repair_speed_modifier 2, visual_merge_group 0, группа wall
    for n in ('magnetics-ferrite-wall', 'magnetics-magnet-wall', 'magnetics-superconducting-wall'):
        chk(f'§4.5 {n} repair_speed_modifier', E('wall', n).get('repair_speed_modifier'), 2)
        chk(f'§4.5 {n} visual_merge_group', E('wall', n).get('visual_merge_group', 0), 0)
    # §4.7 снаряды болванок
    for n, pierce, dmg, tint in (('magnetics-ferrite-slug-projectile', 30, 20, '6E5A62'), ('magnetics-magnet-slug-projectile', 150, 32, '6D86C9'),
                                 ('magnetics-gauss-slug-projectile', 400, 90, '9FB4FF')):
        p = E('projectile', n)
        chk(f'§4.7 {n} piercing_damage', p.get('piercing_damage'), pierce)
        chk(f'§4.7 {n} direction_only', p.get('direction_only'), True)
        chk(f'§4.7 {n} force_condition', p.get('force_condition'), 'not-same')
        chk(f'§4.7 {n} final_action nil', p.get('final_action'), None)
        te = dig(p, 'action', 'action_delivery', 'target_effects') or []
        dm = [x.get('damage') for x in te if isinstance(x, dict) and x.get('type') == 'damage']
        chk(f'§4.7 {n} damage', dm, [{'amount': dmg, 'type': 'physical'}])
        want = [int(tint[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        got = color_tuple(dig(p, 'animation', 'tint'))
        R.add(cfg, 'S4', f'dump §4.7 {n} animation tint #{tint}', got is not None and all(abs(a - b) < 1e-6 for a, b in zip(got, want)), got, want)
    # §4.7 цепь разрядника: мгновенно 30 electric + стикер, косметический луч
    ch = E('chain-active-trigger', 'magnetics-arc-chain')
    dl = dig(ch, 'action', 'action_delivery') or []
    inst = [x for x in dl if isinstance(x, dict) and x.get('type') == 'instant']
    te = dig(inst, 0, 'target_effects') or []
    chk('§4.7 arc chain damage', [x.get('damage') for x in te if x.get('type') == 'damage'], [{'amount': 30, 'type': 'electric'}])
    chk('§4.7 arc chain sticker', [x.get('sticker') for x in te if x.get('type') == 'create-sticker'], ['electric-mini-stun'])
    chk('§4.7 arc chain fork_chance_increase_per_quality_level', ch.get('fork_chance_increase_per_quality_level'), 0.05)
    beams = [x for x in dl if isinstance(x, dict) and x.get('type') == 'beam']
    chk('§4.7 arc chain beam', [[x.get('beam'), x.get('duration'), x.get('add_to_shooter')] for x in beams],
        [['magnetics-arc-bounce-beam', 20, False]])
    for b in ('magnetics-arc-beam', 'magnetics-arc-bounce-beam'):
        chk(f'§4.7 {b} cosmetic (action nil)', E('beam', b).get('action'), None)
        chk(f'§4.7 {b} damage_interval', E('beam', b).get('damage_interval'), 20)
    # §4.7 трассер
    tr = E('explosion', 'magnetics-rail-tracer')
    chk('§4.7 rail-tracer rotate', tr.get('rotate'), True)
    chk('§4.7 rail-tracer beam', tr.get('beam'), True)
    an = dig(tr, 'animations', 0) or {}
    chk('§4.7 rail-tracer animation', [an.get(k) for k in ('filename', 'width', 'height', 'frame_count', 'line_length', 'draw_as_glow', 'blend_mode')],
        ['__magnetics__/graphics/entity/rail-tracer.png', 64, 440, 8, 8, True, 'additive'])
    chk('§4.7 rail-tracer light', [dig(tr, 'light', 'intensity'), dig(tr, 'light', 'size')], [1.5, 16])
    # §4.3 ленты
    chk('§4.3 maglev belt animation_speed_coefficient', E('transport-belt', 'magnetics-maglev-transport-belt').get('animation_speed_coefficient'), 32)
    chk('§4.1 maglev belt related_underground_belt', E('transport-belt', 'magnetics-maglev-transport-belt').get('related_underground_belt'), 'magnetics-maglev-underground-belt')
    chk('§4.1 maglev splitter related_transport_belt', E('splitter', 'magnetics-maglev-splitter').get('related_transport_belt'), 'magnetics-maglev-transport-belt')
    # §4.1 общая процедура: minable.result, hidden, factoriopedia_simulation, corpse/dying_explosion как у основы
    for name, e in sorted(spec_json['entities'].items()):
        p = E(e['type'], name)
        base = (WO.get(e.get('base_type') or e['type']) or {}).get(e['base']) or {}
        chk(f'§4.1 {name} minable.result', dig(p, 'minable', 'result'), name)
        chk(f'§4.1 {name} not hidden', bool(p.get('hidden')), False)
        chk(f'§4.1 {name} factoriopedia_simulation nil', p.get('factoriopedia_simulation'), None)
        chk(f'§4.1 {name} corpse = base', p.get('corpse'), base.get('corpse'))
        chk(f'§4.1 {name} dying_explosion = base', p.get('dying_explosion'), base.get('dying_explosion'))
    # §2.1 предметы с auto_recycle = false
    for n in ('magnetics-superconducting-cable', 'magnetics-flux-crystal-uncharged', 'magnetics-flux-crystal'):
        chk(f'§2.1 item {n} auto_recycle', E('item', n).get('auto_recycle'), False)
    # §3 auto_recycle и main_product рецептов (из разобранных таблиц §3)
    for n, d in sorted(doc._recipes.items()):
        r = E('recipe', n)
        chk(f'§3 recipe {n} auto_recycle', r.get('auto_recycle', True), d['ar'])
    for n in ('magnetics-liquid-nitrogen', 'magnetics-flux-crystal-growth', 'magnetics-flux-crystal-charging', 'magnetics-stone-separation'):
        chk(f'§3.1 recipe {n} main_product "" (own name/icon)', E('recipe', n).get('main_product'), '')
    # §4.2 печи → сборочные машины: полей печи нет (PILOT-2)
    for n in ('magnetics-sintering-kiln', 'magnetics-induction-furnace'):
        left = [k for k in ('result_inventory_size', 'source_inventory_size', 'cant_insert_at_source_message_key',
                            'custom_input_slot_tooltip_key') if k in E('assembling-machine', n)]
        chk(f'§4.2 {n} furnace-only keys removed', left, [])
    # §4.2 жидкостные входы/выходы сохранены: как у основы
    for n, bt, b in (('magnetics-cryo-chamber', 'assembling-machine', 'chemical-plant'),
                     ('magnetics-magnetic-separator', 'assembling-machine', 'assembling-machine-3')):
        fb = lambda e: sorted((x.get('production_type'), x.get('volume'), json.dumps(x.get('pipe_connections'), sort_keys=True))  # noqa: E731
                              for x in (e.get('fluid_boxes') or []))
        chk(f'§4.2 {n} fluid boxes = {b}', fb(E('assembling-machine', n)), fb((WO.get(bt) or {}).get(b) or {}))
    chk('§4.2 magnetic drill input_fluid_box = electric-mining-drill', E('mining-drill', 'magnetics-magnetic-drill').get('input_fluid_box'),
        ((WO.get('mining-drill') or {}).get('electric-mining-drill') or {}).get('input_fluid_box'))
    # §4.4 конденсатор: графика аккумулятора, каждый лист scale × 0.5 и shift × 0.5; без circuit_connector
    cap, acc = E('accumulator', 'magnetics-coil-capacitor'), ((WO.get('accumulator') or {}).get('accumulator') or {})
    chk('§4.4 capacitor circuit_connector nil', cap.get('circuit_connector'), None)
    leaves_a = {p: d for p, d in walk(acc.get('chargable_graphics') or {}) if 'filename' in d or 'filenames' in d or 'stripes' in d}
    leaves_c = {p: d for p, d in walk(cap.get('chargable_graphics') or {}) if 'filename' in d or 'filenames' in d or 'stripes' in d}
    chk('§4.4 capacitor chargable_graphics leaves = accumulator leaves', sorted(map(str, leaves_c)), sorted(map(str, leaves_a)))
    badl = []
    for p, d in leaves_a.items():
        c = leaves_c.get(p)
        if c is None:
            continue
        if abs((c.get('scale') or 1) - 0.5 * (d.get('scale') or 1)) > 1e-9:
            badl.append(f'{p}: scale {c.get("scale")} vs {d.get("scale")}')
        sa_, sc_ = d.get('shift'), c.get('shift')
        if sa_ is not None:
            va = sa_ if isinstance(sa_, list) else [sa_.get('x', sa_.get('1')), sa_.get('y', sa_.get('2'))]
            vc = sc_ if isinstance(sc_, list) else ([sc_.get('x', sc_.get('1')), sc_.get('y', sc_.get('2'))] if sc_ else None)
            if vc is None or any(abs(x * 0.5 - y) > 1e-9 for x, y in zip(va, vc)):
                badl.append(f'{p}: shift {vc} vs {va}')
    chk('§4.4 capacitor every leaf scale x0.5, shift x0.5', badl, [])
    # §4.6 разрядник: 64 направления, смещение источника — как у лазерной турели
    arc, las = E('electric-turret', 'magnetics-arc-emitter'), ((WO.get('electric-turret') or {}).get('laser-turret') or {})
    chk('§4.6 arc source_direction_count', dig(arc, 'attack_parameters', 'source_direction_count'), 64)
    chk('§4.6 arc source_offset = laser', dig(arc, 'attack_parameters', 'source_offset'), dig(las, 'attack_parameters', 'source_offset'))
    # §4.7 выстрелы болванок: вспышка explosion-gunshot; рельсовые: трассер по линии
    for n in ('magnetics-ferrite-slug', 'magnetics-magnet-slug', 'magnetics-gauss-slug'):
        se = dig(E('ammo', n), 'ammo_type', 'action', 'action_delivery', 'source_effects')
        se = se if isinstance(se, list) else [se]
        chk(f'§4.7 {n} source_effects explosion-gunshot', [x.get('entity_name') for x in se if isinstance(x, dict)], ['explosion-gunshot'])
    for n in ('magnetics-rail-slug', 'magnetics-flux-rail-slug'):
        act = dig(E('ammo', n), 'ammo_type', 'action') or {}
        re_ = act.get('range_effects')
        re_ = re_ if isinstance(re_, list) else [re_]
        chk(f'§4.7 {n} range_effects tracer', [(x or {}).get('entity_name') for x in re_], ['magnetics-rail-tracer'])
        se = dig(act, 'action_delivery', 'source_effects')
        se = se if isinstance(se, list) else [se]
        chk(f'§4.7 {n} source_effects explosion-gunshot', [(x or {}).get('entity_name') for x in se], ['explosion-gunshot'])
    # §7.5 резонатор: множитель скорости 1 для каждого качества
    res = E('assembling-machine', 'magnetics-flux-resonator')
    q = sorted((W.get('quality') or {}).keys())
    m = res.get('crafting_speed_quality_multiplier') or {}
    chk('§7.5 resonator crafting_speed_quality_multiplier = 1 for every quality', {k: m.get(k) for k in q}, {k: 1 for k in q})
    chk('§7.5 resonator quality_affects_energy_usage', res.get('quality_affects_energy_usage', False), False)


# ------------------------------------------------------------------------------------------------ S4-doc (игра против §2, §3, §5.1)
def t_s4_doc(R, cfg, export, W, WO, doc, api):
    sa = cfg == 'sa'
    vanilla = {n for t in WO if isinstance(WO[t], dict) and (t == 'fluid' or api.is_kind(t, 'ItemPrototype')) for n in WO[t]}
    fluids = set((W.get('fluid') or {}).keys())
    want = doc.recipes(vanilla, fluids, sa)
    got = export.get('recipes', {})
    R.eq(cfg, 'S4', 'doc §3: 40 recipes in tables', len(want), 40)
    for n, d in sorted(want.items()):
        g = got.get(n)
        if g is None:
            R.add(cfg, 'S4', f'doc §3 recipe {n} read in game', False, None, 'exported')
            continue
        R.eq(cfg, 'S4', f'doc §3 recipe {n} category', g['category'], d['category'])
        R.eq(cfg, 'S4', f'doc §3 recipe {n} energy', g['energy'], d['energy'], 1e-9)
        R.eq(cfg, 'S4', f'doc §3 recipe {n} ingredients', sorted(g['ing']), d['ing'])
        R.eq(cfg, 'S4', f'doc §3 recipe {n} results', sorted(g['res']), d['res'])
        R.eq(cfg, 'S4', f'doc §3 recipe {n} Prod', g['prod'], d['prod'])
        R.eq(cfg, 'S4', f'doc §3 recipe {n} allow_quality', g['quality'], d['allow_quality'])
        R.eq(cfg, 'S4', f'doc §3 recipe {n} enabled at start', g['enabled'], False)
    gt = export.get('techs', {})
    R.eq(cfg, 'S4', 'doc §5.1: 14 technologies in table', len(doc.techs), 14)
    for n, d in sorted(doc.techs.items()):
        g = gt.get(n)
        if g is None:
            R.add(cfg, 'S4', f'doc §5.1 {n} read in game', False, None, 'exported')
            continue
        dd = d['sa'] if (sa and 'sa' in d) else d
        R.eq(cfg, 'S4', f'doc §5.1 {n} prerequisites', sorted(g['pre']), sorted(dd['pre']))
        R.eq(cfg, 'S4', f'doc §5.1 {n} count', g['count'], dd['count'])
        R.eq(cfg, 'S4', f'doc §5.1 {n} time', g['time'], dd['time'], 1e-9)
        R.eq(cfg, 'S4', f'doc §5.1 {n} packs', sorted(g['packs']), sorted(dd['packs']))
        R.eq(cfg, 'S4', f'doc §5.1 {n} unlocks', g['unlocks'], ['unlock-recipe:' + x for x in d['unlocks']])
    items, ents = export.get('items', {}), export.get('entities', {})
    for n, st in sorted(doc.stacks.items()):
        g = (items.get(n) or ents.get(n) or {}).get('stack')
        R.eq(cfg, 'S4', f'doc §2 stack {n}', g, st)


# ------------------------------------------------------------------------------------------------ S11
def parse_cfg(path):
    out, sec = {}, None
    for i, l in enumerate(open(path, encoding='utf-8').read().splitlines(), 1):
        s = l.strip()
        if not s or s[0] in '#;':
            continue
        m = re.fullmatch(r'\[([^\]]+)\]', s)
        if m:
            sec = m.group(1)
            continue
        if '=' in s and sec:
            k, v = s.split('=', 1)
            out[(sec, k.strip())] = v
    return out


def t_s11(R, doc, W, locale_dumps):
    cfg = 'files'
    exp = doc.locale
    R.eq(cfg, 'S11', '§9 rows parsed (13 + 26 + 8 + 14 names)', len([k for k in exp if k[0].endswith('-name')]), 61)
    kinds = {'item': ('item', 'ammo'), 'fluid': ('fluid',), 'entity': None, 'recipe': ('recipe',), 'technology': ('technology',),
             'ammo-category': ('ammo-category',), 'fuel-category': ('fuel-category',)}
    entity_names = {n for t, lst in W.items() if isinstance(lst, dict) for n in lst if n in lst and t in ENTITY_TYPES}

    def exists(kind, name):
        if kind == 'entity':
            return name in entity_names
        return any(name in (W.get(t) or {}) for t in kinds[kind])
    for lang in LOCALES:
        p = os.path.join(run.MOD_SRC, 'locale', lang, 'magnetics.cfg')
        if not os.path.exists(p):
            R.add(cfg, 'S11', f'{lang}: magnetics.cfg exists', False, None, p)
            continue
        have = parse_cfg(p)
        for (sec, key), vals in sorted(exp.items()):
            if lang not in vals:
                continue
            R.eq(cfg, 'S11', f'{lang} [{sec}] {key}', have.get((sec, key)), vals[lang])
        unused = []
        for (sec, key) in sorted(have):
            if sec in ('mod-name', 'mod-description'):
                continue
            kind = sec.rsplit('-', 1)[0]
            if kind not in kinds or not exists(kind, key) or (sec, key) not in exp:
                unused.append(f'[{sec}] {key}')
        R.add(cfg, 'S11', f'{lang}: no unused/unexpected key', not unused, unused, [])
        R.add(cfg, 'S11', f'{lang}: [mod-name] magnetics present', ('mod-name', 'magnetics') in have, ('mod-name', 'magnetics') in have, True)
    # как видит игра (--dump-prototype-locale): имена всех прототипов Magnetics разрешаются и равны §9
    for lang, d in sorted(locale_dumps.items()):
        if not d:
            R.add(cfg, 'S11', f'{lang}: prototype locale dump', False, None, 'dump')
            continue
        bad = []
        for fname, data in d.items():
            for k, v in (data.get('names') or {}).items():
                if k.startswith(P) and ('Unknown key' in v or not v.strip()):
                    bad.append(f'{fname}:{k}={v}')
        R.add(cfg, 'S11', f'{lang}: game resolves every Magnetics name (no "Unknown key")', not bad, bad[:20], [])
        for (sec, key), vals in sorted(exp.items()):
            kind, what = sec.rsplit('-', 1)
            fname = f'{kind}-locale.json'
            want = vals.get(lang) if what == 'name' else (vals.get(lang) or vals.get('en'))
            got = ((d.get(fname) or {}).get('names' if what == 'name' else 'descriptions') or {}).get(key)
            R.eq(cfg, 'S11', f'{lang} game {sec} {key}', got, want)
        # постройка: имя предмета = имя сущности
        for key in sorted(k for (s, k) in exp if s == 'entity-name'):
            gi = ((d.get('item-locale.json') or {}).get('names') or {}).get(key)
            R.eq(cfg, 'S11', f'{lang} game item name of {key} = entity name', gi, exp[('entity-name', key)][lang])


ENTITY_TYPES = set()


# ------------------------------------------------------------------------------------------------ S8-grep
SA_ONLY = re.compile(r'^(turbo-[\w-]+|electromagnetic-plant|cryogenic-plant|foundry|metallurgic-science-pack|electromagnetic-science-pack|space-science-pack)$')


def lua_tokens(src):
    """Грубый лексер Lua: (тип, значение, строка). Типы: name, str, op."""
    i, n, line = 0, len(src), 1
    while i < n:
        c = src[i]
        if c == '\n':
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif src.startswith('--', i):
            m = re.match(r'--\[(=*)\[', src[i:])
            if m:
                end = src.find(']' + m.group(1) + ']', i)
                end = n if end < 0 else end + len(m.group(1)) + 2
            else:
                end = src.find('\n', i)
                end = n if end < 0 else end
            line += src.count('\n', i, end)
            i = end
        elif c in '"\'':
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == '\\' else 1
            yield ('str', src[i + 1:j], line)
            i = j + 1
        elif src.startswith('[[', i) or re.match(r'\[=+\[', src[i:]):
            m = re.match(r'\[(=*)\[', src[i:])
            end = src.find(']' + m.group(1) + ']', i)
            end = n if end < 0 else end
            yield ('str', src[i + len(m.group(0)):end], line)
            line += src.count('\n', i, end)
            i = end + len(m.group(1)) + 2
        elif c.isalpha() or c == '_':
            m = re.match(r'[A-Za-z_]\w*', src[i:])
            yield ('name', m.group(0), line)
            i += len(m.group(0))
        else:
            yield ('op', c, line)
            i += 1


def sa_guard_scan(src):
    """SA-имена вне охраны: охрана — блок `if <условие с SA или "space-age"> then ... [else/elseif — уже без охраны] end`
    или поле-таблица `sa = {...}` (данные spec_data.lua, читаемые только под U.SA)."""
    toks = list(lua_tokens(src))
    stack, hits = [], []           # стек блоков: [вид, охраняет?]
    i = 0
    while i < len(toks):
        t, v, ln = toks[i]
        if t == 'name' and v == 'if':
            j, guarded = i + 1, False
            while j < len(toks) and not (toks[j][0] == 'name' and toks[j][1] == 'then'):
                if (toks[j][0] == 'name' and toks[j][1] == 'SA') or (toks[j][0] == 'str' and toks[j][1] == 'space-age'):
                    guarded = True
                j += 1
            stack.append(['if', guarded])
            i = j + 1
            continue
        if t == 'name' and v in ('else', 'elseif') and stack and stack[-1][0] == 'if':
            stack[-1][1] = False
        elif t == 'name' and v in ('function', 'do', 'repeat'):
            stack.append([v, False])
        elif t == 'name' and v in ('for', 'while'):
            j = i + 1
            while j < len(toks) and not (toks[j][0] == 'name' and toks[j][1] == 'do'):
                j += 1
            stack.append([v, False])
            i = j + 1
            continue
        elif t == 'name' and v in ('end', 'until'):
            if stack:
                stack.pop()
        elif t == 'op' and v == '{':
            g = i >= 2 and toks[i - 1] == ('op', '=', toks[i - 1][2]) and toks[i - 2][0] == 'name' and toks[i - 2][1] == 'sa'
            stack.append(['{', g])
        elif t == 'op' and v == '}':
            if stack and stack[-1][0] == '{':
                stack.pop()
        elif t == 'str' and SA_ONLY.match(v):
            if not any(g for _, g in stack):
                hits.append((ln, v))
        i += 1
    return hits


def t_s8_grep(R):
    cfg = 'files'
    hits = []
    for root, _, files in os.walk(run.MOD_SRC):
        for f in files:
            if f.endswith('.lua'):
                p = os.path.join(root, f)
                for ln, v in sa_guard_scan(open(p, encoding='utf-8').read()):
                    hits.append(f'{os.path.relpath(p, run.MOD_SRC)}:{ln}: "{v}"')
    R.add(cfg, 'S8', 'no SA-only name in mod Lua outside mods["space-age"] guards', not hits, hits, [])
    # отрицательный контроль сканера: имя вне охраны ловится, внутри — нет
    probe = 'local a = "foundry"\nif SA then local b = "foundry" else local c = "turbo-splitter" end\nlocal t = { sa = { "space-science-pack" } }'
    R.eq(cfg, 'S8', 'scanner self-check (catches unguarded, skips guarded)', [v for _, v in sa_guard_scan(probe)], ['foundry', 'turbo-splitter'])


# ------------------------------------------------------------------------------------------------ отчёт
def summarize(R):
    summ = {}
    for r in R.records:
        s = summ.setdefault(r['config'], {}).setdefault(r['test'], [0, 0])
        s[0 if r['pass_'] else 1] += 1
    return summ


def write_reports(R, meta, out_json, out_md):
    recs = []
    for r in R.records:          # компактно: пустые поля опущены; у прошедших expected опущено, если равно got
        o = {'config': r['config'], 'test': r['test'], 'name': r['name'], 'pass': r['pass_']}
        if r.get('got') is not None:
            o['got'] = r['got']
        if r.get('expected') is not None and not (r['pass_'] and r.get('expected') == r.get('got')):
            o['expected'] = r['expected']
        if r.get('note'):
            o['note'] = r['note']
        if r.get('source') and r['source'] != 'python':
            o['source'] = r['source']
        recs.append(o)
    summ = summarize(R)
    with open(out_json, 'w', encoding='utf-8') as f:
        f.write('{"meta": ' + json.dumps(meta, ensure_ascii=False) + ',\n "summary": ' +
                json.dumps({c: {t: {'pass': v[0], 'fail': v[1]} for t, v in d.items()} for c, d in summ.items()}, ensure_ascii=False) +
                ',\n "failures": ' + json.dumps([x for x in recs if not x['pass']], ensure_ascii=False) +
                ',\n "records": [\n' + ',\n'.join(json.dumps(x, ensure_ascii=False) for x in recs) + '\n]}\n')
    cols = [c for c in list(meta['configs']) + ['files'] if c in summ]
    tests = sorted({t for d in summ.values() for t in d}, key=lambda t: (re.sub(r'\d+', '', t), int(re.search(r'\d+', t).group(0)) if re.search(r'\d+', t) else 0, t))
    L = ['# Magnetics: результаты автотестов', '',
         f'Запуск {meta["started"]}, {meta["seconds"]} с; Factorio {meta.get("factorio_version", "?")}; коммит `{meta.get("commit", "?")}`; '
         f'модули ячеек: {", ".join(meta.get("modules", []))}; бенчмарк до записи результатов: {meta.get("cells_done") or "—"}.', '',
         'Клетка: прошло/не прошло (число проверок). `files` — проверки файлов, не зависящие от конфигурации.', '',
         '| тест | ' + ' | '.join(cols) + ' |', '|---|' + '---|' * len(cols)]
    for t in tests:
        row = []
        for c in cols:
            v = summ.get(c, {}).get(t)
            row.append('—' if not v else (f'{v[0]}/0' if v[1] == 0 else f'**{v[0]}/{v[1]}**'))
        L.append(f'| {t} | ' + ' | '.join(row) + ' |')
    tot = {c: [sum(v[0] for v in summ[c].values()), sum(v[1] for v in summ[c].values())] for c in cols}
    L.append('| **всего** | ' + ' | '.join(f'{tot[c][0]}/{tot[c][1]}' for c in cols) + ' |')
    L.append('')
    for c in cols:
        fails = [r for r in R.records if r['config'] == c and not r['pass_']]
        L.append(f'## {c}: провалы ({len(fails)})')
        L.append('')
        if not fails:
            L.append('нет')
        for r in fails[:400]:
            note = f' — {r["note"]}' if r.get('note') else ''
            L.append(f'- **{r["test"]}** {r["name"]}: got `{_short(r["got"], 400)}`, expected `{_short(r["expected"], 400)}`{note}')
        if len(fails) > 400:
            L.append(f'- … ещё {len(fails) - 400}')
        L.append('')
    if meta.get('run_errors'):
        L.append('## Ошибки прогона')
        L.append('')
        for e in meta['run_errors']:
            L.append(f'- {e}')
    open(out_md, 'w', encoding='utf-8').write('\n'.join(L) + '\n')


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--configs', default=','.join(CONFIGS))
    ap.add_argument('--jobs', type=int, default=max(1, os.cpu_count() or 1))
    ap.add_argument('--ticks', type=int, default=1000000,
                    help='потолок тиков бенчмарка; прогон останавливается сам, когда стенд записал результаты')
    ap.add_argument('--cells', default=None, help='модули ячеек через запятую (по умолчанию cells/_all.lua + static)')
    ap.add_argument('--skip-cells', action='store_true')
    ap.add_argument('--skip-dumps', action='store_true')
    ap.add_argument('--work', default=None)
    ap.add_argument('--keep', action='store_true', help='не удалять рабочую папку')
    ap.add_argument('--out', default=HERE)
    ap.add_argument('--mod', default=None, help='другая папка мода (для отрицательных контролей); по умолчанию magnetics/')
    a = ap.parse_args()
    if a.mod:
        run.MOD_SRC = os.path.abspath(a.mod)
    cfgs = [c for c in a.configs.split(',') if c]
    modules = a.cells.split(',') if a.cells else cell_modules()
    ticks = a.ticks
    work = a.work or tempfile.mkdtemp(prefix='mgn_tests_')
    os.makedirs(work, exist_ok=True)
    t0 = time.time()
    meta = dict(started=datetime.datetime.now().isoformat(timespec='seconds'), configs=cfgs, modules=modules, ticks=ticks,
                work=work, mod=run.MOD_SRC, run_errors=[])
    try:
        meta['commit'] = subprocess.run(['git', '-C', ROOT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
        meta['dirty'] = bool(subprocess.run(['git', '-C', ROOT, 'status', '--porcelain', '--', '.'], capture_output=True, text=True).stdout.strip())
    except Exception:  # noqa: BLE001
        pass
    R = Results()
    doc = Doc()
    spec_json = json.load(open(os.path.join(HERE, 'spec.json'), encoding='utf-8'))
    api = Api()
    global ENTITY_TYPES
    ENTITY_TYPES = {t for t in api.typename if api.is_kind(t, 'EntityPrototype')}

    # ремонтная катушка ловит урон всех стен мира, поэтому её ячейки идут отдельным прогоном (в общем прогоне
    # стены ячеек боя попадают в её очередь); в base — ещё повтор (R10, побайтно тот же результат) и смена версии (R9)
    ISOLATED = [m for m in ('mend',) if m in modules]
    main_modules = [m for m in modules if m not in ISOLATED]
    meta['modules'] = main_modules
    meta['isolated_modules'] = ISOLATED
    jobs = {}
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for c in cfgs:
            if not a.skip_cells:
                jobs[ex.submit(job_cells, work, c, ticks, main_modules)] = ('cells', c)
                for m in ISOLATED:
                    jobs[ex.submit(job_cells, work, c, ticks, [m], 3600, m)] = (m, c)
                    if c == 'base':
                        jobs[ex.submit(job_cells, work, c, ticks, [m], 3600, m + '_repeat')] = (m + '_repeat', c)
                        jobs[ex.submit(job_cells, work, c, ticks, [m], 3600, m + '_bump', True)] = (m + '_bump', c)
            if not a.skip_dumps:
                jobs[ex.submit(job_dump, work, c, True)] = ('dump_with', c)
                jobs[ex.submit(job_dump, work, c, False)] = ('dump_without', c)
            jobs[ex.submit(job_create, work, c)] = ('create', c)
        if not a.skip_dumps:
            for lang in LOCALES:
                jobs[ex.submit(job_locale, work, lang)] = ('locale', lang)
        res = {}
        for f in cf.as_completed(jobs):
            k = jobs[f]
            try:
                res[k] = f.result()
            except Exception:  # noqa: BLE001
                meta['run_errors'].append(f'{k}: {traceback.format_exc(limit=3)}')
                res[k] = None
            print(f'  готово {k[0]} {k[1]} ({(res[k] or {}).get("seconds", "?")} с)', flush=True)

    m = re.search(r'Factorio (\d+\.\d+\.\d+)', (res.get(('create', cfgs[0])) or {}).get('log', '') if cfgs else '')
    meta['factorio_version'] = m.group(1) if m else None

    def guard(cfg, test, f, *args):
        try:
            f(*args)
        except Exception:  # noqa: BLE001
            R.add(cfg, test, 'ошибка Python в проверке', False, traceback.format_exc(limit=4), None)

    first_W = None
    for c in cfgs:
        cr = res.get(('create', c))
        if cr:
            guard(c, 'S1', t_s1, R, c, cr)
        else:
            R.add(c, 'S1', 'create ran', False, None, True)
        W = WO = None
        if not a.skip_dumps:
            dw, dwo = res.get(('dump_with', c)), res.get(('dump_without', c))
            ok_w, ok_wo = bool(dw and dw.get('dump')), bool(dwo and dwo.get('dump'))
            R.add(c, 'S2', 'data.raw dumps written (with / without magnetics)', ok_w and ok_wo, [ok_w, ok_wo], [True, True],
                  note=None if ok_w and ok_wo else f'with rc={dw and dw.get("rc")}, without rc={dwo and dwo.get("rc")}')
            if ok_w and ok_wo:
                W = json.load(open(dw['dump'], encoding='utf-8'))
                WO = json.load(open(dwo['dump'], encoding='utf-8'))
                guard(c, 'S2', t_s2, R, c, W, WO, api)
                guard(c, 'S3', t_s3, R, c, dw['dump'])
                guard(c, 'S7', t_s7, R, c, W, WO)
                guard(c, 'S10', t_s10, R, c, W)
                guard(c, 'S12', t_s12, R, c, W, WO, doc, spec_json)
                guard(c, 'S13', t_s13, R, c, W)
                guard(c, 'S4', t_s4_dump, R, c, W, WO, doc, spec_json)
        if not a.skip_cells:
            cr = res.get(('cells', c))
            out = (cr or {}).get('output', {})
            rj = out.get('magnetics-results.json')
            if not isinstance(rj, dict):
                R.add(c, 'RUN', 'cells produced magnetics-results.json', False,
                      dict(create_ok=(cr or {}).get('create_ok'), finished=(cr or {}).get('finished'), timeout=(cr or {}).get('timeout'),
                           errors=(cr or {}).get('errors', [])[:10]),
                      'results', note='сбой стенда или потолок тиков; рабочая папка: ' + str((cr or {}).get('work')))
            else:
                for rec in rj.get('results', []):
                    R.records.append(dict(config=c, test=test_id(rec), name=rec.get('name'), pass_=bool(rec.get('pass')),
                                          got=_short(rec.get('got')), expected=_short(rec.get('expected')), note=rec.get('note'),
                                          source='cell:' + str(rec.get('group'))))
                errs = (cr or {}).get('errors', [])
                R.add(c, 'RUN', 'cells run: 0 Error lines in log', not errs, errs[:20], [])
                meta.setdefault('cells_done', {})[c] = (cr or {}).get('done')
            for m in ISOLATED:
                for key, tag in ((m, ''), (m + '_bump', ' [прогон со сменой версии тестового мода]')):
                    ir = res.get((key, c))
                    if ir is None:
                        continue
                    irj = (ir or {}).get('output', {}).get('magnetics-results.json')
                    if not isinstance(irj, dict):
                        R.add(c, 'RUN', f'isolated run {key} produced results', False, dict(errors=(ir or {}).get('errors', [])[:10]), 'results')
                        continue
                    for rec in irj.get('results', []):
                        R.records.append(dict(config=c, test=test_id(rec), name=str(rec.get('name')) + tag, pass_=bool(rec.get('pass')),
                                              got=_short(rec.get('got')), expected=_short(rec.get('expected')), note=rec.get('note'),
                                              source='cell:' + str(rec.get('group'))))
                    R.add(c, 'RUN', f'isolated run {key}: 0 Error lines in log', not (ir or {}).get('errors'), (ir or {}).get('errors', [])[:20], [])
                r1_, r2_ = res.get((m, c)), res.get((m + '_repeat', c))
                if r1_ is not None and r2_ is not None:
                    import hashlib
                    def h(rr):
                        x = (rr or {}).get('output', {}).get('magnetics-results.json')
                        return hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()[:16] if x is not None else None
                    h1, h2 = h(r1_), h(r2_)
                    R.add(c, 'R10', 'mend: two fresh runs give byte-identical results (sha256)', h1 is not None and h1 == h2, h2, h1)
            tw = out.get('magnetics-combat-tw.json')
            if isinstance(tw, dict):
                json.dump(tw, open(os.path.join(a.out, f'tw_results_{c}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            exp = out.get('magnetics-static-export.json')
            if isinstance(exp, dict) and W is not None:
                guard(c, 'S4', t_s4_doc, R, c, exp, W, WO, doc, api)
            elif 'static' in modules:
                R.add(c, 'S4', 'static export present (doc cross-check)', False, None, 'magnetics-static-export.json')
        if W is not None and first_W is None and c == 'base':
            first_W = W
        del W, WO
    if not a.skip_dumps:
        if first_W is None:
            d = res.get(('dump_with', 'base')) or res.get(('dump_with', cfgs[0]))
            if d and d.get('dump'):
                first_W = json.load(open(d['dump'], encoding='utf-8'))
        dumps = {}
        for lang in LOCALES:
            lr = res.get(('locale', lang))
            dd = {}
            if lr and os.path.isdir(lr['dir']):
                for f in os.listdir(lr['dir']):
                    if f.endswith('-locale.json'):
                        dd[f] = json.load(open(os.path.join(lr['dir'], f), encoding='utf-8'))
            dumps[lang] = dd
        if first_W is not None:
            guard('files', 'S11', t_s11, R, doc, first_W, dumps)
    guard('files', 'S8', t_s8_grep, R)

    meta['seconds'] = round(time.time() - t0, 1)
    out_json = os.path.join(a.out, 'test_results.json')
    out_md = os.path.join(a.out, 'test_results.md')
    write_reports(R, meta, out_json, out_md)
    summ = summarize(R)
    for c in [x for x in cfgs + ['files'] if x in summ]:
        p = sum(v[0] for v in summ[c].values())
        f = sum(v[1] for v in summ[c].values())
        bad = sorted(t for t, v in summ[c].items() if v[1])
        print(f'{c}: прошло {p}, не прошло {f}' + (f' (тесты с провалами: {", ".join(bad)})' if bad else ''))
    print('отчёт:', out_md)
    if not a.keep and not a.work:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print('рабочая папка:', work)
    return 0 if not any(not r['pass_'] for r in R.records) else 1


if __name__ == '__main__':
    sys.exit(main())
