# Турнир решателей (совет 19): руки при равных вызовах (4) и CPU (10 с на экземпляр): изоляция, самопродолжение, обмен кодом, обмен текстом.
#   python3 tourney.py stage <s>            → run/stage<s>.js (s = 1..4)
#   python3 tourney.py collect <s> <out.json>  → оценка кода голов на dev, run/state.json
#   python3 tourney.py final                → оценка итоговых программ рук на test (+ шум семени), run/final.json
import json, os, sys
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from core import run_solver
R = 2          # повторов каждой руки в пилоте
CPU = 10
RUN = os.path.join(HERE, os.environ.get('SOLV_RUN', 'run')); os.makedirs(RUN, exist_ok=True)
DEV = json.load(open(os.path.join(HERE, 'inst', 'dev.json')))
def J(p, d=None): return json.load(open(p)) if os.path.exists(p) else d
def W(p, o): json.dump(o, open(p, 'w'), ensure_ascii=False, indent=1)
STATE = os.path.join(RUN, 'state.json')

TASK = f"""Задача — множественный рюкзак. Даны n предметов (веса weights[i], ценности values[i]) и K рюкзаков с вместимостями caps[b]. Каждый предмет кладётся не больше чем в один рюкзак; суммарный вес в рюкзаке b не больше caps[b]. Цель — максимальная суммарная ценность уложенных предметов.
Напиши программу-решатель на Python 3 (только стандартная библиотека и numpy). Программа читает экземпляр из stdin — JSON-объект с полями cls="MKP", n, K, weights, values, caps — и печатает в stdout одну строку: JSON-список длины n, где элемент i — номер рюкзака 0..K−1 или −1, если предмет не взят. Первый аргумент командной строки (sys.argv[1]) — целое зерно случайности.
Условия запуска: один процесс, лимит процессорного времени {CPU} секунд на экземпляр (при превышении процесс убивается и решение не засчитывается — печатай ответ заранее, следи за time.process_time()), память 1 ГБ, сети и файлов нет. Недопустимое решение (перегруз, неверная длина) даёт 0.
Оценивают решатель на скрытых экземплярах того же распределения (n = 250, K = 6, веса 10–1000, ценности коррелированы с весами, суммарная вместимость ≈ половина суммарного веса). Для проверки у тебя есть 3 открытых экземпляра (ниже, JSON-список). Сравнение — по суммарной ценности; соперники — другие решатели."""
def base(tag):
    return (f"Ты — участник турнира решателей. {TASK}\n\nРаботай только в своём каталоге /tmp/solv/{tag} (создай его; положи туда открытые экземпляры из текста ниже и свой решатель; запускай его сколько хочешь). "
            "Не открывай другие файлы и каталоги (ни репозиторий, ни /root) — это нарушение турнира. Готовые решатели из интернета и pip не устанавливай.\n\n"
            f"Открытые экземпляры (JSON):\n{json.dumps(DEV)}\n\n")
TAIL = ("Верни: code — полный текст программы-решателя; notes — коротко (до 150 слов): какой метод, что пробовал, что сработало, что нет.")
def fmt_score(sc): return ', '.join(str(v) for v in sc['dev']) + f" (сумма {sum(sc['dev'])})"
def prompt_fresh(tag): return base(tag) + TAIL
def prompt_self(tag, own):
    return (base(tag) + f"Это твоя следующая попытка. Твой лучший решатель на сейчас (ценности на открытых экземплярах: {fmt_score(own)}):\n```python\n{own['code']}\n```\n"
            f"Твои заметки к нему: {own.get('notes', '')}\n\nСделай решатель лучше.\n\n" + TAIL)
def prompt_ex(tag, own, opp, text_only):
    o = (f"Лучший решатель соперника (ценности на открытых экземплярах: {fmt_score(opp)}):\n```python\n{opp['code']}\n```\nЕго заметки: {opp.get('notes', '')}\n"
         if not text_only else f"Соперник описал свой лучший решатель так (ценности на открытых экземплярах: {fmt_score(opp)}): {opp.get('notes', '')}\n")
    return (base(tag) + f"Это второй раунд турнира. Твой решатель первого раунда (ценности: {fmt_score(own)}):\n```python\n{own['code']}\n```\nТвои заметки: {own.get('notes', '')}\n\n"
            + o + "\nСделай решатель, который превзойдёт оба.\n\n" + TAIL)
