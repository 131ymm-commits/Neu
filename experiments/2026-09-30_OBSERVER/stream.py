# Проспективный поток «Наблюдателя» по решению совета 23 (PREREG-OBSERVER-STREAM.md).
#   python3 stream.py seal <id> <сообщение.md>   → run/stream_<id>.js (одна голова ex) + prospective/<id>_bases.json (базы и хеши — до ответа)
#   python3 stream.py record <id> <out.json>      → prospective/<id>.json (прогноз головы; коммитится ДО отправки сообщения)
#   python3 stream.py outcome <id> "<ответ автора>"  → метка кодом label.py (прогноз ему не передаётся), журнал и e-процессы → prospective/ledger.json
import json, os, sys, hashlib, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from label import label
from observer import BRIEF, SCHEMA, K_EX, EX_MSG, MSG_MAX, cut, feats, hans, CLS
SECRET = '/root/observer_secret_all.json'; HIST = '/root/observer_stream_history.json'; PRO = os.path.join(HERE, 'prospective'); RUN = os.path.join(HERE, 'run')
SYS = ('This session', 'Another Claude session', 'Your response above was stopped', '[Your previous response', 'Continue from where you left off', '[Request interrupted')
GRID = [0, .25, .5, .75, 1]
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def clean_pairs():
    """фильтр ERRORS №57 в коде: системные тексты и дубль (80) вон"""
    P = json.load(open(SECRET))['pairs']
    return [dict(human=p['human'], prev_assistant=p['prev_assistant']) for p in P if not p['human'].lstrip().startswith(SYS) and p['i'] != 80]
def history():
    H = clean_pairs()
    if os.path.exists(HIST): H += json.load(open(HIST))
    return H
def prompt(H, msg):
    E = H[-K_EX:]
    ex = ("\n\nЭталоны — прошлые пары «сообщение Claude → ответ автора», по времени до этого момента (самые свежие — в конце):\n" +
          '\n'.join(f"--- Claude: {cut(e['prev_assistant'], EX_MSG)}\n    Автор: {e['human']}" for e in E))
    return (f"Ты — «Наблюдатель»: эмулируешь конкретного человека-оценщика и предсказываешь, как он ответит на сообщение. Не используй инструменты, не открывай файлы — отвечай только по тексту ниже.\n\n{BRIEF}{ex}\n\n"
            f"Сообщение Claude, на которое автор сейчас ответит:\n-----\n{cut(msg, MSG_MAX)}\n-----\n\n"
            "Классы ответа: ACCEPT — согласие/продолжение без возражения (начинается с «да», «ок», «делай», «запускай», «продолжи» и т. п.); REJECT — отказ или поворот («нет…», «не туда», «не так»); "
            "OTHER — новое задание, идея, вопрос, прочее. Верни p_accept, p_reject, p_other (сумма 1), predicted_reply — твоя лучшая догадка текста ответа в его стиле (1–2 фразы).")
def bases(H, msg):
    Y = [label(h['human']) for h in H]; n = len(Y)
    freq = [(1 + sum(y == k for y in Y)) / (n + 3) for k in CLS]
    prev = Y[-1]; T = [Y[j + 1] for j in range(n - 1) if Y[j] == prev]
    markov = [(1 + sum(y == k for y in T)) / (len(T) + 3) for k in CLS]
    X = [feats(h, Y[j - 1] if j else None) for j, h in enumerate(H)] + [feats(dict(prev_assistant=msg), prev)]
    hn = [float(x) for x in hans(X, Y + ['OTHER'], n)]   # метка-заглушка для n не используется (обучение на j < n)
    return dict(freq=freq, markov=markov, hans=hn, n_hist=n, prev=prev)
