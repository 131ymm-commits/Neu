# Интегральная ошибка истины (ИОИ) — общий критерий для экспериментов EVO.
# Для каждого поколения g берётся особь, лучшая ПО ОЦЕНЩИКУ: T_g — её доля верных на скрытой правде, C_g — что заявил оценщик.
# ИОИ = среднее по поколениям от (1 − T_g) + max(0, C_g − T_g). Шкала 0…2, меньше — лучше.
#   (1 − T) — незнание правды; max(0, C − T) — самообман (оценщик обещает больше правды, Гудхарт); среднее — учитывает скорость.
# Составляющие отдаются отдельно, чтобы видеть, за счёт чего ошибка.
import numpy as np


def ioi(hist):
    T = np.array([h['true'] for h in hist]); C = np.array([h['claimed'] for h in hist])
    ignorance = float(np.mean(1 - T)); deception = float(np.mean(np.maximum(0, C - T)))
    return dict(ioi=ignorance + deception, ignorance=ignorance, deception=deception)


if __name__ == '__main__':                     # пересчёт для EVO-01 и EVO-02 (пост-хок, описательно)
    import json, glob, sys
    for exp in sys.argv[1:]:
        rows = {}
        for f in glob.glob(f'{exp}/runs/*.json'):
            d = json.load(open(f)); rows.setdefault((d['task'], d['arm']), []).append(ioi(d['hist']))
        print('==', exp)
        for (t, a), v in sorted(rows.items()):
            m = {k: np.median([x[k] for x in v]) for k in v[0]}
            print(f'  {t} {a:9s} ИОИ {m["ioi"]:.3f} = незнание {m["ignorance"]:.3f} + самообман {m["deception"]:.3f}')