SCHEMA = {'type': 'object', 'properties': {'code': {'type': 'string'}, 'notes': {'type': 'string'}}, 'required': ['code', 'notes']}

def best(entries): return max(entries, key=lambda e: (e.get('ok_all', False), sum(e['dev']))) if entries else None
def stage(s):
    st = J(STATE, {}); jobs = []
    for rep in range(R):
        if s == 1:
            for i in range(4): jobs.append((f'iso{rep}_{i}', prompt_fresh(f'iso{rep}_{i}')))
            jobs.append((f'self{rep}_1', prompt_fresh(f'self{rep}_1')))
            for arm in ('ex', 'tx'):
                for h in 'ab': jobs.append((f'{arm}{rep}{h}_1', prompt_fresh(f'{arm}{rep}{h}_1')))
        else:
            own = best([st[k] for k in st if k.startswith(f'self{rep}_')])
            jobs.append((f'self{rep}_{s}', prompt_self(f'self{rep}_{s}', own)))
            if s == 2:
                for arm in ('ex', 'tx'):
                    A, B = st[f'{arm}{rep}a_1'], st[f'{arm}{rep}b_1']
                    jobs.append((f'{arm}{rep}a_2', prompt_ex(f'{arm}{rep}a_2', A, B, arm == 'tx')))
                    jobs.append((f'{arm}{rep}b_2', prompt_ex(f'{arm}{rep}b_2', B, A, arm == 'tx')))
    js = [dict(id=i, prompt=p) for i, p in jobs]
    src = (f"export const meta = {{ name: 'solvers-stage{s}', description: 'Турнир решателей, этап {s}', phases: [{{ title: 'Ход' }}] }}\n"
           f"const JOBS = {json.dumps(js, ensure_ascii=False)}\nconst S = {json.dumps(SCHEMA)}\nphase('Ход')\n"
           "const res = await parallel(JOBS.map(j => () => agent(j.prompt, {label: j.id, phase: 'Ход', schema: S})))\n"
           "const out = {}\nJOBS.forEach((j, i) => { out[j.id] = res[i] })\nreturn {out}\n")
    open(os.path.join(RUN, f'stage{s}.js'), 'w').write(src); print('этап', s, 'вызовов', len(js), 'байт', len(src.encode()))

def eval_one(args):
    code, inst, seed = args
    r = run_solver(code, inst, CPU, args=(seed,)); return r['value'] if r['ok'] else 0, r['ok'], r.get('err')
def collect(s, path):
    d = J(path); out = d.get('out', d); st = J(STATE, {})
    todo = [(k, v) for k, v in out.items() if v and v.get('code')]
    with ProcessPoolExecutor(3) as ex:
        for k, v in todo:
            res = list(ex.map(eval_one, [(v['code'], inst, 0) for inst in DEV]))
            st[k] = dict(code=v['code'], notes=v.get('notes', ''), dev=[x[0] for x in res], ok_all=all(x[1] for x in res), errs=[x[2] for x in res if x[2]], stage=s)
            print(k, st[k]['dev'], st[k]['ok_all'], st[k]['errs'][:1], flush=True)
    for k, v in out.items():
        if not (v and v.get('code')): st[k] = dict(code='', notes='', dev=[0, 0, 0], ok_all=False, errs=['нет ответа'], stage=s)
    W(STATE, st)
def arm_final(st, rep):
    return {'iso': best([st[k] for k in st if k.startswith(f'iso{rep}_')]), 'self': best([st[k] for k in st if k.startswith(f'self{rep}_')]),
            'ex': best([st[k] for k in st if k.startswith(f'ex{rep}')]), 'tx': best([st[k] for k in st if k.startswith(f'tx{rep}')])}
def final():
    st = J(STATE); test = json.load(open(os.path.join(HERE, 'inst', 'test.json'))); res = {}
    with ProcessPoolExecutor(3) as ex:
        for rep in range(R):
            for arm, e in arm_final(st, rep).items():
                vals = {}
                for seed in (0, 1, 2):
                    rr = list(ex.map(eval_one, [(e['code'], inst, seed) for inst in test]))
                    vals[seed] = [x[0] for x in rr]
                res[f'{arm}{rep}'] = dict(values=vals, dev=e['dev'])
                print(arm, rep, sum(vals[0]), flush=True)
    W(os.path.join(RUN, 'final.json'), res)
if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'stage': stage(int(sys.argv[2]))
    elif c == 'collect': collect(int(sys.argv[2]), sys.argv[3])
    elif c == 'final': final()
