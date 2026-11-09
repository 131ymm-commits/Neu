#!/usr/bin/env python3
# TESTER-01: задания для голов-тестировщиков. Промпт одинаков для рук, кроме абзаца об инструментах; описание игры — из её README.
#   python3 make_jobs.py <этап: pilot|test> <выход.jsonl> [--sessions <каталог сессий>]
import json, os, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
SECRET = Path('/root/tester01_secret')
GAMES = {'baeckerei': ('Bäckerei', HERE / 'games/baeckerei/index.html', HERE / 'games/baeckerei/README.md'),
         'reifenwerk': ('Reifenwerk', HERE / 'games/reifenwerk/Reifenwerk.html', HERE / 'games/reifenwerk/README.md')}
README_MAX = 12000          # знаков описания автора (README Reifenwerk — 60 тыс.; берётся начало: правила и интерфейс)
MAX_ACTS = 150
STAGES = {  # копии игр: мутанты банка (вне git) и чистые копии
    'pilot': [('baeckerei', 'B-P'), ('reifenwerk', 'R-P')],
    'test': [('baeckerei', 'B-1'), ('baeckerei', 'B-2'), ('baeckerei', 'clean'), ('reifenwerk', 'R-1'), ('reifenwerk', 'R-2'), ('reifenwerk', 'clean')],
}
ARMS = ['S', 'A', 'W']
TOOLS = {
 'S': 'Ты видишь игру только как снимок экрана 1280×800 (game_observe) и действуешь кликами по точкам экрана, перетаскиванием, клавишами и ожиданием (game_act). Кода игры и её внутреннего состояния у тебя нет.',
 'A': 'Ты видишь игру текстом (game_observe): области экрана, номера кнопок и полей, состояние игры — сводку, объекты карты с клетками, людей, журнал — и новые ошибки страницы. Действуешь по номерам кнопок, кликами по клеткам карты, клавишами и ожиданием (game_act). Кода игры у тебя нет.',
 'W': 'Ты видишь игру текстом (game_observe): области экрана, номера кнопок и полей, состояние игры — сводку, объекты карты с клетками, людей, журнал — и новые ошибки страницы. Действуешь по номерам кнопок, кликами по клеткам карты, клавишами и ожиданием (game_act). Кроме того, тебе доступен исходный код игры: поиск (source_search) и чтение строк (source_read). Код — подсказка, где искать; баг засчитывается только тот, что виден в игре.',
}
PROMPT = """Ты — тестировщик браузерной игры «{title}». Игру сделал с помощью ИИ человек без опыта разработки; ниже — его описание игры.

Задача: найти как можно больше настоящих багов — мест, где игра ведёт себя не так, как обещают её описание, подсказки, подписи кнопок и здравый смысл. Это могут быть падения и ошибки страницы, зависания и положения, из которых нельзя продолжить, неверные числа и расчёты, нарушения правил самой игры, кнопки, которые не работают или делают не то, ошибки текста и перевода, экономические дыры.

Как ты видишь игру. {tools}

Правила работы:
- Каждый найденный баг записывай через report_bug сразу, как увидел: отчёт привязывается к текущему моменту игры. Пиши, чего касается (object — как в игре), что ожидалось, что произошло и как повторить.
- Уверенность (confidence, 0..1) — честная вероятность того, что это настоящий баг игры, а не твоя ошибка или особенность игры.
- Не записывай один и тот же баг дважды. Особенности, о которых предупреждает описание, — не баги.
- Действий в игре — не больше {max_acts} (game_act); наблюдения не считаются. game_restart начинает игру заново с тем же стартом.
- Время в игре идёт только во время действий и ожиданий; ожидание {{"wait": секунд}} — до 600 секунд за раз.
- Когда действия кончатся или ты закончишь, верни краткий итог.

Описание игры от автора (README, начало):
---
{readme}
---"""
SCHEMA = {'type': 'object', 'required': ['summary'], 'properties': {'summary': {'type': 'string', 'description': 'краткий итог тестирования'}}}

def job(game, copy, arm, seed=1, sessions=SECRET / 'sessions'):
    title, clean, readme = GAMES[game]
    file = clean if copy == 'clean' else SECRET / 'mutants' / f'{game}_{copy}.html'
    text = readme.read_text(encoding='utf-8')[:README_MAX]
    prompt = PROMPT.format(title=title, tools=TOOLS[arm], max_acts=MAX_ACTS, readme=text)
    task = f'{game}_{copy}'
    mcp = {'mcpServers': {'game': {'command': 'node', 'args': [str(HERE / 'harness' / 'mcp_server.js')],
           'env': {'TESTER_ARM': arm, 'TESTER_GAME': str(file), 'TESTER_SEED': str(seed), 'TESTER_MAX_ACTS': str(MAX_ACTS),
                   'TESTER_OUT': str(Path(sessions) / task / arm),
                   # в чистом окружении драйвера этих переменных нет, а без них сервер не найдёт Playwright и Chromium (проверено 09.11)
                   'NODE_PATH': os.environ.get('NODE_PATH', ''), 'PLAYWRIGHT_BROWSERS_PATH': os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '')}}}}
    return {'id': f'{task}|{arm}|0', 'task': task, 'arm': arm, 'prompt': prompt, 'schema': SCHEMA, 'mcp': mcp, 'max_turns': 300}

if __name__ == '__main__':
    stage, out = sys.argv[1], Path(sys.argv[2])
    sessions = Path(sys.argv[sys.argv.index('--sessions') + 1]) if '--sessions' in sys.argv else SECRET / 'sessions'
    jobs = [job(g, c, a, sessions=sessions) for g, c in STAGES[stage] for a in ARMS]
    out.write_text(''.join(json.dumps(j, ensure_ascii=False) + '\n' for j in jobs), encoding='utf-8')
    print(f'{stage}: заданий {len(jobs)} → {out}')
