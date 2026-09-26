# Аудит входа голов: что голова workflow получила, кроме промпта скрипта (ERRORS № 31 и проверка 26.09.2026).
# Каналы:
#   1) сообщение человека, переданное обвязкой («the user request that triggered this workflow run»);
#   2) текст CLAUDE.md репозитория — подгружается, когда агент открывает файлы в neu/;
#   3) пути к правде (/root/*_secret);
#   4) инструменты, кроме StructuredOutput, — головам опытов они запрещены.
# Совету и рецензентам каналы 2–4 разрешены; смотреть надо на головы опытов.
#   python3 tools/audit_heads.py [--match <подстрока имени workflow>] [--out <json>]
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
    relayed, md, secret, tools = set(), False, set(), collections.Counter()
    for line in open(path, errors='replace'):
        try: o = json.loads(line)
        except ValueError: continue
        m = o.get('message') or {}
        if o.get('type') == 'assistant' and isinstance(m.get('content'), list):
            for b in m['content']:
                if isinstance(b, dict) and b.get('type') == 'tool_use' and b.get('name') != 'StructuredOutput': tools[b.get('name')] += 1
        for s in strings(o):
            if RELAY in s: relayed.add(s.split('this request wins:', 1)[-1].strip()[:300])
            if any(k in s for k in CLAUDE_MD): md = True
            secret.update(SECRET.findall(s))
    return relayed, md, secret, tools


def audit(match=None):
    rows = []
    for d in sorted(glob.glob(f'{ROOT}/*/*/subagents/workflows/wf_*')):  # идущие прогоны ещё без записи — имя по метке первой головы
        wf = os.path.basename(d); sess = os.path.dirname(os.path.dirname(os.path.dirname(d))); rec = f'{sess}/workflows/{wf}.json'
        r = json.load(open(rec)) if os.path.exists(rec) else dict(status='идёт')
        metas = sorted(glob.glob(f'{d}/agent-*.meta.json'))
        name = r.get('workflowName') or ('? ' + json.load(open(metas[0])).get('description', '') if metas else '?')
        if match and match not in name: continue
        paths = sorted(glob.glob(f'{d}/agent-*.jsonl'))
        relayed, secret, tools, md = set(), set(), collections.Counter(), 0
        for p in paths:
            a = agent(p); relayed |= a[0]; md += a[1]; secret |= a[2]; tools += a[3]
        rows.append(dict(wf=wf, name=name, start=r.get('startTime'), status=r.get('status'), script=r.get('scriptPath'), agents=len(paths),
                         relayed=sorted(relayed), claude_md_agents=md, secret_paths=sorted(secret), tools=dict(tools)))
    return sorted(rows, key=lambda x: str(x['start']))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--match'); ap.add_argument('--out'); a = ap.parse_args()
    rows = audit(a.match)
    for x in rows:
        flags = [f'сообщение человека: {x["relayed"]}' if x['relayed'] else '', f'CLAUDE.md у {x["claude_md_agents"]}' if x['claude_md_agents'] else '',
                 f'пути к правде {x["secret_paths"]}' if x['secret_paths'] else '', f'инструменты {x["tools"]}' if x['tools'] else '']
        print(f'{x["name"]:<26} {x["agents"]:>3} голов  ' + ('; '.join(f for f in flags if f) or 'чисто'))
    if a.out: json.dump(rows, open(a.out, 'w'), ensure_ascii=False, indent=1)
