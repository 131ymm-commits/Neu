# Factorio Magnetics — что дальше (передача следующей сессии, 01.10.2026)

Состояние: мод 1.0.0 готов и проверен на сервере (README, RESULTS.md, design/FINAL_SPEC.md §15). В репозитории всё нужное для продолжения: код, генератор чисел `tools/spec.py`, все тесты (`python3 tools/tests.py`, ~2,5 мин), сборка (`python3 tools/build.py`).

Окружение новой сессии: сеть должна пускать factorio.com, dl.factorio.com, lua-api.factorio.com (у автора это уже настроено). Сервер: `curl -L https://factorio.com/get-download/stable/headless/linux64 | tar -xJ -C /opt` → `/opt/factorio`; API: `https://lua-api.factorio.com/2.0.77/{prototype,runtime}-api.json` → `/opt/factorio-api/`; `pip install pillow numpy`.

Первый шаг (ждёт автора):
1. Автор ставит `magnetics_1.0.0.zip` и `magnetics-showroom_1.0.0.zip` (README, «Установка»), вводит `/magnetics-showroom`, присылает 2–3 скриншота и впечатление.
2. По скриншотам — правка оттенков в `tools/spec.py` (поле tint у построек), пересборка, тесты.

Дальше по плану аддонов (`proposals/2026-09-30_ADDONS_STEAM.md`):
- публикация на mods.factorio.com (нужен аккаунт автора; описание — info.json, миниатюра — magnetics/thumbnail.png, картинки — showcase.png);
- совет голов по результату (правило автора 28.09: результат оценивает совет) — по RESULTS.md и §15.4 (баланс болванок, волна);
- открытые вопросы баланса: турели мода против ванили той же ступени (RESULTS.md, волна) — оценка в настоящей игре.
