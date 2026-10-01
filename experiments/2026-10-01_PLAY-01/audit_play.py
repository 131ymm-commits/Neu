"""PLAY-01: аудит голов по каждой голове (условие анализа, решение совета 24, скептик п. 1).
У тестовой головы нет ни одного вызова инструмента, кроме StructuredOutput; ни в промпте, ни в ответе нет путей к RCON, сейвам,
каталогу прогона, моду и script-output; модель одна на конфигурацию (opus у A, B, C; haiku у H; у D — по ролям).
   python3 audit_play.py <этап> → runs/<этап>/audit.json (по меткам голов → цепочки «участник_зерно»)"""
import collections, glob, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.expanduser('~/.claude/projects')
FORBID = re.compile(r'rcon|/saves?/|runs/|neu-play|neu_play|script-output|password|state\.json|\.zip|/opt/factorio|tourney|game\.py', re.I)
RELAY = 'the user request that triggered this workflow run'
CLAUDE_MD = 'Правила для Claude в репозитории Neu'
LABEL = re.compile(r'^(A2|A|H|B[1-4]|C[1-3]|Ccc|D[1-3]|Dcc)_r(\d+)_s(\d+)$')


def texts(x):
    if isinstance(x, str): yield x
    elif isinstance(x, dict):
        for v in x.values(): yield from texts(v)
    elif isinstance(x, list):
        for v in x: yield from texts(v)


def one(path):
    tools, models, forb_prompt, forb_out, relay, md = collections.Counter(), set(), set(), set(), False, False
    first_user = True
    for line in open(path, errors='replace'):
        try: o = json.loads(line)
        except ValueError: continue
        m = o.get('message') or {}
        if o.get('type') == 'assistant':
            if isinstance(m.get('model'), str) and not m['model'].startswith('<'): models.add(m['model'])
            for b in m.get('content') or []:
                if not isinstance(b, dict): continue
                if b.get('type') == 'tool_use' and b.get('name') != 'StructuredOutput': tools[b.get('name')] += 1
                for s in texts(b):
                    forb_out.update(x.lower() for x in FORBID.findall(s))
        if o.get('type') == 'user':
            for s in texts(m):
                if RELAY in s: relay = True
                if CLAUDE_MD in s: md = True
                if first_user: forb_prompt.update(x.lower() for x in FORBID.findall(s))
            first_user = False
    return dict(tools=dict(tools), models=sorted(models), forbidden_in_prompt=sorted(forb_prompt), forbidden_in_output=sorted(forb_out), relay=relay, claude_md=md)


def audit(stage):
    rows = []
    for d in sorted(glob.glob(f'{ROOT}/*/*/subagents/workflows/wf_*')):
        for meta in glob.glob(f'{d}/agent-*.meta.json'):
            lab = json.load(open(meta)).get('description', '')
            m = LABEL.match(lab)
            if not m: continue
            jl = meta.replace('.meta.json', '.jsonl')
            if not os.path.exists(jl): continue
            # этап — по имени workflow в записи прогона
            rec = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(d))), 'workflows', os.path.basename(d) + '.json')
            name = json.load(open(rec)).get('workflowName', '') if os.path.exists(rec) else ''
            if not name.startswith(f'play01-{stage}-'): continue
            rows.append(dict(label=lab, head=m.group(1), part='A2' if m.group(1) == 'A2' else m.group(1)[0], round=int(m.group(2)), seed=int(m.group(3)), wf=os.path.basename(d), **one(jl)))
    by_chain = collections.defaultdict(lambda: dict(heads=0, tool_calls=0, forbidden=0, models=set()))
    for r in rows:
        c = by_chain[f'{r["part"]}_s{r["seed"]}']
        c['heads'] += 1; c['tool_calls'] += sum(r['tools'].values()); c['forbidden'] += len(r['forbidden_in_prompt']) + len(r['forbidden_in_output'])
        c['models'] |= set(r['models'])
    chains = {k: dict(v, models=sorted(v['models']), clean=v['tool_calls'] == 0 and v['forbidden'] == 0) for k, v in by_chain.items()}
    out = dict(stage=stage, heads=rows, chains=chains,
               relay_heads=sum(r['relay'] for r in rows), claude_md_heads=sum(r['claude_md'] for r in rows))
    json.dump(out, open(os.path.join(HERE, 'runs', stage, 'audit.json'), 'w'), ensure_ascii=False, indent=1)
    return out


if __name__ == '__main__':
    o = audit(sys.argv[1])
    print(f'голов {len(o["heads"])}; с переданным сообщением человека {o["relay_heads"]}; с CLAUDE.md {o["claude_md_heads"]}')
    for k, v in sorted(o['chains'].items()):
        print(f'{k:<12} голов {v["heads"]:>3}  вызовов инструментов {v["tool_calls"]}  запретных строк {v["forbidden"]}  модели {v["models"]}  {"чисто" if v["clean"] else "НАРУШЕНИЕ"}')