def seal(pid, path):
    msg = open(path).read(); H = history(); p = prompt(H, msg)
    assert json.load(open(SECRET))['canary'] not in p
    src = (f"export const meta = {{ name: 'observer-stream-{pid}', description: 'Наблюдатель: запечатанная догадка {pid}', phases: [{{ title: 'Ход' }}] }}\n"
           f"const P = {json.dumps(p, ensure_ascii=False)}\nconst S = {json.dumps(SCHEMA)}\nphase('Ход')\n"
           "const r = await agent(P, {label: 'stream', phase: 'Ход', schema: S})\nreturn {out: r}\n")
    open(os.path.join(RUN, f'stream_{pid}.js'), 'w').write(src)
    b = bases(H, msg); b.update(id=pid, message_sha256=sha(msg), prompt_sha256=sha(p), code_sha256={f: sha(open(os.path.join(HERE, f)).read()) for f in ('stream.py', 'observer.py', 'label.py')})
    json.dump(b, open(os.path.join(PRO, f'{pid}_bases.json'), 'w'), ensure_ascii=False, indent=1); print(json.dumps(b, ensure_ascii=False))
def record(pid, path):
    d = json.load(open(path)); r = d.get('out', d); s = sum(max(0, r[k]) for k in ('p_accept', 'p_reject', 'p_other'))
    r['p'] = [max(0, r[k]) / s for k in ('p_accept', 'p_reject', 'p_other')]
    json.dump(dict(id=pid, **r), open(os.path.join(PRO, f'{pid}.json'), 'w'), ensure_ascii=False, indent=1); print(r)
def bern(p, hit): return p if hit else 1 - p
def ledger():
    L = []; k = 1
    while True:
        pid = f'p{k:03d}'; k += 1
        if pid == 'p001': continue          # пилот, исключён (совет 23, п. 6)
        f = os.path.join(PRO, f'{pid}_outcome.json')
        if not os.path.exists(f): break
        L.append((json.load(open(os.path.join(PRO, f'{pid}.json'))), json.load(open(os.path.join(PRO, f'{pid}_bases.json'))), json.load(open(f))))
    res = dict(n=len(L), n_reject=sum(o['label'] == 'REJECT' for _, _, o in L))
    # задача A: REJECT против остального; задача B: OTHER против ACCEPT среди не-отказов. Смесь по сетке весов «голова + частота», равномерно.
    for task in ('A', 'B'):
        E = {}
        for bn in ('freq', 'hans', 'markov'):
            e_w = []
            for w in GRID:
                lr = 0.0
                for h, b, o in L:
                    y = o['label']
                    if task == 'A':
                        ph = w * h['p'][1] + (1 - w) * b['freq'][1]; pb = b[bn][1]; hit = y == 'REJECT'
                    else:
                        if y == 'REJECT': continue
                        f = lambda q: q[2] / (q[0] + q[2]); ph = w * f(h['p']) + (1 - w) * f(b['freq']); pb = f(b[bn]); hit = y == 'OTHER'
                    lr += math.log(bern(ph, hit)) - math.log(bern(pb, hit))
                e_w.append(math.exp(lr))
            E[bn] = sum(e_w) / len(e_w)
        res[task] = dict(e=E, e_min=min(E.values()), confirmed=min(E.values()) >= 20)
    json.dump(res, open(os.path.join(PRO, 'ledger.json'), 'w'), ensure_ascii=False, indent=1); print(json.dumps(res, ensure_ascii=False))
def outcome(pid, reply):
    msg_sha = json.load(open(os.path.join(PRO, f'{pid}_bases.json')))['message_sha256']
    y = label(reply); json.dump(dict(id=pid, reply=reply, label=y), open(os.path.join(PRO, f'{pid}_outcome.json'), 'w'), ensure_ascii=False, indent=1)
    msg = open(os.path.join(PRO, f'{pid}_message.md')).read(); assert sha(msg) == msg_sha
    H = json.load(open(HIST)) if os.path.exists(HIST) else []; H.append(dict(human=reply, prev_assistant=msg)); json.dump(H, open(HIST, 'w'), ensure_ascii=False)
    ledger()
if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'seal': seal(sys.argv[2], sys.argv[3])
    elif c == 'record': record(sys.argv[2], sys.argv[3])
    elif c == 'outcome': outcome(sys.argv[2], sys.argv[3])
    elif c == 'ledger': ledger()
