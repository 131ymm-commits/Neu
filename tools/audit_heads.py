# Аудит входа голов: что голова workflow получила, кроме промпта скрипта (ERRORS № 31 и проверка 26.09.2026).
# Каналы:
#   1) сообщение человека, переданное обвязкой («the user request that triggered this workflow run»);
#   2) текст CLAUDE.md репозитория — подгружается, когда агент открывает файлы в neu/;
#   3) пути к правде (/root/*_secret);
#   4) инструменты, кроме StructuredOutput, — головам опытов они запрещены.
# Столбец model — идентификаторы модели из транскриптов (message.model у ходов assistant): смена модели между сессиями — стоп прогона (PREREG EVAL-01 §3).
# Совету и рецензентам каналы 2–4 разрешены; смотреть надо на головы опытов.
#   python3 tools/audit_heads.py [--match <подстрока имени workflow>] [--out <json>]
# Головы tools/run_sealed2.py (с SELECT-01) — режим --sealed <журнал> [<журнал> …] (29.10.2026, ERRORS № 118: этот канал аудит не видел):
#   5) снимок git: HOME и рабочая папка голов из run_config.json журнала внутри git-дерева или без CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1;
#   6) инструменты, MCP и модель — из записей init журнала и итоговых записей вызовов.
#   python3 tools/audit_heads.py --sealed experiments/<опыт>/run/<этап> [...]
import json, glob, os, re, argparse, collections

ROOT = os.path.expanduser('~/.claude/projects')
RELAY = 'the user request that triggered this workflow run'
CLAUDE_MD = ('Contents of /home/user/neu/CLAUDE.md', 'Правила для Claude в репозитории Neu')
SECRET = re.compile(r'/root/\w*_secret')


def strings(x):
    if isinstance(x, str): yield x
    elif isinstance(x, dict):
        for v in x.values(): yield from strings(v)
    elif isinstance(x, list):
        for v in x: yield from strings(v)


def agent(path):
    relayed, md, secret, tools, models = set(), False, set(), collections.Counter(), set()
    for line in open(path, errors='replace'):
        try: o = json.loads(line)
        except ValueError: continue
        m = o.get('message') or {}
        if o.get('type') == 'assistant' and isinstance(m.get('model'), str) and not m['model'].startswith('<'): models.add(m['model'])   # '<synthetic>' — служебные ходы обвязки, не модель
        if o.get('type') == 'assistant' and isinstance(m.get('content'), list):
            for b in m['content']:
                if isinstance(b, dict) and b.get('type') == 'tool_use' and b.get('name') != 'StructuredOutput': tools[b.get('name')] += 1
        for s in strings(o):
            if RELAY in s: relayed.add(s.split('this request wins:', 1)[-1].strip()[:300])
            if any(k in s for k in CLAUDE_MD): md = True
            secret.update(SECRET.findall(s))
    return relayed, md, secret, tools, models


def in_git(path):
    p = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(p, '.git')): return True
        q = os.path.dirname(p)
        if q == p: return False
        p = q


def audit_sealed(journal):
    c = json.load(open(os.path.join(journal, 'run_config.json'), encoding='utf-8'))
    env = (c.get('env_explicit') or {}).get('CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS')
    tools, mcp, models, n = set(), set(), collections.Counter(), 0
    for f in glob.glob(os.path.join(journal, 'init_*.json')):
        i = json.load(open(f, encoding='utf-8')); tools |= set(i.get('tools') or []); mcp |= {str(x) for x in i.get('mcp_servers') or []}
    for f in glob.glob(os.path.join(journal, '*.jsonl')):
        for line in open(f, encoding='utf-8'):
            try: r = json.loads(line)
            except ValueError: continue
            if r.get('final'):
                n += 1
                for k in r.get('model_usage_keys') or []: models[k] += 1
    snap = in_git(c.get('home') or '/') or in_git(c.get('work_dir') or '/') or env != '1'
    return dict(journal=journal, calls=n, home=c.get('home'), work_dir=c.get('work_dir'), git_instructions_off=env == '1', git_snapshot_possible=snap,
                tools=sorted(tools), mcp=sorted(mcp), model=dict(models))


def audit(match=None):
    rows = []
    for d in sorted(glob.glob(f'{ROOT}/*/*/subagents/workflows/wf_*')):  # идущие прогоны ещё без записи — имя по метке первой головы
        wf = os.path.basename(d); sess = os.path.dirname(os.path.dirname(os.path.dirname(d))); rec = f'{sess}/workflows/{wf}.json'
        r = json.load(open(rec)) if os.path.exists(rec) else dict(status='идёт')
        metas = sorted(glob.glob(f'{d}/agent-*.meta.json'))
        name = r.get('workflowName') or ('? ' + json.load(open(metas[0])).get('description', '') if metas else '?')
        if match and match not in name: continue
        paths = sorted(glob.glob(f'{d}/agent-*.jsonl'))
        relayed, secret, tools, md, models = set(), set(), collections.Counter(), 0, collections.Counter()
        for p in paths:
            a = agent(p); relayed |= a[0]; md += a[1]; secret |= a[2]; tools += a[3]
            for mm in a[4]: models[mm] += 1   # число голов на модель
        rows.append(dict(wf=wf, name=name, start=r.get('startTime'), status=r.get('status'), script=r.get('scriptPath'), agents=len(paths),
                         relayed=sorted(relayed), claude_md_agents=md, secret_paths=sorted(secret), tools=dict(tools), model=dict(models)))
    return sorted(rows, key=lambda x: str(x['start']))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--match'); ap.add_argument('--out'); ap.add_argument('--sealed', nargs='+'); a = ap.parse_args()
    if a.sealed:
        rows = [audit_sealed(j) for j in a.sealed]
        for x in rows:
            flags = ['СНИМОК GIT ВОЗМОЖЕН (HOME или рабочая папка в git-дереве, или нет CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1)' if x['git_snapshot_possible'] else '',
                     f'инструменты {x["tools"]}' if set(x['tools']) - {'StructuredOutput'} else '', f'MCP {x["mcp"]}' if x['mcp'] else '',
                     f'модель {x["model"]}' + (' — БОЛЬШЕ ОДНОЙ' if len(x['model']) > 1 else '')]
            print(f'{x["journal"]:<60} {x["calls"]:>4} вызовов  ' + '; '.join(f for f in flags if f))
        if a.out: json.dump(rows, open(a.out, 'w'), ensure_ascii=False, indent=1)
        raise SystemExit(0)
    rows = audit(a.match)
    for x in rows:
        flags = [f'сообщение человека: {x["relayed"]}' if x['relayed'] else '', f'CLAUDE.md у {x["claude_md_agents"]}' if x['claude_md_agents'] else '',
                 f'пути к правде {x["secret_paths"]}' if x['secret_paths'] else '', f'инструменты {x["tools"]}' if x['tools'] else '',
                 f'модель {x["model"]}' + (' — БОЛЬШЕ ОДНОЙ' if len(x['model']) > 1 else '') if x['model'] else 'модель не найдена']
        print(f'{x["name"]:<26} {x["agents"]:>3} голов  ' + ('; '.join(f for f in flags if f) or 'чисто'))
    if a.out: json.dump(rows, open(a.out, 'w'), ensure_ascii=False, indent=1)
