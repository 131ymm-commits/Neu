"""CHILD-01 (опыт О1 «Детство»): сколько экзамена нужно показателю и чистит ли экзамен завышение.
Мир EVO-01 без изменений: 300 программ, 150 поколений, элитизм, турнир 5, скрещивание 0,7, мутация 0,3.
Меняется только ключ отбора по поколениям.
  Показатель — доля верных на 16 постоянных тестах (как FIXED16). Экзамен — доля верных на свежих случайных тестах.
Ветви (имя → правило):
  FIX            показатель всегда (q = 0); побитово совпадает с FIXED16 из EVO-01
  RND            экзамен всегда, 16 тестов (q = 1)
  ALT_<p>        экзамен в доле q поколений, равномерно по времени; p — проценты: 6 → 1/16, 12 → 1/8, 25, 50, 75
  NOISE_<p>      как ALT, но в «экзаменационных» поколениях ключ отбора — случайные числа (контроль на неспецифичность)
  MIX_<p>        каждое поколение ключ = (1 − f)·показатель + f·(доля верных на 16·f свежих тестах)
  FINAL_<p>      показатель первые (1 − q)·150 поколений, затем экзамен до конца («экзамен в конце детства»)
  RND4           экзамен всегда, 4 теста
  ALT_6_N64      экзамен в 1/16 поколений, 64 теста
  ALT_25_T20     как ALT_25, но в экзаменационных поколениях турнир 20
Меры пишутся каждое поколение во всех ветвях одинаково; измерительные тесты берутся из отдельного потока и на отбор не влияют.
  python3 child01.py <задача> <ветвь> <сид> [каталог]"""
import sys, os, re, json, time, hashlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evo03 as E3            # добавляет T4–T6 в E.TASKS
from evo03 import E
from truth import ioi

POP, GENS, TOUR, N_FIX = E.POP, E.GENS, E.TOUR, 16
QS = {'6': 1 / 16, '12': 1 / 8, '25': 1 / 4, '50': 1 / 2, '75': 3 / 4}
WINDOWS = ((1, 30), (31, 60), (61, 90), (91, 120), (121, 150))


def parse_arm(arm):
    if arm == 'FIX': return dict(kind='FIX', q=0.0, n=16, tour_exam=TOUR)
    if arm == 'RND': return dict(kind='ALT', q=1.0, n=16, tour_exam=TOUR)
    if arm == 'RND4': return dict(kind='ALT', q=1.0, n=4, tour_exam=TOUR)
    m = re.fullmatch(r'(ALT|NOISE|MIX|FINAL)_(6|12|25|50|75)(?:_N(\d+))?(?:_T(\d+))?', arm)
    if not m: raise ValueError(f'неизвестная ветвь {arm}')
    kind, q = m.group(1), QS[m.group(2)]
    n = int(m.group(3)) if m.group(3) else (int(round(16 * q)) if kind == 'MIX' else 16)
    if (m.group(3) or m.group(4)) and kind != 'ALT': raise ValueError(f'_N и _T только у ALT: {arm}')
    return dict(kind=kind, q=q, n=n, tour_exam=int(m.group(4)) if m.group(4) else TOUR)


def is_exam(g, spec):
    """Экзаменационное ли поколение g (по его ключу отбирают родителей поколения g + 1)."""
    k, q = spec['kind'], spec['q']
    if k == 'FIX' or k == 'MIX': return False
    if k == 'FINAL': return g >= GENS * (1 - q)
    return int((g + 1) * q + 1e-9) > int(g * q + 1e-9)          # ALT, NOISE: равномерно, доля q


def tour_p(key, k):
    """Вероятность быть выбранным в турнире размера k (ничьи делятся поровну). Сумма равна 1."""
    key = np.asarray(key, float); N = len(key); o = np.sort(key)
    lt = np.searchsorted(o, key, 'left'); le = np.searchsorted(o, key, 'right')
    return ((le / N) ** k - (lt / N) ** k) / (le - lt)


def corr(a, b):
    sa, sb = a.std(), b.std()
    return float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb)) if sa > 1e-12 and sb > 1e-12 else None


