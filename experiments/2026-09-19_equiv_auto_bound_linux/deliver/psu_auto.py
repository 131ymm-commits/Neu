"""
psu_auto.py — система автоматического улучшения LLM на основе ПСУ-2 и протокола Основания.

Три слоя:
  1. ПРИБОР (локально, внутри «марковского одеяла»): спектр ПСУ-2, совпадение своего и мирового уровня,
     ошибка замыкания, порог данных n*, направление подстройки «кто под кого» (08 §1),
     подпись границы «порядок / край / хаос» (06 §4, 15 §6-бис; проверена в BOUND-01 на эталонах).
  2. РЕГУЛЯТОР: правила R1–R5, выведенные из экспериментов EQUIV-01/01B.
     ВНИМАНИЕ: предрегистрированная проверка AUTO-01 регулятор УБИЛА — постоянная добавка по R1/R2
     на шаге 1000 ухудшила избыточный лосс на 13% (к шагу 2000 он на 11% ниже — post hoc, 3 сида).
     Поэтому R1–R4 только ПРЕДЛАГАЮТ изменение; решает R5 на заранее записанном горизонте.
  3. ПРОТОКОЛ ФОРКОВ (по образцу Основания): суверенные форки, открытые «патчи» с предрегистрацией,
     обмен только числами, отбор по мировой метрике на своей проверке, отчёты доверенных форков (M3)
     как фильтр, антимонопольный индекс с надбавкой (грубый аналог M7: линейно, без фонда разнообразия).
     Самопроверка _selftest() — механика на синтетике, не доказательство.

Зависимости: только numpy. Модель подключается через три массива, которые считает сам пользователь:
  X      — состояния модели (residual stream) формы (последовательности, позиции, d);
  Yself  — собственная условная статистика модели (увиденное ⊗ свой прогноз) на окне t+τ…;
  Yworld — та же статистика по истинным будущим наблюдениям.
Как их построить для языковой модели — см. psu2_pythia_colab.py.
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field

# ============================================================ 1. ПРИБОР

def _inv_sqrt(S):
    w, U = np.linalg.eigh(S)
    return (U / np.sqrt(np.maximum(w, 1e-300))) @ U.T


def cca(X, Y, reg=1e-10):
    """Канонические корреляции и направления X. reg — доля среднего собственного числа (не больше 1e-10,
    иначе теряется инвариантность к замене координат: см. EQUIV-01, P2/Q6)."""
    X = X - X.mean(0); Y = Y - Y.mean(0); n = len(X)
    Sxx, Syy, Sxy = X.T @ X / n, Y.T @ Y / n, X.T @ Y / n
    Sxx = Sxx + reg * np.trace(Sxx) / len(Sxx) * np.eye(len(Sxx))
    Syy = Syy + reg * np.trace(Syy) / len(Syy) * np.eye(len(Syy))
    Wx, Wy = _inv_sqrt(Sxx), _inv_sqrt(Syy)
    U, s, _ = np.linalg.svd(Wx @ Sxy @ Wy)
    return s, Wx @ U, (Wx, Wy, X, Y)


def pos_center(A):
    """Вычесть среднее по каждой позиции (условие на «часы»). A: (seq, pos, dim)."""
    return A - A.mean(0, keepdims=True)


def spectrum(X3, Y3, nperm=100, q=99, rng=None, reg=1e-10):
    """Спектр ПСУ-2 с нулевой моделью «перемешать целые последовательности».
    Возвращает ρ, порог, число обнаружимых мод и положение наибольшего лог-разрыва."""
    rng = rng or np.random.default_rng(0)
    X3, Y3 = pos_center(X3), pos_center(Y3)
    ns, npos = X3.shape[:2]
    Xf, Yf = X3.reshape(ns * npos, -1), Y3.reshape(ns * npos, -1)
    s, A, (Wx, Wy, Xc, Yc) = cca(Xf, Yf, reg)
    null = []
    for _ in range(nperm):
        Yp = Y3[rng.permutation(ns)].reshape(ns * npos, -1)
        Yp = Yp - Yp.mean(0)
        null.append(np.linalg.svd(Wx @ (Xc.T @ Yp / len(Xc)) @ Wy, compute_uv=False)[0])
    thr = float(np.percentile(null, q))
    det = int((s > thr).sum())
    top = s[:max(det + 1, 2)]
    gaps = np.log(top[:-1] / np.maximum(top[1:], 1e-12))
    k = int(np.argmax(gaps) + 1) if det >= 1 else 0
    return dict(rho=s, thr=thr, detectable=det, levels=k, gap_width=float(2 * gaps.max()) if det else 0.0, dirs=A)


def subspace_cos(X, A1, A2):
    """Косинусы главных углов между подпространствами признаков X@A1 и X@A2 (в метрике данных)."""
    Q1, _ = np.linalg.qr((X - X.mean(0)) @ A1)
    Q2, _ = np.linalg.qr((X - X.mean(0)) @ A2)
    return np.linalg.svd(Q1.T @ Q2, compute_uv=False)


def closure_error(Xseq, A, lag):
    """Насколько уровень (X@A) хуже предсказывает сам себя через lag, чем полное состояние предсказывает его.
    Xseq: (seq, pos, d). 0 — уровень замкнут (марковский сам по себе)."""
    F = Xseq @ A
    f0, f1 = F[:, :-lag].reshape(-1, A.shape[1]), F[:, lag:].reshape(-1, A.shape[1])
    m0 = Xseq[:, :-lag].reshape(-1, Xseq.shape[-1])

    def r2(Z, T):
        Z1 = np.c_[Z, np.ones(len(Z))]
        W, *_ = np.linalg.lstsq(Z1, T, rcond=None)
        return 1 - ((T - Z1 @ W) ** 2).sum() / ((T - T.mean(0)) ** 2).sum()
    lv, mi = r2(f0, f1), r2(m0, f1)
    return float(max(mi - lv, 0.0) / max(mi, 1e-12))


def n_star(X3, Y3, mode=2, sizes=(20, 50, 100, 200, 400, 800), reps=5, rng=None):
    """Наименьшее число последовательностей, при котором мода номер `mode` видна выше нуля в ≥4 из 5 подвыборок."""
    rng = rng or np.random.default_rng(1)
    for n in sizes:
        if n > len(X3):
            break
        hits = 0
        for _ in range(reps):
            idx = rng.choice(len(X3), n, replace=False)
            sp = spectrum(X3[idx], Y3[idx], nperm=50, rng=rng)
            hits += int(sp['detectable'] >= mode)
        if hits >= 4:
            return n
    return None


def adaptation_direction(C, A, lag=1, reg=1e-8):
    """«Кто под кого подстраивается» (Основание, 08_DATA §1) — направленная мера по Грейнджеру
    в канонической форме (для гауссовых данных равна переносу энтропии: Barnett, Barrett, Seth 2009).
    C, A: (T, dc), (T, da) — состояния ребёнка и ИИ во времени.
    Возвращает (C→A, A→C): сколько прошлое одного добавляет к предсказанию будущего другого сверх его
    собственного прошлого (в натах, логарифм отношения обобщённых дисперсий остатков).
    C→A > A→C — ИИ подстраивается под ребёнка («леса»); наоборот — «клетка»."""
    def resid_logdet(T, Z):
        Z1 = np.c_[Z, np.ones(len(Z))]
        W, *_ = np.linalg.lstsq(Z1, T, rcond=None)
        E = T - Z1 @ W
        S = E.T @ E / len(E) + reg * np.eye(E.shape[1])
        return np.linalg.slogdet(S)[1]
    Cp, Ap, Cf, Af = C[:-lag], A[:-lag], C[lag:], A[lag:]
    c2a = 0.5 * (resid_logdet(Af, Ap) - resid_logdet(Af, np.c_[Ap, Cp]))
    a2c = 0.5 * (resid_logdet(Cf, Cp) - resid_logdet(Cf, np.c_[Cp, Ap]))
    return float(c2a), float(a2c)


def boundary_signature(x, tau_long=64, L_small=16, L_big=64, npos=16, stride=8, nperm=50, rng=None):
    """Подпись границы по Основанию (06 §1: порядок — мало мод, хаос — континуум, граница — накопление мод).
    x: (последовательности, время) или (последовательности, время, d) — независимые записи одного процесса.
    Мировая цель: окно будущего длины L через tau_long шагов после окна прошлого длины L.
      N_long — число обнаружимых мод при окне L_small;  G = N(L_big) − N(L_small) — рост с окном.
      хаос: N_long = 0;  порядок: N_long ≥ 1 и G ≤ 1;  край: N_long ≥ 1 и G ≥ 2.
    Вердикт относится к ВОПРОСУ (tau_long, окна, объём данных): при tau = 1 хаос выглядит порядком (BOUND-01).
    Правило и пороги — из PREREG-BOUND-01; на записях жизни людей не проверялось."""
    rng = rng or np.random.default_rng(0)
    x = np.asarray(x, float)
    if x.ndim == 2:
        x = x[..., None]

    def count(L):
        ends = L - 1 + stride * np.arange(npos)
        if ends[-1] + tau_long + L > x.shape[1]:
            raise ValueError(f'записи коротки: нужно ≥ {ends[-1] + tau_long + L} отсчётов')
        X3 = np.stack([x[:, e - L + 1:e + 1].reshape(len(x), -1) for e in ends], 1)
        Y3 = np.stack([x[:, e + tau_long:e + tau_long + L].reshape(len(x), -1) for e in ends], 1)
        X3 = X3 - X3.mean((0, 1), keepdims=True); Y3 = Y3 - Y3.mean((0, 1), keepdims=True)
        sp = spectrum(X3, Y3, nperm=nperm, rng=rng)
        return sp['detectable']
    n_small, n_big = count(L_small), count(L_big)
    G = n_big - n_small
    verdict = 'хаос' if n_small == 0 else ('порядок' if G <= 1 else 'край')
    return dict(N_long=n_small, N_big=n_big, G=G, verdict=verdict)


# ============================================================ 2. РЕГУЛЯТОР

@dataclass
class Diagnosis:
    tau: int
    world_levels: int
    self_levels: int
    align: float            # меньший косинус между k ведущими своими и мировыми направлениями
    artifact_modes: int     # свои моды выше нуля без мирового двойника (cos < 0.5)
    closure: float | None = None


def diagnose(X3, Yself3, Yworld3, tau, nperm=100, rng=None):
    rng = rng or np.random.default_rng(0)
    sw = spectrum(X3, Yworld3, nperm, rng=rng)
    ss = spectrum(X3, Yself3, nperm, rng=rng)
    Xf = pos_center(X3).reshape(-1, X3.shape[-1])
    k = max(sw['levels'], 1)
    cos = subspace_cos(Xf, ss['dirs'][:, :k], sw['dirs'][:, :k])
    # «архитектурные» моды: обнаружимы в самоописании, но не имеют мирового двойника среди первых 10 мировых мод
    m = min(ss['detectable'], 10)
    art = 0
    if m:
        c_all = subspace_cos(Xf, ss['dirs'][:, :m], sw['dirs'][:, :10])
        art = int((c_all < 0.5).sum())
    return Diagnosis(tau, sw['levels'], ss['levels'], float(cos.min()), art)


@dataclass
class Action:
    kind: str       # 'aux_world' | 'aux_self' | 'aux_off' | 'more_data' | 'none'
    tau: int
    why: str


def policy(d: Diagnosis, n_have: int | None = None, n_need: int | None = None) -> Action:
    """Правила R1–R4 — ПРЕДЛОЖЕНИЯ, а не решения. R5 (приёмка только по мировой метрике) — в Protocol.adopt().
    AUTO-01 (PREREG-AUTO-01): постоянная добавка по R1→R2 на шаге 1000 хуже базы на 13% (критерий убийства
    сработал), своя цель с начала — хуже на 95%; совпадение уровней наступало раньше всего в худшей ветви.
    Значит, совпадение уровней — не мера качества; каждое предложение проходит R5 на своём горизонте."""
    if d.world_levels == 0:
        if n_need and n_have is not None and n_have < n_need:
            return Action('more_data', d.tau, f'R4: мировой уровень не виден, данных {n_have} < n*={n_need}')
        return Action('none', d.tau, 'нет мирового уровня на этой шкале')
    if d.align < 0.95:
        return Action('aux_world', d.tau, f'R1: мировой уровень есть, своё описание с ним не совпало (cos={d.align:.2f}); '
                                          f'учить на мировую цель, свою не подкреплять ({d.artifact_modes} архитектурных мод)')
    return Action('aux_self', d.tau, f'R2: уровень родился (cos={d.align:.2f}); учить на свою цель — она менее шумная (Q5)')


# ============================================================ 3. ПРОТОКОЛ ФОРКОВ (Основание)

@dataclass
class Patch:
    pid: str
    source: str             # кто предложил
    recipe: dict            # что делать (напр. {'aux': 'world', 'tau': 16, 'lam': 0.3})
    prediction: str         # предрегистрированное предсказание с порогом
    reports: list = field(default_factory=list)   # (fork, дельта мировой метрики) — только числа


@dataclass
class Fork:
    name: str
    base: str               # от какой общей базы стартовал (замороженная версия, не живая модель)
    trusts: set = field(default_factory=set)      # список общения (M3): чьим отчётам верит
    adopted: list = field(default_factory=list)
    world_metric: float = 0.0                      # напр. лосс на свежих данных; меньше — лучше


class Protocol:
    """Никакого центра: форки суверенны, веса не передаются, наружу идут только числа (M4),
    рецепты открыты (M10), приёмка — по мировой метрике (M9), монополия считается и дорожает (M7)."""

    def __init__(self, margin=0.0005, monopoly_cap=0.25, min_trusted=2):
        self.forks: dict[str, Fork] = {}
        self.patches: dict[str, Patch] = {}
        self.margin, self.cap, self.min_trusted = margin, monopoly_cap, min_trusted
        self.tests_run, self.tests_saved = 0, 0

    def publish(self, patch: Patch):
        self.patches[patch.pid] = patch

    def report(self, pid, fork, delta):
        self.patches[pid].reports.append((fork, float(delta)))

    def evidence(self, fork: Fork, pid):
        """Средняя польза патча по отчётам тех, кому форк доверяет (граф общения)."""
        rs = [d for f, d in self.patches[pid].reports if f in fork.trusts]
        return (float(np.mean(rs)), len(rs)) if rs else (0.0, 0)

    def monopoly_index(self):
        """M7 для ИИ: максимальная доля одного источника среди всех принятых патчей всех форков
        и максимальная доля одной базы среди форков."""
        src = [self.patches[p].source for f in self.forks.values() for p in f.adopted]
        s = max((src.count(x) / len(src) for x in set(src)), default=0.0)
        bases = [f.base for f in self.forks.values()]
        b = max((bases.count(x) / len(bases) for x in set(bases)), default=0.0)
        return float(s), float(b)

    def adopt(self, fork: Fork, pid, local_test):
        """R5: форк пробует патч у себя; принимает, только если мировая метрика улучшилась больше порога
        на горизонте, записанном в рецепте ДО проверки (AUTO-01: на 1000 шагах добавка вредна, на 2000 — полезна).
        Отчёты тех, кому форк доверяет (M3), служат фильтром: если не меньше min_trusted из них уже показали
        вред или ноль, свою проверку не тратят. Принять патч по чужим отчётам без своей проверки нельзя.
        Антимонополия (грубый аналог M7): чем больше доля источника среди принятых, тем больший выигрыш нужен
        (линейно; фонда разнообразия нет)."""
        if 'horizon' not in self.patches[pid].recipe:
            raise ValueError('R5: горизонт проверки должен быть записан в рецепте патча заранее')
        ev, n_ev = self.evidence(fork, pid)
        if n_ev >= self.min_trusted and ev <= 0:
            self.tests_saved += 1
            return False, None, None
        self.tests_run += 1
        src = self.patches[pid].source
        src_share = 0.0
        allp = [self.patches[p].source for f in self.forks.values() for p in f.adopted]
        if allp:
            src_share = allp.count(src) / len(allp)
        need = self.margin * (1.0 + max(0.0, src_share - self.cap) * 10)   # прогрессивная «цена» доминирования
        delta = local_test(fork, self.patches[pid].recipe)                  # улучшение мировой метрики (>0 — лучше)
        self.report(pid, fork.name, delta)
        if delta > need:
            fork.adopted.append(pid)
            fork.world_metric -= delta
            return True, delta, need
        return False, delta, need


# ============================================================ самопроверки (механика, не доказательства)

def _selftest(seed=0):
    rng = np.random.default_rng(seed)
    # 1) направление подстройки: ИИ следует за ребёнком (A_t = 0.8 C_{t-1} + шум), ребёнок автономен
    T = 5000
    C = np.zeros((T, 3)); A = np.zeros((T, 3))
    for t in range(1, T):
        C[t] = 0.7 * C[t - 1] + rng.normal(size=3)
        A[t] = 0.3 * A[t - 1] + 0.8 * C[t - 1] + rng.normal(size=3)
    c2a, a2c = adaptation_direction(C, A)
    ok1 = c2a > 0.2 and a2c < 0.01
    # 2) протокол: 30 форков, 12 патчей со скрытой настоящей пользой; источник «big» публикует половину
    P = Protocol()
    for i in range(30):
        P.forks[f'f{i}'] = Fork(f'f{i}', base=f'b{i % 5}', trusts={f'f{j}' for j in rng.choice(30, 6, replace=False)})
    true = {}
    for j in range(12):
        src = 'big' if j < 6 else f's{j}'
        P.publish(Patch(f'p{j}', src, {'j': j, 'horizon': 2000}, 'улучшит мировую метрику ≥ 0.0005 к шагу 2000'))
        true[f'p{j}'] = rng.normal(0.0005, 0.001)
    for f in P.forks.values():
        for pid in P.patches:
            P.adopt(f, pid, lambda fork, rec, pid=pid: true[pid] + rng.normal(0, 0.0003))
    good = [p for p in true if true[p] > 0.0005]
    adopted = [p for f in P.forks.values() for p in f.adopted]
    precision = np.mean([true[p] > 0 for p in adopted]) if adopted else float('nan')
    s, b = P.monopoly_index()
    # 3) подпись границы на эталонах 06 §4: синусы (порядок), Фейгенбаум (край), логистика r = 4 (хаос)
    T, ns = 16 * 8 + 64 + 64 + 64, 400
    t = np.arange(T)[None, :]
    sines = sum(a * np.sin(w * t + rng.uniform(0, 2 * np.pi, (ns, 1)))
                for w, a in ((0.21, 1.0), (0.21 * 2 ** 0.5, 0.7), (0.21 * 5 ** 0.5, 0.5)))

    def logistic(r):
        x = rng.uniform(0.2, 0.8, ns)
        for _ in range(65536):
            x = r * x * (1 - x)
        out = np.empty((ns, T))
        for i in range(T):
            out[:, i] = x; x = r * x * (1 - x)
        return out
    bound = {}
    for name, z in (('синусы', sines), ('Фейгенбаум', logistic(3.569945671870944)), ('логистика r=4', logistic(4.0))):
        z = (z - z.mean()) / z.std() + 0.01 * rng.normal(size=z.shape)
        bound[name] = boundary_signature(z, rng=rng)['verdict']
    return dict(adaptation=(round(c2a, 3), round(a2c, 3)), direction_ok=bool(ok1),
                patches_good=len(good), adopted=len(adopted), precision=round(float(precision), 3),
                tests_run=P.tests_run, tests_saved=P.tests_saved,
                monopoly_source=round(s, 3), monopoly_base=round(b, 3), boundary=bound)


if __name__ == '__main__':
    print(_selftest())
