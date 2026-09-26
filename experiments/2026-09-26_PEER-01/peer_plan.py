# PEER-01: задачи, промпты, пачки.
#   python3 peer_plan.py tasks <dir> <seed> [fam:want ...]  -> tasks.json
#   python3 peer_plan.py solve <dir>                         -> runner_solve.js
#   python3 peer_plan.py peer <dir> <solve.json>             -> answers.json (с правдой) и runner_peer.js
import json, os, sys, random
from peer_tasks import make, check, FAM

NO_TOOLS = 'Не используй никакие инструменты и не открывай файлы: рассуждай сам, опираясь только на текст ниже.'
HONEST = ('У задачи может не быть ни одного решения, а может быть много. Если решение есть, достаточно привести одно. '
          'Если решения нет, скажи «нет решения» и объясни почему.')


def bundle(D, tag, calls):
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'peer_runner.js')).read()
    head, body = src.split('\n// args:', 1)
    a = json.dumps(dict(part=tag, calls=calls), ensure_ascii=False)
    open(os.path.join(D, f'runner_{tag}.js'), 'w').write(head.replace("name: 'peer-runner'", f"name: 'peer-{tag}'") + f'\nconst ARGS = {a}\n// args:' + body.replace('args.', 'ARGS.'))
    json.dump(dict(calls=calls), open(os.path.join(D, f'calls_{tag}.json'), 'w'), ensure_ascii=False, indent=0)
    print(tag, len(calls), 'вызовов')


def solve_prompt(t):
    return (f'{NO_TOOLS}\n\nЗадача: {t["text"]}\n\n{HONEST}\n'
            'Верни: status — «решение» или «нет решения»; solution — решение в указанном формате JSON (пусто, если решения нет); '
            'argument — кратко, как нашёл решение или почему его нет (до 6 фраз); confidence — твоя вероятность того, что ответ полностью верен (от 0 до 1).')


def peer_prompt(t, a):
    ans = (f'Ответ: решение {a["solution"]}' if a['status'] == 'решение' else 'Ответ: нет решения') + f'\nОбоснование автора: {a["argument"]}'
    return (f'{NO_TOOLS}\n\nТы проверяешь чужое решение задачи. Задача: {t["text"]}\n\n{HONEST}\n\n{ans}\n\n'
            'Верен ли ответ? Если приведено решение — удовлетворяет ли оно всем условиям. Если заявлено «нет решения» — действительно ли решений нет. '
            'Верни: verdict — «верно» или «неверно»; p_correct — твоя вероятность того, что ответ верен (от 0 до 1); reason — кратко (до 4 фраз).')


def parse_sol(s):
    try:
        v = json.loads(s) if isinstance(s, str) and s.strip() else None
        return v
    except Exception:
        return None


if __name__ == '__main__':
    cmd, D = sys.argv[1], sys.argv[2]
    os.makedirs(D, exist_ok=True)
    if cmd == 'tasks':
        seed = int(sys.argv[3]); spec = [x.split(':') for x in sys.argv[4:]]
        ts = [make(f, w, seed + i) for i, (f, w) in enumerate(spec)]
        json.dump(ts, open(f'{D}/tasks.json', 'w'), ensure_ascii=False, indent=1)
        for t in ts: print(t['id'], t['n_solutions'])
    elif cmd == 'solve':
        ts = json.load(open(f'{D}/tasks.json'))
        bundle(D, 'solve', [dict(label=f'S:{t["id"]}', alias=f's{i:03d}', kind='solve', prompt=solve_prompt(t)) for i, t in enumerate(ts)])
    elif cmd == 'peer':
        ts = {t['id']: t for t in json.load(open(f'{D}/tasks.json'))}
        recs = json.load(open(sys.argv[3]))['records']
        answers, calls = [], []
        for t_id, t in ts.items():
            rs = [r for r in recs if r['label'] == f'S:{t_id}']; ok = [r for r in rs if not r.get('problem')]
            a = ((ok or rs or [{}])[-1].get('response')) or {}
            sol = parse_sol(a.get('solution'))
            correct = check(t, sol) if a.get('status') == 'решение' else (a.get('status') == 'нет решения' and t['n_solutions'] == 0)
            answers.append(dict(task=t_id, fam=t['fam'], want=t['want'], status=a.get('status'), solution=a.get('solution'), argument=a.get('argument'),
                                confidence=a.get('confidence'), correct=bool(correct)))
            for k in (1, 2, 3):
                calls.append(dict(label=f'P{k}:{t_id}', alias=f'p{len(calls):03d}', kind='peer', prompt=peer_prompt(t, a)))
        json.dump(answers, open(f'{D}/answers.json', 'w'), ensure_ascii=False, indent=1)
        for a in answers: print(a['task'], a['status'], a['correct'], a['confidence'])
        bundle(D, 'peer', calls)
