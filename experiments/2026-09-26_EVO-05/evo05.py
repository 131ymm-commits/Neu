# EVO-05: оценщик как голова — гипотеза об истине с неуверенностью (см. PREREG-EVO-05.md).
# Истина T — доля верных на 1000 скрытых входах (отбор её не видит). Оценка C — предположение оценщика об T.
# Ветви: BASE — отбор по доле верных на 16 свежих тестах; R80 — на 80 свежих (столько же ответов оракула, сколько у голов);
#        HEAD — отбор по предсказанию головы (гребневая регрессия по признакам поведения, дообучается на сверках);
#        HEAD_LCB — отбор по нижней границе: предсказание − σ (поправка на «проклятие оптимизатора»).
# Версия 2 (после проверки агентами, до регистрации): признаки стандартизуются по окну, свободный член не штрафуется;
# σ — только неуверенность головы (эпистемическая); сверки: 2 лучших по ключу ветви + 2 лучших по сырой доле + 4 случайных,
# без повторов одинаковых программ; отдельные потоки случайных чисел для вариации, тестов и сверок; тесты вложены (16 = первые из 80).
# Входы сверок — свежие случайные из того же отрезка −100…100 (со скрытыми совпадают по значениям, как и тесты BASE; отбор
# скрытых ответов не видит). Ответов оракула на поколение у голов: 16 + 64 = 80.
import sys, os, json, time
import numpy as np
import evo03 as E3
from evo03 import E
from truth import ioi

N_AUDIT, AUDIT_X, WINDOW, LAM, KAPPA = 8, 64, 400, 1.0, 1.0


def feats(t, out, y):
    ok = out == y
    ps = list(E.nodes(t))
    return np.array([ok.mean(), len(ps) / 30, E.depth(t) / E.MAXD, len(np.unique(out)) / len(out),
                     float(any(E.get(t, p) == 'x' for p in ps)), ok.mean() ** 2, 1.0])


class Head:
    def __init__(self): self.X, self.y = [], []

    def add(self, x, y):
        self.X.append(x); self.y.append(y)
        self.X, self.y = self.X[-WINDOW:], self.y[-WINDOW:]

    def _z(self, F):
        Z = (F[:, :-1] - self.m) / self.sdv
        return np.hstack([Z, np.ones((len(F), 1))])

    def fit(self):
        if len(self.y) < 16: self.w = None; return
        X = np.array(self.X); y = np.array(self.y)
        self.m = X[:, :-1].mean(0); self.sdv = X[:, :-1].std(0) + 1e-6
        Z = self._z(X); P = LAM * np.eye(Z.shape[1]); P[-1, -1] = 0.0      # свободный член не штрафуется
        self.Ai = np.linalg.inv(Z.T @ Z + P); self.w = self.Ai @ Z.T @ y
        res = y - Z @ self.w; self.s2 = float(res @ res / max(1, len(y) - Z.shape[1]))

    def predict(self, F):
        if self.w is None:                                  # пока нет сверок — голова = сырая доля верных
            return F[:, 0], np.zeros(len(F))
        Z = self._z(F); mu = np.clip(Z @ self.w, 0, 1)
        sd = np.sqrt(self.s2 * np.einsum('ij,jk,ik->i', Z, self.Ai, Z))    # неуверенность головы, без шума меток
        return mu, sd


def run(task, arm, seed):
    ss = np.random.SeedSequence(seed * 1000 + int(task[1]))
    r, r_test, r_aud = [np.random.default_rng(x) for x in ss.spawn(3)]     # вариация / тесты / сверки
    f = E.TASKS[task]
    hid = np.random.default_rng(10 ** 6 + seed).integers(E.LO, E.HI + 1, 1000); yhid = f(hid)
    pop = [E.rand_tree(r, 4) for _ in range(E.POP)]; head = Head(); hist = []; calib = []
    for g in range(E.GENS + 1):
        X80 = r_test.integers(E.LO, E.HI + 1, 80); X = X80 if arm == 'R80' else X80[:16]; y = f(X)
        outs = [E.ev(t, X) for t in pop]; raw = np.array([(o == y).mean() for o in outs])
        if arm.startswith('HEAD'):
            F = np.array([feats(t, o, y) for t, o in zip(pop, outs)]); head.fit()
            mu, sd = head.predict(F)
            key = mu - KAPPA * sd if arm == 'HEAD_LCB' else mu
            claim = mu
        else:
            key = raw; claim = raw
        best = int(np.argmax(key))
        hist.append(dict(gen=g, claimed=float(claim[best]), true=float((E.ev(pop[best], hid) == yhid).mean())))
        if arm.startswith('HEAD'):                          # сверки с истиной на свежих входах
            AX = r_aud.integers(E.LO, E.HI + 1, AUDIT_X); ay = f(AX)
            chosen, seen = [], set()
            def take(order, k):
                n = 0
                for i in order:
                    if n == k: break
                    if pop[i] in seen: continue
                    seen.add(pop[i]); chosen.append((int(i), 'top' if order is not rnd else 'rnd')); n += 1
            rnd = r_aud.permutation(len(pop))
            take(np.argsort(-key), 2); take(np.argsort(-raw), 2); take(rnd, 4)
            for i, kind in chosen:
                t_aud = float((E.ev(pop[i], AX) == ay).mean()); head.add(F[i], t_aud)
                if head.w is not None:                      # калибровка: только поколения, где голова уже обучена
                    calib.append(dict(g=g, kind=kind, mu=float(mu[i]), aud=t_aud,
                                      hid=float((E.ev(pop[i], hid) == yhid).mean()),        # только для отчёта, в отбор не идёт
                                      base=float(np.mean(head.y[:-1])) if len(head.y) > 1 else float(t_aud)))
        if g == E.GENS: break
        new = [pop[best]]
        while len(new) < E.POP:
            i = max(r.integers(E.POP, size=E.TOUR), key=lambda k: key[k])
            c = E.cross(pop[i], pop[max(r.integers(E.POP, size=E.TOUR), key=lambda k: key[k])], r) if r.random() < 0.7 else pop[i]
            if r.random() < 0.3: c = E.mutate(c, r)
            new.append(c)
        pop = new
    return hist, calib


if __name__ == '__main__':
    task, arm, seed = sys.argv[1], sys.argv[2], int(sys.argv[3]); t0 = time.time()
    hist, calib = run(task, arm, seed)
    cal = calib
    def mae(rows, k): return float(np.mean([abs(x['mu'] - x[k]) for x in rows])) if rows else None
    top = [x for x in cal if x['kind'] == 'top']
    res = dict(task=task, arm=arm, seed=seed, hist=hist, **ioi(hist), final_true=hist[-1]['true'],
               calib_n=len(cal), head_mae_hidden=mae(cal, 'hid'), head_mae_hidden_top=mae(top, 'hid'),
               base_mae_hidden=float(np.mean([abs(x['base'] - x['hid']) for x in cal])) if cal else None,
               head_bias_hidden_top=float(np.mean([x['mu'] - x['hid'] for x in top])) if top else None,
               sec=round(time.time() - t0, 1))
    os.makedirs('runs', exist_ok=True); json.dump(res, open(f'runs/{task}_{arm}_s{seed}.json', 'w'))
    print(task, arm, seed, 'ИОИ', round(res['ioi'], 3), 'незн', round(res['ignorance'], 3), 'самообман', round(res['deception'], 3),
          'итог', round(res['final_true'], 3), 'ошибка головы', res['head_mae_hidden'] and round(res['head_mae_hidden'], 3), 'у «среднего»', res['base_mae_hidden'] and round(res['base_mae_hidden'], 3), res['sec'], 'с')
