# EVO-06: «честная заявка оценщика» — отбор по одной выборке тестов, заявка C по другой (см. PREREG-EVO-06.md,
# решение совета docs/council/2026-09-26_EVO-06_session1.md). CPU-опыт, вызовов LLM нет.
# Мир EVO-01/03 (evo01.py, evo03.py): 300 программ, 150 поколений, задачи T1–T6, TOUR=5, элитизм.
# Истина T — доля верных элиты на 1000 скрытых входах (отбор их не видит). Заявка C — что оценщик говорит о T.
#
# Ветви (имя разбирается из строки; бюджет — размеченные входы и вызовы программ на поколение, оба пишутся в hist):
#   FIXED<n>      — n постоянных тестов на весь прогон (Гудхарт EVO-01; FIXED16 побитово = FIXED16 из EVO-01);
#   SAME<n>       — n свежих случайных тестов на поколение, отбор и заявка по ним же (SAME16 = RANDOM16/BASE);
#   SPLIT<k>+<m>  — отбор по k свежим, заявка элиты по ДРУГИМ m свежим из отдельного потока default_rng(3·10^6+seed);
#   AA<n>         — то же, что SAME<n>, но все потоки случайности (кроме скрытой правды) сдвинуты: контроль A/A;
#   RANDEVAL      — пол меры: оценщик случайный (ключ отбора и заявка — шум);
#   ORACLE        — потолок: отбор и заявка по 1000 скрытым (как в EVO-01).
# Совет: B0 = FIXED32, B1 = SAME32, B2 = SPLIT16+16, A/A = AA32; в единицах labels на поколение — 32 у всех трёх.
#
# В каждой записи hist: gen, claimed (заявка ветви), true (на 1000 скрытых), claimed_fresh (доля верных элиты на
# отдельной свежей выборке потока заявки; у SPLIT равна claimed), true_fresh (на другой независимой свежей выборке того же
# размера, поток 4·10^6+seed), n_labels (новых размеченных входов за поколение), n_calls (вызовов программ, потраченных
# оценщиком: отбор + заявка; измерительные вызовы для true/true_fresh/claimed_fresh у SAME/FIXED не считаются),
# elite_age (сколько поколений подряд эта же программа — элита; для пуллинга заявок в анализе).
# Потоки случайности: r — популяция и вариация (seed·1000 + номер задачи, как в EVO-01); r_sel — свежие тесты отбора
# (10^7 + seed·1000 + номер задачи); r_claim — выборка заявки (3·10^6 + seed); r_tf — выборка true_fresh (4·10^6 + seed);
# постоянные тесты — default_rng(2·10^6 + seed), как fixed в EVO-01. Выборка заявки не влияет на отбор: при подмене r_claim
# траектория популяции совпадает побитово (проверка — evo06_checks.py).
import sys, os, re, json, time, hashlib
import numpy as np
import evo03 as E3          # добавляет T4–T6 в E.TASKS
from evo03 import E
from truth import ioi

N_FRESH = 16                # размер измерительной свежей выборки (claimed_fresh / true_fresh) у ветвей без разделения
WINDOW = 30                 # окно «поздних» поколений для итоговых мер: последние 30 (121–150 при GENS=150)
GENS = int(os.environ.get('EVO06_GENS', E.GENS))    # укороченная длина — только для пилота


def parse_arm(arm):
    """→ (вид, n_sel, n_claim, сдвиг сидов)."""
    m = re.fullmatch(r'(FIXED|SAME|AA)(\d+)', arm)
    if m:
        return m.group(1), int(m.group(2)), 0, (500 if m.group(1) == 'AA' else 0)
    m = re.fullmatch(r'SPLIT(\d+)\+(\d+)', arm)
    if m:
        return 'SPLIT', int(m.group(1)), int(m.group(2)), 0
    if arm in ('RANDEVAL', 'ORACLE'):
        return arm, 0, 0, 0
    raise ValueError(f'неизвестная ветвь {arm}')


