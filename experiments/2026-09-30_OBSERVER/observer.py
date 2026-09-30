# «Наблюдатель» (совет 22): эмуляция автора-оценщика. Правда — настоящие ответы автора (вне репозитория).
#   python3 observer.py build <from> <to>      → run/obs_<from>_<to>.js (руки: одна голова / голова с эталонами)
#   python3 observer.py score <out.json>...    → run/scores.json (логпотеря против последовательной базы и «Ганса»)
import json, os, sys, re, math, hashlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from label import label
SECRET = '/root/observer_secret_all.json'; RUN = os.path.join(HERE, 'run'); os.makedirs(RUN, exist_ok=True)
CLS = ['ACCEPT', 'REJECT', 'OTHER']; K_EX = 15; MSG_MAX = 3000; EX_MSG = 500
BRIEF = ("Автор — русскоязычный исследователь, ведёт проект Neu: «сильный ИИ как система взаимодействия голов Claude». Claude (ассистент) ставит опыты, "
         "совет из голов Claude проектирует и оценивает их, автор смотрит сообщения Claude и отвечает коротко: соглашается («да», «делай», «запускай», «продолжи»), "
         "отказывает и поворачивает («нет, не туда…»), даёт новое задание или идею, задаёт вопрос.")
def load(): d = json.load(open(SECRET)); return d['canary'], d['pairs']
def cut(s, n): s = (s or '').strip(); return s if len(s) <= n else s[:n] + ' […]'
def prompt(i, P, exemplars):
    p = P[i]; ex = ''
    if exemplars:
        E = P[max(0, i - K_EX):i]
        ex = ("\n\nЭталоны — прошлые пары «сообщение Claude → ответ автора», по времени до этого момента (самые свежие — в конце):\n" +
              '\n'.join(f"--- Claude: {cut(e['prev_assistant'], EX_MSG)}\n    Автор: {e['human']}" for e in E))
    return (f"Ты — «Наблюдатель»: эмулируешь конкретного человека-оценщика и предсказываешь, как он ответит на сообщение. Не используй инструменты, не открывай файлы — отвечай только по тексту ниже.\n\n{BRIEF}{ex}\n\n"
            f"Сообщение Claude, на которое автор сейчас ответит:\n-----\n{cut(p['prev_assistant'], MSG_MAX)}\n-----\n\n"
            "Классы ответа: ACCEPT — согласие/продолжение без возражения (начинается с «да», «ок», «делай», «запускай», «продолжи» и т. п.); REJECT — отказ или поворот («нет…», «не туда», «не так»); "
            "OTHER — новое задание, идея, вопрос, прочее. Верни p_accept, p_reject, p_other (сумма 1), predicted_reply — твоя лучшая догадка текста ответа в его стиле (1–2 фразы).")
SCHEMA = {'type': 'object', 'properties': {'p_accept': {'type': 'number'}, 'p_reject': {'type': 'number'}, 'p_other': {'type': 'number'}, 'predicted_reply': {'type': 'string'}},
          'required': ['p_accept', 'p_reject', 'p_other', 'predicted_reply']}
def build(a, b):
    can, P = load(); jobs = []
    for i in range(a, b):
        for arm in ('solo', 'ex'): jobs.append(dict(id=f'{i}|{arm}', prompt=prompt(i, P, arm == 'ex')))
    assert not any(can in j['prompt'] for j in jobs) and not any(P[int(j['id'].split('|')[0])]['human'] in j['prompt'].split('Сообщение Claude, на которое автор сейчас ответит')[1] for j in jobs if len(P[int(j['id'].split('|')[0])]['human']) > 25)
    src = (f"export const meta = {{ name: 'observer-{a}-{b}', description: 'Наблюдатель: пары {a}–{b - 1}, одна голова и голова с эталонами', phases: [{{ title: 'Ход' }}] }}\n"
           f"const JOBS = {json.dumps(jobs, ensure_ascii=False)}\nconst S = {json.dumps(SCHEMA)}\nphase('Ход')\n"
           "const res = await parallel(JOBS.map(j => () => agent(j.prompt, {label: j.id, phase: 'Ход', schema: S})))\n"
           "const out = {}\nJOBS.forEach((j, i) => { out[j.id] = res[i] })\nreturn {out}\n")
    f = os.path.join(RUN, f'obs_{a}_{b}.js'); open(f, 'w').write(src)
    print('вызовов', len(jobs), 'байт', len(src.encode()), 'sha', hashlib.sha256(src.encode()).hexdigest()[:16])

