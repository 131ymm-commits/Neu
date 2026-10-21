# Проклятие победителя при переборе предусловий: 100 ОДИНАКОВЫХ по силе промптов, по 1 голосу на задачу.
# Регрет голоса = эффект задачи + шум с СКО sd. Сколько «выигрыша» у лучшего из 100 — чистой случайности?
import random, statistics as st
def run(n_prompts, n_tasks, sd, reps=2000, seed=7):
    rng = random.Random(seed); gains = []
    for _ in range(reps):
        task = [rng.gauss(0, 0.3) for _ in range(n_tasks)]
        means = [st.fmean(task[t] + rng.gauss(0, sd) for t in range(n_tasks)) for _ in range(n_prompts)]
        gains.append(st.fmean(means) - min(means))          # насколько лучший (меньший регрет) лучше среднего
    gains.sort(); return st.fmean(gains), gains[int(.05 * reps)], gains[int(.95 * reps)]
for n_tasks in (6, 15, 50):
    m, lo, hi = run(100, n_tasks, 0.6)
    print(f'100 одинаковых промптов, {n_tasks:2d} задач: мнимый выигрыш лучшего {m:.2f} (90 % от {lo:.2f} до {hi:.2f})')
m, lo, hi = run(32, 15, 0.6); print(f' 32 одинаковых промпта, 15 задач: мнимый выигрыш лучшего {m:.2f} (90 % от {lo:.2f} до {hi:.2f})')
