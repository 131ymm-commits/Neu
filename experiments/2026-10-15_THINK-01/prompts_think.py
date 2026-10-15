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
TPL = dict(ROLE=P.ROLE, ROLE_REFUSE=P.ROLE_REFUSE, ROLE_UNSURE=ROLE_UNSURE, ROLE_PLACEBO=ROLE_PLACEBO)
ARMS = dict(C_N='ROLE', D_N='ROLE_REFUSE', U_N='ROLE_UNSURE', P_N='ROLE_PLACEBO')   # рука → шаблон; effort задаёт конфиг прогона

def eval_prompt(arm, rules, pool):
    return TPL[ARMS[arm]].format(k=len(pool), rules=rules, cands=P.cands_text(pool, False))

if __name__ == '__main__':
    assert P.ROLE_REFUSE == P.ROLE.replace(LAST, ADD['REFUSE'] + LAST[len('Верни'):]), 'добавка REFUSE не совпала с SELECT-01'
    base = len(ADD['REFUSE']) - len('\nИначе верни')
    for k, v in ADD.items():
        n = len(v) - len(v.split('\n')[-1]) - 1
        print(k, n, f'{100 * (n / base - 1):+.0f} %')
    print(json.dumps({k: hashlib.sha256(v.encode()).hexdigest() for k, v in TPL.items()}, indent=1))