def gradients(p, T, I):
    """Частные градиенты отбора (Lande & Arnold 1983) в слое T > 0: МНК относительной приспособленности w = p / mean(p) на T и I со свободным членом.
    Возвращает (β_T, β_I, sd_T, sd_I, n) или None, если слой мал или один из признаков в нём постоянен. Случайных чисел не берёт."""
    m = T > 0; n = int(m.sum())
    if n < 10: return None
    t, i = T[m], I[m]; st, si = float(t.std()), float(i.std())
    if st < 1e-9 or si < 1e-9: return None
    w = p[m] / p[m].mean()
    A = np.column_stack([np.ones(n), t, i])
    try: b = np.linalg.lstsq(A, w, rcond=None)[0]
    except np.linalg.LinAlgError: return None
    return float(b[1]), float(b[2]), st, si, n


def run(task, arm, seed):
    spec = parse_arm(arm); tn = int(task[1]); f = E.TASKS[task]
    hid = np.random.default_rng(10 ** 6 + seed).integers(E.LO, E.HI + 1, 1000)        # скрытая правда — как в EVO-01
    fixed = np.random.default_rng(2 * 10 ** 6 + seed).integers(E.LO, E.HI + 1, N_FIX)  # постоянные тесты — как FIXED16
    r = np.random.default_rng(seed * 1000 + tn)                                         # популяция и вариация — как в EVO-01
    r_exam = np.random.default_rng(10 ** 7 + seed * 1000 + tn)                          # свежие тесты экзамена
    r_meas = np.random.default_rng(5 * 10 ** 6 + seed * 1000 + tn)                      # измерительные свежие тесты (на отбор не влияют)
    r_noise = np.random.default_rng(6 * 10 ** 6 + seed * 1000 + tn)                     # случайный ключ ветви NOISE
    out_x = np.concatenate([np.arange(-300, -100), np.arange(101, 301)])                # входы вне обучающего диапазона
    XC = np.concatenate([fixed, hid]); YC = f(XC); y_out = f(out_x)
    pop = [E.rand_tree(r, 4) for _ in range(POP)]
    cache, cache_out = {}, {}
    S = {k: [] for k in ('c_key', 't_key', 'c_fix', 't_fix', 'cm_key', 'c_eb', 'to_key', 'mT', 'mI', 'uniq')}
    G = {k: [] for k in ('SP_T', 'SP_I', 'SE_T', 'SE_I', 'V_T', 'V_I', 'C_TI', 'rho_fix', 'rho_ex')}
    B = {k: [] for k in ('bE_T', 'bE_I', 'bP_T', 'bP_I', 'sd_T', 'sd_I', 'n1')}          # градиенты в слое T > 0, по поколениям
    kinds, labels = [], 0
    for g in range(GENS + 1):
        exam = is_exam(g, spec)
        need_fresh = exam and spec['kind'] in ('ALT', 'FINAL') or spec['kind'] == 'MIX'
        Xm = r_meas.integers(E.LO, E.HI + 1, 16)
        Xe = r_exam.integers(E.LO, E.HI + 1, spec['n']) if need_fresh else np.zeros(0, int)
        XF = np.concatenate([Xm, Xe]); YF = f(XF)
        cfix = np.empty(POP); T = np.empty(POP); cm = np.empty(POP); ce = np.empty(POP); fresh = {}
        for i, t in enumerate(pop):
            if t not in cache:
                v = E.ev(t, XC) == YC; cache[t] = (float(v[:N_FIX].mean()), float(v[N_FIX:].mean()))
            if t not in fresh:
                v = E.ev(t, XF) == YF; fresh[t] = (float(v[:16].mean()), float(v[16:].mean()) if len(Xe) else 0.0)
            cfix[i], T[i] = cache[t]; cm[i], ce[i] = fresh[t]
        if spec['kind'] == 'MIX': key = (1 - spec['q']) * cfix + spec['q'] * ce; kind = 'M'; labels += spec['n']
        elif exam and spec['kind'] == 'NOISE': key = r_noise.random(POP); kind = 'N'
        elif exam: key = ce; kind = 'E'; labels += spec['n']
        else: key = cfix; kind = 'P'
        tour = spec['tour_exam'] if kind == 'E' else TOUR
        best = int(np.argmax(key)); bfix = int(np.argmax(cfix))
        # --- меры (одинаковые во всех ветвях) ---
        I = cfix - T
        pP, pE = tour_p(cfix, TOUR), tour_p(cm, TOUR)                        # отбор по показателю и по свежим 16 тестам
        G['SP_T'].append(float(pP @ T - T.mean())); G['SP_I'].append(float(pP @ I - I.mean()))
        G['SE_T'].append(float(pE @ T - T.mean())); G['SE_I'].append(float(pE @ I - I.mean()))
        G['V_T'].append(float(T.var())); G['V_I'].append(float(I.var())); G['C_TI'].append(float(((T - T.mean()) * (I - I.mean())).mean()))
        G['rho_fix'].append(corr(cfix, T)); G['rho_ex'].append(corr(cm, T))
        gE, gP = gradients(pE, T, I), gradients(pP, T, I)
        for k, v in (('bE_T', gE and gE[0]), ('bE_I', gE and gE[1]), ('bP_T', gP and gP[0]), ('bP_I', gP and gP[1]),
                     ('sd_T', gE and gE[2]), ('sd_I', gE and gE[3]), ('n1', gE and gE[4])): B[k].append(v)
        c_key = float(key[best]) if kind in ('P', 'E', 'M') else float(cfix[best])
        # заявка с усадкой (эмпирический Байес по популяции этого поколения, формула Келли): только мера
        s = ce if kind == 'E' else cfix; n_s = spec['n'] if kind == 'E' else N_FIX
        mu, vs = float(s.mean()), float(s.var())
        vp = max(0.0, (vs - mu * (1 - mu) / n_s) / (1 - 1 / n_s)) if n_s > 1 else 0.0
        c_eb = mu + (vp / vs if vs > 1e-12 else 0.0) * (float(s[best]) - mu)
        tb = pop[best]
        if tb not in cache_out: cache_out[tb] = float((E.ev(tb, out_x) == y_out).mean())
        for k, v in (('c_key', c_key), ('t_key', float(T[best])), ('c_fix', float(cfix[bfix])), ('t_fix', float(T[bfix])), ('cm_key', float(cm[best])),
                     ('c_eb', float(c_eb)), ('to_key', cache_out[tb]), ('mT', float(T.mean())), ('mI', float(I.mean())), ('uniq', len(fresh))):
            S[k].append(v)
        kinds.append(kind)
        if g == GENS: break
        # --- вариация: дословно EVO-01 (элитизм + турнир по ключу) ---
        new = [pop[best]]
        while len(new) < POP:
            i = max(r.integers(POP, size=tour), key=lambda k: key[k])
            if r.random() < 0.7:
                j = max(r.integers(POP, size=tour), key=lambda k: key[k]); c = E.cross(pop[i], pop[j], r)
            else:
                c = pop[i]
            if r.random() < 0.3: c = E.mutate(c, r)
            new.append(c)
        pop = new
    hist = [dict(gen=g, claimed=S['c_key'][g], true=S['t_key'][g]) for g in range(GENS + 1)]
    win = {k: [(None if any(x is None for x in v[a:b + 1]) else round(float(np.mean(v[a:b + 1])), 6)) for a, b in WINDOWS] for k, v in G.items()}
    r6 = lambda v: [None if x is None else round(float(x), 6) for x in v]
    return dict(task=task, arm=arm, seed=seed, spec=spec, kinds=''.join(kinds), labels_total=labels,
                series={k: [round(x, 5) for x in v] for k, v in S.items()}, win=win, **ioi(hist),
                gser={k: r6(v) for k, v in G.items()}, grad={k: r6(v) for k, v in B.items()})


def code_hash():
    h = hashlib.sha256()
    for fn in ('child01.py', 'evo01.py', 'evo02.py', 'evo03.py', 'truth.py'): h.update(open(os.path.join(HERE, fn), 'rb').read())
    return h.hexdigest()[:12]


if __name__ == '__main__':
    task, arm, seed = sys.argv[1], sys.argv[2], int(sys.argv[3]); outdir = sys.argv[4] if len(sys.argv) > 4 else os.path.join(HERE, 'runs')
    t0 = time.time(); res = run(task, arm, seed); res['code'] = code_hash(); res['sec'] = round(time.time() - t0, 1)
    os.makedirs(outdir, exist_ok=True); name = os.path.join(outdir, f'{task}_{arm}_s{seed}.json')
    with open(name + '.tmp', 'w') as fh: json.dump(res, fh)
    os.replace(name + '.tmp', name)
    s = res['series']; late = slice(121, 151)
    print(task, arm, seed, 'завышение показателя поздно', round(float(np.mean(np.array(s['c_fix'][late]) - np.array(s['t_fix'][late]))), 3),
          'правда элиты поздно', round(float(np.mean(s['t_key'][late])), 3), res['sec'], 'с', flush=True)