# ---- базы ----
ACT = re.compile(r'(запуска|запущу|начну|рекоменду|скажете|если да|делать\?|продолжать\?|согласны|предлагаю)', re.I)
def feats(p, prev_label):
    m = p['prev_assistant'] or ''
    return [math.log(1 + len(m)), float(m.rstrip().endswith('?')), float(bool(ACT.search(m))), float(len(re.findall(r'^\s*(?:[-*•]|\d+[.)])\s', m, re.M)) / 10),
            float(prev_label == 'ACCEPT'), float(prev_label == 'REJECT')]
def seq_base(Y, i):
    c = [1 + sum(y == k for y in Y[:i]) for k in CLS]; s = sum(c); return [x / s for x in c]
def hans(X, Y, i, lam=1.0, use_prev=True):
    if i < 5: return seq_base(Y, i)
    Xa = np.array(X[:i]) if use_prev else np.array(X[:i])[:, :4]; x = np.array(X[i]) if use_prev else np.array(X[i])[:4]
    mu, sd = Xa.mean(0), Xa.std(0) + 1e-6; Xa = (Xa - mu) / sd; x = (x - mu) / sd
    Yo = np.zeros((i, 3)); Yo[np.arange(i), [CLS.index(y) for y in Y[:i]]] = 1
    Wt = np.zeros((Xa.shape[1] + 1, 3)); Xb = np.hstack([Xa, np.ones((i, 1))])
    for _ in range(500):
        Z = Xb @ Wt; Z -= Z.max(1, keepdims=True); Pm = np.exp(Z); Pm /= Pm.sum(1, keepdims=True)
        G = Xb.T @ (Pm - Yo) / i + lam * np.vstack([Wt[:-1], np.zeros((1, 3))]) / i; Wt -= 0.5 * G
    z = np.append(x, 1) @ Wt; z -= z.max(); q = np.exp(z); q /= q.sum(); return list(q)
def ll(p, y, eps=1e-3):
    q = max(eps, p[CLS.index(y)]); return -math.log(q)
def score(paths):
    can, P = load(); Y = [label(p['human']) for p in P]
    X = [feats(p, Y[i - 1] if i else None) for i, p in enumerate(P)]
    out = {}
    for f in paths:
        d = json.load(open(f)); out.update(d.get('out', d))
    rows = []
    for key, v in out.items():
        i, arm = key.split('|'); i = int(i)
        if not v: continue
        s = sum(max(0, v[k]) for k in ('p_accept', 'p_reject', 'p_other')) or 1
        pe = [max(0, v['p_accept']) / s, max(0, v['p_reject']) / s, max(0, v['p_other']) / s]
        leak = can in json.dumps(v, ensure_ascii=False)
        rows.append(dict(i=i, arm=arm, y=Y[i], p=pe, ll=ll(pe, Y[i]), ll_seq=ll(seq_base(Y, i), Y[i]), ll_hans=ll(hans(X, Y, i), Y[i]), ll_hans4=ll(hans(X, Y, i, use_prev=False), Y[i]),
                         leak=leak, pred=v.get('predicted_reply', '')))
    json.dump(rows, open(os.path.join(RUN, 'scores.json'), 'w'), ensure_ascii=False, indent=1)
    for arm in ('solo', 'ex'):
        R = [r for r in rows if r['arm'] == arm]
        if not R: continue
        m = lambda k: sum(r[k] for r in R) / len(R)
        print(arm, 'n', len(R), 'логпотеря', round(m('ll'), 3), 'посл.база', round(m('ll_seq'), 3), 'Ганс', round(m('ll_hans'), 3), 'Ганс-4', round(m('ll_hans4'), 3), 'утечек', sum(r['leak'] for r in R))
if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'build': build(int(sys.argv[2]), int(sys.argv[3]))
    elif c == 'score': score(sys.argv[2:])
