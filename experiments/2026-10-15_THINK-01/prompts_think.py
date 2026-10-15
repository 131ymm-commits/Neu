# THINK-01: промпты. ROLE и ROLE_REFUSE — без изменений из SELECT-01 (prompts.py, sha256 48ce93b0…); новые — две добавки
# той же длины вместо строки с отказом:
#   ROLE_UNSURE  — та же фраза о неуверенности и «не наказывается», но без варианта −1 (выбор обязателен);
#   ROLE_PLACEBO — нейтральный текст той же длины без неуверенности и без −1.
# Длины добавок сверяются в main ниже (допуск ±10 % к добавке ROLE_REFUSE).
import hashlib, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '2026-10-07_SELECT-01'))
import prompts as P  # noqa: E402
LAST = 'Верни choice — номер кандидата с наибольшим ожидаемым итогом.'
ADD = dict(
    REFUSE='Если ты не можешь отличить лучшего кандидата от остальных с разумной уверенностью — откажись: верни choice = -1 («не знаю»). Отказ не наказывается сам по себе.\nИначе верни',
    UNSURE='Если ты не можешь отличить лучшего кандидата от остальных с разумной уверенностью — всё равно выбери того, кто вероятнее лучший. Такой выбор не наказывается сам по себе.\nВерни',
    PLACEBO='Кандидаты пронумерованы с нуля в том порядке, в каком перечислены ниже; порядок перечисления ничего не значит. Описание задачи и всех кандидатов полное.\nВерни',
)
ROLE_UNSURE = P.ROLE.replace(LAST, ADD['UNSURE'] + LAST[len('Верни'):])
ROLE_PLACEBO = P.ROLE.replace(LAST, ADD['PLACEBO'] + LAST[len('Верни'):])
# ROLE_CONF — ROLE с самооценкой: кроме номера — вероятность, что выбранный кандидат действительно лучший (оценка оценки).
ROLE_CONF = P.ROLE.replace(LAST, LAST + '\nВерни также p_best — твою вероятность от 0 до 1, что выбранный кандидат действительно лучший по фактическому итогу.')
CONF_SCHEMA = {"type": "object", "properties": {"choice": {"type": "integer"}, "p_best": {"type": "number"}}, "required": ["choice", "p_best"]}
TPL = dict(BASE=P.BASE, ROLE=P.ROLE, ROLE_REFUSE=P.ROLE_REFUSE, ROLE_UNSURE=ROLE_UNSURE, ROLE_PLACEBO=ROLE_PLACEBO, ROLE_CONF=ROLE_CONF)
# рука → (шаблон, effort, схема). B_blind, C_N, D_N — промпты SELECT-01 байт в байт; H — один и тот же ROLE на effort high
# (H_1 = вызов i = 0, H_3 = большинство трёх); H_c — ROLE_CONF на high, один вызов.
ARMS = dict(B_blind=('BASE', 'medium', P.EVAL_SCHEMA), C_N=('ROLE', 'medium', P.EVAL_SCHEMA), D_N=('ROLE_REFUSE', 'medium', P.EVAL_SCHEMA),
            U_N=('ROLE_UNSURE', 'medium', P.EVAL_SCHEMA), P_N=('ROLE_PLACEBO', 'medium', P.EVAL_SCHEMA),
            H=('ROLE', 'high', P.EVAL_SCHEMA), H_c=('ROLE_CONF', 'high', CONF_SCHEMA))
SPEC = dict(B_blind=12, C_N=5, D_N=5, U_N=5, P_N=5, H=3, H_c=1)   # вызовов на задачу

def eval_prompt(arm, rules, pool):
    return TPL[ARMS[arm][0]].format(k=len(pool), rules=rules, cands=P.cands_text(pool, False))

if __name__ == '__main__':
    assert P.ROLE_REFUSE == P.ROLE.replace(LAST, ADD['REFUSE'] + LAST[len('Верни'):]), 'добавка REFUSE не совпала с SELECT-01'
    base = len(ADD['REFUSE']) - len('\nИначе верни')
    for k, v in ADD.items():
        n = len(v) - len(v.split('\n')[-1]) - 1
        print(k, n, f'{100 * (n / base - 1):+.0f} %')
    print(json.dumps({k: hashlib.sha256(v.encode()).hexdigest() for k, v in TPL.items()}, indent=1))
    print('ROLE_CONF, последние строки:', ROLE_CONF.split('{rules}')[0].strip().splitlines()[-2:])
