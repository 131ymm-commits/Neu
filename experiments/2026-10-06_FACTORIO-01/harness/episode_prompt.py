# Промпт эпизода для головы-агента (одинаковый во всех руках; руки различаются только блоком RULES).
def prompt(slot, goal, max_steps, rules=None, H='/home/user/neu/experiments/2026-10-06_FACTORIO-01/harness'):
    r = f"\n\nТвои правила (выработаны раньше, используй их):\n-----\n{rules}\n-----\n" if rules else ''
    return (f"Ты — агент в игре Factorio (среда FLE). Задача:\n{goal}\n\n"
            f"Как действовать: пиши Python-код шага в файл в своём каталоге /tmp/fle_ep_{slot}/ (создай его) и выполняй его командой\n"
            f"  python3 {H}/fle_step.py {slot} step < /tmp/fle_ep_{slot}/stepN.py\n"
            f"Код исполняется в игре инструментами FLE; ответ — вывод print() и текущая производительность завода (за 60 игровых секунд). "
            f"Переменные между шагами сохраняются. Шагов не больше {max_steps}; `python3 {H}/fle_step.py {slot} info` — сколько осталось.\n"
            f"Документация API FLE (инструменты, типы, руководства) — файл {H}/FLE_API.md; читай нужные части (grep/sed).\n"
            "Запрещено: import, обращения к серверу и RCON в обход инструментов, чтение любых других файлов, кроме FLE_API.md и своих шагов; запрещённый код отклоняется." + r +
            "\n\nКогда закончишь (или шаги кончатся), верни: summary — что построил и что получилось (до 200 слов); lessons — 3–8 коротких уроков, что работает и что нет в этой среде; best_throughput — лучшая производительность, которую ты видел в ответах.")
SCHEMA = {'type': 'object', 'properties': {'summary': {'type': 'string'}, 'lessons': {'type': 'string'}, 'best_throughput': {'type': 'number'}}, 'required': ['summary', 'lessons', 'best_throughput']}