def run(task, arm, seed, tour=E.TOUR, claim_seed=None):
    kind, n_sel, n_claim, shift = parse_arm(arm)
    tn = int(task[1]); s = seed + shift
    f = E.TASKS[task]
    hid = np.random.default_rng(10 ** 6 + seed).integers(E.LO, E.HI + 1, 1000); yhid = f(hid)   # скрытая правда общая для всех ветвей
    r = np.random.default_rng(s * 1000 + tn)                                # популяция и вариация — как в EVO-01
    r_sel = np.random.default_rng(10 ** 7 + s * 1000 + tn)                  # свежие тесты отбора
    r_claim = np.random.default_rng(3 * 10 ** 6 + (s if claim_seed is None else claim_seed))   # выборка заявки
    r_tf = np.random.default_rng(4 * 10 ** 6 + s)                           # выборка true_fresh
    fixed = np.random.default_rng(2 * 10 ** 6 + s).integers(E.LO, E.HI + 1, max(n_sel, 1))
    pop = [E.rand_tree(r, 4) for _ in range(E.POP)]
    truth = lambda t: float((E.ev(t, hid) == yhid).mean())
    hist, prev_elite, age = [], None, 0
    for g in range(GENS + 1):
        # --- оценщик: ключ отбора и заявка ---
        if kind == 'FIXED':
            X = fixed; y = f(X); score = np.array([(E.ev(t, X) == y).mean() for t in pop]); key = score
            n_labels = n_sel if g == 0 else 0; n_calls = E.POP * n_sel
        elif kind in ('SAME', 'AA'):
            X = r_sel.integers(E.LO, E.HI + 1, n_sel); y = f(X)
            score = np.array([(E.ev(t, X) == y).mean() for t in pop]); key = score
            n_labels = n_sel; n_calls = E.POP * n_sel
        elif kind == 'SPLIT':
            X = r_sel.integers(E.LO, E.HI + 1, n_sel); y = f(X)
            score = np.array([(E.ev(t, X) == y).mean() for t in pop]); key = score
            n_labels = n_sel + n_claim; n_calls = E.POP * n_sel + n_claim
        elif kind == 'RANDEVAL':
            key = r_sel.random(E.POP); score = key
            n_labels = 0; n_calls = 0
        else:                                                               # ORACLE
            score = np.array([truth(t) for t in pop]); key = score
            n_labels = 1000 if g == 0 else 0; n_calls = E.POP * 1000
        best = int(np.argmax(key))
        # --- заявка ---
        m_fresh = n_claim if kind == 'SPLIT' else N_FRESH
        XC = r_claim.integers(E.LO, E.HI + 1, m_fresh)
        claimed_fresh = float((E.ev(pop[best], XC) == f(XC)).mean())
        claimed = claimed_fresh if kind == 'SPLIT' else float(score[best])
        XT = r_tf.integers(E.LO, E.HI + 1, m_fresh)
        true_fresh = float((E.ev(pop[best], XT) == f(XT)).mean())
        age = age + 1 if pop[best] == prev_elite else 0; prev_elite = pop[best]
        hist.append(dict(gen=g, claimed=claimed, true=truth(pop[best]), claimed_fresh=claimed_fresh, true_fresh=true_fresh,
                         n_labels=int(n_labels), n_calls=int(n_calls), elite_age=int(age)))
        if g == GENS: break
        # --- вариация: дословно EVO-01 (элитизм + турнир по ключу оценщика) ---
        new = [pop[best]]
        while len(new) < E.POP:
            i = max(r.integers(E.POP, size=tour), key=lambda k: key[k])
            if r.random() < 0.7:
                j = max(r.integers(E.POP, size=tour), key=lambda k: key[k]); c = E.cross(pop[i], pop[j], r)
            else:
                c = pop[i]
            if r.random() < 0.3: c = E.mutate(c, r)
            new.append(c)
        pop = new
    return hist


def late(hist, window=WINDOW):
    """Меры по окну последних `window` поколений (121–150 при 150 поколениях) и по всем поколениям."""
    h = hist[-window:]
    C = np.array([x['claimed'] for x in h]); T = np.array([x['true'] for x in h])
    CF = np.array([x['claimed_fresh'] for x in h]); TF = np.array([x['true_fresh'] for x in h])
    return dict(abs_ct_late=float(np.mean(np.abs(C - T))), signed_ct_late=float(np.mean(C - T)), ign_late=float(np.mean(1 - T)),
                ioi2_late=float(np.mean(1 - T) + np.mean(np.abs(C - T))), abs_cf_t_late=float(np.mean(np.abs(CF - T))),
                abs_cf_tf_late=float(np.mean(np.abs(CF - TF))), signed_cf_t_late=float(np.mean(CF - T)),
                true_late=float(np.mean(T)), claimed_late=float(np.mean(C)),
                abs_ct_all=float(np.mean([abs(x['claimed'] - x['true']) for x in hist])))


def code_hash():
    here = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    for fn in ('evo06.py', 'evo01.py', 'evo02.py', 'evo03.py', 'truth.py'):
        h.update(open(os.path.join(here, fn), 'rb').read())
    return h.hexdigest()[:12]


if __name__ == '__main__':
    task, arm, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    tour = int(sys.argv[4]) if len(sys.argv) > 4 else E.TOUR
    outdir = os.environ.get('EVO06_OUT', 'runs'); t0 = time.time()
    hist = run(task, arm, seed, tour)
    res = dict(task=task, arm=arm, seed=seed, tour=tour, gens=GENS, hist=hist, **ioi(hist), **late(hist),
               final_true=hist[-1]['true'], labels_total=int(sum(x['n_labels'] for x in hist)),
               calls_total=int(sum(x['n_calls'] for x in hist)), code=code_hash(), sec=round(time.time() - t0, 1))
    os.makedirs(outdir, exist_ok=True)
    name = f'{task}_{arm}_s{seed}' + (f'_tour{tour}' if tour != E.TOUR else '')
    json.dump(res, open(f'{outdir}/{name}.json', 'w'))
    print(task, arm, seed, 'ИОИ', round(res['ioi'], 3), '|C−T| поздн.', round(res['abs_ct_late'], 3), 'C−T', round(res['signed_ct_late'], 3),
          'незн.', round(res['ign_late'], 3), 'итог', round(res['final_true'], 3), 'labels', res['labels_total'], res['sec'], 'с', flush=True)
