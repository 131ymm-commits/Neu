# Промпт агента-разметчика A (PARSE-02), дословно

Запущен 2026-10-07T08:07:25.417Z (повтор после сбоя первой попытки на лимите API, 429; первая попытка файла не записала).

```text
Ты помогаешь проекту «голосовой тренер Dota 2». Дословное сообщение автора проекта: «Привет. Делаем игру. Тренер доты. Голосовое управление 5 агентами с навыками известных игроков. Отцифровоть игроков в доту по по файлам или видео. В итоге это должна быть кастомка. В которой ты опосредовано, голосом управляет игроками. Но каждый агент свои Мусы делает сам я готов потратить на прожкт пару месяцев с норм подпиской. Не торопись сделай все с самого начала хорошо. ИИ в начале поиск в интернете. Помнивпо итогу Костромка на 2 игроков. Который каждый управляет своей командой звёзд. Или даже просто игроков в доту. Их тоже можно оцифровать любоготдаже на 2 ммр в репозиьарии создай отдельную папку». Последнее сообщение автора: «Продолжи».

Задача: составить НЕЗАВИСИМЫЙ проверочный набор фраз (второй, PARSE-02), которыми тренер голосом командует своими 5 ИИ-игроками в Dota 2, с ожидаемым смыслом. Нужен, чтобы честно измерить точность разборщика речи, который написал другой агент. ЗАПРЕЩЕНО открывать и читать что-либо в /home/user/Neu/games/Dota2_VoiceCoach/ (кроме записи своего выходного файла, путь ниже) — ни код, ни тесты, ни прошлый набор фраз, ни отчёты. Не подстраивайся под разборщик. Интернет не нужен. Работай экономно: сразу пиши файл одним проходом, затем проверь его коротким скриптом.

Контекст матча (одинаковый для всех фраз): команда тренера — Dire (Тьма). Для Dire лёгкая линия (сейф) — top, сложная (оффлейн) — bot. Свои агенты: позиция 1 — «Петя», герой Juggernaut (джагг); позиция 2 — «Серёга», Storm Spirit (шторм); позиция 3 — «Лёха», Axe (акс); позиция 4 — «Дима», Rubick (рубик); позиция 5 — «Вова», Witch Doctor (вд, доктор). Враги: Anti-Mage (ам, антимаг), Invoker (инвокер, инвок), Mars (марс), Earthshaker (шейкер), Crystal Maiden (цмка, кристалка).

Язык команд (протокол v1). Фраза превращается в список команд; команда = action + agents (список позиций 1..5, кому приказ; по возрастанию) + params. Действия и параметры:
- farm {area: lane|jungle_own|jungle_enemy|ancients|auto, lane?: top|mid|bot} (если место не названо — area auto)
- push {lane: top|mid|bot|auto, tier?: 1..4}
- defend {lane или place: base, tier?}
- gank {lane?, enemy?: npc_dota_hero_*, enemy_pos?: 1..5}
- group {place?|lane?} — собраться
- roshan {} ; tormentor {}
- smoke {then?: gank, lane?, enemy?}
- retreat {place?: base}
- focus {enemy: npc_dota_hero_* или enemy_pos: 1..5}
- engage {enemy?}
- hold {what?: действие, которое запрещено}
- split {lane}
- ward {place?: rune|roshan|jungle_own|jungle_enemy|..., lane?, kind?: sentry}
- stack {place?: ancients}
- buy {item: item_*} ; use_item {item: item_*}
- buyback {} ; use_ult {enemy?} ; save_ult {}
- save {ally: позиция} ; follow {ally: позиция}
- tp {place|lane} ; move {place|lane}
- free {} (играйте сами) ; cancel {} (отмена) ; report {} (доклад)
Если адресат не назван: командные действия (push, defend, group, roshan, tormentor, smoke, retreat, focus, engage, hold, free, cancel, report) идут всем [1,2,3,4,5]; если глагол во множественном числе («фармите») — всем; иначе адресат неясен — тогда "clarify": true и agents: []. «Остальные» — все, кого ещё не назвали в этой фразе. Внутренние имена героев: npc_dota_hero_juggernaut, npc_dota_hero_storm_spirit, npc_dota_hero_axe, npc_dota_hero_rubick, npc_dota_hero_witch_doctor, npc_dota_hero_antimage, npc_dota_hero_invoker, npc_dota_hero_mars, npc_dota_hero_earthshaker, npc_dota_hero_crystal_maiden. Предметы: item_black_king_bar, item_blink, item_gem, item_dust, item_smoke_of_deceit, item_ward_observer, item_ward_sentry, item_tpscroll, item_force_staff, item_glimmer_cape, item_sphere, item_ultimate_scepter, item_aghanims_shard, item_manta, item_butterfly, item_monkey_king_bar, item_cyclone, item_sheepstick, item_blade_mail, item_pipe и т.п.

Требования (80 фраз):
- живая русская речь игрока, как её выдаёт распознаватель речи: строчные буквы, без запятых, сленг, имена агентов в разных падежах («Пете», «с Серёгой», «Лёхе», «Диму»), герои сленгом;
- категории (поле "category"): "simple" — 20; "multi" (2–3 приказа в одной фразе) — 20; "modal" (отрицание, «потом», «срочно», исправление себя) — 15; "hard" (двусмысленные, сведения вместо приказа, необычные обороты) — 15; "asr" (ошибки распознавания речи: пропущенный или слитый предлог, опечатки в именах, «ё» как «е», лишние слова-паразиты) — 10;
- пиши разнообразно и по-своему, как говорил бы капитан команды или тренер; не повторяй шаблоны.

Формат: JSON Lines, по одной фразе на строку:
{"id": 1, "category": "simple", "text": "петя фарми лес", "expected": [{"action": "farm", "agents": [1], "params": {"area": "jungle_own"}}], "clarify": false, "note": ""}
Для фразы с переспросом — "clarify": true. В params указывай только то, что точно следует из фразы. Спорные толкования поясняй в note.

Запиши в /home/user/Neu/games/Dota2_VoiceCoach/coach/tests/heldout_phrases_02.jsonl (создай файл; больше ничего в репозитории не трогай). Проверь, что каждая строка — валидный JSON и действия/параметры из списка выше. Не делай git commit. Верни: сколько фраз по категориям, сколько с clarify, sha256 файла.
```
